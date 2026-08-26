"""Command-line routing for interactive and headless Haplux workflows."""

import argparse
import json
import sys
from typing import List, Optional, Sequence

from haplux.analysis import (
    AnalysisRequest,
    ObservedAllele,
    SCHEMA_VERSION,
    analyze_variant,
)
from haplux.context import ContextSource
from haplux.experiment import EXPERIMENT_SCHEMA_VERSION, FocalVariant, run_experiment
from haplux.experiment_io import load_experiment_file, parse_experiment_document
from haplux.fasta_vcf import FastaVcfProvider
from haplux.models import create_builtin_model
from haplux.providers import AnchorLocus, ContextQuery, WindowSpecification
from haplux.real_data import REAL_DATA_SCHEMA_VERSION, run_provider_experiment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="haplux",
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
    vcf_experiment = subparsers.add_parser(
        "vcf-experiment",
        help="reconstruct phased haplotypes from indexed FASTA/VCF and run an experiment",
    )
    vcf_experiment.add_argument("--fasta", required=True, help="indexed FASTA path")
    vcf_experiment.add_argument("--vcf", required=True, help="indexed VCF/BCF path")
    vcf_experiment.add_argument("--assembly", required=True, help="assembly/source name")
    vcf_experiment.add_argument("--contig", required=True)
    vcf_experiment.add_argument("--position", required=True, type=int)
    vcf_experiment.add_argument("--ref", required=True, dest="reference")
    vcf_experiment.add_argument("--alt", required=True, dest="alternate")
    vcf_experiment.add_argument("--variant-id")
    vcf_experiment.add_argument("--experiment-id")
    vcf_experiment.add_argument("--left-flank", type=int, default=512)
    vcf_experiment.add_argument("--right-flank", type=int, default=512)
    vcf_experiment.add_argument(
        "--sample",
        action="append",
        dest="samples",
        help="sample to include; repeat for multiple samples (default: all)",
    )
    vcf_experiment.add_argument(
        "--model",
        choices=("gc_content", "motif_count"),
        default="gc_content",
        help="deterministic development scorer",
    )
    vcf_experiment.add_argument("--motif", help="required by motif_count")
    vcf_experiment.add_argument("--zero-tolerance", type=float, default=0.0)
    vcf_experiment.add_argument(
        "--allow-filtered",
        action="store_true",
        help="include records regardless of FILTER status",
    )
    vcf_experiment.add_argument(
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


def _run_vcf_experiment_headless(arguments: argparse.Namespace) -> int:
    variant_id = arguments.variant_id or (
        f"{arguments.contig}:{arguments.position}:"
        f"{arguments.reference}:{arguments.alternate}"
    )
    experiment_id = arguments.experiment_id or f"vcf-{variant_id}"
    try:
        focal = FocalVariant(
            identifier=variant_id,
            reference=arguments.reference,
            alternate=arguments.alternate,
        )
        query = ContextQuery(
            focal_variant=focal,
            anchor=AnchorLocus(
                source_name=arguments.assembly,
                sequence_id=arguments.contig,
                position=arguments.position,
            ),
            window=WindowSpecification(
                left_flank=arguments.left_flank,
                right_flank=arguments.right_flank,
            ),
        )
        provider = FastaVcfProvider(
            fasta_path=arguments.fasta,
            vcf_path=arguments.vcf,
            assembly_name=arguments.assembly,
            samples=arguments.samples,
            require_pass=not arguments.allow_filtered,
        )
        parameters = {"motif": arguments.motif} if arguments.model == "motif_count" else {}
        model = create_builtin_model(arguments.model, parameters)
        result = run_provider_experiment(
            experiment_id=experiment_id,
            provider=provider,
            query=query,
            model=model,
            zero_tolerance=arguments.zero_tolerance,
        )
    except (OSError, ValueError) as error:
        report = {
            "schema_version": REAL_DATA_SCHEMA_VERSION,
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
        from haplux.tui import run

        run()
        return 0

    parsed = _parser().parse_args(arguments)
    if parsed.command == "analyze":
        return _run_headless(parsed)
    if parsed.command == "experiment":
        return _run_experiment_headless(parsed)
    if parsed.command == "vcf-experiment":
        return _run_vcf_experiment_headless(parsed)
    raise AssertionError(f"unhandled command: {parsed.command}")
