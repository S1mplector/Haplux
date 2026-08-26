"""Indexed FASTA and phased VCF context reconstruction.

This provider projects every supported local VCF record into each selected
haplotype. Coordinates from the source files are never reused after an indel:
the focal offset is measured again in the reconstructed haplotype sequence.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pysam

from haplux.analysis import ObservedAllele
from haplux.context import ContextSource
from haplux.domain import DNA_ALPHABET
from haplux.experiment import ExperimentContext
from haplux.providers import (
    ContextQuery,
    ProviderBatch,
    ProviderIssue,
    ProviderValidationError,
)


@dataclass(frozen=True)
class _LocalRecord:
    """The small subset of a VCF record needed after its file is closed."""

    record_id: str
    start: int
    stop: int
    reference: str
    alternate: Optional[str]
    supported: bool
    problem_code: str = ""
    problem_message: str = ""
    genotypes: Mapping[str, Tuple[Tuple[Optional[int], ...], bool]] = field(
        default_factory=dict
    )


def _record_label(record: Any) -> str:
    if record.id not in (None, "."):
        return str(record.id)
    alleles = ",".join(record.alts or ())
    return f"{record.contig}:{record.pos}:{record.ref}:{alleles}"


def _is_literal_dna(allele: str) -> bool:
    return bool(allele) and set(allele.upper()) <= DNA_ALPHABET


def _index_path(path: Path, suffixes: Sequence[str]) -> Optional[str]:
    for suffix in suffixes:
        candidate = Path(f"{path}{suffix}")
        if candidate.exists():
            return str(candidate.resolve())
    return None


def _file_identity(path: Path, *, index_suffixes: Sequence[str]) -> Dict[str, Any]:
    resolved = path.resolve()
    try:
        stat = resolved.stat()
    except OSError:
        return {"path": str(resolved), "exists": False, "index_path": None}
    return {
        "path": str(resolved),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
        "index_path": _index_path(resolved, index_suffixes),
    }


class FastaVcfProvider:
    """Reconstruct diploid haplotype windows from indexed FASTA and VCF files."""

    provider_id = "indexed-fasta-phased-vcf"
    version = "1"

    def __init__(
        self,
        *,
        fasta_path: str,
        vcf_path: str,
        assembly_name: str,
        samples: Optional[Sequence[str]] = None,
        require_pass: bool = True,
    ) -> None:
        assembly = assembly_name.strip()
        if not assembly:
            raise ProviderValidationError("assembly name must not be blank")
        selected = None if samples is None else tuple(sample.strip() for sample in samples)
        if selected is not None:
            if any(not sample for sample in selected):
                raise ProviderValidationError("sample names must not be blank")
            if len(set(selected)) != len(selected):
                raise ProviderValidationError("selected sample names must be unique")

        self.fasta_path = Path(fasta_path)
        self.vcf_path = Path(vcf_path)
        self.assembly_name = assembly
        self.samples = selected
        self.require_pass = bool(require_pass)

    def metadata(self) -> Dict[str, Any]:
        """Return reproducibility metadata without opening either input file."""

        return {
            "provider": self.provider_id,
            "version": self.version,
            "assembly": self.assembly_name,
            "pysam_version": pysam.__version__,
            "inputs": {
                "fasta": _file_identity(self.fasta_path, index_suffixes=(".fai",)),
                "vcf": _file_identity(self.vcf_path, index_suffixes=(".tbi", ".csi")),
            },
            "sample_selection": "all" if self.samples is None else list(self.samples),
            "policies": {
                "contig_aliases": "exact-only",
                "genotypes": "diploid; heterozygous calls must be phased",
                "variants": "biallelic literal ACGTN replacements",
                "normalization": "exact VCF representation; no automatic left alignment",
                "filtered_records": "exclude carrying sample" if self.require_pass else "include",
                "boundaries": "reject incomplete requested windows",
                "window_length": (
                    "reference-coordinate flanks; reconstructed length may vary after indels"
                ),
                "strand": "forward reference orientation",
                "overlaps": "exclude carrying sample",
                "ordering": "VCF header sample order, then haplotype 1 and 2",
            },
        }

    def load(self, query: ContextQuery) -> ProviderBatch:
        """Load and reconstruct haplotypes for one focal variant query."""

        if query.anchor.source_name != self.assembly_name:
            raise ProviderValidationError(
                f"query source {query.anchor.source_name!r} does not match provider "
                f"assembly {self.assembly_name!r}"
            )

        try:
            fasta = pysam.FastaFile(str(self.fasta_path))
        except (OSError, ValueError) as error:
            raise ProviderValidationError(f"could not open indexed FASTA: {error}") from error
        try:
            vcf = pysam.VariantFile(str(self.vcf_path))
        except (OSError, ValueError) as error:
            fasta.close()
            raise ProviderValidationError(f"could not open VCF: {error}") from error

        try:
            return self._load_open_files(query, fasta, vcf)
        finally:
            vcf.close()
            fasta.close()

    def _load_open_files(
        self,
        query: ContextQuery,
        fasta: Any,
        vcf: Any,
    ) -> ProviderBatch:
        contig = query.anchor.sequence_id
        if contig not in fasta.references:
            raise ProviderValidationError(f"FASTA has no exact contig {contig!r}")
        if contig not in vcf.header.contigs:
            raise ProviderValidationError(f"VCF has no exact contig {contig!r}")

        sample_names = self._selected_samples(tuple(vcf.header.samples))
        focal_start = query.anchor.position - 1
        start = focal_start - query.window.left_flank
        stop = focal_start + len(query.focal_variant.reference) + query.window.right_flank
        contig_length = fasta.get_reference_length(contig)
        if start < 0 or stop > contig_length:
            raise ProviderValidationError(
                f"requested reference interval [{start}, {stop}) exceeds {contig!r} "
                f"bounds [0, {contig_length})"
            )

        reference_window = fasta.fetch(contig, start, stop).upper()
        try:
            raw_records = list(vcf.fetch(contig, start, stop))
        except (OSError, ValueError) as error:
            raise ProviderValidationError(
                f"could not fetch indexed VCF interval {contig}:[{start}, {stop}): {error}"
            ) from error
        raw_records.sort(key=lambda record: (record.start, record.stop, _record_label(record)))

        focal_matches = [
            record
            for record in raw_records
            if record.start == focal_start
            and record.ref.upper() == query.focal_variant.reference
            and query.focal_variant.alternate in tuple(
                allele.upper() for allele in (record.alts or ())
            )
        ]
        if len(focal_matches) != 1:
            raise ProviderValidationError(
                "expected exactly one VCF record matching focal variant "
                f"{contig}:{query.anchor.position}:{query.focal_variant.reference}:"
                f"{query.focal_variant.alternate}; found {len(focal_matches)}"
            )
        focal_label = _record_label(focal_matches[0])

        records, global_issues = self._normalize_records(
            raw_records=raw_records,
            fasta=fasta,
            contig=contig,
            window_start=start,
            window_stop=stop,
            sample_names=sample_names,
            focal_label=focal_label,
        )
        focal_records = [record for record in records if record.record_id == focal_label]
        if len(focal_records) != 1 or not focal_records[0].supported:
            reason = focal_records[0].problem_message if focal_records else "record unavailable"
            raise ProviderValidationError(f"focal VCF record is unsupported: {reason}")

        contexts: List[ExperimentContext] = []
        issues = list(global_issues)
        supported = tuple(record for record in records if record.supported)
        for sample in sample_names:
            sample_issue = self._sample_exclusion(records, sample)
            if sample_issue is not None:
                issues.append(sample_issue)
                continue
            contexts.extend(
                self._project_sample(
                    sample=sample,
                    contig=contig,
                    reference_window=reference_window,
                    window_start=start,
                    records=supported,
                    focal_label=focal_label,
                )
            )

        return ProviderBatch(contexts=tuple(contexts), issues=tuple(issues))

    def _selected_samples(self, header_samples: Tuple[str, ...]) -> Tuple[str, ...]:
        if not header_samples:
            raise ProviderValidationError("VCF contains no samples")
        if self.samples is None:
            return header_samples
        missing = [sample for sample in self.samples if sample not in header_samples]
        if missing:
            raise ProviderValidationError(
                "selected sample(s) absent from VCF header: " + ", ".join(missing)
            )
        selected = set(self.samples)
        return tuple(sample for sample in header_samples if sample in selected)

    def _normalize_records(
        self,
        *,
        raw_records: Sequence[Any],
        fasta: Any,
        contig: str,
        window_start: int,
        window_stop: int,
        sample_names: Sequence[str],
        focal_label: str,
    ) -> Tuple[Tuple[_LocalRecord, ...], Tuple[ProviderIssue, ...]]:
        normalized: List[_LocalRecord] = []
        issues: List[ProviderIssue] = []
        previous_stop = window_start

        for raw in raw_records:
            label = _record_label(raw)
            reference = raw.ref.upper()
            alternates = tuple(allele.upper() for allele in (raw.alts or ()))
            alternate = alternates[0] if len(alternates) == 1 else None
            record_stop = raw.start + len(reference)
            problem_code = ""
            problem = ""

            if len(alternates) != 1:
                problem_code = "multiallelic_record"
                problem = "record must contain exactly one alternate allele"
            elif not _is_literal_dna(reference) or not _is_literal_dna(alternate or ""):
                problem_code = "nonliteral_allele"
                problem = "record contains a symbolic, breakend, or unsupported allele"
            elif raw.start < window_start or record_stop > window_stop:
                problem_code = "boundary_overlap"
                problem = "record is not fully contained in the requested reference window"
            elif self.require_pass and set(raw.filter.keys()) not in (set(), {"PASS"}):
                problem_code = "filtered_record"
                problem = "record does not have PASS filter status"
            elif fasta.fetch(contig, raw.start, record_stop).upper() != reference:
                problem_code = "reference_mismatch"
                problem = "VCF REF allele does not match FASTA"
            elif raw.start < previous_stop:
                problem_code = "overlapping_record"
                problem = "record overlaps a previously accepted local variant"

            supported = not problem_code
            if supported:
                previous_stop = record_stop
            genotypes = {
                sample: (tuple(raw.samples[sample].get("GT") or ()), raw.samples[sample].phased)
                for sample in sample_names
            }
            record = _LocalRecord(
                record_id=label,
                start=raw.start,
                stop=record_stop,
                reference=reference,
                alternate=alternate,
                supported=supported,
                problem_code=problem_code,
                problem_message=problem,
                genotypes=genotypes,
            )
            normalized.append(record)
            if not supported and label != focal_label:
                issues.append(ProviderIssue(problem_code, problem, label))

        return tuple(normalized), tuple(issues)

    def _sample_exclusion(
        self,
        records: Sequence[_LocalRecord],
        sample: str,
    ) -> Optional[ProviderIssue]:
        for record in records:
            genotype, phased = record.genotypes[sample]
            if len(genotype) != 2:
                return ProviderIssue(
                    "unsupported_ploidy",
                    f"sample {sample!r} does not have a diploid GT call",
                    record.record_id,
                )
            if any(allele is None for allele in genotype):
                return ProviderIssue(
                    "missing_genotype",
                    f"sample {sample!r} has a missing GT allele",
                    record.record_id,
                )
            allele_numbers = tuple(int(allele) for allele in genotype if allele is not None)
            if any(allele < 0 for allele in allele_numbers):
                return ProviderIssue(
                    "invalid_genotype",
                    f"sample {sample!r} has an invalid GT allele index",
                    record.record_id,
                )
            if len(set(allele_numbers)) > 1 and not phased:
                return ProviderIssue(
                    "unphased_heterozygote",
                    f"sample {sample!r} has an unphased heterozygous GT call",
                    record.record_id,
                )
            if not record.supported and any(allele != 0 for allele in allele_numbers):
                return ProviderIssue(
                    "sample_carries_unsupported_record",
                    f"sample {sample!r} carries {record.problem_code}",
                    record.record_id,
                )
            if record.supported and any(allele not in (0, 1) for allele in allele_numbers):
                return ProviderIssue(
                    "invalid_genotype",
                    f"sample {sample!r} GT allele is outside biallelic range 0/1",
                    record.record_id,
                )
        return None

    def _project_sample(
        self,
        *,
        sample: str,
        contig: str,
        reference_window: str,
        window_start: int,
        records: Sequence[_LocalRecord],
        focal_label: str,
    ) -> List[ExperimentContext]:
        contexts = []
        for haplotype_index in (0, 1):
            chunks: List[str] = []
            cursor = window_start
            focal_offset: Optional[int] = None
            focal_observed: Optional[ObservedAllele] = None

            for record in records:
                local_cursor = cursor - window_start
                local_start = record.start - window_start
                chunks.append(reference_window[local_cursor:local_start])
                genotype, _ = record.genotypes[sample]
                allele_number = genotype[haplotype_index]
                if allele_number is None:
                    raise AssertionError("missing alleles must be excluded before projection")
                allele = record.reference if allele_number == 0 else record.alternate
                if allele is None:
                    raise AssertionError("supported record must have one alternate allele")
                if record.record_id == focal_label:
                    focal_offset = sum(len(chunk) for chunk in chunks)
                    focal_observed = (
                        ObservedAllele.REFERENCE
                        if allele_number == 0
                        else ObservedAllele.ALTERNATE
                    )
                chunks.append(allele)
                cursor = record.stop

            chunks.append(reference_window[cursor - window_start :])
            if focal_offset is None or focal_observed is None:
                raise AssertionError("validated focal record must be projected")
            haplotype_number = haplotype_index + 1
            contexts.append(
                ExperimentContext(
                    context_id=f"{sample}:h{haplotype_number}",
                    source_type=ContextSource.PHASED_VCF_HAPLOTYPE,
                    source_name=self.assembly_name,
                    sequence_id=f"{contig}|{sample}|h{haplotype_number}",
                    window_start=0,
                    sequence="".join(chunks),
                    vcf_position=focal_offset + 1,
                    observed_allele=focal_observed,
                    sample_id=sample,
                    haplotype_id=str(haplotype_number),
                )
            )
        return contexts
