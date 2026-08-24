import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from pancontext.cli import main


EXPERIMENT_FIXTURE = Path(__file__).parent / "fixtures" / "experiment_request.json"


def example_arguments() -> list:
    return [
        "analyze",
        "--source-type",
        "linear_reference",
        "--source-name",
        "GRCh38",
        "--sequence-id",
        "chr1",
        "--window-start",
        "100",
        "--sequence",
        "AACCGG",
        "--position",
        "103",
        "--ref",
        "C",
        "--alt",
        "T",
    ]


class HeadlessCommandTests(unittest.TestCase):
    def test_no_subcommand_routes_to_the_tui_without_exercising_a_terminal(self) -> None:
        with patch("pancontext.tui.run") as run:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        run.assert_called_once_with()

    def test_writes_valid_json_to_stdout(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(example_arguments())

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(report["status"], "validated")
        self.assertEqual(report["model_inputs"]["alternate"]["sequence"], "AATCGG")

    def test_writes_scientific_validation_errors_to_stderr(self) -> None:
        arguments = example_arguments()
        arguments[arguments.index("C", arguments.index("--ref"))] = "G"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(arguments)

        report = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["error"]["type"], "ReferenceMismatchError")
        self.assertIn("observed 'C'", report["error"]["message"])

    def test_pretty_output_remains_machine_readable(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = main(example_arguments() + ["--pretty"])

        self.assertEqual(exit_code, 0)
        self.assertIn("\n  ", stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["status"], "validated")

    def test_runs_multi_context_experiment_from_json(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(
                ["experiment", "--input", str(EXPERIMENT_FIXTURE), "--pretty"]
            )

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["counts"]["analyzed"], 2)

    def test_reports_invalid_experiment_document_as_json_error(self) -> None:
        stdin = io.StringIO('{"schema_version": "wrong"}')
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("sys.stdin", stdin), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["experiment", "--input", "-"])

        report = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(report["status"], "error")
        self.assertIn("unsupported", report["error"]["message"])


if __name__ == "__main__":
    unittest.main()
