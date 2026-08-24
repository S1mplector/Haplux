"""Context-provider boundary for reference, graph, and assembly data adapters."""

from dataclasses import dataclass
from typing import Any, Dict, Protocol, Tuple, runtime_checkable

from pancontext.experiment import ExperimentContext, ExperimentValidationError, FocalVariant


@dataclass(frozen=True)
class AnchorLocus:
    """A 1-based source locus used to begin context discovery or projection."""

    source_name: str
    sequence_id: str
    position: int

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ExperimentValidationError("anchor source name must not be blank")
        if not self.sequence_id.strip():
            raise ExperimentValidationError("anchor sequence ID must not be blank")
        if self.position < 1:
            raise ExperimentValidationError("anchor position must be at least 1")


@dataclass(frozen=True)
class WindowSpecification:
    """Requested bases on either side of the focal allele."""

    left_flank: int
    right_flank: int

    def __post_init__(self) -> None:
        if self.left_flank < 0 or self.right_flank < 0:
            raise ExperimentValidationError("window flanks must be non-negative")


@dataclass(frozen=True)
class ContextQuery:
    """Provider-neutral request for projected haplotype contexts."""

    focal_variant: FocalVariant
    anchor: AnchorLocus
    window: WindowSpecification


@dataclass(frozen=True)
class ProviderIssue:
    """Structured non-fatal problem encountered while loading contexts."""

    code: str
    message: str
    record_id: str = ""

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ExperimentValidationError("provider issue code must not be blank")
        if not self.message.strip():
            raise ExperimentValidationError("provider issue message must not be blank")

    def as_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "record_id": self.record_id,
        }


@dataclass(frozen=True)
class ProviderBatch:
    """Projected contexts plus non-fatal records rejected by the provider."""

    contexts: Tuple[ExperimentContext, ...]
    issues: Tuple[ProviderIssue, ...] = ()

    def __post_init__(self) -> None:
        contexts = tuple(self.contexts)
        issues = tuple(self.issues)
        context_ids = [context.context_id for context in contexts]
        if len(set(context_ids)) != len(context_ids):
            raise ExperimentValidationError("provider context IDs must be unique")
        object.__setattr__(self, "contexts", contexts)
        object.__setattr__(self, "issues", issues)


@runtime_checkable
class ContextProvider(Protocol):
    """Contract implemented by future FASTA/VCF, graph, and assembly loaders."""

    provider_id: str
    version: str

    def load(self, query: ContextQuery) -> ProviderBatch:
        """Return projected contexts and structured non-fatal issues."""

    def metadata(self) -> Dict[str, Any]:
        """Return input identities, adapter version, and relevant parameters."""
