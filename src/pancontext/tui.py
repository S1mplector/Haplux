"""Textual renderer for the headless PanContext analysis service."""

from rich.console import Group
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static

from pancontext.analysis import AnalysisRequest, AnalysisResult, analyze_variant
from pancontext.context import ContextSource


EXAMPLE = {
    "source_type": ContextSource.LINEAR_REFERENCE.value,
    "source_name": "GRCh38",
    "sequence_id": "chr1",
    "window_start": "100",
    "sequence": "AACCGG",
    "vcf_position": "103",
    "reference": "C",
    "alternate": "T",
}

SOURCE_OPTIONS = [(source.label, source.value) for source in ContextSource]


class PanContextApp(App[None]):
    """Interactive PanContext research workspace."""

    TITLE = "PanContext"
    SUB_TITLE = "Haplotype context for variants"
    CSS_PATH = "pancontext.tcss"
    HORIZONTAL_BREAKPOINTS = [(0, "-compact"), (100, "-wide")]
    BINDINGS = [
        ("ctrl+r", "analyze", "Analyze"),
        ("e", "load_example", "Load example"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="")
        with Horizontal(id="workspace"):
            with VerticalScroll(id="input-panel"):
                yield Static("CONTEXT WORKSPACE", classes="panel-kicker")
                yield Label("Context source type", classes="field-label")
                yield Select(
                    SOURCE_OPTIONS,
                    value=EXAMPLE["source_type"],
                    allow_blank=False,
                    id="source-type",
                )
                yield Label("Source name", classes="field-label")
                yield Input(id="source-name", placeholder="e.g. GRCh38 or HPRC-v2")
                yield Label("Sequence identifier", classes="field-label")
                yield Input(id="sequence-id", placeholder="e.g. chr1")
                yield Label("Window start | 0-based interbase", classes="field-label")
                yield Input(id="window-start", placeholder="e.g. 100", type="integer")
                yield Label("Sequence context window", classes="field-label")
                yield Input(id="sequence", placeholder="DNA sequence, e.g. AACCGG")
                yield Label("Variant position | 1-based VCF-style", classes="field-label")
                yield Input(id="vcf-position", placeholder="e.g. 103", type="integer")
                with Horizontal(id="allele-row"):
                    with Vertical(classes="allele-field"):
                        yield Label("REF allele", classes="field-label")
                        yield Input(id="reference", placeholder="C")
                    with Vertical(classes="allele-field"):
                        yield Label("ALT allele", classes="field-label")
                        yield Input(id="alternate", placeholder="T")
                with Horizontal(id="actions"):
                    yield Button("Analyze", id="analyze", variant="primary")
                    yield Button("Load example", id="load-example", variant="default")
                yield Static(
                    "External records enter as 1-based VCF positions. PanContext converts "
                    "them once and uses 0-based half-open intervals internally. The source "
                    "label records provenance; the sequence digest records content.",
                    id="coordinate-note",
                )

            with Vertical(id="results-panel"):
                yield Static("ANALYSIS", classes="panel-kicker")
                yield Static("Ready for input.", id="status")
                yield DataTable(id="coordinate-table")
                yield Static("Sequence comparison will appear here.", id="preview")
                yield Static(
                    "[b]Interpretation[/b]\nProvide a variant to inspect its representation.",
                    id="interpretation",
                )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#coordinate-table", DataTable)
        table.add_columns("Field", "Input", "PanContext internal")
        table.cursor_type = "row"
        table.zebra_stripes = True
        self.action_load_example()
        self.action_analyze()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "analyze":
            self.action_analyze()
        elif event.button.id == "load-example":
            self.action_load_example()

    def action_load_example(self) -> None:
        self.query_one("#source-type", Select).value = EXAMPLE["source_type"]
        self.query_one("#source-name", Input).value = EXAMPLE["source_name"]
        self.query_one("#sequence-id", Input).value = EXAMPLE["sequence_id"]
        self.query_one("#window-start", Input).value = EXAMPLE["window_start"]
        self.query_one("#sequence", Input).value = EXAMPLE["sequence"]
        self.query_one("#vcf-position", Input).value = EXAMPLE["vcf_position"]
        self.query_one("#reference", Input).value = EXAMPLE["reference"]
        self.query_one("#alternate", Input).value = EXAMPLE["alternate"]
        self.query_one("#status", Static).update(
            "Example loaded. Press Analyze or Ctrl+R after editing."
        )

    def action_analyze(self) -> None:
        status = self.query_one("#status", Static)
        try:
            result = analyze_variant(self._read_request())
        except ValueError as error:
            status.remove_class("success")
            status.add_class("error")
            status.update(f"Validation failed: {error}")
            self._clear_results()
            return

        status.remove_class("error")
        status.add_class("success")
        status.update(result.status_text)
        self._update_coordinate_table(result)
        self.query_one("#preview", Static).update(self._sequence_preview(result))
        self.query_one("#interpretation", Static).update(
            f"[b]Interpretation[/b]\n{result.interpretation}"
        )

    def _read_request(self) -> AnalysisRequest:
        source_value = self.query_one("#source-type", Select).value
        if source_value is Select.NULL:
            raise ValueError("context source type must be selected")
        return AnalysisRequest(
            source_type=ContextSource(str(source_value)),
            source_name=self.query_one("#source-name", Input).value,
            sequence_id=self.query_one("#sequence-id", Input).value,
            window_start=int(self.query_one("#window-start", Input).value),
            sequence=self.query_one("#sequence", Input).value,
            vcf_position=int(self.query_one("#vcf-position", Input).value),
            reference=self.query_one("#reference", Input).value,
            alternate=self.query_one("#alternate", Input).value,
        )

    def _update_coordinate_table(self, result: AnalysisResult) -> None:
        table = self.query_one("#coordinate-table", DataTable)
        table.clear(columns=False)
        table.add_rows(result.coordinate_rows)

    def _clear_results(self) -> None:
        self.query_one("#coordinate-table", DataTable).clear(columns=False)
        self.query_one("#preview", Static).update("No sequence preview: correct the input.")
        self.query_one("#interpretation", Static).update(
            "[b]Interpretation[/b]\nScientific analysis stops at invalid input."
        )

    @staticmethod
    def _sequence_preview(result: AnalysisResult) -> Group:
        window = result.context.window
        variant = result.variant
        alternate_sequence = result.alternate_sequence
        local_start = variant.start - window.start
        local_ref_end = local_start + len(variant.reference)
        local_alt_end = local_start + len(variant.alternate)

        reference = Text("REF  ", style="bold #a7a9ad")
        reference.append(window.sequence[:local_start])
        reference.append(
            window.sequence[local_start:local_ref_end],
            style="bold #f2f2f2 on #4d4f54",
        )
        reference.append(window.sequence[local_ref_end:])

        alternate = Text("ALT  ", style="bold #a7a9ad")
        alternate.append(alternate_sequence[:local_start])
        alternate.append(
            alternate_sequence[local_start:local_alt_end],
            style="bold #111214 on #d5d6d8",
        )
        alternate.append(alternate_sequence[local_alt_end:])

        coordinates = Text(
            f"     window {window.sequence_id}:[{window.start}, {window.end})",
            style="dim",
        )
        return Group(reference, alternate, coordinates)


def run() -> None:
    """Launch the PanContext terminal application."""

    PanContextApp().run()
