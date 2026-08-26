import unittest

from haplux.analysis import ObservedAllele
from haplux.context import ContextSource
from haplux.experiment import ExperimentContext, ExperimentValidationError, FocalVariant
from haplux.providers import (
    AnchorLocus,
    ContextProvider,
    ContextQuery,
    ProviderBatch,
    ProviderIssue,
    WindowSpecification,
)


class InMemoryProvider:
    provider_id = "in-memory"
    version = "1"

    def __init__(self, batch: ProviderBatch) -> None:
        self.batch = batch

    def load(self, query: ContextQuery) -> ProviderBatch:
        return self.batch

    def metadata(self) -> dict:
        return {"provider": self.provider_id, "version": self.version}


def example_context(context_id: str = "context-1") -> ExperimentContext:
    return ExperimentContext(
        context_id=context_id,
        source_type=ContextSource.LINEAR_REFERENCE,
        source_name="GRCh38",
        sequence_id="chr1",
        window_start=100,
        sequence="AACCGG",
        vcf_position=103,
        observed_allele=ObservedAllele.REFERENCE,
    )


class ProviderContractTests(unittest.TestCase):
    def test_runtime_provider_contract_and_batch(self) -> None:
        batch = ProviderBatch(
            contexts=(example_context(),),
            issues=(ProviderIssue("unphased", "sample has no phase", "sample-2"),),
        )
        provider = InMemoryProvider(batch)
        query = ContextQuery(
            focal_variant=FocalVariant("variant", "C", "T"),
            anchor=AnchorLocus("GRCh38", "chr1", 103),
            window=WindowSpecification(left_flank=2, right_flank=3),
        )

        self.assertIsInstance(provider, ContextProvider)
        self.assertEqual(provider.load(query), batch)
        self.assertEqual(batch.issues[0].as_dict()["code"], "unphased")

    def test_rejects_invalid_query_boundaries(self) -> None:
        with self.assertRaisesRegex(ExperimentValidationError, "at least 1"):
            AnchorLocus("GRCh38", "chr1", 0)
        with self.assertRaisesRegex(ExperimentValidationError, "non-negative"):
            WindowSpecification(left_flank=-1, right_flank=10)

    def test_rejects_duplicate_provider_context_ids(self) -> None:
        duplicate = example_context()
        with self.assertRaisesRegex(ExperimentValidationError, "unique"):
            ProviderBatch(contexts=(duplicate, duplicate))


if __name__ == "__main__":
    unittest.main()
