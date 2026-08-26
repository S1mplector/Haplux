import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pysam


EXPERIMENT_FIXTURE = Path(__file__).parent / "fixtures" / "experiment_request.json"
FASTA_FIXTURE = Path(__file__).parent / "fixtures" / "mini.fa"
VCF_FIXTURE = Path(__file__).parent / "fixtures" / "cohort.vcf"


def module_command(reference: str = "C") -> list:
    return [
        sys.executable,
        "-m",
        "haplux",
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
        reference,
        "--alt",
        "T",
    ]


class ModuleEntrypointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.indexed_vcf = Path(cls.temporary_directory.name) / "cohort.vcf.gz"
        pysam.tabix_compress(str(VCF_FIXTURE), str(cls.indexed_vcf), force=True)
        pysam.tabix_index(str(cls.indexed_vcf), preset="vcf", force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def test_module_entrypoint_runs_headlessly_in_a_fresh_process(self) -> None:
        completed = subprocess.run(
            module_command(),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertEqual(json.loads(completed.stdout)["status"], "validated")

    def test_module_entrypoint_preserves_error_exit_code_and_stream(self) -> None:
        completed = subprocess.run(
            module_command(reference="G"),
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(json.loads(completed.stderr)["status"], "error")

    def test_module_entrypoint_runs_multi_context_experiment(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "haplux",
                "experiment",
                "--input",
                str(EXPERIMENT_FIXTURE),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["counts"]["analyzed"], 2)

    def test_module_entrypoint_runs_a_real_data_experiment(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "haplux",
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
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["provider"]["counts"]["contexts"], 2)
        self.assertEqual(report["experiment"]["counts"]["analyzed"], 2)


if __name__ == "__main__":
    unittest.main()
