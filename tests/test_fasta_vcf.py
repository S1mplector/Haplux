import tempfile
import unittest
from pathlib import Path

import pysam

from haplux.analysis import ObservedAllele
from haplux.experiment import FocalVariant
from haplux.fasta_vcf import FastaVcfProvider
from haplux.models import GCContentModel
from haplux.providers import (
    AnchorLocus,
    ContextQuery,
    ProviderValidationError,
    WindowSpecification,
)
from haplux.real_data import run_provider_experiment


FIXTURES = Path(__file__).parent / "fixtures"
FASTA = FIXTURES / "mini.fa"


class FastaVcfProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.indexed_vcfs = {}
        destination_root = Path(cls.temporary_directory.name)
        for name in ("cohort", "reference_mismatch", "multiallelic"):
            source = FIXTURES / f"{name}.vcf"
            destination = destination_root / f"{name}.vcf.gz"
            pysam.tabix_compress(str(source), str(destination), force=True)
            pysam.tabix_index(str(destination), preset="vcf", force=True)
            cls.indexed_vcfs[name] = destination

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def query(
        self,
        *,
        position: int = 21,
        reference: str = "C",
        alternate: str = "T",
        left_flank: int = 10,
        right_flank: int = 10,
    ) -> ContextQuery:
        return ContextQuery(
            focal_variant=FocalVariant(
                identifier=f"chr1:{position}:{reference}:{alternate}",
                reference=reference,
                alternate=alternate,
            ),
            anchor=AnchorLocus("mini-v1", "chr1", position),
            window=WindowSpecification(left_flank, right_flank),
        )

    def provider(
        self,
        *,
        vcf: str = "cohort",
        samples=None,
    ) -> FastaVcfProvider:
        return FastaVcfProvider(
            fasta_path=str(FASTA),
            vcf_path=str(self.indexed_vcfs[vcf]),
            assembly_name="mini-v1",
            samples=samples,
        )

    def test_reconstructs_local_phased_haplotypes_and_indel_shifted_offsets(self) -> None:
        batch = self.provider(
            samples=("HG_HOMALT", "HG_REF", "HG_MIX")
        ).load(self.query())

        self.assertEqual(len(batch.contexts), 6)
        self.assertEqual(batch.issues, ())
        self.assertEqual(
            [context.context_id for context in batch.contexts],
            [
                "HG_REF:h1",
                "HG_REF:h2",
                "HG_MIX:h1",
                "HG_MIX:h2",
                "HG_HOMALT:h1",
                "HG_HOMALT:h2",
            ],
        )

        contexts = {context.context_id: context for context in batch.contexts}
        mixed_h1 = contexts["HG_MIX:h1"]
        mixed_h2 = contexts["HG_MIX:h2"]
        self.assertEqual(mixed_h1.observed_allele, ObservedAllele.REFERENCE)
        self.assertEqual(mixed_h1.vcf_position, 13)
        self.assertEqual(mixed_h1.sequence[mixed_h1.vcf_position - 1], "C")
        self.assertEqual(mixed_h2.observed_allele, ObservedAllele.ALTERNATE)
        self.assertEqual(mixed_h2.vcf_position, 11)
        self.assertEqual(mixed_h2.sequence[mixed_h2.vcf_position - 1], "T")

    def test_excludes_unphased_and_missing_samples_with_structured_issues(self) -> None:
        batch = self.provider().load(self.query())

        self.assertEqual(len(batch.contexts), 6)
        self.assertEqual(
            [issue.code for issue in batch.issues],
            ["unphased_heterozygote", "missing_genotype"],
        )
        self.assertTrue(all(issue.record_id == "focal-snv" for issue in batch.issues))

    def test_supports_insertion_and_deletion_as_the_focal_variant(self) -> None:
        provider = self.provider(samples=("HG_MIX",))
        insertion = provider.load(
            self.query(
                position=13,
                reference="T",
                alternate="TAG",
                left_flank=5,
                right_flank=5,
            )
        )
        deletion = provider.load(
            self.query(
                position=25,
                reference="GGG",
                alternate="G",
                left_flank=5,
                right_flank=5,
            )
        )

        self.assertEqual(
            [context.observed_allele for context in insertion.contexts],
            [ObservedAllele.ALTERNATE, ObservedAllele.REFERENCE],
        )
        self.assertEqual(
            [context.observed_allele for context in deletion.contexts],
            [ObservedAllele.ALTERNATE, ObservedAllele.REFERENCE],
        )

    def test_rejects_boundaries_aliases_reference_mismatch_and_multiallelic_focal(self) -> None:
        with self.assertRaisesRegex(ProviderValidationError, "bounds"):
            self.provider(samples=("HG_REF",)).load(
                self.query(left_flank=30, right_flank=10)
            )
        bad_contig = ContextQuery(
            focal_variant=FocalVariant("bad", "C", "T"),
            anchor=AnchorLocus("mini-v1", "1", 21),
            window=WindowSpecification(5, 5),
        )
        with self.assertRaisesRegex(ProviderValidationError, "exact contig"):
            self.provider(samples=("HG_REF",)).load(bad_contig)
        with self.assertRaisesRegex(ProviderValidationError, "does not match FASTA"):
            self.provider(vcf="reference_mismatch").load(
                self.query(reference="G", alternate="T")
            )
        with self.assertRaisesRegex(ProviderValidationError, "exactly one alternate"):
            self.provider(vcf="multiallelic").load(self.query())

    def test_requires_an_indexed_vcf_and_records_input_metadata(self) -> None:
        unindexed = FastaVcfProvider(
            fasta_path=str(FASTA),
            vcf_path=str(FIXTURES / "cohort.vcf"),
            assembly_name="mini-v1",
            samples=("HG_REF",),
        )
        with self.assertRaisesRegex(ProviderValidationError, "indexed VCF"):
            unindexed.load(self.query())

        metadata = self.provider(samples=("HG_REF",)).metadata()
        self.assertEqual(metadata["provider"], "indexed-fasta-phased-vcf")
        self.assertEqual(metadata["sample_selection"], ["HG_REF"])
        self.assertTrue(metadata["inputs"]["fasta"]["index_path"].endswith(".fai"))
        self.assertTrue(metadata["inputs"]["vcf"]["index_path"].endswith(".tbi"))

    def test_runs_the_shared_experiment_engine_with_provider_diagnostics(self) -> None:
        result = run_provider_experiment(
            experiment_id="real-fixture",
            provider=self.provider(samples=("HG_REF", "HG_MIX", "HG_HOMALT")),
            query=self.query(),
            model=GCContentModel(),
        )
        report = result.as_dict()

        self.assertEqual(result.status, "completed")
        self.assertEqual(report["schema_version"], "haplux.real-data-experiment.v1")
        self.assertEqual(report["provider"]["counts"]["contexts"], 6)
        self.assertEqual(report["experiment"]["counts"]["analyzed"], 6)


if __name__ == "__main__":
    unittest.main()
