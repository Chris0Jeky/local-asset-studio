"""Render a drawn COCO-18 pose into a stored guide picture.  This module never calls ComfyUI."""
import math

from studio_workflow import pose_artifact, pose_artifact_store
from studio_workflow.pose_raster import RENDERER, render_png

MAX_BODY_BYTES = 16 * 1024          # a bounded 18-joint document, not an upload channel
CANVAS_LIMITS = (64, 1536)          # server.py's own recipe grid defaults (dimension_limits)
CANVAS_MULTIPLE = 8                 # server.py's dimension_multiple default; the Klein recipes use 16
MINIMUM_JOINTS = 2                  # fewer than two known joints cannot draw a limb
FILENAME = "drawn-pose"    # Studio.upload appends the image extension, exactly as it does for an upload
ARTIFACT_DIRECTORY = pose_artifact_store.DIRECTORY


def _canvas(value, name):
    low, high = CANVAS_LIMITS
    if type(value) is not int: raise ValueError(f"{name} must be a whole number of pixels")
    if not low <= value <= high: raise ValueError(f"{name} must be between {low} and {high} pixels")
    if value % CANVAS_MULTIPLE: raise ValueError(f"{name} must be a multiple of {CANVAS_MULTIPLE}")
    return value


def _coordinate(value, limit):
    # json.loads accepts NaN and Infinity literals, so a finite check is not decoration.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value): raise ValueError("Every joint coordinate must be a finite number")
    if not 0 <= value <= limit: raise ValueError("Every joint must sit inside the canvas")
    return float(value)


def edits(payload):
    """Validate one drawn pose and return its canvas plus {joint: [x, y] | None}. Pure; no file is written."""
    if not isinstance(payload, dict) or set(payload) != {"width", "height", "keypoints"}: raise ValueError("A pose needs width, height and keypoints, and nothing else")
    width, height = _canvas(payload["width"], "width"), _canvas(payload["height"], "height")
    points = payload["keypoints"]
    if not isinstance(points, list) or len(points) != len(pose_artifact.JOINTS): raise ValueError(f"A pose has exactly {len(pose_artifact.JOINTS)} joints, in COCO-18 order")
    drawn = {}
    for name, entry in zip(pose_artifact.JOINTS, points):
        if entry is None: drawn[name] = None; continue
        if not isinstance(entry, list) or len(entry) != 2: raise ValueError("Each joint is [x, y] in canvas pixels, or null when it is unknown")
        drawn[name] = [_coordinate(entry[0], width), _coordinate(entry[1], height)]
    if sum(1 for value in drawn.values() if value is not None) < MINIMUM_JOINTS: raise ValueError("Mark at least two joints: a guide with fewer draws no limb")
    return {"width": width, "height": height}, drawn


def artifact(payload):
    """Build the validated pose artifact for one drawn pose. Every joint is manual, never detector evidence."""
    canvas, drawn = edits(payload)
    blank = pose_artifact.canonical({"version": 1.3, "canvas_width": canvas["width"], "canvas_height": canvas["height"],
                                     "people": [{"pose_keypoints_2d": [0] * (3 * len(pose_artifact.JOINTS))}]})
    empty = pose_artifact.import_openpose(blank, width=canvas["width"], height=canvas["height"], coordinate_space="pixels")
    # revise() is the only path that records manual origin with no detector confidence (pose-control P-02).
    return pose_artifact.validate(pose_artifact.revise(empty, empty["id"], {k: v for k, v in drawn.items() if v is not None}))


def read_artifact(studio, artifact_id):
    """Read and revalidate one exact editable sidecar. It remains unreviewed and non-authoritative."""
    return pose_artifact_store.read(studio.experiments, artifact_id)


def render(studio, payload):
    """Store an editable artifact plus its rendered upload. No generation is submitted."""
    drawn = artifact(payload)
    editable = pose_artifact_store.publish(studio.experiments, drawn)
    stored = studio.upload(FILENAME, "image/png", render_png(drawn))
    return dict(stored, artifact_id=drawn["id"], artifact=editable,
                renderer=RENDERER, generation_submitted=False)
