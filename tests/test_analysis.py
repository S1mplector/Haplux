import json
import unittest

from haplux.analysis import (
    AnalysisRequest,
    ObservedAllele,
    SCHEMA_VERSION,
    analyze_variant,
)
from haplux.context import ContextSource
from haplux.domain import ReferenceMismatchError, SequenceValidationError


def example_request(**overrides: object) -> AnalysisRequest:
    values = {
        "source_type": ContextSource.LINEAR_REFERENCE,
        "source_name": "GRCh38",
        "sequence_id": "chr1",
        "window_start": 100,
        "sequence": "AACCGG",
        "vcf_position": 103,
        "reference": "C",
        "alternate": "T",
    }
    values.update(overrides)
    return AnalysisRequest(**values)  # type: ignore[arg-type]


class AnalysisServiceTests(unittest.TestCase):
    def test_analyzes_example_without_a_user_interface(self) -> None:
        result = analyze_variant(example_request())

        self.assertEqual(result.variant_kind, "single-nucleotide variant")
        self.assertEqual(result.variant.start, 102)
        self.assertEqual(result.variant.end, 103)
        self.assertEqual(result.context.window.sequence, "AACCGG")
        self.assertEqual(result.alternate_sequence, "AATCGG")
        self.assertNotEqual(result.baseline_content_id, result.alternate_content_id)
        self.assertEqual(len(result.coordinate_rows), 8)

    def test_all_context_sources_share_the_same_analysis_contract(self) -> None:
        baseline = analyze_variant(example_request())

        for source in ContextSource:
            with self.subTest(source=source.value):
                result = analyze_variant(
                    example_request(source_type=source, source_name=f"test-{source.value}")
                )
                self.assertEqual(result.alternate_sequence, "AATCGG")
                self.assertEqual(result.baseline_content_id, baseline.baseline_content_id)
                self.assertEqual(result.context.provenance.source_type, source)

    def test_constructs_a_matched_pair_when_alternate_was_observed(self) -> None:
        result = analyze_variant(
            example_request(
                sequence="AATCGG",
                observed_allele=ObservedAllele.ALTERNATE,
            )
        )

        self.assertEqual(result.context.window.sequence, "AATCGG")
        self.assertEqual(result.baseline_sequence, "AACCGG")
        self.assertEqual(result.alternate_sequence, "AATCGG")
        self.assertEqual(result.baseline_construction, "focal-reference-constructed")
        self.assertEqual(result.alternate_construction, "observed-context")

    def test_classifies_supported_small_variant_shapes(self) -> None:
        cases = (
            ({}, "single-nucleotide variant", "AATCGG"),
            (
                {"vcf_position": 102, "reference": "A", "alternate": "AT"},
                "insertion",
                "AATCCGG",
            ),
            (
                {"vcf_position": 102, "reference": "ACC", "alternate": "A"},
                "deletion",
                "AAGG",
            ),
            (
                {"vcf_position": 103, "reference": "CC", "alternate": "TT"},
                "multi-nucleotide substitution",
                "AATTGG",
            ),
        )

        for overrides, expected_kind, expected_sequence in cases:
            with self.subTest(expected_kind=expected_kind):
                result = analyze_variant(example_request(**overrides))
                self.assertEqual(result.variant_kind, expected_kind)
                self.assertEqual(result.alternate_sequence, expected_sequence)

    def test_serializes_a_stable_machine_readable_report(self) -> None:
        result = analyze_variant(
            example_request(
                source_type=ContextSource.PANGENOME_PATH,
                source_name="HPRC-v2",
                sample_id="HG002",
                haplotype_id="1",
            )
        )
        report = result.as_dict()

        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["status"], "validated")
        self.assertEqual(report["context"]["source"]["type"], "pangenome_path")
        self.assertEqual(report["context"]["source"]["sample_id"], "HG002")
        self.assertEqual(report["variant"]["internal_interval"], {"start": 102, "end": 103})
        self.assertEqual(report["model_inputs"]["baseline"]["sequence"], "AACCGG")
        self.assertEqual(report["model_inputs"]["alternate"]["sequence"], "AATCGG")
        self.assertEqual(
            report["model_inputs"]["alternate"]["construction"],
            "focal-variant-applied",
        )
        json.dumps(report)

    def test_rejects_reference_mismatch_headlessly(self) -> None:
        with self.assertRaisesRegex(ReferenceMismatchError, "observed 'C'"):
            analyze_variant(example_request(reference="G"))

    def test_rejects_out_of_bounds_variant_headlessly(self) -> None:
        with self.assertRaisesRegex(ReferenceMismatchError, "outside window"):
            analyze_variant(example_request(vcf_position=200))

    def test_rejects_invalid_coordinates_and_sequence_headlessly(self) -> None:
        invalid_requests = (
            (example_request(window_start=-1), "window start"),
            (example_request(vcf_position=0), "VCF position"),
            (example_request(sequence="AACXGG"), "unsupported DNA symbol"),
            (example_request(reference="C", alternate="C"), "must differ"),
        )

        for request, message in invalid_requests:
            with self.subTest(message=message):
                with self.assertRaisesRegex(SequenceValidationError, message):
                    analyze_variant(request)


if __name__ == "__main__":
    unittest.main()
