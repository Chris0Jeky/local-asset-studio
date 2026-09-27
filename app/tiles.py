"""Seamless tiles (#1220): the lab's roll-and-repaint method as a Studio route. This module never calls ComfyUI or queues work.

1. Prepare (`prepare`): roll a square, flat texture by half in both axes so its wrap seam becomes a centre cross, and store
   it as an RGBA upload whose transparent cross is the repaint region (LoadImage MASK = 1 - alpha).
2. Generate: the owner presses Generate on the catalog's `tile_route` recipe, a masked repaint (SetLatentNoiseMask). The
   job carries the plan as its `tile` claim; `validate` re-derives the cross from the source before binding and before
   the POST, so only the prepared picture of that exact source can run.
3. Finish (`finish`, run once when the repaint completes, or by hand): soft composite of the repainted cross over the
   rolled texture, a circular Gaussian lighting flatten, the seam metric and a 3x3 repeat preview, stored as a
   `tile.finish.v1` job whose assets carry lineage to the source and the repaint.

Method and numbers: experiments/curated/background-lab-20260927/ (PR #1222): wall seam 4.34 -> 0.82 against its own
gradient of 0.95. Pillow only: numpy is not a Studio dependency, so the circular blur repeats the picture 3x3 instead of
using an FFT. Numbers are evidence for review, never art acceptance.
"""
from __future__ import annotations

import copy
import hashlib
import io
import re
import threading
import time
import uuid
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageMath, ImageStat

import continuation

VERSION = 1
OPERATION = "tile.finish.v1"
BAND = 112                  # lab: 112 px for the wall (keep), 160 px for floor v2
BAND_LIMITS = (16, 512)
FEATHER = 12                # lab: GaussianBlur(12) on the hard cross before the composite
SIZE_LIMITS = (256, 1536)
SIZE_MULTIPLE = 16
PREVIEW_CELL = 512
FLAT_ONLY = "Flat textures only: top-down or front-on, with no perspective; a perspective picture cannot tile."
CLAIM_FIELDS = {"version", "preset_id", "source_asset_id", "source_sha256", "rolled_file", "rolled_sha256", "size", "band_px", "feather_px", "flatten_sigma_px"}
_FINISH_LOCK = threading.Lock()


def default_sigma(size):
    """The lab's 96 px flatten at 1024 px, scaled with the side (3/32 of it)."""
    return max(1, round(size * 3 / 32))


def roll_half(image):
    """np.roll by half in both axes: the wrap seam moves to the centre lines."""
    width, height = image.size
    return ImageChops.offset(image, width // 2, height // 2)


def band_mask(size, band):
    """L mask: 255 on the centre cross, `band` px wide in both axes, 0 elsewhere."""
    width, height = size; half = band // 2; mask = Image.new("L", size, 0)
    mask.paste(255, (width // 2 - half, 0, width // 2 + half, height)); mask.paste(255, (0, height // 2 - half, width, height // 2 + half))
    return mask


def repaint_input(source, band):
    """The rolled texture as RGBA, transparent on the cross: the repaint region of a `requires_rgba_mask` graph."""
    rolled = roll_half(source.convert("RGB")).convert("RGBA")
    rolled.putalpha(ImageChops.invert(band_mask(rolled.size, band)))
    return rolled


def soft_mask(size, band, feather=FEATHER):
    return band_mask(size, band).filter(ImageFilter.GaussianBlur(feather)) if feather else band_mask(size, band)


def composite(rolled, repaint, band, feather=FEATHER):
    """The repainted cross over the rolled texture through a feathered mask; everything outside it keeps the source pixels."""
    return Image.composite(repaint.convert("RGB"), rolled.convert("RGB"), soft_mask(rolled.size, band, feather))


def circular_blur(image, sigma):
    """A Gaussian blur on a torus: blur a 3x3 repeat and keep the middle, so the blur tiles exactly as the picture does."""
    width, height = image.size
    if not 0 < sigma * 3 <= min(width, height): raise ValueError("The flatten radius must be positive and at most a third of the tile side.")
    grid = Image.new(image.mode, (width * 3, height * 3))
    for column in range(3):
        for row in range(3): grid.paste(image, (column * width, row * height))
    return grid.filter(ImageFilter.GaussianBlur(sigma)).crop((width, height, width * 2, height * 2))


def flatten(image, sigma):
    """Lighting flatten: out = picture * mean / circular_blur(picture), per channel (the lab's FFT step, sigma 96 px at 1024)."""
    rgb = image.convert("RGB"); blurred = circular_blur(rgb, sigma); channels = []
    for plain, low in zip(rgb.split(), blurred.split()):
        mean = ImageStat.Stat(plain).mean[0]
        channels.append(ImageMath.lambda_eval(lambda a: a["convert"](a["p"] * mean / a["max"](a["b"], 1.0) + 0.5, "L"), p=plain.convert("F"), b=low.convert("F")))
    return Image.merge("RGB", channels)


def _mean_abs(first, second):
    means = ImageStat.Stat(ImageChops.difference(first, second)).mean
    return sum(means) / len(means)


def seam(image):
    """The lab's seam score: mean |difference| across the wrap edges (last column vs first, last row vs first)."""
    rgb = image.convert("RGB"); width, height = rgb.size
    return round((_mean_abs(rgb.crop((width - 1, 0, width, height)), rgb.crop((0, 0, 1, height)))
                  + _mean_abs(rgb.crop((0, height - 1, width, height)), rgb.crop((0, 0, width, 1)))) / 2, 2)


def centre_seam(image):
    """The same score across the centre lines, where a rolled picture carries its old wrap seam."""
    rgb = image.convert("RGB"); width, height = rgb.size; x, y = width // 2, height // 2
    return round((_mean_abs(rgb.crop((x - 1, 0, x, height)), rgb.crop((x, 0, x + 1, height)))
                  + _mean_abs(rgb.crop((0, y - 1, width, y)), rgb.crop((0, y, width, y + 1)))) / 2, 2)


def inner_gradient(image):
    """Mean |difference| between neighbouring pixels inside the picture: the texture's own gradient, the seam's yardstick."""
    rgb = image.convert("RGB"); width, height = rgb.size
    return round((_mean_abs(rgb.crop((1, 0, width, height)), rgb.crop((0, 0, width - 1, height)))
                  + _mean_abs(rgb.crop((0, 1, width, height)), rgb.crop((0, 0, width, height - 1)))) / 2, 2)


def repeat_preview(image, cell=PREVIEW_CELL):
    """Nine copies in a 3x3 grid, each at most `cell` px: the review view for a tile."""
    rgb = image.convert("RGB"); side = min(cell, rgb.size[0])
    tile = rgb if side == rgb.size[0] else rgb.resize((side, side * rgb.size[1] // rgb.size[0]), Image.LANCZOS)
    grid = Image.new("RGB", (tile.size[0] * 3, tile.size[1] * 3))
    for column in range(3):
        for row in range(3): grid.paste(tile, (column * tile.size[0], row * tile.size[1]))
    return grid


def png_bytes(image):
    stream = io.BytesIO(); image.save(stream, "PNG"); return stream.getvalue()


def eligibility(width, height):
    """None when a picture can become a tile, else the reason shown on the disabled control."""
    if width != height: return "Needs a square texture: this picture is %d × %d." % (width, height)
    if not SIZE_LIMITS[0] <= width <= SIZE_LIMITS[1]: return "Make seamless needs a side between %d and %d px; this picture is %d px." % (SIZE_LIMITS + (width,))
    if width % SIZE_MULTIPLE: return "Make seamless needs a side that is a multiple of %d px; this picture is %d px." % (SIZE_MULTIPLE, width)
    return None


def route(studio):
    """The catalog's one seamless-tile recipe."""
    routes = [preset for preset in studio.catalog()["presets"] if preset.get("tile_route")]
    if len(routes) != 1: raise ValueError("No single seamless-tile recipe is registered in the catalog.")
    return routes[0]


def route_problems(presets):
    """Catalog contract, checked by scripts/validate-repo.py: at most one tile route, and it is a masked repaint of one picture."""
    routes = [preset for preset in presets if preset.get("tile_route")]
    problems = ["more than one tile_route recipe: " + ", ".join(p["id"] for p in routes)] if len(routes) > 1 else []
    for preset in routes:
        if preset.get("tile_route") is not True: problems.append(preset["id"] + ": tile_route must be true")
        if not preset.get("requires_rgba_mask") or not preset.get("reference"): problems.append(preset["id"] + ": a tile route repaints an RGBA cross, so it needs requires_rgba_mask and a reference binding")
        if preset.get("modality", "image") != "image": problems.append(preset["id"] + ": a tile route makes pictures")
        if preset.get("width") or preset.get("height"): problems.append(preset["id"] + ": a tile route draws at the source size; it binds no width or height")
    return problems


def _source(studio, asset_id):
    """(context, RGB picture) of a library image whose bytes still match its record."""
    context = continuation.source_context(studio, asset_id)
    raw = studio.assets.file(asset_id).read_bytes()
    if hashlib.sha256(raw).hexdigest() != context["sha256"]: raise ValueError("Source bytes changed. Restore the original asset before making it seamless.")
    with Image.open(io.BytesIO(raw)) as decoded: return context, decoded.convert("RGB")


def source_status(studio, asset_id):
    """Whether one library picture can become a tile, with the reason when it cannot."""
    context = continuation.source_context(studio, asset_id)
    reason = eligibility(context["width"], context["height"])
    return {"asset_id": context["asset_id"], "width": context["width"], "height": context["height"], "eligible": reason is None,
            "reason": reason, "flag": FLAT_ONLY, "preset_id": route(studio)["id"], "band_px": BAND}


def prepare(studio, payload):
    """Roll one library texture and store its seam cross as an RGBA upload. Nothing is queued or submitted."""
    if not isinstance(payload, dict) or not set(payload) <= {"asset_id", "band_px", "flatten"} or "asset_id" not in payload:
        raise ValueError("Make seamless takes asset_id, and optionally band_px and flatten.")
    band = payload.get("band_px", BAND); flat = payload.get("flatten", True)
    if type(band) is not int or band % 2 or not BAND_LIMITS[0] <= band <= BAND_LIMITS[1]: raise ValueError("band_px must be an even whole number from %d to %d." % BAND_LIMITS)
    if type(flat) is not bool: raise ValueError("flatten must be true or false.")
    preset = route(studio)
    context, source = _source(studio, payload["asset_id"])
    reason = eligibility(*source.size)
    if reason: raise ValueError(reason)
    size = source.size[0]
    if band > size // 2: raise ValueError("band_px must be at most half the tile side (%d px)." % (size // 2))
    upload = studio.upload("seam-cross", "image/png", png_bytes(repaint_input(source, band)))
    plan = {"version": VERSION, "preset_id": preset["id"], "source_asset_id": context["asset_id"], "source_sha256": context["sha256"],
            "rolled_file": upload["file"], "rolled_sha256": upload["sha256"], "size": size, "band_px": band, "feather_px": FEATHER,
            "flatten_sigma_px": default_sigma(size) if flat else 0}
    return {"plan": plan, "file": upload["file"], "sha256": upload["sha256"], "width": size, "height": size, "preset_id": preset["id"],
            "context": context, "flag": FLAT_ONLY, "seam_source": seam(source), "inner_gradient_source": inner_gradient(source), "generation_submitted": False}


def _claim(claim):
    if not isinstance(claim, dict) or set(claim) != CLAIM_FIELDS or type(claim.get("version")) is not int or claim["version"] != VERSION:
        raise ValueError("Invalid seamless-tile plan. Press Make seamless on the source again.")
    for key in ("preset_id", "source_asset_id", "rolled_file"):
        if not isinstance(claim[key], str) or not claim[key] or len(claim[key]) > 255: raise ValueError("Invalid seamless-tile plan field: " + key)
    if any(not isinstance(claim[key], str) or not re.fullmatch("[a-f0-9]{64}", claim[key]) for key in ("source_sha256", "rolled_sha256")) \
            or not re.fullmatch(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.png", claim["rolled_file"]):
        raise ValueError("Invalid seamless-tile plan identity.")
    size, band, feather, sigma = claim["size"], claim["band_px"], claim["feather_px"], claim["flatten_sigma_px"]
    if any(type(value) is not int for value in (size, band, feather, sigma)) or eligibility(size, size) or band % 2 \
            or not BAND_LIMITS[0] <= band <= min(BAND_LIMITS[1], size // 2) or not 0 <= feather <= 64 or not 0 <= sigma * 3 <= size:
        raise ValueError("Invalid seamless-tile plan geometry. Press Make seamless on the source again.")
    return claim


def validate(studio, payload, preset, graph, batch, check_runtime=False):
    """Refuse a tile route without its plan, or a plan whose cross no longer derives from its source. Returns the claim."""
    claim = payload.get("tile")
    if claim is None:
        if preset.get("tile_route"):
            raise ValueError("%s starts from Make seamless on a square, flat texture in the Asset library; the authored example cannot be queued." % (preset.get("name") or preset.get("id")))
        return None
    if not preset.get("tile_route"): raise ValueError("A seamless-tile plan runs only on the seamless-tile recipe.")
    _claim(claim)
    if claim["preset_id"] != preset.get("id"): raise ValueError("This seamless-tile plan was prepared for another recipe. Press Make seamless again.")
    if payload.get("continuation") is not None: raise ValueError("A seamless tile is not a continuation; leave the continuation first.")
    if str(batch) != "1": raise ValueError("A seamless tile repaints one picture: set the batch count to 1.")
    parents = payload.get("parent_assets")
    if not isinstance(parents, list) or claim["source_asset_id"] not in parents: raise ValueError("The seamless-tile source is missing from lineage.")
    name = claim["rolled_file"]
    try: node, field = preset["reference"]; bound = graph[str(node)]["inputs"][str(field)]
    except (KeyError, TypeError, ValueError): raise ValueError("The seamless-tile recipe has no valid picture binding.") from None
    if (payload.get("controls") or {}).get("reference") != name or bound != name:
        raise ValueError("Attach the prepared seam cross, not another picture. Press Make seamless again.")
    upload = studio.experiments / "uploads" / name
    if upload.is_symlink() or not upload.is_file() or hashlib.sha256(upload.read_bytes()).hexdigest() != claim["rolled_sha256"]:
        raise ValueError("The prepared seam cross changed or is missing. Press Make seamless again.")
    context, source = _source(studio, claim["source_asset_id"])
    if context["sha256"] != claim["source_sha256"] or source.size != (claim["size"], claim["size"]):
        raise ValueError("The seamless-tile source changed. Press Make seamless on it again.")
    with Image.open(upload) as decoded:
        if decoded.mode != "RGBA" or decoded.tobytes() != repaint_input(source, claim["band_px"]).tobytes():
            raise ValueError("The prepared seam cross no longer matches its source. Press Make seamless again.")
    if check_runtime:
        runtime = Path(payload.get("comfy_root", studio.comfy_root)) / "input" / name
        if runtime.is_symlink() or not runtime.is_file() or hashlib.sha256(runtime.read_bytes()).hexdigest() != claim["rolled_sha256"]:
            raise ValueError("The seam cross in ComfyUI's input folder changed or is missing. Press Make seamless again.")
    return dict(claim)


def finish_id(job_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "asset-studio:tile-finish:" + job_id))


def summary(metrics):
    return "Seam %.2f → %.2f (the tile's own neighbour gradient %.2f). Review the 3×3 repeat; a number is not art acceptance." % (
        metrics["seam_source"], metrics["seam_tile"], metrics["inner_gradient_tile"])


def finish(studio, job_id):
    """Composite, flatten, measure and preview one completed repaint. Idempotent: a second call returns the first result."""
    with _FINISH_LOCK:
        job = studio.jobs.get(job_id) if isinstance(job_id, str) else None
        if not job: raise ValueError("Unknown job")
        claim = job.get("tile")
        if not claim: raise ValueError("This job is not a seamless-tile repaint.")
        identifier = finish_id(job_id)
        if identifier in studio.jobs: return studio.jobs[identifier]
        if job.get("status") != "completed": raise ValueError("Finish the tile after its repaint completes; this job is %s." % job.get("status"))
        _claim(claim)
        images = [output for output in job.get("outputs", []) if output.get("media_type", "image") == "image"]
        if len(images) != 1 or not images[0].get("asset_id"):
            raise ValueError("The repaint left %d saved pictures; a tile needs exactly one." % sum(1 for output in images if output.get("asset_id")))
        output = images[0]
        repaint_path, repaint_asset = studio.assets.file_entry(output["asset_id"])
        repaint_raw = repaint_path.read_bytes()
        if hashlib.sha256(repaint_raw).hexdigest() != repaint_asset["sha256"]: raise ValueError("The repaint's saved bytes changed; the tile was not finished.")
        rolled_raw = (studio.experiments / "uploads" / claim["rolled_file"]).read_bytes()
        if hashlib.sha256(rolled_raw).hexdigest() != claim["rolled_sha256"]: raise ValueError("The prepared seam cross changed; the tile was not finished.")
        with Image.open(io.BytesIO(rolled_raw)) as decoded: rolled = decoded.convert("RGB")
        with Image.open(io.BytesIO(repaint_raw)) as decoded: repaint = decoded.convert("RGB")
        if repaint.size != rolled.size: raise ValueError("The repaint is %d × %d but the texture is %d × %d; the tile was not finished." % (repaint.size + rolled.size))
        joined = composite(rolled, repaint, claim["band_px"], claim["feather_px"])
        final = flatten(joined, claim["flatten_sigma_px"]) if claim["flatten_sigma_px"] else joined
        preview = repeat_preview(final)
        metrics = {"seam_source": centre_seam(rolled), "seam_composite": seam(joined), "seam_tile": seam(final), "centre_seam_tile": centre_seam(final),
                   "inner_gradient_source": inner_gradient(rolled), "inner_gradient_tile": inner_gradient(final)}
        metrics["summary"] = summary(metrics)
        directory = studio.runs / identifier; directory.mkdir(parents=True, exist_ok=True)
        files = {"tile.png": png_bytes(final), "tile-3x3.png": png_bytes(preview)}
        if claim["flatten_sigma_px"]: files["tile-unflattened.png"] = png_bytes(joined)
        for filename, data in files.items(): (directory / filename).write_bytes(data)
        hashes = {filename: hashlib.sha256(data).hexdigest() for filename, data in files.items()}
        submission = next((item for item in job.get("submissions", []) if item.get("prompt_id") == output.get("prompt_id")), {})
        preview_asset = uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:{identifier}:1").hex
        steps = ["Soft composite of the repainted cross over the rolled texture (Gaussian feather %d px)" % claim["feather_px"],
                 "Circular Gaussian lighting flatten, sigma %d px (Pillow, 3x3 wrap)" % claim["flatten_sigma_px"] if claim["flatten_sigma_px"] else "No lighting flatten",
                 "Seam metric: mean |difference| across the wrap edges; 3x3 repeat preview"]
        receipt = {"version": VERSION, "plan": copy.deepcopy(claim), "repaint_job_id": job_id, "repaint_prompt_id": output.get("prompt_id"),
                   "repaint_asset_id": output["asset_id"], "repaint_sha256": repaint_asset["sha256"], "repaint_preset_id": job.get("preset_id"),
                   "repaint_graph_path": job.get("graph_path"), "repaint_controls": copy.deepcopy(job.get("controls")), "repaint_seed": output.get("seed"),
                   "submitted_graph": copy.deepcopy(submission.get("graph")), "steps": steps, "metrics": metrics, "files": hashes,
                   "method": "experiments/curated/background-lab-20260927 (PR #1222)", "finished_at": time.time()}
        tile = dict(metrics, preview_asset_id=preview_asset, repaint_prompt_id=output.get("prompt_id"), flat_only=FLAT_ONLY)
        finished = {"id": identifier, "operation": OPERATION, "status": "completed", "created_at": time.time(), "preset_id": "seamless-tile",
                    "preset_name": "Seamless tile", "controls": {}, "batch_count": 1, "prompt_ids": [], "submissions": [], "references": [],
                    "parent_assets": [claim["source_asset_id"], output["asset_id"]], "graph_path": "", "graph": {}, "tile_receipt": receipt,
                    "message": "Seamless tile finished from repaint prompt %s. %s No generation was submitted." % (output.get("prompt_id"), metrics["summary"]),
                    "outputs": [{"filename": "tile.png", "run_file": "tile.png", "type": "output", "media_type": "image", "prompt_id": output.get("prompt_id"), "seed": output.get("seed"), "tile": tile},
                                {"filename": "tile-3x3.png", "run_file": "tile-3x3.png", "type": "output", "media_type": "image", "prompt_id": output.get("prompt_id"), "tile_preview": {"of": "tile.png", "summary": metrics["summary"]}}]}
        studio.index_outputs(finished); studio._save(finished)
        with studio.lock:
            studio.jobs[identifier] = finished
            job["tile_finish"] = {"job_id": identifier, "tile_asset_id": finished["outputs"][0].get("asset_id"), "preview_asset_id": finished["outputs"][1].get("asset_id"), "summary": metrics["summary"]}
        studio._save(job)
        return finished


def finish_after_run(studio, job):
    """The worker's hook after a repaint completes: finish once, and record a failure on the job instead of raising."""
    if not job.get("tile") or job.get("status") != "completed" or (job.get("tile_finish") or {}).get("job_id"): return
    try: finish(studio, job["id"])
    except Exception as exc:  # the repaint's own outcome never changes because its finishing step failed
        job["tile_finish"] = {"error": str(exc)[:300], "failed_at": time.time()}
        try: studio._save(job)
        except Exception: pass
