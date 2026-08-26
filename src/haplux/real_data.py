"""Application service joining context providers to experiment execution."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from haplux.experiment import ExperimentRequest, ExperimentResult, run_experiment
from haplux.models import ScalarModelAdapter
from haplux.providers import ContextProvider, ContextQuery, ProviderBatch


REAL_DATA_SCHEMA_VERSION = "haplux.real-data-experiment.v1"


@dataclass(frozen=True)
class RealDataExperimentResult:
    """Provider diagnostics and an optional experiment result in one report."""

    experiment_id: str
    query: ContextQuery
    provider_metadata: Dict[str, Any]
    batch: ProviderBatch
    experiment: Optional[ExperimentResult]

    @property
    def status(self) -> str:
        if self.experiment is None or self.experiment.status == "failed":
            return "failed"
        if self.batch.issues or self.experiment.status == "partial":
            return "partial"
        return "completed"

    def as_dict(self) -> Dict[str, Any]:
        focal = self.query.focal_variant
        anchor = self.query.anchor
        return {
            "schema_version": REAL_DATA_SCHEMA_VERSION,
            "status": self.status,
            "experiment_id": self.experiment_id,
            "query": {
                "focal_variant": {
                    "identifier": focal.identifier,
                    "reference": focal.reference,
                    "alternate": focal.alternate,
                },
                "anchor": {
                    "source_name": anchor.source_name,
                    "sequence_id": anchor.sequence_id,
                    "position": anchor.position,
                    "coordinate_system": "1-based-VCF-style",
                },
                "window": {
                    "left_flank": self.query.window.left_flank,
                    "right_flank": self.query.window.right_flank,
                    "boundary_policy": "complete-window-required",
                },
            },
            "provider": {
                "metadata": self.provider_metadata,
                **self.batch.as_dict(),
            },
            "experiment": None if self.experiment is None else self.experiment.as_dict(),
        }


def run_provider_experiment(
    *,
    experiment_id: str,
    provider: ContextProvider,
    query: ContextQuery,
    model: ScalarModelAdapter,
    zero_tolerance: float = 0.0,
) -> RealDataExperimentResult:
    """Load contexts and, when possible, run the shared experiment engine."""

    batch = provider.load(query)
    experiment = None
    if batch.contexts:
        experiment = run_experiment(
            ExperimentRequest(
                experiment_id=experiment_id,
                focal_variant=query.focal_variant,
                contexts=batch.contexts,
                zero_tolerance=zero_tolerance,
            ),
            model,
        )
    return RealDataExperimentResult(
        experiment_id=experiment_id,
        query=query,
        provider_metadata=provider.metadata(),
        batch=batch,
        experiment=experiment,
    )
