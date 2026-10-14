"""Pin app/references.image_record traversal guard: escape rejects, in-root succeeds."""
import importlib.util
from pathlib import Path

import pytest
from PIL import Image

SPEC = importlib.util.spec_from_file_location(
    "references", Path(__file__).resolve().parents[1] / "app/references.py"
)
references = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(references)


def _save_png(path):
    Image.new("RGB", (8, 6), "teal").save(path, "PNG")


def test_image_record_rejects_escape(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _save_png(root / "inside.png")
    # Escape target must exist as a real image so this test fails if the
    # containment (parents) check is removed: without it the call succeeds.
    _save_png(tmp_path / "outside.png")
    with pytest.raises(ValueError, match="unavailable"):
        references.image_record(root, "../outside.png")
    record = references.image_record(root, "inside.png")
    assert record["file"] == "inside.png"
    assert (record["width"], record["height"]) == (8, 6)
