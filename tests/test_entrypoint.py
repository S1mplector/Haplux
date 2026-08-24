import json
import subprocess
import sys
import unittest
from pathlib import Path


EXPERIMENT_FIXTURE = Path(__file__).parent / "fixtures" / "experiment_request.json"


def module_command(reference: str = "C") -> list:
    return [
        sys.executable,
        "-m",
        "pancontext",
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
                "pancontext",
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


if __name__ == "__main__":
    unittest.main()
