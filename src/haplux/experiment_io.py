"""Strict versioned input parsing for headless context experiments."""

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from haplux.analysis import ObservedAllele
from haplux.context import ContextSource
from haplux.experiment import (
    ExperimentContext,
    ExperimentRequest,
    ExperimentValidationError,
    FocalVariant,
)
from haplux.models import ScalarModelAdapter, create_builtin_model


EXPERIMENT_REQUEST_SCHEMA_VERSION = "haplux.experiment-request.v1"


@dataclass(frozen=True)
class ParsedExperiment:
    """Validated experiment request paired with its model adapter."""

    request: ExperimentRequest
    model: ScalarModelAdapter


def _mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExperimentValidationError(f"{path} must be an object")
    return value


def _sequence(value: Any, *, path: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ExperimentValidationError(f"{path} must be an array")
    return value


def _string(value: Any, *, path: str) -> str:
    if not isinstance(value, str):
        raise ExperimentValidationError(f"{path} must be a string")
    return value


def _integer(value: Any, *, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExperimentValidationError(f"{path} must be an integer")
    return value


def _number(value: Any, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentValidationError(f"{path} must be a number")
    return float(value)


def _required(mapping: Mapping[str, Any], key: str, *, path: str) -> Any:
    if key not in mapping:
        raise ExperimentValidationError(f"{path}.{key} is required")
    return mapping[key]


def _optional_string(
    mapping: Mapping[str, Any],
    key: str,
    *,
    path: str,
) -> Optional[str]:
    value = mapping.get(key)
    if value is None:
        return None
    return _string(value, path=f"{path}.{key}")


def _reject_unknown(
    mapping: Mapping[str, Any],
    allowed: Sequence[str],
    *,
    path: str,
) -> None:
    unexpected = sorted(set(mapping) - set(allowed))
    if unexpected:
        raise ExperimentValidationError(
            f"{path} contains unknown field(s): " + ", ".join(unexpected)
        )


def parse_experiment_document(document: Any) -> ParsedExperiment:
    """Parse a strict experiment-request document into executable domain objects."""

    root = _mapping(document, path="document")
    _reject_unknown(root, ("schema_version", "experiment", "model"), path="document")
    schema_version = _string(
        _required(root, "schema_version", path="document"),
        path="document.schema_version",
    )
    if schema_version != EXPERIMENT_REQUEST_SCHEMA_VERSION:
        raise ExperimentValidationError(
            f"unsupported experiment request schema: {schema_version!r}"
        )

    experiment_data = _mapping(
        _required(root, "experiment", path="document"),
        path="document.experiment",
    )
    _reject_unknown(
        experiment_data,
        ("experiment_id", "focal_variant", "contexts", "zero_tolerance"),
        path="document.experiment",
    )
    focal_data = _mapping(
        _required(experiment_data, "focal_variant", path="document.experiment"),
        path="document.experiment.focal_variant",
    )
    _reject_unknown(
        focal_data,
        ("identifier", "reference", "alternate"),
        path="document.experiment.focal_variant",
    )
    focal = FocalVariant(
        identifier=_string(
            _required(
                focal_data,
                "identifier",
                path="document.experiment.focal_variant",
            ),
            path="document.experiment.focal_variant.identifier",
        ),
        reference=_string(
            _required(
                focal_data,
                "reference",
                path="document.experiment.focal_variant",
            ),
            path="document.experiment.focal_variant.reference",
        ),
        alternate=_string(
            _required(
                focal_data,
                "alternate",
                path="document.experiment.focal_variant",
            ),
            path="document.experiment.focal_variant.alternate",
        ),
    )

    contexts_data = _sequence(
        _required(experiment_data, "contexts", path="document.experiment"),
        path="document.experiment.contexts",
    )
    contexts = []
    allowed_context_fields = (
        "context_id",
        "source_type",
        "source_name",
        "sequence_id",
        "window_start",
        "sequence",
        "vcf_position",
        "observed_allele",
        "sample_id",
        "haplotype_id",
    )
    for index, raw_context in enumerate(contexts_data):
        path = f"document.experiment.contexts[{index}]"
        context_data = _mapping(raw_context, path=path)
        _reject_unknown(context_data, allowed_context_fields, path=path)
        try:
            source_type = ContextSource(
                _string(
                    _required(context_data, "source_type", path=path),
                    path=f"{path}.source_type",
                )
            )
            observed_allele = ObservedAllele(
                _string(
                    _required(context_data, "observed_allele", path=path),
                    path=f"{path}.observed_allele",
                )
            )
        except ValueError as error:
            raise ExperimentValidationError(f"{path}: {error}") from error
        contexts.append(
            ExperimentContext(
                context_id=_string(
                    _required(context_data, "context_id", path=path),
                    path=f"{path}.context_id",
                ),
                source_type=source_type,
                source_name=_string(
                    _required(context_data, "source_name", path=path),
                    path=f"{path}.source_name",
                ),
                sequence_id=_string(
                    _required(context_data, "sequence_id", path=path),
                    path=f"{path}.sequence_id",
                ),
                window_start=_integer(
                    _required(context_data, "window_start", path=path),
                    path=f"{path}.window_start",
                ),
                sequence=_string(
                    _required(context_data, "sequence", path=path),
                    path=f"{path}.sequence",
                ),
                vcf_position=_integer(
                    _required(context_data, "vcf_position", path=path),
                    path=f"{path}.vcf_position",
                ),
                observed_allele=observed_allele,
                sample_id=_optional_string(context_data, "sample_id", path=path),
                haplotype_id=_optional_string(context_data, "haplotype_id", path=path),
            )
        )

    zero_tolerance = _number(
        experiment_data.get("zero_tolerance", 0.0),
        path="document.experiment.zero_tolerance",
    )
    request = ExperimentRequest(
        experiment_id=_string(
            _required(experiment_data, "experiment_id", path="document.experiment"),
            path="document.experiment.experiment_id",
        ),
        focal_variant=focal,
        contexts=tuple(contexts),
        zero_tolerance=zero_tolerance,
    )

    model_data = _mapping(
        _required(root, "model", path="document"),
        path="document.model",
    )
    _reject_unknown(model_data, ("adapter", "parameters"), path="document.model")
    adapter = _string(
        _required(model_data, "adapter", path="document.model"),
        path="document.model.adapter",
    )
    parameters = _mapping(
        model_data.get("parameters", {}),
        path="document.model.parameters",
    )
    model = create_builtin_model(adapter, parameters)
    return ParsedExperiment(request=request, model=model)


def load_experiment_file(path: str) -> ParsedExperiment:
    """Load and parse one UTF-8 JSON experiment request from disk."""

    with open(path, "r", encoding="utf-8") as input_file:
        return parse_experiment_document(json.load(input_file))
