import unittest

from pancontext.models import (
    GCContentModel,
    ModelValidationError,
    MotifCountModel,
    create_builtin_model,
)


class DeterministicModelTests(unittest.TestCase):
    def test_gc_content_scores_validated_sequence(self) -> None:
        model = GCContentModel()

        self.assertEqual(model.predict("AAGCNN"), 2 / 6)
        self.assertEqual(model.metadata()["scientific_use"], "development-only")

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
