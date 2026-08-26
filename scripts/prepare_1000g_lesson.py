"""Prepare a compact, public GRCh38/1000 Genomes lesson dataset.

The script downloads one GRCh38 chromosome FASTA and extracts only a two-kilobase
slice of an indexed, phased 1000 Genomes VCF for three teaching samples.
"""

import argparse
import gzip
import json
from pathlib import Path
import shutil
from typing import Dict
from urllib.request import urlopen

import pysam


REFERENCE_URL = (
    "https://ftp.ensembl.org/pub/release-115/fasta/homo_sapiens/dna/"
    "Homo_sapiens.GRCh38.dna.chromosome.22.fa.gz"
)
VCF_URL = (
    "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/"
    "1000_genomes_project/release/20190312_biallelic_SNV_and_INDEL/"
    "ALL.chr22.shapeit2_integrated_snvindels_v2a_27022019.GRCh38.phased.vcf.gz"
)
SAMPLES = ("HG00096", "HG00149", "HG01770")
CONTIG = "22"
REGION_START = 10_526_000
REGION_STOP = 10_528_000
FOCAL_POSITION = 10_527_034
FOCAL_REFERENCE = "G"
FOCAL_ALTERNATE = "T"


def _download(url: str, destination: Path) -> None:
    if destination.exists():
        return
    partial = destination.with_name(f"{destination.name}.part")
    with urlopen(url) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    partial.replace(destination)


def _prepare_reference(destination: Path) -> Path:
    compressed = destination / "GRCh38.chr22.fa.gz"
    fasta = destination / "GRCh38.chr22.fa"
    _download(REFERENCE_URL, compressed)
    if not fasta.exists():
        partial = fasta.with_name(f"{fasta.name}.part")
        with gzip.open(compressed, "rb") as source, partial.open("wb") as output:
            shutil.copyfileobj(source, output)
        partial.replace(fasta)
    if not Path(f"{fasta}.fai").exists():
        pysam.faidx(str(fasta))
    with pysam.FastaFile(str(fasta)) as reference:
        if CONTIG not in reference.references:
            raise RuntimeError(f"downloaded FASTA has no contig {CONTIG!r}")
    return fasta


def _prepare_vcf(destination: Path) -> Path:
    source_index = destination / "1000-genomes-chr22.source.vcf.gz.tbi"
    output_vcf = destination / "1000g.lesson.vcf.gz"
    _download(f"{VCF_URL}.tbi", source_index)
    if output_vcf.exists() and Path(f"{output_vcf}.tbi").exists():
        return output_vcf

    with pysam.VariantFile(VCF_URL, index_filename=str(source_index)) as source:
        source.subset_samples(SAMPLES)
        with pysam.VariantFile(str(output_vcf), "wz", header=source.header) as output:
            for record in source.fetch(CONTIG, REGION_START, REGION_STOP):
                output.write(record)
    pysam.tabix_index(str(output_vcf), preset="vcf", force=True)
    return output_vcf


def _validate_lesson(fasta: Path, vcf: Path) -> Dict[str, object]:
    with pysam.FastaFile(str(fasta)) as reference:
        observed = reference.fetch(
            CONTIG,
            FOCAL_POSITION - 1,
            FOCAL_POSITION,
        ).upper()
    if observed != FOCAL_REFERENCE:
        raise RuntimeError(
            f"lesson REF mismatch: expected {FOCAL_REFERENCE!r}, observed {observed!r}"
        )

    focal = None
    with pysam.VariantFile(str(vcf)) as variants:
        for record in variants.fetch(CONTIG, FOCAL_POSITION - 1, FOCAL_POSITION):
            if record.pos == FOCAL_POSITION:
                focal = record
                break
        if focal is None:
            raise RuntimeError("lesson VCF does not contain the focal record")
        genotypes = {
            sample: {
                "GT": "|".join(str(allele) for allele in focal.samples[sample]["GT"]),
                "phased": focal.samples[sample].phased,
            }
            for sample in SAMPLES
        }
    return {
        "focal_variant": {
            "contig": CONTIG,
            "position": FOCAL_POSITION,
            "reference": FOCAL_REFERENCE,
            "alternate": FOCAL_ALTERNATE,
        },
        "genotypes": genotypes,
    }


def prepare(destination: Path) -> Dict[str, object]:
    destination.mkdir(parents=True, exist_ok=True)
    fasta = _prepare_reference(destination)
    vcf = _prepare_vcf(destination)
    validation = _validate_lesson(fasta, vcf)
    manifest = {
        "dataset": "Haplux public lesson 01",
        "assembly": "GRCh38",
        "sources": {
            "reference": REFERENCE_URL,
            "variants": VCF_URL,
        },
        "local_files": {
            "fasta": str(fasta.resolve()),
            "vcf": str(vcf.resolve()),
        },
        "samples": list(SAMPLES),
        "extracted_interval": {
            "contig": CONTIG,
            "start": REGION_START,
            "stop": REGION_STOP,
            "coordinate_system": "0-based-half-open",
        },
        **validation,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".haplux-data/1000g-lesson"),
    )
    arguments = parser.parse_args()
    manifest = prepare(arguments.output)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
