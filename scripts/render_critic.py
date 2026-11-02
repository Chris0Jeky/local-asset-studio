"""Local render critic: ask a vision model served by llama-server which rubric defects render views show.

  python scripts/render_critic.py check view_front.png view_back.png [--reference ref_front.png ...] [--rubric r.json]
  python scripts/render_critic.py eval <set_dir> --out results.jsonl [--reference-root <dir>] [--limit N]
  python scripts/render_critic.py score results.jsonl [--threshold 0.5]
  python scripts/render_critic.py serve --exe <llama-server.exe> --model <gguf> --mmproj <gguf> [--port 8290]

The answer is constrained to a JSON schema: a list of at most four defects, each a rubric type, region, confidence and
one short evidence phrase (an empty list means no defect). A list keeps output short: generation dominates the cost on a
local GPU. `check` prints that JSON; `eval` runs it over a `scripts/critic_defect_scene.py` set and `score` reports precision and
recall per category. Trust only categories whose measured precision held; see docs/research/LOCAL-RENDER-CRITIC.md.
The HTTP client is stdlib; reference pixel comparison also uses Pillow. The model server exposes
OpenAI-compatible `/v1/chat/completions`.
"""
import argparse, base64, json, re, subprocess, sys, time, urllib.request
from pathlib import Path

DEFAULT_SERVER = "http://127.0.0.1:8290"
VIEWS = ("front", "left", "back", "right")
RUBRIC = {
    "missing_texture": "A surface shows the bright magenta/pink 'missing texture' colour, or a flat placeholder where a "
                       "pattern or image texture belongs.",
    "omitted_mesh": "A part that should exist is absent: e.g. a missing hand, eye, arm, leg or head (compare with its "
                    "mirror partner and with the other views). Stylised models are deliberately simple: details absent "
                    "on both sides by design (no nose, no mouth) are not omissions.",
    "material_swap": "Materials are on the wrong parts: e.g. skin colour on clothing, a shirt pattern on the head or "
                     "legs, trouser colour on skin.",
    "flipped_normals": "A part looks inside-out: rendered solid black or hollow while similar parts are lit normally, "
                       "or showing its inner back surface instead of its outside.",
    "broken_weights": "Geometry is stretched into spikes, shards or smeared ribbons, as when skinning weights are wrong "
                      "and vertices follow the wrong bone.",
    "white_material": "A part renders plain flat white with no texture or colour, unlike the rest of the model (a failed "
                      "shader).",
    "asymmetry": "Both parts of a left/right pair (arm, leg, hand, eye) exist but one is clearly bigger, smaller, longer "
                 "or shorter than its partner. A missing partner is omitted_mesh; a different pose or angle is fine.",
    "backside_hole": "A hole in the surface through which the background or the inside of the model shows.",
}
REGIONS = ("none", "head", "face", "left_eye", "right_eye", "torso", "left_arm", "right_arm", "left_hand", "right_hand",
           "left_leg", "right_leg", "feet", "whole")


def schema(rubric):
    defect = {"type": "object", "additionalProperties": False, "required": ["type", "region", "confidence", "evidence"],
              "properties": {"type": {"type": "string", "enum": list(rubric)}, "region": {"type": "string", "enum": list(REGIONS)},
                             "confidence": {"type": "number"}, "evidence": {"type": "string", "maxLength": 120}}}
    return {"type": "object", "additionalProperties": False, "required": ["defects"],
            "properties": {"defects": {"type": "array", "items": defect, "maxItems": 4}}}


def _image(path):
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()}}


def _label(path):
    m = re.fullmatch(r"view_([a-z]+)", Path(path).stem); return m.group(1) if m else Path(path).stem


def messages(images, rubric, reference=()):
    checklist = "\n".join(f"- {k}: {v}" for k, v in rubric.items())
    task = ("You are a strict technical QA checker for 3D renders. Judge technical defects only, never style or taste. "
            "The views show one 3D model; 'left'/'right' views and regions mean the model's own left and right "
            "(in the front view the model's left is on the image right). Each view shows a different side, so a "
            "feature seen from one side only (a face, a chest emblem) is normal.\n")
    content = []
    if reference:
        task += ("The REFERENCE views are an approved render of the same model. Report a defect only if it is in the "
                 "CANDIDATE and not in the REFERENCE; small noise or lighting differences are not defects.\n")
        for p in reference: content += [{"type": "text", "text": f"REFERENCE {_label(p)} view:"}, _image(p)]
        prefix = "CANDIDATE "
    else: prefix = ""
    for p in images: content += [{"type": "text", "text": f"{prefix}{_label(p)} view:"}, _image(p)]
    content.append({"type": "text", "text": task + "Check the views against every defect type below. List each defect you "
                    "can see with its type, region, your confidence 0-1 and a short evidence phrase; return an empty "
                    "list if the model has none of them.\n" + checklist})
    return [{"role": "user", "content": content}]


# Measured on 2 Nov: 4.5 vs 5.4 renders of one scene differ in at most 2 px over level 8; the smallest seeded defect
# changed 171 px. Recalibrate both for other scenes, samplers or denoisers.
DIFF_LEVEL, DIFF_MIN_PX = 8, 20


class ReferenceEvidenceError(ValueError):
    """The supplied reference evidence cannot support a pixel comparison."""


def _view_map(paths, role):
    mapped = {}
    for path in paths:
        label = _label(path)
        if label in mapped: raise ReferenceEvidenceError(f"duplicate {role} view label: {label}")
        mapped[label] = path
    if not mapped: raise ReferenceEvidenceError(f"no {role} views")
    return mapped


def _rgba8(image):
    """Reject lossy sample conversion before decoding. This is decoded-value QA, not colour-managed comparison."""
    if getattr(image, "n_frames", 1) != 1: raise ReferenceEvidenceError("multi-frame evidence is not supported")
    if image.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
        raise ReferenceEvidenceError(f"unsupported evidence mode {image.mode}; use an explicitly converted 8-bit copy")
    if image.format not in ("PNG", "TIFF", "JPEG", "WEBP", "GIF", "BMP"):
        raise ReferenceEvidenceError(f"unqualified evidence container {image.format}; use an explicitly converted 8-bit PNG copy")
    if image.format == "TIFF" and any(bits > 8 for bits in image.tag_v2.get(258, (1,))):
        raise ReferenceEvidenceError("high-bit TIFF evidence is not supported; convert a copy explicitly")
    if image.format == "JPEG" and getattr(image, "bits", 8) > 8:
        raise ReferenceEvidenceError("high-bit JPEG evidence is not supported; convert a copy explicitly")
    if image.format == "PNG":
        # PNG RGB16/RGBA16 is exposed as RGB/RGBA by Pillow, so checking image.mode alone loses low bits.
        position = image.fp.tell()
        try:
            image.fp.seek(0); header = image.fp.read(29)
        finally: image.fp.seek(position)
        if header[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" or len(header) != 29:
            raise ReferenceEvidenceError("noncanonical PNG header")
        if header[24] not in (1, 2, 4, 8):
            raise ReferenceEvidenceError("high-bit PNG evidence is not supported; retain the original and convert a copy explicitly")
    return image.convert("RGBA")


def _pixel_observations(images, reference, level):
    from PIL import Image, ImageChops
    if type(level) is not int or not 0 <= level <= 255: raise ValueError("pixel level must be an integer from 0 to 255")
    candidates, refs = _view_map(images, "candidate"), _view_map(reference, "reference")
    if candidates.keys() != refs.keys():
        raise ReferenceEvidenceError(f"view sets differ: candidate missing {sorted(refs.keys() - candidates.keys())}; "
                                     f"reference missing {sorted(candidates.keys() - refs.keys())}")
    out, sizes = {}, {}
    for label, p in candidates.items():
        with Image.open(p) as a_raw, Image.open(refs[label]) as b_raw:
            a, b = _rgba8(a_raw), _rgba8(b_raw)
        sizes[label] = {"candidate": list(a.size), "reference": list(b.size)}
        if a.size != b.size:  # ImageChops compares only the overlap; never clear a size mismatch.
            out[label] = {"changed_px": a.width * a.height, "bbox": (0, 0) + a.size, "size_mismatch": [a.size, b.size]}; continue
        channels = ImageChops.difference(a, b).split(); peak = channels[0]
        for channel in channels[1:]: peak = ImageChops.lighter(peak, channel)
        mask = peak.point(lambda x: 255 if x > level else 0)
        out[label] = {"changed_px": mask.histogram()[255], "bbox": mask.getbbox()}
    return out, sizes


def pixel_diff(images, reference, level=DIFF_LEVEL):
    """Complete, unique label-matched RGBA8 evidence; unsupported precision/animation is an error, not a match."""
    return _pixel_observations(images, reference, level)[0]


def check(images, rubric=RUBRIC, reference=(), server=DEFAULT_SERVER, timeout=600, max_tokens=1500, diff_only=False):
    """With a reference, a pixel diff decides whether anything changed and the model only names what changed; an
    unchanged candidate never reaches the model, which removes its false alarms on clean renders. (diff_only=None is
    the internal 'gate passed' call.)"""
    if not images: raise ValueError("no candidate views")
    if diff_only is True and not reference: raise ValueError("diff_only requires reference views")
    if reference and diff_only is not None:
        policy = {"level": DIFF_LEVEL, "min_pixels": DIFF_MIN_PX, "channels": "decoded-RGBA8", "colour_management": "none"}
        try:
            diff, sizes = _pixel_observations(images, reference, DIFF_LEVEL)
        except ReferenceEvidenceError as exc:
            # Existing bool consumers remain conservative; scorer/evaluate recognise error rows, never clean negatives.
            return {"defects": [], "pixel_diff": {}, "view_sizes": {}, "changed": True, "model": None,
                    "evidence_complete": False, "error": str(exc), "pixel_policy": policy}
        changed = (sum(v["changed_px"] for v in diff.values()) >= DIFF_MIN_PX
                   or any("size_mismatch" in v for v in diff.values()))
        receipt = {"pixel_diff": diff, "view_sizes": sizes, "changed": changed, "evidence_complete": True, "pixel_policy": policy}
        if diff_only or not changed: return dict(receipt, defects=[], model=None)
        return dict(check(images, rubric, reference, server, timeout, max_tokens, diff_only=None), **receipt)
    body = {"messages": messages(images, rubric, reference), "temperature": 0, "max_tokens": max_tokens, "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "critique", "schema": schema(rubric)}}}
    req = urllib.request.Request(server.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r: resp = json.load(r)
    out = json.loads(resp["choices"][0]["message"]["content"])
    return {"defects": out["defects"], "wall_s": round(time.perf_counter() - t, 3), "timings": resp.get("timings", {}),
            "model": resp.get("model")}


def views(sample_dir): return [Path(sample_dir) / f"view_{v}.png" for v in VIEWS if (Path(sample_dir) / f"view_{v}.png").exists()]


def evaluate(set_dir, out, rubric=RUBRIC, reference_root=None, server=DEFAULT_SERVER, limit=None):
    """Run `check` over every sample dir with a truth.json; with reference_root, compare against <root>/clean-<seed>.

    A sample that would be its own reference is skipped; for clean negatives with real parity noise, point set_dir at
    clean renders from another Blender build and reference_root at the original set. Appends JSON lines to `out` and
    skips sample ids already in it, so an interrupted run resumes."""
    out = Path(out); done = set()
    if out.exists(): done = {r["id"] for r in map(json.loads, filter(str.strip, out.read_text(encoding="utf-8").splitlines())) if "error" not in r}
    samples = sorted(p.parent for p in Path(set_dir).glob("*/truth.json"))
    n = 0
    for d in samples:
        if d.name in done: continue
        if limit is not None and n >= limit: break
        truth = json.loads((d / "truth.json").read_text(encoding="utf-8"))
        ref_dir = Path(reference_root) / f"clean-{truth['seed']}" if reference_root else None
        if ref_dir and ref_dir.resolve() == d.resolve(): continue
        ref = views(ref_dir) if ref_dir else ()
        try:
            # A sample or reference with missing views would silently drop them (or fall back to reference-free).
            if len(views(d)) < len(VIEWS) or (ref_dir and len(ref) < len(VIEWS)): raise FileNotFoundError(f"missing views for {d.name}")
            r = check(views(d), rubric, ref, server)
        except Exception as e: r = {"error": repr(e)}
        r.update(id=d.name, truth=truth, reference=bool(ref))
        with out.open("a", encoding="utf-8") as f: f.write(json.dumps(r) + "\n")
        n += 1; print(d.name, r.get("wall_s"), "ERROR" if "error" in r else "", flush=True)


def load_rows(path):
    """Result rows, last row per sample id: a resumed run's retry replaces the earlier error row."""
    return list({r["id"]: r for r in map(json.loads, filter(str.strip, Path(path).read_text(encoding="utf-8").splitlines()))}.values())


FAMILY = {"arm": "arm", "hand": "hand", "leg": "leg", "eye": "eye", "shoe": "feet", "head": "head", "torso": "torso"}
MATERIAL_REGIONS = {"shirt": {"torso", "arm"}, "pants": {"leg"}, "skin": {"head", "face", "hand", "whole"}}


def accepted_regions(truth):
    """Region families that count as a correct localisation of a seeded defect."""
    part = truth.get("part") or ""
    if truth["category"] in ("material_swap", "white_material", "missing_texture"):
        fam = set().union(*(MATERIAL_REGIONS.get(p, set()) for p in re.split(r"\+", part.replace("arms", "arm"))))
        return fam | ({"torso", "arm"} if "torso" in part else set()) | {"whole"}
    return {FAMILY.get(part.split(".")[0], part.split(".")[0])} | ({"face", "head"} if part.startswith("eye") else set())


def region_family(region): return region.split("_", 1)[1] if region.startswith(("left_", "right_")) else region


def score(rows, rubric=RUBRIC, threshold=0.0):
    """Per-category confusion over samples; a verdict counts as positive when present and confidence >= threshold.

    A seeded sample is positive only for its own category; every other category on it, and all on clean samples, are
    negatives, so cross-category false alarms count against precision."""
    stats = {k: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "region_ok": 0, "side_ok": 0, "side_n": 0} for k in rubric}
    detect = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}; errors = 0
    for r in rows:
        if "error" in r: errors += 1; continue
        t = r["truth"]
        found = {}
        for d in r["defects"]:  # keep the most confident report per type
            c = float(d.get("confidence", 1))
            if c >= threshold and c >= float(found.get(d["type"], {}).get("confidence", -1)): found[d["type"]] = d
        # Sample level: anything wrong, whatever the label. In reference mode the pixel gate decides that, not the model.
        flagged, defective = r.get("changed", bool(found)), t["category"] != "clean"
        detect["tp" if flagged and defective else "fp" if flagged else "fn" if defective else "tn"] += 1
        for k in rubric:
            v = found.get(k, {}); pred = bool(v)
            actual = t["category"] == k; s = stats[k]
            s["tp" if pred and actual else "fp" if pred else "fn" if actual else "tn"] += 1
            if pred and actual:
                reg = v.get("region", "none"); s["region_ok"] += region_family(reg) in accepted_regions(t)
                if t.get("side"):  # a region without a side (e.g. face for an eye) counts as a side miss
                    s["side_n"] += 1; s["side_ok"] += reg.startswith("left_" if t["side"] == "L" else "right_")
    for s in list(stats.values()) + [detect]:
        s["precision"] = round(s["tp"] / (s["tp"] + s["fp"]), 3) if s["tp"] + s["fp"] else None
        s["recall"] = round(s["tp"] / (s["tp"] + s["fn"]), 3) if s["tp"] + s["fn"] else None
    return {"categories": stats, "detection": detect, "samples": len(rows), "errors": errors, "threshold": threshold}


def table(summary):
    lines = ["| category | TP | FP | FN | precision | recall | region ok | side ok |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k, s in summary["categories"].items():
        lines.append(f"| {k} | {s['tp']} | {s['fp']} | {s['fn']} | {s['precision']} | {s['recall']} | "
                     f"{s['region_ok']}/{s['tp']} | {s['side_ok']}/{s['side_n']} |")
    d = summary["detection"]
    lines.append(f"| **any defect (sample level)** | {d['tp']} | {d['fp']} | {d['fn']} | {d['precision']} | {d['recall']} | | |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("images", nargs="+"); c.add_argument("--reference", nargs="*", default=())
    c.add_argument("--diff-only", action="store_true", help="with --reference: pixel diff only, no model call")
    e = sub.add_parser("eval"); e.add_argument("set_dir"); e.add_argument("--out", required=True)
    e.add_argument("--reference-root"); e.add_argument("--limit", type=int)
    s = sub.add_parser("score"); s.add_argument("results"); s.add_argument("--threshold", type=float, default=0.0)
    v = sub.add_parser("serve"); v.add_argument("--exe", required=True); v.add_argument("--model", required=True)
    v.add_argument("--mmproj", required=True); v.add_argument("--port", type=int, default=8290); v.add_argument("--ctx", type=int, default=8192)
    v.add_argument("--device", required=True, help="one llama.cpp device, e.g. Vulkan0 or ROCm0 (see llama-server --list-devices)")
    for p in (c, e): p.add_argument("--rubric"); p.add_argument("--server", default=DEFAULT_SERVER)
    a = ap.parse_args(argv)
    rubric = json.loads(Path(a.rubric).read_text(encoding="utf-8")) if getattr(a, "rubric", None) else RUBRIC
    if a.cmd == "check": print(json.dumps(check(a.images, rubric, a.reference, a.server, diff_only=a.diff_only), indent=1))
    elif a.cmd == "eval": evaluate(a.set_dir, a.out, rubric, a.reference_root, a.server, a.limit)
    elif a.cmd == "score":
        rows = load_rows(a.results)
        summary = score(rows, threshold=a.threshold); print(table(summary))
        print(json.dumps({k: v for k, v in summary.items() if k not in ("categories", "detection")}))
    elif a.cmd == "serve":
        # Loopback only, one slot (requests are sequential), every layer on ONE named device: the Vulkan build also sees
        # the Intel iGPU and by default splits layers across both, which ran generation at ~1 token/s here.
        sys.exit(subprocess.call([a.exe, "-m", a.model, "--mmproj", a.mmproj, "--host", "127.0.0.1", "--port", str(a.port),
                                  "-c", str(a.ctx), "-ngl", "999", "-np", "1", "--no-webui", "--device", a.device,
                                  "--load-mode", "none"]))  # no mmap: weights live in VRAM, not 17 GB of host RAM


if __name__ == "__main__":
    main()
