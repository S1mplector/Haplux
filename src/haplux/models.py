"""Model adapter contracts, input policies, and deterministic development scorers."""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable

from haplux.domain import HaplotypeWindow, SequenceValidationError


class ModelValidationError(ValueError):
    """Raised when a model specification or input is invalid."""


def _validated_sequence(sequence: str) -> str:
    return HaplotypeWindow(
        sequence_id="model-input",
        start=0,
        sequence=sequence,
    ).sequence


@dataclass(frozen=True)
class ModelInputProjection:
    """The concrete sequence handed to a model after applying input policy."""

    sequence: str
    original_length: int
    focal_offset: int
    policy_id: str
    target_length: int
    anchor_index: int
    source_start: int
    source_end: int
    left_padding: int = 0
    right_padding: int = 0

    def __post_init__(self) -> None:
        normalized = _validated_sequence(self.sequence)
        if self.original_length < 1:
            raise ModelValidationError("original model-input length must be positive")
        if not 0 <= self.focal_offset < self.original_length:
            raise ModelValidationError("focal offset must point inside the original sequence")
        if self.target_length != len(normalized):
            raise ModelValidationError("target length must match projected model sequence")
        if not 0 <= self.anchor_index < self.target_length:
            raise ModelValidationError("anchor index must point inside the projected sequence")
        if self.source_start < 0 or self.source_end < self.source_start:
            raise ModelValidationError("source interval must be ordered and non-negative")
        if self.left_padding < 0 or self.right_padding < 0:
            raise ModelValidationError("padding counts must be non-negative")
        object.__setattr__(self, "sequence", normalized)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy_id,
            "original_length": self.original_length,
            "target_length": self.target_length,
            "focal_offset": self.focal_offset,
            "anchor_index": self.anchor_index,
            "source_interval": {
                "start": self.source_start,
                "end": self.source_end,
                "coordinate_system": "0-based-half-open-sequence-offset",
            },
            "padding": {
                "left": self.left_padding,
                "right": self.right_padding,
            },
        }


@runtime_checkable
class ModelInputPolicy(Protocol):
    """Project a constructed REF/ALT sequence into the exact model input."""

    policy_id: str
    version: str

    def prepare(self, sequence: str, *, focal_offset: int) -> ModelInputProjection:
        """Return the sequence that should be passed to a model."""

    def metadata(self) -> Dict[str, Any]:
        """Return JSON-serializable policy identity and parameters."""


@dataclass(frozen=True)
class FullSequencePolicy:
    """Use the complete constructed sequence as the model input."""

    policy_id: str = "full_sequence"
    version: str = "1"

    def prepare(self, sequence: str, *, focal_offset: int) -> ModelInputProjection:
        normalized = _validated_sequence(sequence)
        return ModelInputProjection(
            sequence=normalized,
            original_length=len(normalized),
            focal_offset=focal_offset,
            policy_id=self.policy_id,
            target_length=len(normalized),
            anchor_index=focal_offset,
            source_start=0,
            source_end=len(normalized),
        )

    def metadata(self) -> Dict[str, Any]:
        return {
            "policy": self.policy_id,
            "version": self.version,
            "parameters": {},
        }


@dataclass(frozen=True)
class FixedLengthCenteredPolicy:
    """Trim or pad a sequence so the focal anchor lands at a fixed index."""

    target_length: int
    anchor_index: Optional[int] = None
    pad_symbol: str = "N"
    policy_id: str = "fixed_length_centered"
    version: str = "1"

    def __post_init__(self) -> None:
        if self.target_length < 1:
            raise ModelValidationError("target length must be positive")
        anchor = self.target_length // 2 if self.anchor_index is None else self.anchor_index
        if not 0 <= anchor < self.target_length:
            raise ModelValidationError("anchor index must point inside target length")
        pad_symbol = self.pad_symbol.upper()
        if len(pad_symbol) != 1:
            raise ModelValidationError("pad symbol must be one DNA base")
        try:
            _validated_sequence(pad_symbol)
        except SequenceValidationError as error:
            raise ModelValidationError(f"invalid pad symbol: {error}") from error
        object.__setattr__(self, "anchor_index", anchor)
        object.__setattr__(self, "pad_symbol", pad_symbol)

    def prepare(self, sequence: str, *, focal_offset: int) -> ModelInputProjection:
        normalized = _validated_sequence(sequence)
        if not 0 <= focal_offset < len(normalized):
            raise ModelValidationError("focal offset must point inside the original sequence")

        raw_start = focal_offset - int(self.anchor_index)
        raw_end = raw_start + self.target_length
        source_start = max(0, raw_start)
        source_end = min(len(normalized), raw_end)
        left_padding = max(0, -raw_start)
        right_padding = max(0, raw_end - len(normalized))
        projected = (
            self.pad_symbol * left_padding
            + normalized[source_start:source_end]
            + self.pad_symbol * right_padding
        )
        return ModelInputProjection(
            sequence=projected,
            original_length=len(normalized),
            focal_offset=focal_offset,
            policy_id=self.policy_id,
            target_length=self.target_length,
            anchor_index=int(self.anchor_index),
            source_start=source_start,
            source_end=source_end,
            left_padding=left_padding,
            right_padding=right_padding,
        )

    def metadata(self) -> Dict[str, Any]:
        return {
            "policy": self.policy_id,
            "version": self.version,
            "parameters": {
                "target_length": self.target_length,
                "anchor_index": self.anchor_index,
                "pad_symbol": self.pad_symbol,
            },
        }


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

    input_policy: ModelInputPolicy = field(default_factory=FullSequencePolicy)
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
            "input_policy": self.input_policy.metadata(),
            "parameters": {},
            "scientific_use": "development-only",
        }


@dataclass(frozen=True)
class MotifCountModel:
    """Development scorer counting overlapping occurrences of one DNA motif."""

    motif: str
    input_policy: ModelInputPolicy = field(default_factory=FullSequencePolicy)
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
            "input_policy": self.input_policy.metadata(),
            "parameters": {"motif": self.motif},
            "scientific_use": "development-only",
        }


def create_input_policy(
    kind: str,
    parameters: Mapping[str, Any],
) -> ModelInputPolicy:
    """Construct a model-input policy from a serialized specification."""

    if kind == "full_sequence":
        if parameters:
            raise ModelValidationError("full_sequence does not accept parameters")
        return FullSequencePolicy()
    if kind == "fixed_length_centered":
        target_length = parameters.get("target_length")
        if isinstance(target_length, bool) or not isinstance(target_length, int):
            raise ModelValidationError(
                "fixed_length_centered requires integer parameter 'target_length'"
            )
        anchor_index = parameters.get("anchor_index")
        if anchor_index is not None and (
            isinstance(anchor_index, bool) or not isinstance(anchor_index, int)
        ):
            raise ModelValidationError(
                "fixed_length_centered parameter 'anchor_index' must be an integer"
            )
        pad_symbol = parameters.get("pad_symbol", "N")
        if not isinstance(pad_symbol, str):
            raise ModelValidationError(
                "fixed_length_centered parameter 'pad_symbol' must be a string"
            )
        unexpected = sorted(
            set(parameters) - {"target_length", "anchor_index", "pad_symbol"}
        )
        if unexpected:
            raise ModelValidationError(
                "fixed_length_centered received unexpected parameter(s): "
                + ", ".join(unexpected)
            )
        return FixedLengthCenteredPolicy(
            target_length=target_length,
            anchor_index=anchor_index,
            pad_symbol=pad_symbol,
        )
    raise ModelValidationError(f"unknown model input policy: {kind!r}")


def model_input_policy(model: ScalarModelAdapter) -> ModelInputPolicy:
    """Return an adapter's declared input policy or the legacy full-sequence default."""

    policy = getattr(model, "input_policy", None)
    if policy is None:
        return FullSequencePolicy()
    if not isinstance(policy, ModelInputPolicy):
        raise ModelValidationError("model input_policy must implement ModelInputPolicy")
    return policy


def create_builtin_model(
    adapter: str,
    parameters: Mapping[str, Any],
    *,
    input_policy: Optional[ModelInputPolicy] = None,
) -> ScalarModelAdapter:
    """Construct a deterministic built-in adapter from a serialized specification."""

    policy = FullSequencePolicy() if input_policy is None else input_policy
    if adapter == "gc_content":
        if parameters:
            raise ModelValidationError("gc_content does not accept parameters")
        return GCContentModel(input_policy=policy)
    if adapter == "motif_count":
        motif = parameters.get("motif")
        if not isinstance(motif, str):
            raise ModelValidationError("motif_count requires string parameter 'motif'")
        unexpected = sorted(set(parameters) - {"motif"})
        if unexpected:
            raise ModelValidationError(
                "motif_count received unexpected parameter(s): " + ", ".join(unexpected)
            )
        return MotifCountModel(motif=motif, input_policy=policy)
    raise ModelValidationError(f"unknown built-in model adapter: {adapter!r}")
