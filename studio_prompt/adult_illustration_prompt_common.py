"""Shared constants and validation primitives for adult prompt profiles."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MANIFEST = Path("research/adult-illustration/prompt-profile-vocabulary.json")
FORMAT = "studio.adult-illustration.prompt-projection/v2"
MAX_MANIFEST_BYTES = 1_048_576
MAX_ENTRIES = 4096
MAX_PROFILES = 32
MAX_DIAGNOSTICS = 256
SHA40 = re.compile(r"[0-9a-f]{40}")
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
POLARITIES = {"positive", "negative"}
MODES = {"tag", "hybrid", "instruction"}

AUTHORITY = {
    "execution_authorized": False,
    "generation_submitted": False,
    "download_authorized": False,
    "install_authorized": False,
    "training_authorized": False,
}


class DuplicateKeyError(ValueError):
    """Raised when checked-in JSON repeats an object key."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value {value!r} is not allowed")


def _text(value: Any, label: str, maximum: int = 4096, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError(f"{label} must be bounded text")
    if any(ord(character) < 32 and character not in "\n\t\r" for character in value):
        raise ValueError(f"{label} contains a control character")
    return value


def _strings(value: Any, label: str, maximum_count: int, item_limit: int = 256) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum_count:
        raise ValueError(f"{label} must be a bounded array")
    result: list[str] = []
    for item in value:
        result.append(_text(item, label, item_limit))
    if len(result) != len(set(result)):
        raise ValueError(f"{label} contains duplicates")
    return result


def _https(value: Any, label: str) -> str:
    text = _text(value, label, 4096)
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} must be an HTTPS URL without credentials")
    return text


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} is not a valid identifier")
    return value


def _normalise_term(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())
