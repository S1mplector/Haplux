import unittest

from textual.widgets import Button, DataTable, Input, Select, Static

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
            self.assertEqual(table.row_count, 8)

    async def test_accepts_a_de_novo_context_without_changing_variant_logic(self) -> None:
        app = PanContextApp()

        async with app.run_test(size=(120, 40)) as pilot:
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


if __name__ == "__main__":
    unittest.main()
