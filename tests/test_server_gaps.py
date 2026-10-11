"""Pinning tests for the app/server.py traversal guard.

Covers ``inside`` only: an escape via ``root/../evil`` must raise
``StudioError``, and a member such as ``root/a.json`` must resolve under
the root. Fixtures live under ``tmp_path`` only; the real repo root is
never touched.
"""
from pathlib import Path

import pytest

from app.server import StudioError, inside


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    return root.resolve()


def test_inside_rejects_escape(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(StudioError):
        inside(root, root / "../evil")


def test_inside_resolves_member(tmp_path):
    root = _root(tmp_path)
    target = root / "a.json"
    target.touch()
    resolved = inside(root, target)
    assert resolved == target.resolve()
    assert resolved.parent == root
