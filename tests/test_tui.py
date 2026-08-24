import unittest
import json
from pathlib import Path
import tempfile

import pysam
from textual.widgets import Button, DataTable, Input, Select, Static, TabbedContent

from pancontext.context import ContextSource
from pancontext.tui import PanContextApp


FIXTURES = Path(__file__).parent / "fixtures"
FASTA_FIXTURE = FIXTURES / "mini.fa"
VCF_FIXTURE = FIXTURES / "cohort.vcf"


class PanContextAppTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.indexed_vcf = Path(cls.temporary_directory.name) / "cohort.vcf.gz"
        pysam.tabix_compress(str(VCF_FIXTURE), str(cls.indexed_vcf), force=True)
        pysam.tabix_index(str(cls.indexed_vcf), preset="vcf", force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary_directory.cleanup()

    def fill_real_data_form(self, app: PanContextApp, *, contig: str = "chr1") -> None:
        app.query_one("#real-fasta", Input).value = str(FASTA_FIXTURE)
        app.query_one("#real-vcf", Input).value = str(self.indexed_vcf)
        app.query_one("#real-assembly", Input).value = "mini-v1"
        app.query_one("#real-contig", Input).value = contig
        app.query_one("#real-position", Input).value = "21"
        app.query_one("#real-reference", Input).value = "C"
        app.query_one("#real-alternate", Input).value = "T"
        app.query_one("#real-left-flank", Input).value = "10"
        app.query_one("#real-right-flank", Input).value = "10"
        app.query_one("#real-samples", Input).value = "HG_REF, HG_MIX"

    async def test_compact_terminal_layout_mounts_with_results(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(80, 24)):
            status = app.query_one("#experiment-status", Static)
            self.assertIn("Completed", str(status.render()))
            self.assertTrue(app.screen.has_class("-compact"))

    async def test_demo_experiment_is_analyzed_on_mount(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)):
            tabs = app.query_one("#main-tabs", TabbedContent)
            table = app.query_one("#experiment-table", DataTable)
            metadata = app.query_one("#experiment-metadata", Static)

            self.assertEqual(tabs.active, "experiment-tab")
            self.assertEqual(table.row_count, 3)
            self.assertIn("three-haplotype-demo", str(metadata.render()))

    async def test_example_is_analyzed_on_mount(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)):
            status = app.query_one("#status", Static)
            table = app.query_one("#coordinate-table", DataTable)

            self.assertIn("Validated", str(status.render()))
            self.assertEqual(table.row_count, 8)

    async def test_accepts_a_de_novo_context_without_changing_variant_logic(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#main-tabs", TabbedContent).active = "inspector-tab"
            app.query_one("#source-type", Select).value = ContextSource.DE_NOVO_ASSEMBLY.value
            app.query_one("#source-name", Input).value = "sample-assembly-v1"
            await pilot.press("ctrl+r")
            await pilot.pause()

            status = app.query_one("#status", Static)
            table = app.query_one("#coordinate-table", DataTable)
            self.assertIn("De novo assembly", str(status.render()))
            self.assertEqual(table.row_count, 8)

    async def test_reference_mismatch_stops_analysis(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#main-tabs", TabbedContent).active = "inspector-tab"
            app.query_one("#reference", Input).value = "G"
            await pilot.press("ctrl+r")
            await pilot.pause()

            status = app.query_one("#status", Static)
            table = app.query_one("#coordinate-table", DataTable)
            self.assertIn("Validation failed", str(status.render()))
            self.assertEqual(table.row_count, 0)

    async def test_buttons_restore_and_analyze_the_example_headlessly(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#sequence", Input).value = "TTTT"
            app.query_one("#load-example", Button).press()
            await pilot.pause()

            self.assertEqual(app.query_one("#sequence", Input).value, "AACCGG")
            app.query_one("#analyze", Button).press()
            await pilot.pause()
            self.assertIn(
                "Validated",
                str(app.query_one("#status", Static).render()),
            )

    async def test_experiment_file_error_is_rendered_without_crashing(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#experiment-path", Input).value = "/not/a/real/experiment.json"
            app.query_one("#run-experiment", Button).press()
            await pilot.pause()

            status = app.query_one("#experiment-status", Static)
            self.assertIn("Experiment failed", str(status.render()))
            self.assertEqual(
                app.query_one("#experiment-table", DataTable).row_count,
                0,
            )
            self.assertIn(
                "No valid experiment",
                str(app.query_one("#experiment-metadata", Static).render()),
            )

    async def test_experiment_fixture_runs_from_the_file_control(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            fixture = FIXTURES / "experiment_request.json"
            app.query_one("#experiment-path", Input).value = str(fixture)
            app.query_one("#run-experiment", Button).press()
            await pilot.pause()

            self.assertIn(
                "Completed: 2 analyzed",
                str(app.query_one("#experiment-status", Static).render()),
            )
            self.assertEqual(
                app.query_one("#experiment-table", DataTable).row_count,
                2,
            )
            self.assertIn(
                "two-haplotype-demo",
                str(app.query_one("#experiment-metadata", Static).render()),
            )

    async def test_tab_shortcut_routes_ctrl_r_to_inspector(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("3")
            app.query_one("#reference", Input).value = "G"
            await pilot.press("ctrl+r")
            await pilot.pause()

            self.assertEqual(
                app.query_one("#main-tabs", TabbedContent).active,
                "inspector-tab",
            )
            self.assertIn(
                "Validation failed",
                str(app.query_one("#status", Static).render()),
            )

    async def test_real_data_workspace_reconstructs_and_routes_to_experiment(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("2")
            self.fill_real_data_form(app)
            app.query_one("#run-real-data", Button).press()
            await pilot.pause()

            self.assertEqual(
                app.query_one("#main-tabs", TabbedContent).active,
                "experiment-tab",
            )
            self.assertEqual(
                app.query_one("#experiment-table", DataTable).row_count,
                4,
            )
            self.assertIn(
                "Indexed FASTA/VCF",
                str(app.query_one("#experiment-metadata", Static).render()),
            )
            self.assertIn(
                "Completed: 4 contexts",
                str(app.query_one("#real-data-status", Static).render()),
            )

    async def test_real_data_provider_error_remains_in_loader(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("2")
            self.fill_real_data_form(app, contig="1")
            app.query_one("#run-real-data", Button).press()
            await pilot.pause()

            self.assertEqual(
                app.query_one("#main-tabs", TabbedContent).active,
                "real-data-tab",
            )
            self.assertIn(
                "Provider failed",
                str(app.query_one("#real-data-status", Static).render()),
            )

    async def test_real_data_form_names_the_missing_field(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("2")
            self.fill_real_data_form(app)
            app.query_one("#real-position", Input).value = ""
            await pilot.pause()

            readiness = str(app.query_one("#real-data-readiness", Static).render())
            self.assertIn("Position is required", readiness)
            self.assertTrue(app.query_one("#real-position", Input).has_class("invalid"))

            app.query_one("#run-real-data", Button).press()
            await pilot.pause()
            self.assertIn(
                "Input failed: Position is required",
                str(app.query_one("#real-data-status", Static).render()),
            )

    async def test_real_data_preview_explains_expected_work_unit(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("2")
            self.fill_real_data_form(app)
            await pilot.pause()

            readiness = str(app.query_one("#real-data-readiness", Static).render())
            self.assertIn("Ready to run", readiness)
            self.assertIn("21 reference-coordinate bases", readiness)
            self.assertIn("2 samples; up to 4 contexts", readiness)
            self.assertIn("C>T", readiness)

    async def test_real_data_input_rows_do_not_expand_vertically(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("2")
            await pilot.pause()

            rows = list(app.query(".form-row"))
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row.region.height <= 6 for row in rows))
            self.assertEqual(rows[1].region.y, rows[0].region.bottom)

    async def test_motif_scorer_requires_a_valid_motif(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("2")
            self.fill_real_data_form(app)
            app.query_one("#real-model", Select).value = "motif_count"
            await pilot.pause()

            motif = app.query_one("#real-motif", Input)
            self.assertFalse(motif.disabled)
            self.assertIn(
                "Motif is required",
                str(app.query_one("#real-data-readiness", Static).render()),
            )

            motif.value = "CX"
            await pilot.pause()
            self.assertIn(
                "Motif must contain only",
                str(app.query_one("#real-data-readiness", Static).render()),
            )

            motif.value = "CAG"
            await pilot.pause()
            self.assertIn(
                "Ready to run",
                str(app.query_one("#real-data-readiness", Static).render()),
            )

    async def test_public_lesson_manifest_populates_the_workflow(self) -> None:
        manifest = Path(self.temporary_directory.name) / "lesson.json"
        manifest.write_text(
            json.dumps(
                {
                    "assembly": "mini-v1",
                    "local_files": {
                        "fasta": str(FASTA_FIXTURE),
                        "vcf": str(self.indexed_vcf),
                    },
                    "samples": ["HG_REF", "HG_MIX"],
                    "focal_variant": {
                        "contig": "chr1",
                        "position": 21,
                        "reference": "C",
                        "alternate": "T",
                    },
                }
            ),
            encoding="utf-8",
        )
        app = PanContextApp(lesson_manifest=manifest)

        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.press("l")
            await pilot.pause()

            self.assertEqual(
                app.query_one("#main-tabs", TabbedContent).active,
                "real-data-tab",
            )
            self.assertEqual(app.query_one("#real-contig", Input).value, "chr1")
            self.assertEqual(app.query_one("#real-position", Input).value, "21")
            self.assertEqual(app.query_one("#real-left-flank", Input).value, "8")
            self.assertEqual(app.query_one("#real-model", Select).value, "motif_count")
            self.assertIn(
                "2 samples; up to 4 contexts",
                str(app.query_one("#real-data-readiness", Static).render()),
            )

    async def test_experiment_results_explain_context_dependence(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(140, 45)):
            insight = str(app.query_one("#stability-interpretation", Static).render())
            table = app.query_one("#experiment-table", DataTable)
            self.assertIn("Interpretation", insight)
            self.assertIn("tested contexts", insight)
            self.assertEqual(len(table.columns), 6)


if __name__ == "__main__":
    unittest.main()
