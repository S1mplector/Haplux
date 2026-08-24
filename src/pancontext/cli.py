"""Command-line routing for interactive and headless PanContext workflows."""

import argparse
import json
import sys
from typing import List, Optional, Sequence

from pancontext.analysis import (
    AnalysisRequest,
    ObservedAllele,
    SCHEMA_VERSION,
    analyze_variant,
)
from pancontext.context import ContextSource
from pancontext.experiment import EXPERIMENT_SCHEMA_VERSION, run_experiment
from pancontext.experiment_io import load_experiment_file, parse_experiment_document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pancontext",
        description="Audit genomic variant contexts interactively or headlessly.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser(
        "analyze",
        help="validate one context and write a machine-readable result",
    )
    analyze.add_argument(
        "--source-type",
        choices=[source.value for source in ContextSource],
        required=True,
    )
    analyze.add_argument("--source-name", required=True)
    analyze.add_argument("--sequence-id", required=True)
    analyze.add_argument("--window-start", type=int, required=True)
    analyze.add_argument("--sequence", required=True)
    analyze.add_argument("--position", type=int, required=True, dest="vcf_position")
    analyze.add_argument("--ref", required=True, dest="reference")
    analyze.add_argument("--alt", required=True, dest="alternate")
    analyze.add_argument(
        "--observed-allele",
        choices=[allele.value for allele in ObservedAllele],
        default=ObservedAllele.REFERENCE.value,
    )
    analyze.add_argument("--sample-id")
    analyze.add_argument("--haplotype-id")
    analyze.add_argument(
        "--pretty",
        action="store_true",
        help="indent JSON output for human inspection",
    )
    experiment = subparsers.add_parser(
        "experiment",
        help="run a versioned multi-context experiment document",
    )
    experiment.add_argument(
        "--input",
        required=True,
        help="JSON request path, or - to read standard input",
    )
    experiment.add_argument(
        "--pretty",
        action="store_true",
        help="indent JSON output for human inspection",
    )
    return parser


def _request_from_args(arguments: argparse.Namespace) -> AnalysisRequest:
    return AnalysisRequest(
        source_type=ContextSource(arguments.source_type),
        source_name=arguments.source_name,
        sequence_id=arguments.sequence_id,
        window_start=arguments.window_start,
        sequence=arguments.sequence,
        vcf_position=arguments.vcf_position,
        reference=arguments.reference,
        alternate=arguments.alternate,
        observed_allele=ObservedAllele(arguments.observed_allele),
        sample_id=arguments.sample_id,
        haplotype_id=arguments.haplotype_id,
    )


def _run_headless(arguments: argparse.Namespace) -> int:
    try:
        result = analyze_variant(_request_from_args(arguments))
    except ValueError as error:
        report = {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 2

    indent = 2 if arguments.pretty else None
    print(json.dumps(result.as_dict(), indent=indent, sort_keys=True))
    return 0


def _load_stdin_document() -> object:
    """Read one JSON experiment document from standard input."""

    return json.load(sys.stdin)


def _run_experiment_headless(arguments: argparse.Namespace) -> int:
    try:
        if arguments.input == "-":
            parsed = parse_experiment_document(_load_stdin_document())
        else:
            parsed = load_experiment_file(arguments.input)
        result = run_experiment(parsed.request, parsed.model)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        report = {
            "schema_version": EXPERIMENT_SCHEMA_VERSION,
            "status": "error",
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 2

    indent = 2 if arguments.pretty else None
    output = json.dumps(result.as_dict(), indent=indent, sort_keys=True)
    if result.status == "failed":
        print(output, file=sys.stderr)
        return 2
    print(output)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the TUI by default or dispatch an explicit headless subcommand."""

    arguments: List[str] = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        from pancontext.tui import run

        run()
        return 0

    parsed = _parser().parse_args(arguments)
    if parsed.command == "analyze":
        return _run_headless(parsed)
    if parsed.command == "experiment":
        return _run_experiment_headless(parsed)
    raise AssertionError(f"unhandled command: {parsed.command}")
