"""Multi-context model-effect experiments and descriptive stability metrics."""

from dataclasses import dataclass
from math import isfinite
from statistics import fmean, pstdev
from typing import Any, Dict, Optional, Tuple

from pancontext.analysis import AnalysisRequest, ObservedAllele, analyze_variant
from pancontext.context import ContextSource
from pancontext.domain import SequenceValidationError, Variant
from pancontext.models import ModelValidationError, ScalarModelAdapter


EXPERIMENT_SCHEMA_VERSION = "pancontext.experiment.v1"


class ExperimentValidationError(ValueError):
    """Raised when an experiment definition is structurally invalid."""


def _required_label(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ExperimentValidationError(f"{field_name} must not be blank")
    return normalized


@dataclass(frozen=True)
class FocalVariant:
    """Sequence-level focal alleles projected independently into each context."""

    identifier: str
    reference: str
    alternate: str

    def __post_init__(self) -> None:
        identifier = _required_label(self.identifier, field_name="focal variant identifier")
        try:
            normalized = Variant(
                sequence_id="focal-alleles",
                start=0,
                reference=self.reference,
                alternate=self.alternate,
            )
        except SequenceValidationError as error:
            raise ExperimentValidationError(str(error)) from error
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "reference", normalized.reference)
        object.__setattr__(self, "alternate", normalized.alternate)


@dataclass(frozen=True)
class ExperimentContext:
    """One projected haplotype window participating in an experiment."""

    context_id: str
    source_type: ContextSource
    source_name: str
    sequence_id: str
    window_start: int
    sequence: str
    vcf_position: int
    observed_allele: ObservedAllele
    sample_id: Optional[str] = None
    haplotype_id: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "context_id",
            _required_label(self.context_id, field_name="context ID"),
        )
        object.__setattr__(self, "source_type", ContextSource(self.source_type))
        object.__setattr__(self, "observed_allele", ObservedAllele(self.observed_allele))


@dataclass(frozen=True)
class ExperimentRequest:
    """A focal variant and its projected sequence contexts."""

    experiment_id: str
    focal_variant: FocalVariant
    contexts: Tuple[ExperimentContext, ...]
    zero_tolerance: float = 0.0

    def __post_init__(self) -> None:
        experiment_id = _required_label(self.experiment_id, field_name="experiment ID")
        contexts = tuple(self.contexts)
        if not contexts:
            raise ExperimentValidationError("experiment requires at least one context")
        context_ids = [context.context_id for context in contexts]
        if len(set(context_ids)) != len(context_ids):
            raise ExperimentValidationError("context IDs must be unique within an experiment")
        if self.zero_tolerance < 0:
            raise ExperimentValidationError("zero tolerance must be non-negative")
        object.__setattr__(self, "experiment_id", experiment_id)
        object.__setattr__(self, "contexts", contexts)


@dataclass(frozen=True)
class ContextEffect:
    """Paired model predictions for one successfully constructed context."""

    context_id: str
    source_type: ContextSource
    source_name: str
    sample_id: Optional[str]
    haplotype_id: Optional[str]
    observed_allele: ObservedAllele
    sequence_id: str
    vcf_position: int
    baseline_sequence: str
    alternate_sequence: str
    baseline_content_id: str
    alternate_content_id: str
    baseline_construction: str
    alternate_construction: str
    baseline_score: float
    alternate_score: float

    @property
    def effect(self) -> float:
        """Return the paired alternate-minus-baseline model effect."""

        return self.alternate_score - self.baseline_score

    def as_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "source": {
                "type": self.source_type.value,
                "name": self.source_name,
                "sample_id": self.sample_id,
                "haplotype_id": self.haplotype_id,
            },
            "projection": {
                "sequence_id": self.sequence_id,
                "position": self.vcf_position,
                "coordinate_system": "1-based-VCF-style",
                "observed_allele": self.observed_allele.value,
            },
            "model_inputs": {
                "baseline": {
                    "sequence": self.baseline_sequence,
                    "content_id": self.baseline_content_id,
                    "construction": self.baseline_construction,
                    "score": self.baseline_score,
                },
                "alternate": {
                    "sequence": self.alternate_sequence,
                    "content_id": self.alternate_content_id,
                    "construction": self.alternate_construction,
                    "score": self.alternate_score,
                },
            },
            "effect": self.effect,
        }


@dataclass(frozen=True)
class SkippedContext:
    """One context excluded without terminating the remaining experiment."""

    context_id: str
    stage: str
    error_type: str
    reason: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "context_id": self.context_id,
            "stage": self.stage,
            "error_type": self.error_type,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class StabilitySummary:
    """Descriptive statistics across paired context effects."""

    context_count: int
    mean_effect: float
    minimum_effect: float
    maximum_effect: float
    effect_range: float
    population_standard_deviation: float
    positive_count: int
    negative_count: int
    zero_count: int
    sign_agreement: float
    sign_consistent: bool
    zero_tolerance: float

    @classmethod
    def from_effects(
        cls,
        effects: Tuple[float, ...],
        *,
        zero_tolerance: float,
    ) -> "StabilitySummary":
        if not effects:
            raise ExperimentValidationError("stability requires at least one effect")
        positive = sum(effect > zero_tolerance for effect in effects)
        negative = sum(effect < -zero_tolerance for effect in effects)
        zero = len(effects) - positive - negative
        return cls(
            context_count=len(effects),
            mean_effect=fmean(effects),
            minimum_effect=min(effects),
            maximum_effect=max(effects),
            effect_range=max(effects) - min(effects),
            population_standard_deviation=pstdev(effects),
            positive_count=positive,
            negative_count=negative,
            zero_count=zero,
            sign_agreement=max(positive, negative, zero) / len(effects),
            sign_consistent=positive == 0 or negative == 0,
            zero_tolerance=zero_tolerance,
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "context_count": self.context_count,
            "mean_effect": self.mean_effect,
            "minimum_effect": self.minimum_effect,
            "maximum_effect": self.maximum_effect,
            "effect_range": self.effect_range,
            "population_standard_deviation": self.population_standard_deviation,
            "sign": {
                "positive_count": self.positive_count,
                "negative_count": self.negative_count,
                "zero_count": self.zero_count,
                "agreement": self.sign_agreement,
                "consistent": self.sign_consistent,
                "zero_tolerance": self.zero_tolerance,
            },
        }


@dataclass(frozen=True)
class ExperimentResult:
    """Completed, partial, or failed multi-context experiment report."""

    request: ExperimentRequest
    model_metadata: Dict[str, Any]
    effects: Tuple[ContextEffect, ...]
    skipped_contexts: Tuple[SkippedContext, ...]
    stability: Optional[StabilitySummary]

    @property
    def status(self) -> str:
        if not self.effects:
            return "failed"
        if self.skipped_contexts:
            return "partial"
        return "completed"

    def as_dict(self) -> Dict[str, Any]:
        focal = self.request.focal_variant
        return {
            "schema_version": EXPERIMENT_SCHEMA_VERSION,
            "status": self.status,
            "experiment_id": self.request.experiment_id,
            "focal_variant": {
                "identifier": focal.identifier,
                "reference": focal.reference,
                "alternate": focal.alternate,
            },
            "model": self.model_metadata,
            "counts": {
                "requested": len(self.request.contexts),
                "analyzed": len(self.effects),
                "skipped": len(self.skipped_contexts),
            },
            "stability": None if self.stability is None else self.stability.as_dict(),
            "contexts": [effect.as_dict() for effect in self.effects],
            "skipped_contexts": [skip.as_dict() for skip in self.skipped_contexts],
        }


def run_experiment(
    request: ExperimentRequest,
    model: ScalarModelAdapter,
) -> ExperimentResult:
    """Construct paired inputs, score them, and summarize effects across contexts."""

    effects = []
    skipped = []
    focal = request.focal_variant

    for context in request.contexts:
        try:
            analysis = analyze_variant(
                AnalysisRequest(
                    source_type=context.source_type,
                    source_name=context.source_name,
                    sequence_id=context.sequence_id,
                    window_start=context.window_start,
                    sequence=context.sequence,
                    vcf_position=context.vcf_position,
                    reference=focal.reference,
                    alternate=focal.alternate,
                    observed_allele=context.observed_allele,
                    sample_id=context.sample_id,
                    haplotype_id=context.haplotype_id,
                )
            )
        except ValueError as error:
            skipped.append(
                SkippedContext(
                    context_id=context.context_id,
                    stage="context-construction",
                    error_type=type(error).__name__,
                    reason=str(error),
                )
            )
            continue

        try:
            baseline_score = float(model.predict(analysis.baseline_sequence))
            alternate_score = float(model.predict(analysis.alternate_sequence))
            if not isfinite(baseline_score) or not isfinite(alternate_score):
                raise ModelValidationError("model predictions must be finite")
        except ValueError as error:
            skipped.append(
                SkippedContext(
                    context_id=context.context_id,
                    stage="model-inference",
                    error_type=type(error).__name__,
                    reason=str(error),
                )
            )
            continue

        effects.append(
            ContextEffect(
                context_id=context.context_id,
                source_type=context.source_type,
                source_name=context.source_name,
                sample_id=context.sample_id,
                haplotype_id=context.haplotype_id,
                observed_allele=context.observed_allele,
                sequence_id=context.sequence_id,
                vcf_position=context.vcf_position,
                baseline_sequence=analysis.baseline_sequence,
                alternate_sequence=analysis.alternate_sequence,
                baseline_content_id=analysis.baseline_content_id,
                alternate_content_id=analysis.alternate_content_id,
                baseline_construction=analysis.baseline_construction,
                alternate_construction=analysis.alternate_construction,
                baseline_score=baseline_score,
                alternate_score=alternate_score,
            )
        )

    effect_values = tuple(effect.effect for effect in effects)
    stability = (
        StabilitySummary.from_effects(
            effect_values,
            zero_tolerance=request.zero_tolerance,
        )
        if effect_values
        else None
    )
    return ExperimentResult(
        request=request,
        model_metadata=model.metadata(),
        effects=tuple(effects),
        skipped_contexts=tuple(skipped),
        stability=stability,
    )
