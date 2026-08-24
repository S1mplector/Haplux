"""Professional Textual client for experiments and single-context inspection."""

from typing import Optional

from rich.console import Group
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from pancontext.analysis import AnalysisRequest, AnalysisResult, analyze_variant
from pancontext.context import ContextSource
from pancontext.demo import experiment_demo_document
from pancontext.experiment import ExperimentResult, run_experiment
from pancontext.experiment_io import (
    ParsedExperiment,
    load_experiment_file,
    parse_experiment_document,
)


INSPECTOR_EXAMPLE = {
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
    """Interactive client backed exclusively by headless PanContext services."""

    TITLE = "PanContext"
    SUB_TITLE = "Haplotype context stability laboratory"
    CSS_PATH = "pancontext.tcss"
    HORIZONTAL_BREAKPOINTS = [(0, "-compact"), (100, "-wide")]
    BINDINGS = [
        ("ctrl+r", "rerun", "Run"),
        ("d", "load_demo", "Demo"),
        ("1", "show_experiment", "Experiment"),
        ("2", "show_inspector", "Inspector"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_experiment: Optional[ParsedExperiment] = None
        self._experiment_result: Optional[ExperimentResult] = None
        self._experiment_source = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="")
        with TabbedContent(initial="experiment-tab", id="main-tabs"):
            with TabPane("Experiment", id="experiment-tab"):
                yield from self._compose_experiment()
            with TabPane("Context Inspector", id="inspector-tab"):
                yield from self._compose_inspector()
            with TabPane("Guide", id="guide-tab"):
                yield from self._compose_guide()
        yield Footer()

    def _compose_experiment(self) -> ComposeResult:
        with Horizontal(id="experiment-workspace"):
            with Vertical(id="experiment-controls", classes="panel"):
                yield Static("EXPERIMENT SETUP", classes="panel-kicker")
                yield Label("Experiment request", classes="field-label")
                yield Input(
                    id="experiment-path",
                    placeholder="Path to a pancontext.experiment-request.v1 JSON file",
                )
                with Horizontal(classes="button-row"):
                    yield Button("Run file", id="run-experiment", variant="primary")
                    yield Button("Load demo", id="load-demo", variant="default")
                yield Static(
                    "A request defines one focal variant, projected haplotype contexts, "
                    "the observed allele in each context, and a model adapter.",
                    classes="callout",
                )
                yield Static("CURRENT RUN", classes="section-label")
                yield Static("No experiment loaded.", id="experiment-metadata")
                yield Static(
                    "GC-content and motif-count are deterministic development scorers. "
                    "They verify the experiment pipeline; they are not biological models.",
                    classes="boundary-note",
                )

            with Vertical(id="experiment-results", classes="panel"):
                yield Static("CONTEXT STABILITY", classes="panel-kicker")
                yield Static("Ready for an experiment.", id="experiment-status")
                with Horizontal(id="metric-row"):
                    yield Static("0 / 0\nContexts", id="metric-contexts", classes="metric-card")
                    yield Static("--\nMean effect", id="metric-mean", classes="metric-card")
                    yield Static("--\nEffect range", id="metric-range", classes="metric-card")
                    yield Static("--\nSign agreement", id="metric-sign", classes="metric-card")
                yield Static("PAIRED CONTEXT EFFECTS", classes="section-label")
                yield DataTable(id="experiment-table")
                yield Static("No skipped contexts.", id="skipped-contexts")

    def _compose_inspector(self) -> ComposeResult:
        with Horizontal(id="inspector-workspace"):
            with VerticalScroll(id="input-panel", classes="panel"):
                yield Static("CONTEXT INSPECTOR", classes="panel-kicker")
                yield Label("Context source type", classes="field-label")
                yield Select(
                    SOURCE_OPTIONS,
                    value=INSPECTOR_EXAMPLE["source_type"],
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
                with Horizontal(classes="button-row"):
                    yield Button("Analyze", id="analyze", variant="primary")
                    yield Button("Reset example", id="load-example", variant="default")
                yield Static(
                    "The inspector validates one projected context. Use the Experiment "
                    "workspace to compare effects across haplotypes.",
                    classes="callout",
                )

            with Vertical(id="results-panel", classes="panel"):
                yield Static("VALIDATION", classes="panel-kicker")
                yield Static("Ready for input.", id="status")
                yield DataTable(id="coordinate-table")
                yield Static("Sequence comparison will appear here.", id="preview")
                yield Static(
                    "[b]Interpretation[/b]\nProvide a variant to inspect its representation.",
                    id="interpretation",
                )

    def _compose_guide(self) -> ComposeResult:
        with VerticalScroll(id="guide-content", classes="panel"):
            yield Static("WORKFLOW GUIDE", classes="panel-kicker")
            yield Static(
                "[b]Experiment[/b]\n"
                "Load a versioned JSON request or the bundled demo. PanContext constructs "
                "matched REF/ALT inputs, scores both, and compares paired effects across "
                "contexts.\n\n"
                "[b]Context Inspector[/b]\n"
                "Validate one sequence window, coordinate conversion, and allele "
                "replacement. This is the debugging surface for provider output.\n\n"
                "[b]Keyboard[/b]\n"
                "1 opens Experiment. 2 opens Context Inspector. Ctrl+R reruns the active "
                "workflow. D restores the bundled experiment. Q quits.\n\n"
                "[b]Scientific boundary[/b]\n"
                "Current scorers are development instruments. PanContext does not yet load "
                "FASTA, VCF, GFA, or execute a biological foundation model.",
                id="guide-text",
            )

    def on_mount(self) -> None:
        experiment_table = self.query_one("#experiment-table", DataTable)
        experiment_table.add_columns(
            "Context",
            "Observed",
            "Baseline",
            "Alternate",
            "Effect",
        )
        experiment_table.cursor_type = "row"
        experiment_table.zebra_stripes = True

        coordinate_table = self.query_one("#coordinate-table", DataTable)
        coordinate_table.add_columns("Field", "Input", "PanContext internal")
        coordinate_table.cursor_type = "row"
        coordinate_table.zebra_stripes = True

        self._load_inspector_example()
        self._analyze_context()
        self.action_load_demo()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "run-experiment":
            self.action_run_experiment_file()
        elif button_id == "load-demo":
            self.action_load_demo()
        elif button_id == "analyze":
            self._analyze_context()
        elif button_id == "load-example":
            self._load_inspector_example()
            self._analyze_context()

    def action_show_experiment(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "experiment-tab"

    def action_show_inspector(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "inspector-tab"

    def action_rerun(self) -> None:
        active = self.query_one("#main-tabs", TabbedContent).active
        if active == "inspector-tab":
            self._analyze_context()
        elif self._current_experiment is not None:
            self._execute_experiment(self._current_experiment, self._experiment_source)
        else:
            self.action_load_demo()

    def action_load_demo(self) -> None:
        try:
            parsed = parse_experiment_document(experiment_demo_document())
        except ValueError as error:
            self._render_experiment_error(error)
            return
        self.query_one("#experiment-path", Input).value = ""
        self._execute_experiment(parsed, "Bundled three-haplotype demo")

    def action_run_experiment_file(self) -> None:
        path = self.query_one("#experiment-path", Input).value.strip()
        if not path:
            self._render_experiment_error(ValueError("provide an experiment JSON path"))
            return
        try:
            parsed = load_experiment_file(path)
        except (OSError, ValueError) as error:
            self._render_experiment_error(error)
            return
        self._execute_experiment(parsed, path)

    def _execute_experiment(self, parsed: ParsedExperiment, source: str) -> None:
        try:
            result = run_experiment(parsed.request, parsed.model)
        except ValueError as error:
            self._render_experiment_error(error)
            return
        self._current_experiment = parsed
        self._experiment_result = result
        self._experiment_source = source
        self._render_experiment(result, source)

    def _render_experiment(self, result: ExperimentResult, source: str) -> None:
        status = self.query_one("#experiment-status", Static)
        status.remove_class("completed", "error", "failed", "partial")
        status.add_class("error" if result.status == "failed" else result.status)
        status.update(
            f"{result.status.title()}: {len(result.effects)} analyzed, "
            f"{len(result.skipped_contexts)} skipped"
        )

        model = result.model_metadata
        focal = result.request.focal_variant
        self.query_one("#experiment-metadata", Static).update(
            f"[b]{result.request.experiment_id}[/b]\n"
            f"Variant: {focal.identifier} ({focal.reference} to {focal.alternate})\n"
            f"Model: {model.get('adapter', 'unknown')} v{model.get('version', 'unknown')}\n"
            f"Source: {source}"
        )

        requested = len(result.request.contexts)
        analyzed = len(result.effects)
        self.query_one("#metric-contexts", Static).update(
            f"[b]{analyzed} / {requested}[/b]\nContexts"
        )
        if result.stability is None:
            mean = effect_range = agreement = "--"
        else:
            mean = self._format_score(result.stability.mean_effect)
            effect_range = self._format_score(result.stability.effect_range)
            agreement = f"{result.stability.sign_agreement:.0%}"
        self.query_one("#metric-mean", Static).update(f"[b]{mean}[/b]\nMean effect")
        self.query_one("#metric-range", Static).update(
            f"[b]{effect_range}[/b]\nEffect range"
        )
        self.query_one("#metric-sign", Static).update(
            f"[b]{agreement}[/b]\nSign agreement"
        )

        table = self.query_one("#experiment-table", DataTable)
        table.clear(columns=False)
        table.add_rows(
            (
                effect.context_id,
                effect.observed_allele.value,
                self._format_score(effect.baseline_score),
                self._format_score(effect.alternate_score),
                self._format_score(effect.effect),
            )
            for effect in result.effects
        )

        skipped = self.query_one("#skipped-contexts", Static)
        if not result.skipped_contexts:
            skipped.update("No contexts skipped. All supplied projections were compatible.")
        else:
            lines = ["[b]Skipped contexts[/b]"]
            lines.extend(
                f"{item.context_id}: {item.stage} | {item.reason}"
                for item in result.skipped_contexts
            )
            skipped.update("\n".join(lines))

    def _render_experiment_error(self, error: Exception) -> None:
        self._current_experiment = None
        self._experiment_result = None
        self._experiment_source = ""

        status = self.query_one("#experiment-status", Static)
        status.remove_class("completed", "failed", "partial")
        status.add_class("error")
        status.update(f"Experiment failed: {error}")

        self.query_one("#experiment-metadata", Static).update(
            "No valid experiment loaded. Correct the request or load the demo."
        )
        self.query_one("#metric-contexts", Static).update("0 / 0\nContexts")
        self.query_one("#metric-mean", Static).update("--\nMean effect")
        self.query_one("#metric-range", Static).update("--\nEffect range")
        self.query_one("#metric-sign", Static).update("--\nSign agreement")
        self.query_one("#experiment-table", DataTable).clear(columns=False)
        self.query_one("#skipped-contexts", Static).update("No experiment results.")

    def _load_inspector_example(self) -> None:
        self.query_one("#source-type", Select).value = INSPECTOR_EXAMPLE["source_type"]
        self.query_one("#source-name", Input).value = INSPECTOR_EXAMPLE["source_name"]
        self.query_one("#sequence-id", Input).value = INSPECTOR_EXAMPLE["sequence_id"]
        self.query_one("#window-start", Input).value = INSPECTOR_EXAMPLE["window_start"]
        self.query_one("#sequence", Input).value = INSPECTOR_EXAMPLE["sequence"]
        self.query_one("#vcf-position", Input).value = INSPECTOR_EXAMPLE["vcf_position"]
        self.query_one("#reference", Input).value = INSPECTOR_EXAMPLE["reference"]
        self.query_one("#alternate", Input).value = INSPECTOR_EXAMPLE["alternate"]

    def _analyze_context(self) -> None:
        status = self.query_one("#status", Static)
        try:
            result = analyze_variant(self._read_inspector_request())
        except ValueError as error:
            status.remove_class("success")
            status.add_class("error")
            status.update(f"Validation failed: {error}")
            self._clear_inspector_results()
            return

        status.remove_class("error")
        status.add_class("success")
        status.update(result.status_text)
        table = self.query_one("#coordinate-table", DataTable)
        table.clear(columns=False)
        table.add_rows(result.coordinate_rows)
        self.query_one("#preview", Static).update(self._sequence_preview(result))
        self.query_one("#interpretation", Static).update(
            f"[b]Interpretation[/b]\n{result.interpretation}"
        )

    def _read_inspector_request(self) -> AnalysisRequest:
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

    def _clear_inspector_results(self) -> None:
        self.query_one("#coordinate-table", DataTable).clear(columns=False)
        self.query_one("#preview", Static).update("No sequence preview: correct the input.")
        self.query_one("#interpretation", Static).update(
            "[b]Interpretation[/b]\nScientific analysis stops at invalid input."
        )

    @staticmethod
    def _format_score(value: float) -> str:
        return f"{value:+.6f}"

    @staticmethod
    def _sequence_preview(result: AnalysisResult) -> Group:
        window = result.context.window
        variant = result.variant
        local_start = variant.start - window.start
        local_ref_end = local_start + len(variant.reference)
        local_alt_end = local_start + len(variant.alternate)

        reference = Text("REF  ", style="bold #a7a9ad")
        reference.append(result.baseline_sequence[:local_start])
        reference.append(
            result.baseline_sequence[local_start:local_ref_end],
            style="bold #f2f2f2 on #4d4f54",
        )
        reference.append(result.baseline_sequence[local_ref_end:])

        alternate = Text("ALT  ", style="bold #a7a9ad")
        alternate.append(result.alternate_sequence[:local_start])
        alternate.append(
            result.alternate_sequence[local_start:local_alt_end],
            style="bold #111214 on #d5d6d8",
        )
        alternate.append(result.alternate_sequence[local_alt_end:])

        coordinates = Text(
            f"     source window {window.sequence_id}:[{window.start}, {window.end})",
            style="dim",
        )
        return Group(reference, alternate, coordinates)


def run() -> None:
    """Launch the PanContext terminal application."""

    PanContextApp().run()
