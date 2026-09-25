"""Public prompt projection API with fail-closed constraint binding."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import _adult_illustration_prompt_projection_impl as _impl
from .adult_illustration_prompt_catalog import load_catalog


def compile_prompt(
    source_projection: Any, profile_id: str, root: Path | str
) -> dict[str, Any]:
    """Compile reviewed intent, resolving the catalog via the public loader."""

    return _impl.compile_prompt(
        source_projection, profile_id, root, catalog_loader=load_catalog
    )


def validate_prompt_projection(
    value: Any, source_projection: Any, root: Path | str
) -> dict[str, Any]:
    """Recompile a prompt projection so changed derived records fail closed."""

    return _impl.validate_prompt_projection(
        value, source_projection, root, catalog_loader=load_catalog
    )


def __getattr__(name: str) -> Any:
    """Preserve access to implementation constants/helpers for stacked callers."""

    return getattr(_impl, name)


__all__ = ["compile_prompt", "load_catalog", "validate_prompt_projection"]
