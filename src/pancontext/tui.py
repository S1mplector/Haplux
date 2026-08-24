"""Textual workspace for inspecting variants and coordinate conversions."""

from typing import Tuple

from rich.console import Group
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from pancontext.domain import (
    HaplotypeWindow,
    ReferenceMismatchError,
    SequenceValidationError,
    Variant,
)


EXAMPLE = {
    "sequence_id": "chr1",
    "window_start": "100",
    "sequence": "AACCGG",
    "vcf_position": "103",
    "reference": "C",
    "alternate": "T",
}


class PanContextApp(App[None]):
    """Interactive PanContext research workspace."""

    TITLE = "PanContext"
    SUB_TITLE = "Haplotype context laboratory · Milestone 01"
    CSS_PATH = "pancontext.tcss"
    HORIZONTAL_BREAKPOINTS = [(0, "-compact"), (100, "-wide")]
    BINDINGS = [
        ("ctrl+r", "analyze", "Analyze"),
        ("e", "load_example", "Load example"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="workspace"):
            with VerticalScroll(id="input-panel"):
                yield Static("VARIANT WORKSPACE", classes="panel-kicker")
                yield Label("Sequence identifier", classes="field-label")
                yield Input(id="sequence-id", placeholder="e.g. chr1")
                yield Label("Window start · 0-based interbase", classes="field-label")
                yield Input(id="window-start", placeholder="e.g. 100", type="integer")
                yield Label("Reference haplotype window", classes="field-label")
                yield Input(id="sequence", placeholder="DNA sequence, e.g. AACCGG")
                yield Label("Variant position · 1-based VCF", classes="field-label")
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
                    "them once and uses 0-based half-open intervals internally.",
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
            window, variant = self._read_workspace()
            alternate_sequence = variant.apply_to(window)
        except (SequenceValidationError, ReferenceMismatchError, ValueError) as error:
            status.remove_class("success")
            status.add_class("error")
            status.update(f"Validation failed · {error}")
            self._clear_results()
            return

        status.remove_class("error")
        status.add_class("success")
        status.update(
            f"Validated · {self._variant_kind(variant)} on "
            f"{variant.sequence_id}:[{variant.start}, {variant.end})"
        )
        self._update_coordinate_table(window, variant)
        self.query_one("#preview", Static).update(
            self._sequence_preview(window, variant, alternate_sequence)
        )
        self.query_one("#interpretation", Static).update(
            "[b]Interpretation[/b]\n"
            f"The VCF position {variant.start + 1} becomes internal start "
            f"{variant.start}. The declared REF allele matches the supplied window, "
            "so this sequence replacement is safe to pass to later model adapters."
        )

    def _read_workspace(self) -> Tuple[HaplotypeWindow, Variant]:
        sequence_id = self.query_one("#sequence-id", Input).value
        window_start = int(self.query_one("#window-start", Input).value)
        sequence = self.query_one("#sequence", Input).value
        vcf_position = int(self.query_one("#vcf-position", Input).value)
        reference = self.query_one("#reference", Input).value
        alternate = self.query_one("#alternate", Input).value

        window = HaplotypeWindow(
            sequence_id=sequence_id,
            start=window_start,
            sequence=sequence,
        )
        variant = Variant.from_vcf(
            sequence_id=sequence_id,
            position=vcf_position,
            reference=reference,
            alternate=alternate,
        )
        return window, variant

    def _update_coordinate_table(self, window: HaplotypeWindow, variant: Variant) -> None:
        table = self.query_one("#coordinate-table", DataTable)
        table.clear(columns=False)
        table.add_rows(
            [
                ("Sequence", window.sequence_id, window.sequence_id),
                ("Variant position", str(variant.start + 1), str(variant.start)),
                ("Variant interval", "VCF POS + REF", f"[{variant.start}, {variant.end})"),
                ("Window interval", str(window.start), f"[{window.start}, {window.end})"),
                ("Alleles", f"{variant.reference} → {variant.alternate}", "validated"),
            ]
        )

    def _clear_results(self) -> None:
        self.query_one("#coordinate-table", DataTable).clear(columns=False)
        self.query_one("#preview", Static).update("No sequence preview: correct the input.")
        self.query_one("#interpretation", Static).update(
            "[b]Interpretation[/b]\nScientific analysis stops at invalid input."
        )

    @staticmethod
    def _variant_kind(variant: Variant) -> str:
        if len(variant.reference) == len(variant.alternate) == 1:
            return "single-nucleotide variant"
        if len(variant.alternate) > len(variant.reference):
            return "insertion"
        if len(variant.alternate) < len(variant.reference):
            return "deletion"
        return "multi-nucleotide substitution"

    @staticmethod
    def _sequence_preview(
        window: HaplotypeWindow,
        variant: Variant,
        alternate_sequence: str,
    ) -> Group:
        local_start = variant.start - window.start
        local_ref_end = local_start + len(variant.reference)
        local_alt_end = local_start + len(variant.alternate)

        reference = Text("REF  ", style="bold #8fa7b3")
        reference.append(window.sequence[:local_start])
        reference.append(window.sequence[local_start:local_ref_end], style="bold #ffb86c")
        reference.append(window.sequence[local_ref_end:])

        alternate = Text("ALT  ", style="bold #8fa7b3")
        alternate.append(alternate_sequence[:local_start])
        alternate.append(alternate_sequence[local_start:local_alt_end], style="bold #63e6be")
        alternate.append(alternate_sequence[local_alt_end:])

        coordinates = Text(
            f"     window {window.sequence_id}:[{window.start}, {window.end})",
            style="dim",
        )
        return Group(reference, alternate, coordinates)


def run() -> None:
    """Launch the PanContext terminal application."""

    PanContextApp().run()
