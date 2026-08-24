import unittest

from textual.widgets import DataTable, Input, Select, Static

from pancontext.context import ContextSource
from pancontext.tui import PanContextApp


class PanContextAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_compact_terminal_layout_mounts_with_results(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(80, 24)):
            status = app.query_one("#status", Static)
            self.assertIn("Validated", str(status.render()))
            self.assertTrue(app.screen.has_class("-compact"))

    async def test_example_is_analyzed_on_mount(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)):
            status = app.query_one("#status", Static)
            table = app.query_one("#coordinate-table", DataTable)

            self.assertIn("Validated", str(status.render()))
            self.assertEqual(table.row_count, 7)

    async def test_accepts_a_de_novo_context_without_changing_variant_logic(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#source-type", Select).value = ContextSource.DE_NOVO_ASSEMBLY.value
            app.query_one("#source-name", Input).value = "sample-assembly-v1"
            app.action_analyze()
            await pilot.pause()

            status = app.query_one("#status", Static)
            table = app.query_one("#coordinate-table", DataTable)
            self.assertIn("De novo assembly", str(status.render()))
            self.assertEqual(table.row_count, 7)

    async def test_reference_mismatch_stops_analysis(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
            app.query_one("#reference", Input).value = "G"
            app.action_analyze()
            await pilot.pause()

            status = app.query_one("#status", Static)
            table = app.query_one("#coordinate-table", DataTable)
            self.assertIn("Validation failed", str(status.render()))
            self.assertEqual(table.row_count, 0)


if __name__ == "__main__":
    unittest.main()
