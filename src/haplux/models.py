"""Model adapter contracts and deterministic development scorers."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Protocol, runtime_checkable

from haplux.domain import HaplotypeWindow, SequenceValidationError


class ModelValidationError(ValueError):
    """Raised when a model specification or input is invalid."""


def _validated_sequence(sequence: str) -> str:
    return HaplotypeWindow(
        sequence_id="model-input",
        start=0,
        sequence=sequence,
    ).sequence


@runtime_checkable
class ScalarModelAdapter(Protocol):
    """Minimal contract for models returning one scalar per sequence."""

    model_id: str
    version: str
    output_name: str

    def predict(self, sequence: str) -> float:
        """Return one deterministic scalar prediction for a DNA sequence."""

    def metadata(self) -> Dict[str, Any]:
        """Return JSON-serializable model identity and parameters."""


@dataclass(frozen=True)
class GCContentModel:
    """Development scorer returning the fraction of G/C bases in a sequence."""

    model_id: str = "gc_content"
    version: str = "1"
    output_name: str = "gc_fraction"

    def predict(self, sequence: str) -> float:
        normalized = _validated_sequence(sequence)
        return (normalized.count("G") + normalized.count("C")) / len(normalized)

    def metadata(self) -> Dict[str, Any]:
        return {
            "adapter": self.model_id,
            "version": self.version,
            "output": self.output_name,
            "parameters": {},
            "scientific_use": "development-only",
        }


@dataclass(frozen=True)
class MotifCountModel:
    """Development scorer counting overlapping occurrences of one DNA motif."""

    motif: str
    model_id: str = "motif_count"
    version: str = "1"
    output_name: str = "overlapping_motif_count"

    def __post_init__(self) -> None:
        try:
            motif = _validated_sequence(self.motif)
        except SequenceValidationError as error:
            raise ModelValidationError(f"invalid motif: {error}") from error
        object.__setattr__(self, "motif", motif)

    def predict(self, sequence: str) -> float:
        normalized = _validated_sequence(sequence)
        last_start = len(normalized) - len(self.motif)
        if last_start < 0:
            return 0.0
        return float(
            sum(
                normalized.startswith(self.motif, index)
                for index in range(last_start + 1)
            )
        )

    def metadata(self) -> Dict[str, Any]:
        return {
            "adapter": self.model_id,
            "version": self.version,
            "output": self.output_name,
            "parameters": {"motif": self.motif},
            "scientific_use": "development-only",
        }


def create_builtin_model(
    adapter: str,
    parameters: Mapping[str, Any],
) -> ScalarModelAdapter:
    """Construct a deterministic built-in adapter from a serialized specification."""

    if adapter == "gc_content":
        if parameters:
            raise ModelValidationError("gc_content does not accept parameters")
        return GCContentModel()
    if adapter == "motif_count":
        motif = parameters.get("motif")
        if not isinstance(motif, str):
            raise ModelValidationError("motif_count requires string parameter 'motif'")
        unexpected = sorted(set(parameters) - {"motif"})
        if unexpected:
            raise ModelValidationError(
                "motif_count received unexpected parameter(s): " + ", ".join(unexpected)
            )
        return MotifCountModel(motif=motif)
    raise ModelValidationError(f"unknown built-in model adapter: {adapter!r}")
