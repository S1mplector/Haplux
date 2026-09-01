import unittest

from haplux.models import (
    FixedLengthCenteredPolicy,
    FullSequencePolicy,
    GCContentModel,
    ModelValidationError,
    MotifCountModel,
    create_builtin_model,
    create_input_policy,
)


class DeterministicModelTests(unittest.TestCase):
    def test_full_sequence_policy_preserves_the_constructed_input(self) -> None:
        projection = FullSequencePolicy().prepare("aacCGG", focal_offset=2)

        self.assertEqual(projection.sequence, "AACCGG")
        self.assertEqual(projection.anchor_index, 2)
        self.assertEqual(projection.as_dict()["policy"], "full_sequence")

    def test_fixed_length_policy_centers_trims_and_pads(self) -> None:
        policy = FixedLengthCenteredPolicy(target_length=5, anchor_index=2)

        centered = policy.prepare("AACCGG", focal_offset=2)
        self.assertEqual(centered.sequence, "AACCG")
        self.assertEqual(centered.source_start, 0)
        self.assertEqual(centered.source_end, 5)
        self.assertEqual(centered.left_padding, 0)
        self.assertEqual(centered.right_padding, 0)

        left_edge = policy.prepare("AACCGG", focal_offset=0)
        self.assertEqual(left_edge.sequence, "NNAAC")
        self.assertEqual(left_edge.left_padding, 2)
        self.assertEqual(left_edge.source_start, 0)

        right_edge = policy.prepare("AACCGG", focal_offset=5)
        self.assertEqual(right_edge.sequence, "CGGNN")
        self.assertEqual(right_edge.right_padding, 2)
        self.assertEqual(right_edge.source_end, 6)

    def test_input_policy_factory_validates_serialized_specs(self) -> None:
        self.assertIsInstance(create_input_policy("full_sequence", {}), FullSequencePolicy)
        self.assertIsInstance(
            create_input_policy(
                "fixed_length_centered",
                {"target_length": 5, "anchor_index": 2},
            ),
            FixedLengthCenteredPolicy,
        )

        invalid_specs = (
            ("unknown", {}, "unknown"),
            ("full_sequence", {"target_length": 5}, "does not accept"),
            ("fixed_length_centered", {}, "requires"),
            ("fixed_length_centered", {"target_length": 0}, "positive"),
            ("fixed_length_centered", {"target_length": 5, "anchor_index": 8}, "inside"),
            ("fixed_length_centered", {"target_length": 5, "pad_symbol": "X"}, "invalid"),
            ("fixed_length_centered", {"target_length": 5, "extra": 1}, "unexpected"),
        )
        for kind, parameters, message in invalid_specs:
            with self.subTest(kind=kind, parameters=parameters):
                with self.assertRaisesRegex(ModelValidationError, message):
                    create_input_policy(kind, parameters)

    def test_gc_content_scores_validated_sequence(self) -> None:
        model = GCContentModel()

        self.assertEqual(model.predict("AAGCNN"), 2 / 6)
        self.assertEqual(model.metadata()["scientific_use"], "development-only")
        self.assertEqual(model.metadata()["input_policy"]["policy"], "full_sequence")

    def test_motif_count_includes_overlapping_occurrences(self) -> None:
        model = MotifCountModel(motif="aa")

        self.assertEqual(model.motif, "AA")
        self.assertEqual(model.predict("AAAA"), 3.0)
        self.assertEqual(model.predict("A"), 0.0)

    def test_builtin_factory_validates_adapter_parameters(self) -> None:
        self.assertIsInstance(create_builtin_model("gc_content", {}), GCContentModel)
        self.assertIsInstance(
            create_builtin_model("motif_count", {"motif": "CG"}),
            MotifCountModel,
        )

        invalid_specs = (
            ("unknown", {}, "unknown"),
            ("gc_content", {"motif": "A"}, "does not accept"),
            ("motif_count", {}, "requires"),
            ("motif_count", {"motif": "A", "extra": 1}, "unexpected"),
        )
        for adapter, parameters, message in invalid_specs:
            with self.subTest(adapter=adapter, parameters=parameters):
                with self.assertRaisesRegex(ModelValidationError, message):
                    create_builtin_model(adapter, parameters)


if __name__ == "__main__":
    unittest.main()
