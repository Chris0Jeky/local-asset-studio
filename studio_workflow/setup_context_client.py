"""Bounded read-only client for exact setup compatibility reports."""
from __future__ import annotations

import copy
from http.client import HTTPException
from urllib.error import HTTPError

from . import setup_context_compatibility as evaluator
from .client import ClientError, read_response
from .core import canonical, decode, need

PREFIX = '/api/workflow-studio/setup-compatibility'
MAX_ERROR_BYTES = 65536
ZERO_AUTHORITY_FIELDS = (
    'provider_accessed',
    'file_hashed',
    'model_downloaded',
    'installation_authorized',
    'backend_switched',
    'selection_changed',
    'generation_submitted',
)


def validate_reply(result, expected):
    message = 'Setup compatibility response does not match this exact retained context'
    need(
        isinstance(result, dict)
        and all(result.get(field) is False for field in ZERO_AUTHORITY_FIELDS)
        and canonical(result) == canonical(expected),
        message,
    )
    return result


def observe(transport, value):
    """Evaluate one immutable snapshot and accept only its exact server report."""
    query = copy.deepcopy(value)
    expected = evaluator.evaluate(query)
    try:
        result = transport(PREFIX, copy.deepcopy(query))
    except HTTPError as exc:
        try:
            with exc:
                detail = decode(read_response(exc, MAX_ERROR_BYTES))
        except (ValueError, OSError, HTTPException):
            detail = {}
        message = detail.get('error') if isinstance(detail, dict) else None
        error = {
            'error': message if isinstance(message, str)
            else 'Setup compatibility is unavailable; check again explicitly.',
            'code': 'setup_compatibility_unavailable',
            **{field: False for field in ZERO_AUTHORITY_FIELDS},
        }
        raise ClientError(exc.code, error) from exc
    return validate_reply(result, expected)
