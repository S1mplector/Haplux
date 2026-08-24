import json
import unittest

from pancontext.analysis import ObservedAllele
from pancontext.context import ContextSource
from pancontext.experiment import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentContext,
    ExperimentRequest,
    ExperimentValidationError,
    FocalVariant,
    StabilitySummary,
    run_experiment,
)
from pancontext.models import GCContentModel


class NonFiniteModel:
    model_id = "non_finite"
    version = "1"
    output_name = "invalid"

    def predict(self, sequence: str) -> float:
        return float("nan")

    def metadata(self) -> dict:
        return {"adapter": self.model_id, "version": self.version}


def context(
    context_id: str,
    *,
    sequence: str = "AACCGG",
    position: int = 103,
    observed_allele: ObservedAllele = ObservedAllele.REFERENCE,
) -> ExperimentContext:
    return ExperimentContext(
        context_id=context_id,
        source_type=ContextSource.PANGENOME_PATH,
        source_name="test-graph",
        sequence_id=f"path-{context_id}",
        window_start=100,
        sequence=sequence,
        vcf_position=position,
        observed_allele=observed_allele,
        sample_id=context_id.split("-")[0],
        haplotype_id=context_id.split("-")[-1],
    )


def experiment_request(*contexts: ExperimentContext) -> ExperimentRequest:
    return ExperimentRequest(
        experiment_id="experiment-001",
        focal_variant=FocalVariant(
            identifier="example:C:T",
            reference="C",
            alternate="T",
        ),
        contexts=tuple(contexts),
    )


class ExperimentEngineTests(unittest.TestCase):
    def test_runs_matched_effects_across_reference_and_alternate_observations(self) -> None:
        request = experiment_request(
            context("HG001-1"),
            context(
                "HG002-2",
                sequence="GGAATCGG",
                position=105,
                observed_allele=ObservedAllele.ALTERNATE,
            ),
        )

        result = run_experiment(request, GCContentModel())

        self.assertEqual(result.status, "completed")
        self.assertEqual(len(result.effects), 2)
        self.assertAlmostEqual(result.effects[0].effect, -1 / 6)
        self.assertAlmostEqual(result.effects[1].effect, -1 / 8)
        self.assertEqual(result.effects[1].baseline_sequence, "GGAACCGG")
        self.assertEqual(result.effects[1].alternate_sequence, "GGAATCGG")
        self.assertEqual(result.effects[1].alternate_construction, "observed-context")
        self.assertAlmostEqual(result.stability.mean_effect, (-1 / 6 - 1 / 8) / 2)
        self.assertAlmostEqual(result.stability.effect_range, 1 / 24)
        self.assertTrue(result.stability.sign_consistent)

    def test_skips_incompatible_context_and_preserves_reason(self) -> None:
        request = experiment_request(
            context("valid"),
            context("mismatch", sequence="AAGCGG"),
        )

        result = run_experiment(request, GCContentModel())

        self.assertEqual(result.status, "partial")
        self.assertEqual(len(result.effects), 1)
        self.assertEqual(len(result.skipped_contexts), 1)
        self.assertEqual(result.skipped_contexts[0].context_id, "mismatch")
        self.assertEqual(result.skipped_contexts[0].stage, "context-construction")
        self.assertIn("reference mismatch", result.skipped_contexts[0].reason)

    def test_reports_failure_when_no_context_is_compatible(self) -> None:
        result = run_experiment(
            experiment_request(context("mismatch", sequence="AAGCGG")),
            GCContentModel(),
        )

        self.assertEqual(result.status, "failed")
        self.assertIsNone(result.stability)
        self.assertEqual(len(result.skipped_contexts), 1)

    def test_rejects_non_finite_model_predictions_per_context(self) -> None:
        result = run_experiment(
            experiment_request(context("valid")),
            NonFiniteModel(),
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.skipped_contexts[0].stage, "model-inference")
        self.assertIn("finite", result.skipped_contexts[0].reason)

    def test_serializes_versioned_experiment_report(self) -> None:
        result = run_experiment(experiment_request(context("HG001-1")), GCContentModel())
        report = result.as_dict()

        self.assertEqual(report["schema_version"], EXPERIMENT_SCHEMA_VERSION)
        self.assertEqual(report["counts"], {"requested": 1, "analyzed": 1, "skipped": 0})
        self.assertEqual(report["model"]["adapter"], "gc_content")
        self.assertAlmostEqual(report["contexts"][0]["effect"], -1 / 6)
        self.assertEqual(report["stability"]["sign"]["agreement"], 1.0)
        json.dumps(report)

    def test_stability_summary_reports_sign_disagreement_without_classifying_it(self) -> None:
        summary = StabilitySummary.from_effects(
            (-1.0, 2.0, 0.001),
            zero_tolerance=0.01,
        )

        self.assertEqual(summary.positive_count, 1)
        self.assertEqual(summary.negative_count, 1)
        self.assertEqual(summary.zero_count, 1)
        self.assertEqual(summary.sign_agreement, 1 / 3)
        self.assertFalse(summary.sign_consistent)

    def test_rejects_structurally_invalid_experiment(self) -> None:
        duplicate = context("duplicate")
        with self.assertRaisesRegex(ExperimentValidationError, "unique"):
            experiment_request(duplicate, duplicate)

        with self.assertRaisesRegex(ExperimentValidationError, "at least one"):
            experiment_request()

        with self.assertRaisesRegex(ExperimentValidationError, "non-negative"):
            ExperimentRequest(
                experiment_id="experiment",
                focal_variant=FocalVariant("variant", "C", "T"),
                contexts=(context("valid"),),
                zero_tolerance=-0.1,
            )


if __name__ == "__main__":
    unittest.main()
