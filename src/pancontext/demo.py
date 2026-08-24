"""Bundled deterministic documents used by the TUI and documentation."""

from typing import Any, Dict


def experiment_demo_document() -> Dict[str, Any]:
    """Return a fresh three-context experiment request for interactive exploration."""

    return {
        "schema_version": "pancontext.experiment-request.v1",
        "experiment": {
            "experiment_id": "three-haplotype-demo",
            "focal_variant": {
                "identifier": "example:C:T",
                "reference": "C",
                "alternate": "T",
            },
            "zero_tolerance": 0.0,
            "contexts": [
                {
                    "context_id": "HG001-1",
                    "source_type": "pangenome_path",
                    "source_name": "synthetic-demo",
                    "sequence_id": "path-HG001-1",
                    "window_start": 100,
                    "sequence": "AACCGG",
                    "vcf_position": 103,
                    "observed_allele": "reference",
                    "sample_id": "HG001",
                    "haplotype_id": "1",
                },
                {
                    "context_id": "HG002-2",
                    "source_type": "pangenome_path",
                    "source_name": "synthetic-demo",
                    "sequence_id": "path-HG002-2",
                    "window_start": 100,
                    "sequence": "GGAATCGG",
                    "vcf_position": 105,
                    "observed_allele": "alternate",
                    "sample_id": "HG002",
                    "haplotype_id": "2",
                },
                {
                    "context_id": "HG003-1",
                    "source_type": "de_novo_assembly",
                    "source_name": "synthetic-demo-assembly",
                    "sequence_id": "contig-42",
                    "window_start": 500,
                    "sequence": "TTCCAAGGTT",
                    "vcf_position": 503,
                    "observed_allele": "reference",
                    "sample_id": "HG003",
                    "haplotype_id": "1",
                },
            ],
        },
        "model": {
            "adapter": "gc_content",
            "parameters": {},
        },
    }
