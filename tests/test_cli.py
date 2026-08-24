import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
from unittest.mock import patch

import pysam

from pancontext.cli import main


EXPERIMENT_FIXTURE = Path(__file__).parent / "fixtures" / "experiment_request.json"
FASTA_FIXTURE = Path(__file__).parent / "fixtures" / "mini.fa"
VCF_FIXTURE = Path(__file__).parent / "fixtures" / "cohort.vcf"


def experiment_document() -> dict:
    return json.loads(EXPERIMENT_FIXTURE.read_text(encoding="utf-8"))


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
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.indexed_vcf = Path(cls.temporary_directory.name) / "cohort.vcf.gz"
        pysam.tabix_compress(str(VCF_FIXTURE), str(cls.indexed_vcf), force=True)
        pysam.tabix_index(str(cls.indexed_vcf), preset="vcf", force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def vcf_arguments(self) -> list:
        return [
            "vcf-experiment",
            "--fasta",
            str(FASTA_FIXTURE),
            "--vcf",
            str(self.indexed_vcf),
            "--assembly",
            "mini-v1",
            "--contig",
            "chr1",
            "--position",
            "21",
            "--ref",
            "C",
            "--alt",
            "T",
            "--left-flank",
            "10",
            "--right-flank",
            "10",
            "--sample",
            "HG_REF",
            "--sample",
            "HG_MIX",
        ]

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

    def test_failed_experiment_uses_stderr_and_nonzero_exit(self) -> None:
        document = experiment_document()
        for context in document["experiment"]["contexts"]:
            context["sequence"] = "AAGCGG"
            context["vcf_position"] = 103
            context["observed_allele"] = "reference"
        stdin = io.StringIO(json.dumps(document))
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("sys.stdin", stdin), redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(["experiment", "--input", "-"])

        report = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counts"]["analyzed"], 0)

    def test_runs_an_indexed_fasta_vcf_experiment(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(self.vcf_arguments() + ["--pretty"])

        report = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["provider"]["counts"]["contexts"], 4)
        self.assertEqual(report["experiment"]["counts"]["analyzed"], 4)

    def test_reports_real_data_provider_errors_as_versioned_json(self) -> None:
        arguments = self.vcf_arguments()
        arguments[arguments.index("chr1")] = "1"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = main(arguments)

        report = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(report["schema_version"], "pancontext.real-data-experiment.v1")
        self.assertEqual(report["status"], "error")
        self.assertIn("exact contig", report["error"]["message"])


if __name__ == "__main__":
    unittest.main()
