import copy
import json
import unittest
from pathlib import Path

from pancontext.experiment import ExperimentValidationError, run_experiment
from pancontext.experiment_io import (
    EXPERIMENT_REQUEST_SCHEMA_VERSION,
    parse_experiment_document,
)


FIXTURE = Path(__file__).parent / "fixtures" / "experiment_request.json"


def fixture_document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class ExperimentInputTests(unittest.TestCase):
    def test_parses_and_executes_versioned_fixture(self) -> None:
        parsed = parse_experiment_document(fixture_document())
        result = run_experiment(parsed.request, parsed.model)

        self.assertEqual(parsed.request.experiment_id, "two-haplotype-demo")
        self.assertEqual(len(parsed.request.contexts), 2)
        self.assertEqual(result.status, "completed")

    def test_rejects_unknown_schema_and_fields(self) -> None:
        wrong_schema = fixture_document()
        wrong_schema["schema_version"] = "future.v99"
        with self.assertRaisesRegex(ExperimentValidationError, "unsupported"):
            parse_experiment_document(wrong_schema)

        unknown_field = fixture_document()
        unknown_field["experiment"]["contxts"] = []
        with self.assertRaisesRegex(ExperimentValidationError, "unknown field"):
            parse_experiment_document(unknown_field)

    def test_rejects_missing_or_mistyped_required_values_with_paths(self) -> None:
        missing = fixture_document()
        del missing["experiment"]["contexts"][0]["sequence"]
        with self.assertRaisesRegex(
            ExperimentValidationError,
            r"contexts\[0\]\.sequence is required",
        ):
            parse_experiment_document(missing)

        mistyped = fixture_document()
        mistyped["experiment"]["contexts"][0]["window_start"] = "100"
        with self.assertRaisesRegex(ExperimentValidationError, "window_start must be an integer"):
            parse_experiment_document(mistyped)

    def test_input_document_is_not_mutated(self) -> None:
        document = fixture_document()
        original = copy.deepcopy(document)

        parse_experiment_document(document)

        self.assertEqual(document, original)
        self.assertEqual(document["schema_version"], EXPERIMENT_REQUEST_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
