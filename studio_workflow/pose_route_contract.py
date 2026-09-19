"""One canonical contract for every corrected-pose route.

Screening and native binding use projections of the same immutable facts. This
module owns no graph execution, detector invocation, persistence or generation.
"""
from __future__ import annotations

from dataclasses import dataclass

COMMON_PINS = frozenset({
    'model', 'encoder', 'vae', 'graph', 'nodes', 'runtime',
    'reference_transform', 'prompt_dialect',
})
KNOWN_BACKEND_IDS = ('primary', 'hidream', 'h3')


@dataclass(frozen=True)
class RouteContract:
    route_id: str
    mechanism: str
    source_representation: str
    detector_behavior: str
    native_slot: str
    formats: tuple[str, ...]
    route_pins: frozenset[str]
    backend_ids: tuple[str, ...]


_CONTRACTS = (
    RouteContract(
        route_id='klein-geometry',
        mechanism='klein-geometry-reference',
        source_representation='precomputed-skeleton',
        detector_behavior='not-applicable',
        native_slot='geometry-reference',
        formats=('PNG',),
        route_pins=frozenset({'renderer'}),
        backend_ids=KNOWN_BACKEND_IDS,
    ),
    RouteContract(
        route_id='copy-pose',
        mechanism='copy-pose-rgb',
        source_representation='rgb-pose-donor',
        detector_behavior='not-applicable',
        native_slot='pose-donor-image-2',
        formats=('PNG', 'JPEG', 'WEBP'),
        route_pins=frozenset({'lora'}),
        backend_ids=KNOWN_BACKEND_IDS,
    ),
    RouteContract(
        route_id='sdxl-corrected-skeleton',
        mechanism='sdxl-precomputed-skeleton',
        source_representation='precomputed-skeleton',
        detector_behavior='bypass-precomputed-guide',
        native_slot='control-image',
        formats=('PNG',),
        route_pins=frozenset({'controlnet', 'renderer'}),
        backend_ids=KNOWN_BACKEND_IDS,
    ),
)
_BY_ID = {contract.route_id: contract for contract in _CONTRACTS}
ROUTE_IDS = tuple(contract.route_id for contract in _CONTRACTS)


def route_contract(route_id: str) -> RouteContract:
    """Return the immutable route contract or fail closed for an unknown ID."""
    if not isinstance(route_id, str) or route_id not in _BY_ID:
        raise ValueError('unsupported pose route')
    return _BY_ID[route_id]


def screening_projection(route_id: str) -> dict:
    """Project only the facts frozen by a screening manifest."""
    contract = route_contract(route_id)
    return {
        'id': contract.route_id,
        'mechanism': contract.mechanism,
        'input_representation': contract.source_representation,
        'detector_behavior': contract.detector_behavior,
        'pins': contract.route_pins,
        'backend_ids': contract.backend_ids,
    }


def binding_projection(route_id: str) -> dict:
    """Project only the facts required to bind exact source bytes."""
    contract = route_contract(route_id)
    return {
        'mechanism': contract.mechanism,
        'source_kind': contract.source_representation,
        'detector_behavior': contract.detector_behavior,
        'native_slot': contract.native_slot,
        'formats': contract.formats,
        'pins': contract.route_pins,
        'backend_ids': contract.backend_ids,
    }


def validate_backend(route_id: str, backend_id: str) -> str:
    """Bind a route only to a backend declared by the Studio configuration."""
    contract = route_contract(route_id)
    if not isinstance(backend_id, str) or backend_id not in contract.backend_ids:
        raise ValueError('backend id is not configured for this pose route')
    return backend_id
