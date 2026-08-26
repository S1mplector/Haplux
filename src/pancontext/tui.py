"""Professional Textual client for experiments and genomic context loading."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Group
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
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
from pancontext.experiment import ContextEffect, ExperimentResult, FocalVariant, run_experiment
from pancontext.experiment_io import (
    ParsedExperiment,
    load_experiment_file,
    parse_experiment_document,
)
from pancontext.fasta_vcf import FastaVcfProvider
from pancontext.models import create_builtin_model
from pancontext.providers import AnchorLocus, ContextQuery, WindowSpecification
from pancontext.real_data import RealDataExperimentResult, run_provider_experiment


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
MODEL_OPTIONS = [
    ("GC content | development", "gc_content"),
    ("Motif count | development", "motif_count"),
]
REAL_DATA_FIELD_IDS = {
    "real-fasta",
    "real-vcf",
    "real-assembly",
    "real-contig",
    "real-position",
    "real-reference",
    "real-alternate",
    "real-left-flank",
    "real-right-flank",
    "real-samples",
    "real-motif",
}
DEFAULT_LESSON_MANIFEST = Path(".pancontext-data/1000g-lesson/manifest.json")


@dataclass(frozen=True)
class RealDataInputs:
    """Validated strings read from the FASTA/VCF loader workspace."""

    fasta_path: str
    vcf_path: str
    assembly: str
    contig: str
    position: int
    reference: str
    alternate: str
    left_flank: int
    right_flank: int
    samples: Optional[Tuple[str, ...]]
    model: str
    motif: str


@dataclass(frozen=True)
class FormIssue:
    """One actionable FASTA/VCF form problem associated with a widget."""

    widget_id: str
    message: str


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
        ("2", "show_data_loader", "FASTA/VCF"),
        ("3", "show_inspector", "Inspector"),
        ("4", "show_guide", "Guide"),
        Binding("l", "load_lesson", "Lesson", key_display="L"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, *, lesson_manifest: Optional[Path] = None) -> None:
        super().__init__()
        self._current_experiment: Optional[ParsedExperiment] = None
        self._experiment_result: Optional[ExperimentResult] = None
        self._experiment_source = ""
        self._current_real_data: Optional[RealDataInputs] = None
        self._lesson_manifest = lesson_manifest

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="")
        with TabbedContent(initial="experiment-tab", id="main-tabs"):
            with TabPane("Experiment", id="experiment-tab"):
                yield from self._compose_experiment()
            with TabPane("FASTA + VCF", id="real-data-tab"):
                yield from self._compose_real_data()
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
                yield Static(
                    "Run interpretation will appear here.",
                    id="stability-interpretation",
                    classes="result-insight",
                )
                yield Static("PAIRED CONTEXT EFFECTS", classes="section-label")
                yield DataTable(id="experiment-table")
                yield Static("SELECTED CONTEXT", classes="section-label")
                yield Static(
                    "Select a result row to inspect its matched REF and ALT sequences.",
                    id="context-detail",
                )
                yield Static("No skipped contexts.", id="skipped-contexts")

    def _compose_real_data(self) -> ComposeResult:
        with Horizontal(id="real-data-workspace"):
            with VerticalScroll(id="real-data-controls", classes="panel"):
                yield Static("NEW HAPLOTYPE EXPERIMENT", classes="panel-kicker")
                yield Static(
                    "Reconstruct two inherited sequence copies per selected sample, then "
                    "measure the same focal variant in every compatible context.",
                    classes="workspace-intro",
                )
                with Horizontal(classes="button-row preset-row"):
                    yield Button(
                        "Load public lesson",
                        id="load-public-lesson",
                        variant="default",
                    )
                    yield Button("Clear form", id="clear-real-data", variant="default")

                yield Static("1  INDEXED SOURCE FILES", classes="step-label")
                yield Label("Reference FASTA  *", classes="field-label")
                yield Input(
                    id="real-fasta",
                    placeholder="Path to reference.fa; reference.fa.fai must exist",
                )
                yield Static(
                    "Supplies the baseline DNA sequence for the requested interval.",
                    classes="field-help",
                )
                yield Label("Phased VCF or BCF  *", classes="field-label")
                yield Input(
                    id="real-vcf",
                    placeholder="Path to cohort.vcf.gz; .tbi or .csi must exist",
                )
                yield Static(
                    "Supplies sample genotypes and assigns alleles to haplotype 1 or 2.",
                    classes="field-help",
                )
                yield Label("Assembly / source label  *", classes="field-label")
                yield Input(id="real-assembly", placeholder="GRCh38")

                yield Static("2  FOCAL VARIANT", classes="step-label")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-field-wide"):
                        yield Label("Contig  *", classes="field-label")
                        yield Input(id="real-contig", placeholder="Exact name, e.g. 22")
                    with Vertical(classes="form-field"):
                        yield Label("Position  *", classes="field-label")
                        yield Input(
                            id="real-position",
                            placeholder="1-based VCF coordinate",
                            type="integer",
                        )
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-field"):
                        yield Label("REF allele  *", classes="field-label")
                        yield Input(id="real-reference", placeholder="e.g. G")
                    with Vertical(classes="form-field"):
                        yield Label("ALT allele  *", classes="field-label")
                        yield Input(id="real-alternate", placeholder="e.g. T")
                yield Static(
                    "REF must match both the FASTA and the focal VCF record.",
                    classes="field-help",
                )

                yield Static("3  CONTEXT AND SCORER", classes="step-label")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-field"):
                        yield Label("Bases before", classes="field-label")
                        yield Input(id="real-left-flank", value="512", type="integer")
                    with Vertical(classes="form-field"):
                        yield Label("Bases after", classes="field-label")
                        yield Input(id="real-right-flank", value="512", type="integer")
                yield Label("Samples", classes="field-label")
                yield Input(
                    id="real-samples",
                    placeholder="Comma-separated IDs; blank analyzes every VCF sample",
                )
                yield Static(
                    "A diploid sample can contribute at most two contexts.",
                    classes="field-help",
                )
                yield Label("Scorer  *", classes="field-label")
                yield Select(
                    MODEL_OPTIONS,
                    value="gc_content",
                    allow_blank=False,
                    id="real-model",
                )
                yield Label("Motif", classes="field-label", id="real-motif-label")
                yield Input(
                    id="real-motif",
                    placeholder="Required for motif count, e.g. GCGGC",
                )
                yield Static("Required fields are marked with *.", classes="required-note")
                yield Button(
                    "Validate, reconstruct, and analyze",
                    id="run-real-data",
                    variant="primary",
                )

            with Vertical(id="real-data-diagnostics", classes="panel"):
                yield Static("RUN PREVIEW", classes="panel-kicker")
                yield Static(
                    "Complete the required fields to build a run preview.",
                    id="real-data-readiness",
                    classes="readiness incomplete",
                )
                yield Static("WHAT PANCONTEXT WILL DO", classes="section-label")
                yield Static(
                    "1. Fetch one reference window\n"
                    "2. Verify the focal REF allele\n"
                    "3. Project nearby phased variants into each chromosome copy\n"
                    "4. Build matched REF and ALT sequences\n"
                    "5. Compare ALT score minus REF score across contexts",
                    id="real-data-plan",
                    classes="process-card",
                )
                yield Static("RUN STATUS", classes="section-label")
                yield Static(
                    "No run started.",
                    id="real-data-status",
                )
                yield Static("LAST PROVIDER REPORT", classes="section-label")
                yield Static("No provider run yet.", id="real-data-report")
                yield Static(
                    "Scientific guardrails: exact contig names; complete windows; "
                    "diploid phased heterozygous calls; PASS, biallelic, literal ACGTN "
                    "alleles. Unsupported records are reported, never silently guessed.",
                    id="real-data-policy",
                    classes="boundary-note",
                )

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
                "[b]FASTA + VCF[/b]\n"
                "Query indexed files, reconstruct phased local haplotypes, and send them "
                "to the Experiment dashboard. Nearby variants are projected before the "
                "focal REF/ALT counterfactual is scored. The live preview explains how "
                "many contexts and bases the request can produce. Load the public lesson "
                "to explore a real 1000 Genomes locus without typing the form manually.\n\n"
                "[b]Reading results[/b]\n"
                "Each sample has up to two haplotype copies. REF score and ALT score are "
                "computed on matched versions of the same reconstructed copy. Effect is "
                "ALT minus REF; the range tells you how much that effect changes across "
                "the tested sequence backgrounds. Focus the effects table and use the "
                "arrow keys to inspect each copy's sequence change below it.\n\n"
                "[b]Keyboard[/b]\n"
                "1 opens Experiment. 2 opens FASTA + VCF. 3 opens Context Inspector. "
                "4 opens this guide. Ctrl+R reruns the active workflow. D restores the "
                "bundled experiment. L loads the public lesson. Q quits.\n\n"
                "[b]Scientific boundary[/b]\n"
                "Current scorers are development instruments. PanContext loads indexed "
                "linear FASTA/VCF input, but does not yet load GFA/GBZ or execute a "
                "biological foundation model.",
                id="guide-text",
            )

    def on_mount(self) -> None:
        experiment_table = self.query_one("#experiment-table", DataTable)
        experiment_table.add_columns(
            "Sample / context",
            "Copy",
            "Observed",
            "REF score",
            "ALT score",
            "Effect (ALT-REF)",
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
        model_value = self.query_one("#real-model", Select).value
        self.query_one("#real-motif", Input).disabled = model_value != "motif_count"
        self._refresh_real_data_readiness()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "run-experiment":
            self.action_run_experiment_file()
        elif button_id == "load-demo":
            self.action_load_demo()
        elif button_id == "run-real-data":
            self.action_run_real_data()
        elif button_id == "load-public-lesson":
            self.action_load_lesson()
        elif button_id == "clear-real-data":
            self.action_clear_real_data()
        elif button_id == "analyze":
            self._analyze_context()
        elif button_id == "load-example":
            self._load_inspector_example()
            self._analyze_context()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Keep the real-data preview synchronized with typed values."""

        if event.input.id in REAL_DATA_FIELD_IDS:
            self._refresh_real_data_readiness()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Apply scorer-specific form behavior immediately."""

        if event.select.id != "real-model":
            return
        motif_input = self.query_one("#real-motif", Input)
        motif_input.disabled = event.select.value != "motif_count"
        motif_label = self.query_one("#real-motif-label", Label)
        motif_required = event.select.value == "motif_count"
        motif_label.update(
            "Motif  *" if motif_required else "Motif  |  not used by GC content"
        )
        motif_label.set_class(motif_required, "required-field")
        self._refresh_real_data_readiness()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Explain the highlighted paired effect without rerunning analysis."""

        if event.data_table.id == "experiment-table":
            self._render_context_detail(event.cursor_row)

    def action_show_experiment(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "experiment-tab"

    def action_show_inspector(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "inspector-tab"

    def action_show_data_loader(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "real-data-tab"

    def action_show_guide(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "guide-tab"

    def action_clear_real_data(self) -> None:
        """Reset the FASTA/VCF workspace without changing existing results."""

        for widget_id in REAL_DATA_FIELD_IDS:
            field = self.query_one(f"#{widget_id}", Input)
            field.value = ""
        self.query_one("#real-left-flank", Input).value = "512"
        self.query_one("#real-right-flank", Input).value = "512"
        self.query_one("#real-model", Select).value = "gc_content"
        status = self.query_one("#real-data-status", Static)
        status.remove_class("error", "completed", "partial")
        status.update("No run started.")
        self.query_one("#real-data-report", Static).update("No provider run yet.")
        self._refresh_real_data_readiness()
        self.query_one("#real-fasta", Input).focus()

    def action_load_lesson(self) -> None:
        """Populate the form from the locally prepared public lesson manifest."""

        manifest_path = self._find_lesson_manifest()
        status = self.query_one("#real-data-status", Static)
        if manifest_path is None:
            self.action_show_data_loader()
            status.remove_class("completed", "partial")
            status.add_class("error")
            status.update(
                "Public lesson is not prepared. Exit PanContext, run "
                "'make public-lesson', then press L."
            )
            return
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = document["local_files"]
            focal = document["focal_variant"]
            samples = document["samples"]
            assembly = document["assembly"]
            if not isinstance(samples, list) or not all(
                isinstance(sample, str) for sample in samples
            ):
                raise ValueError("samples must be a list of strings")
            values = {
                "real-fasta": files["fasta"],
                "real-vcf": files["vcf"],
                "real-assembly": assembly,
                "real-contig": focal["contig"],
                "real-position": focal["position"],
                "real-reference": focal["reference"],
                "real-alternate": focal["alternate"],
                "real-left-flank": 8,
                "real-right-flank": 8,
                "real-samples": ", ".join(samples),
                "real-motif": "GCGGC",
            }
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self.action_show_data_loader()
            status.remove_class("completed", "partial")
            status.add_class("error")
            status.update(f"Could not load lesson manifest: {error}")
            return
        for widget_id, value in values.items():
            self.query_one(f"#{widget_id}", Input).value = str(value)
        self.query_one("#real-model", Select).value = "motif_count"
        self.action_show_data_loader()
        status.remove_class("error", "completed", "partial")
        status.update(
            "Lesson loaded. Review the preview, then validate, reconstruct, and analyze."
        )
        self._refresh_real_data_readiness()

    def _find_lesson_manifest(self) -> Optional[Path]:
        if self._lesson_manifest is not None:
            return self._lesson_manifest if self._lesson_manifest.is_file() else None
        candidates = (
            Path.cwd() / DEFAULT_LESSON_MANIFEST,
            Path(__file__).resolve().parents[2] / DEFAULT_LESSON_MANIFEST,
        )
        return next((path for path in candidates if path.is_file()), None)

    def action_rerun(self) -> None:
        active = self.query_one("#main-tabs", TabbedContent).active
        if active == "inspector-tab":
            self._analyze_context()
        elif active == "real-data-tab":
            self.action_run_real_data()
        elif self._current_real_data is not None:
            self._execute_real_data(self._current_real_data)
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
        self._current_real_data = None
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
        self._current_real_data = None
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
        self.query_one("#stability-interpretation", Static).update(
            self._stability_interpretation(result)
        )

        table = self.query_one("#experiment-table", DataTable)
        table.clear(columns=False)
        table.add_rows(
            (
                effect.sample_id or effect.context_id,
                effect.haplotype_id or "--",
                effect.observed_allele.value,
                self._format_score(effect.baseline_score),
                self._format_score(effect.alternate_score),
                self._format_score(effect.effect),
            )
            for effect in result.effects
        )
        if result.effects:
            table.move_cursor(row=0, column=0, animate=False)
            self._render_context_detail(0)

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
        self._current_real_data = None
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
        self.query_one("#stability-interpretation", Static).update(
            "No interpretation is available because the experiment did not run."
        )
        self.query_one("#experiment-table", DataTable).clear(columns=False)
        self.query_one("#context-detail", Static).update(
            "No context is available because the experiment did not run."
        )
        self.query_one("#skipped-contexts", Static).update("No experiment results.")

    def _stability_interpretation(self, result: ExperimentResult) -> str:
        stability = result.stability
        if stability is None:
            return "No compatible contexts were available for comparison."
        if stability.effect_range == 0:
            conclusion = (
                "The focal effect is identical across all analyzed contexts for this scorer."
            )
        else:
            conclusion = (
                "The focal effect changes across the analyzed sequence backgrounds for "
                "this scorer."
            )
        directions = (
            f"Direction counts: {stability.positive_count} positive, "
            f"{stability.negative_count} negative, {stability.zero_count} zero."
        )
        return (
            f"[b]Interpretation[/b]  {conclusion}\n{directions} "
            "These are descriptive results for the tested contexts, not a clinical claim."
        )

    def _render_context_detail(self, row: int) -> None:
        result = self._experiment_result
        if result is None or row < 0 or row >= len(result.effects):
            self.query_one("#context-detail", Static).update(
                "Select a result row to inspect its matched REF and ALT sequences."
            )
            return
        self.query_one("#context-detail", Static).update(
            self._context_effect_detail(result.effects[row])
        )

    @classmethod
    def _context_effect_detail(cls, effect: ContextEffect) -> Group:
        sample = effect.sample_id or effect.context_id
        haplotype = effect.haplotype_id or "not specified"
        provenance = Text()
        provenance.append(sample, style="bold #f0f0f1")
        provenance.append(f"  |  copy {haplotype}  |  ")
        provenance.append(effect.source_type.label)
        provenance.append(f"  |  {effect.source_name}")

        locus = Text(
            f"{effect.sequence_id}:{effect.vcf_position}  |  "
            f"observed {effect.observed_allele.value}  |  "
            f"{len(effect.baseline_sequence)} bp REF / "
            f"{len(effect.alternate_sequence)} bp ALT",
            style="#aeb0b4",
        )
        scores = Text("Scores  ", style="bold #aeb0b4")
        scores.append(cls._format_score(effect.baseline_score))
        scores.append(" REF  ->  ")
        scores.append(cls._format_score(effect.alternate_score))
        scores.append(" ALT  |  effect ")
        scores.append(cls._format_score(effect.effect), style="bold #f0f0f1")
        reference, alternate = cls._paired_sequence_preview(effect)
        return Group(provenance, locus, scores, reference, alternate)

    @staticmethod
    def _paired_sequence_preview(effect: ContextEffect) -> Tuple[Text, Text]:
        baseline = effect.baseline_sequence
        alternate = effect.alternate_sequence
        prefix = 0
        shared_limit = min(len(baseline), len(alternate))
        while prefix < shared_limit and baseline[prefix] == alternate[prefix]:
            prefix += 1

        suffix = 0
        baseline_remaining = len(baseline) - prefix
        alternate_remaining = len(alternate) - prefix
        while (
            suffix < baseline_remaining
            and suffix < alternate_remaining
            and baseline[-suffix - 1] == alternate[-suffix - 1]
        ):
            suffix += 1

        baseline_end = len(baseline) - suffix
        alternate_end = len(alternate) - suffix
        flank = 28
        left_start = max(0, prefix - flank)
        baseline_right_end = min(len(baseline), baseline_end + flank)
        alternate_right_end = min(len(alternate), alternate_end + flank)

        def build_line(
            label: str,
            sequence: str,
            change_end: int,
            right_end: int,
            *,
            alternate_style: bool,
        ) -> Text:
            line = Text(f"{label:<5}", style="bold #a7a9ad")
            if left_start:
                line.append("...")
            line.append(sequence[left_start:prefix])
            changed = sequence[prefix:change_end]
            if changed:
                style = (
                    "bold #111214 on #d5d6d8"
                    if alternate_style
                    else "bold #f2f2f2 on #4d4f54"
                )
                line.append(changed, style=style)
            else:
                line.append("-", style="bold #a7a9ad")
            line.append(sequence[change_end:right_end])
            if right_end < len(sequence):
                line.append("...")
            return line

        return (
            build_line(
                "REF",
                baseline,
                baseline_end,
                baseline_right_end,
                alternate_style=False,
            ),
            build_line(
                "ALT",
                alternate,
                alternate_end,
                alternate_right_end,
                alternate_style=True,
            ),
        )

    def action_run_real_data(self) -> None:
        status = self.query_one("#real-data-status", Static)
        try:
            inputs = self._read_real_data_inputs()
        except ValueError as error:
            status.remove_class("completed", "partial")
            status.add_class("error")
            status.update(f"Input failed: {error}")
            self.query_one("#real-data-report", Static).update(
                "No provider run. Correct the source fields."
            )
            issues = self._real_data_form_issues()
            if issues:
                field = self.query_one(f"#{issues[0].widget_id}")
                field.focus()
                field.scroll_visible()
            return
        self._execute_real_data(inputs)

    def _execute_real_data(self, inputs: RealDataInputs) -> None:
        status = self.query_one("#real-data-status", Static)
        try:
            focal = FocalVariant(
                identifier=(
                    f"{inputs.contig}:{inputs.position}:"
                    f"{inputs.reference}:{inputs.alternate}"
                ),
                reference=inputs.reference,
                alternate=inputs.alternate,
            )
            query = ContextQuery(
                focal_variant=focal,
                anchor=AnchorLocus(inputs.assembly, inputs.contig, inputs.position),
                window=WindowSpecification(inputs.left_flank, inputs.right_flank),
            )
            provider = FastaVcfProvider(
                fasta_path=inputs.fasta_path,
                vcf_path=inputs.vcf_path,
                assembly_name=inputs.assembly,
                samples=inputs.samples,
            )
            parameters = {"motif": inputs.motif} if inputs.model == "motif_count" else {}
            model = create_builtin_model(inputs.model, parameters)
            result = run_provider_experiment(
                experiment_id=f"vcf-{focal.identifier}",
                provider=provider,
                query=query,
                model=model,
            )
        except (OSError, ValueError) as error:
            status.remove_class("completed", "partial")
            status.add_class("error")
            status.update(f"Provider failed: {error}")
            self.query_one("#real-data-report", Static).update(
                "No contexts reconstructed. The previous experiment remains unchanged."
            )
            return
        self._current_real_data = inputs
        self._current_experiment = None
        self._experiment_result = result.experiment
        self._render_real_data_result(result)

    def _render_real_data_result(self, result: RealDataExperimentResult) -> None:
        status = self.query_one("#real-data-status", Static)
        status.remove_class("error", "completed", "partial")
        status.add_class(result.status)
        status.update(
            f"{result.status.title()}: {len(result.batch.contexts)} contexts, "
            f"{len(result.batch.issues)} provider issues"
        )
        metadata = result.provider_metadata
        inputs = metadata["inputs"]
        lines = [
            f"Provider: {metadata['provider']} v{metadata['version']}",
            f"Assembly: {metadata['assembly']}",
            (
                f"Query: {result.query.anchor.sequence_id}:"
                f"{result.query.anchor.position} "
                f"{result.query.focal_variant.reference}>"
                f"{result.query.focal_variant.alternate}"
            ),
            (
                f"Window: {result.query.window.left_flank} before + focal allele + "
                f"{result.query.window.right_flank} after"
            ),
            f"Reconstructed: {len(result.batch.contexts)} haplotype contexts",
            f"FASTA: {inputs['fasta']['path']}",
            f"VCF: {inputs['vcf']['path']}",
        ]
        if result.batch.issues:
            lines.append("")
            lines.append("[b]Exclusions[/b]")
            lines.extend(
                f"{issue.code} | {issue.record_id} | {issue.message}"
                for issue in result.batch.issues
            )
        else:
            lines.append("No provider exclusions.")
        self.query_one("#real-data-report", Static).update("\n".join(lines))

        if result.experiment is None:
            return
        source = (
            f"Indexed FASTA/VCF | {result.query.anchor.source_name} | "
            f"{result.query.anchor.sequence_id}:{result.query.anchor.position}"
        )
        self._experiment_source = source
        self._render_experiment(result.experiment, source)
        if result.batch.issues:
            experiment_status = self.query_one("#experiment-status", Static)
            experiment_status.remove_class("completed")
            experiment_status.add_class("partial")
            experiment_status.update(
                f"Partial: {len(result.experiment.effects)} analyzed, "
                f"{len(result.batch.issues)} provider issues"
            )
            self.query_one("#skipped-contexts", Static).update(
                "[b]Provider exclusions[/b]\n"
                + "\n".join(
                    f"{issue.code}: {issue.message}" for issue in result.batch.issues
                )
            )
        self.query_one("#main-tabs", TabbedContent).active = "experiment-tab"

    def _read_real_data_inputs(self) -> RealDataInputs:
        issues = self._real_data_form_issues()
        if issues:
            raise ValueError(issues[0].message)
        samples_value = self.query_one("#real-samples", Input).value
        samples = tuple(
            sample.strip() for sample in samples_value.split(",") if sample.strip()
        )
        model_value = self.query_one("#real-model", Select).value
        if model_value is Select.NULL:
            raise ValueError("development scorer must be selected")
        return RealDataInputs(
            fasta_path=str(
                Path(self.query_one("#real-fasta", Input).value.strip()).expanduser()
            ),
            vcf_path=str(Path(self.query_one("#real-vcf", Input).value.strip()).expanduser()),
            assembly=self.query_one("#real-assembly", Input).value.strip(),
            contig=self.query_one("#real-contig", Input).value.strip(),
            position=int(self.query_one("#real-position", Input).value.strip()),
            reference=self.query_one("#real-reference", Input).value.strip().upper(),
            alternate=self.query_one("#real-alternate", Input).value.strip().upper(),
            left_flank=int(self.query_one("#real-left-flank", Input).value.strip()),
            right_flank=int(self.query_one("#real-right-flank", Input).value.strip()),
            samples=samples or None,
            model=str(model_value),
            motif=self.query_one("#real-motif", Input).value.strip().upper(),
        )

    def _real_data_form_issues(self) -> Tuple[FormIssue, ...]:
        """Return every locally detectable form issue in workflow order."""

        issues = []
        value = lambda widget_id: self.query_one(f"#{widget_id}", Input).value.strip()

        fasta_value = value("real-fasta")
        fasta_path = Path(fasta_value).expanduser()
        if not fasta_value:
            issues.append(FormIssue("real-fasta", "Reference FASTA is required."))
        elif not fasta_path.is_file():
            issues.append(FormIssue("real-fasta", "Reference FASTA file does not exist."))
        elif not Path(f"{fasta_path}.fai").is_file():
            issues.append(
                FormIssue("real-fasta", "FASTA index is missing; expected <FASTA>.fai.")
            )

        vcf_value = value("real-vcf")
        vcf_path = Path(vcf_value).expanduser()
        if not vcf_value:
            issues.append(FormIssue("real-vcf", "Phased VCF or BCF is required."))
        elif not vcf_path.is_file():
            issues.append(FormIssue("real-vcf", "VCF or BCF file does not exist."))
        elif not any(Path(f"{vcf_path}{suffix}").is_file() for suffix in (".tbi", ".csi")):
            issues.append(
                FormIssue("real-vcf", "Variant index is missing; expected .tbi or .csi.")
            )

        for widget_id, label in (
            ("real-assembly", "Assembly / source label"),
            ("real-contig", "Contig"),
        ):
            if not value(widget_id):
                issues.append(FormIssue(widget_id, f"{label} is required."))

        position = self._validate_integer_field(
            widget_id="real-position",
            label="Position",
            minimum=1,
        )
        if position is not None:
            issues.append(position)
        reference = value("real-reference").upper()
        alternate = value("real-alternate").upper()
        for widget_id, label, allele in (
            ("real-reference", "REF allele", reference),
            ("real-alternate", "ALT allele", alternate),
        ):
            if not allele:
                issues.append(FormIssue(widget_id, f"{label} is required."))
            elif not set(allele) <= set("ACGTN"):
                issues.append(
                    FormIssue(widget_id, f"{label} must contain only A, C, G, T, or N.")
                )
        if reference and alternate and reference == alternate:
            issues.append(FormIssue("real-alternate", "ALT must differ from REF."))

        left_flank = self._validate_integer_field(
            widget_id="real-left-flank",
            label="Bases before",
            minimum=0,
        )
        right_flank = self._validate_integer_field(
            widget_id="real-right-flank",
            label="Bases after",
            minimum=0,
        )
        issues.extend(issue for issue in (left_flank, right_flank) if issue)

        samples = [
            sample.strip() for sample in value("real-samples").split(",") if sample.strip()
        ]
        if len(samples) != len(set(samples)):
            issues.append(FormIssue("real-samples", "Sample IDs must be unique."))

        model_value = self.query_one("#real-model", Select).value
        if model_value is Select.NULL:
            issues.append(FormIssue("real-model", "A scorer must be selected."))
        elif model_value == "motif_count":
            motif = value("real-motif").upper()
            if not motif:
                issues.append(
                    FormIssue("real-motif", "Motif is required for the motif-count scorer.")
                )
            elif not set(motif) <= set("ACGTN"):
                issues.append(
                    FormIssue("real-motif", "Motif must contain only A, C, G, T, or N.")
                )
        return tuple(issues)

    def _validate_integer_field(
        self,
        *,
        widget_id: str,
        label: str,
        minimum: int,
    ) -> Optional[FormIssue]:
        raw = self.query_one(f"#{widget_id}", Input).value.strip()
        if not raw:
            return FormIssue(widget_id, f"{label} is required.")
        try:
            parsed = int(raw)
        except ValueError:
            return FormIssue(widget_id, f"{label} must be a whole number.")
        if parsed < minimum:
            return FormIssue(widget_id, f"{label} must be at least {minimum}.")
        return None

    def _refresh_real_data_readiness(self) -> None:
        """Render validation state and the expected biological work unit."""

        readiness = self.query_one("#real-data-readiness", Static)
        issues = self._real_data_form_issues()
        invalid_ids = {issue.widget_id for issue in issues}
        for widget_id in REAL_DATA_FIELD_IDS:
            self.query_one(f"#{widget_id}", Input).set_class(
                widget_id in invalid_ids,
                "invalid",
            )
        readiness.remove_class("ready", "incomplete")
        if issues:
            readiness.add_class("incomplete")
            visible = issues[:4]
            lines = [f"[b]Form incomplete[/b]  {len(issues)} item(s) need attention."]
            lines.extend(f"- {issue.message}" for issue in visible)
            if len(issues) > len(visible):
                lines.append(f"- Plus {len(issues) - len(visible)} more below.")
            readiness.update("\n".join(lines))
            return

        inputs = self._read_real_data_inputs()
        sequence_length = inputs.left_flank + len(inputs.reference) + inputs.right_flank
        if inputs.samples is None:
            cohort = "all VCF samples; up to two contexts per sample"
        else:
            context_count = len(inputs.samples) * 2
            cohort = f"{len(inputs.samples)} samples; up to {context_count} contexts"
        scorer = "GC fraction" if inputs.model == "gc_content" else f"motif {inputs.motif!r}"
        readiness.add_class("ready")
        readiness.update(
            "[b]Ready to run[/b]\n"
            f"{inputs.assembly}  |  {inputs.contig}:{inputs.position}  |  "
            f"{inputs.reference}>{inputs.alternate}\n"
            f"{sequence_length} reference-coordinate bases  |  {cohort}\n"
            f"Scorer: {scorer}  |  Effect: ALT score - REF score"
        )

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
            source_name=self._required_inspector_text("source-name", "Source name"),
            sequence_id=self._required_inspector_text(
                "sequence-id",
                "Sequence identifier",
            ),
            window_start=self._inspector_integer("window-start", "Window start", minimum=0),
            sequence=self._required_inspector_text("sequence", "Sequence context window"),
            vcf_position=self._inspector_integer(
                "vcf-position",
                "Variant position",
                minimum=1,
            ),
            reference=self._required_inspector_text("reference", "REF allele"),
            alternate=self._required_inspector_text("alternate", "ALT allele"),
        )

    def _required_inspector_text(self, widget_id: str, label: str) -> str:
        value = self.query_one(f"#{widget_id}", Input).value.strip()
        if not value:
            raise ValueError(f"{label} is required")
        return value

    def _inspector_integer(self, widget_id: str, label: str, *, minimum: int) -> int:
        value = self.query_one(f"#{widget_id}", Input).value.strip()
        if not value:
            raise ValueError(f"{label} is required")
        try:
            parsed = int(value)
        except ValueError as error:
            raise ValueError(f"{label} must be a whole number") from error
        if parsed < minimum:
            raise ValueError(f"{label} must be at least {minimum}")
        return parsed

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
