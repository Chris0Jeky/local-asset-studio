"""Regular-only boundaries for advanced operations without private storage.

Legacy records without a classification are regular. Explicit private or invalid
classifications must never be silently copied into ordinary project artifacts.
HTTP scope parsing and supported private creation belong to the app owner.
"""


def is_regular(record):
    """Whether a stored record is visible to an unsupported, regular-only owner."""
    return isinstance(record, dict) and record.get('privacy', 'regular') == 'regular'


def require_regular_creation(payload):
    """Refuse a non-regular creation intent before an advanced owner has effects."""
    if isinstance(payload, dict) and not is_regular(payload):
        raise ValueError('Private creation is not supported for this operation')
