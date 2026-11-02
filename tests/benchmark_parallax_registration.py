"""Manual exact-equivalence benchmark; excluded from unittest discovery.

Run with the full-suite allocation instrumentation:
    python -X tracemalloc=1 tests/benchmark_parallax_registration.py --out .runtime/parallax-cost/benchmark.json
"""
import argparse
import hashlib
import json
import math
import platform
import time
import tracemalloc
from pathlib import Path
from unittest.mock import patch

import PIL
from PIL import Image

from test_parallax import WINDOW, klein, parallax, room, speckle
from test_parallax_registration_cost import histogram_search, noise


def digest(value):
    return hashlib.sha256(value).hexdigest()


def compact(value):
    if isinstance(value, bytes): return {"bytes": len(value), "sha256": digest(value)}
    if isinstance(value, dict): return {key: compact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [compact(item) for item in value]
    return value


def encoded(value):
    return json.dumps(compact(value), sort_keys=True, separators=(",", ":")).encode()


def picture(image):
    return {"mode": image.mode, "size": list(image.size), "pixels": image.tobytes(), "png": parallax.png_bytes(image)}


def register_picture(source, edit, background):
    registered, record = parallax.register(source, edit, background)
    try: return {"record": record, "images": {"registered": picture(registered)}}
    finally: registered.close()


def split_pictures(source, plate, isolate):
    registered_plate, plate_record = parallax.register(source, plate, source)
    registered_isolate, isolate_record = parallax.register(source, isolate, (255, 255, 255))
    images = {"plate_registered": registered_plate, "isolate_registered": registered_isolate}
    try:
        layers, record = parallax.layers(source, registered_plate, registered_isolate, parallax._polygons([WINDOW], *source.size))
        images.update(layers); record["registration"] = {"plate": plate_record, "isolate": isolate_record}
        return {"record": record, "images": {name: picture(image) for name, image in images.items() if image is not None}}
    finally:
        for image in images.values():
            if image is not None: image.close()


def full_search_windows(other):
    results = []
    for index in range(parallax.REGISTRATION["max_patches"]):
        x, y = 40 + index % 8, 40 + index // 8
        for side, radius in [(parallax.REGISTRATION["patch_px"] // 4, math.ceil(parallax.REGISTRATION["max_shift_px"] / 4)),
                             (parallax.REGISTRATION["patch_px"], 3)]:
            best, costs = parallax._search(other.crop((x, y, x + side, y + side)), other, x, y, (0, 0), radius)
            results.append([best, list(costs.items())])
    return results


def measure(run, inputs, search):
    before = [digest(image.tobytes()) for image in inputs]; searches = []; histograms = 0
    original_histogram = Image.Image.histogram

    def counted(image, *args, **kwargs):
        nonlocal histograms
        histograms += 1
        return original_histogram(image, *args, **kwargs)

    def observed(patch_image, other, x, y, centre, radius):
        best, costs = search(patch_image, other, x, y, centre, radius)
        searches.append({"patch": list(patch_image.size), "origin": [x, y], "centre": list(centre), "radius": radius,
                         "best": best, "candidates": len(costs), "ordered_scores_sha256": digest(encoded(list(costs.items())))})
        return best, costs

    started = time.perf_counter()
    with patch.object(parallax, "_search", observed), patch.object(Image.Image, "histogram", counted): output = run()
    seconds = time.perf_counter() - started
    if before != [digest(image.tobytes()) for image in inputs]: raise AssertionError("a benchmark input image was modified")
    return output, searches, {"seconds": seconds, "histograms": histograms, "input_sha256": before}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--out", type=Path, required=True); args = parser.parse_args()
    source, plate, isolate = room(); shifted_plate = klein(plate, fill=None); shifted_isolate = klein(isolate, 1.012, -4, -1, fill=(255, 255, 255))
    unrelated = speckle((640, 640), 99); flat = Image.new("RGB", source.size, "white"); search_image = noise((144, 144), 1910)
    # The largest 1536-wide multiple-of-16 canvas below the existing 1,600,000-pixel bound.
    largest_size = (parallax.SIZE_LIMITS[1], (parallax.MAX_PIXELS // parallax.SIZE_LIMITS[1] // parallax.SIZE_MULTIPLE) * parallax.SIZE_MULTIPLE)
    largest = speckle(largest_size, 1219); largest_edit = klein(largest)
    cases = [
        ("all_48_coarse_and_fine_searches", [search_image], lambda: full_search_windows(search_image)),
        ("shifted_room_split", [source, shifted_plate, shifted_isolate], lambda: split_pictures(source, shifted_plate, shifted_isolate)),
        ("unchanged_room_split", [source, plate, isolate], lambda: split_pictures(source, plate, isolate)),
        ("unrelated_resized_fallback", [source, unrelated], lambda: register_picture(source, unrelated, source)),
        ("flat_fallback", [flat], lambda: register_picture(flat, flat, flat)),
        ("largest_bounded_canvas", [largest, largest_edit], lambda: register_picture(largest, largest_edit, largest)),
    ]
    report = {"python": platform.python_version(), "pillow": PIL.__version__, "tracemalloc_frames": tracemalloc.get_traceback_limit() if tracemalloc.is_tracing() else 0,
              "registration_settings": dict(parallax.REGISTRATION), "largest_canvas": list(largest_size), "cases": [],
              "timing_scope": "Single local observation per method/case, including identical trace digests and PNG encoding; no latency guarantee or CI threshold."}
    production_search = parallax._search
    for index, (name, inputs, run) in enumerate(cases):
        results = {}; order = ("histogram", "bytes") if index % 2 == 0 else ("bytes", "histogram")
        for method in order:
            results[method] = measure(run, inputs, histogram_search if method == "histogram" else production_search)
            print(json.dumps({"case": name, "method": method, **results[method][2]}), flush=True)
        baseline, current = results["histogram"], results["bytes"]
        if baseline[0] != current[0]: raise AssertionError(name + ": output pixels, PNG bytes or records differ")
        if baseline[1] != current[1]: raise AssertionError(name + ": candidate order, score, winner or search sequence differs")
        if baseline[2]["input_sha256"] != current[2]["input_sha256"]: raise AssertionError(name + ": baseline and current inputs differ")
        receipt = {"case": name, "order": list(order), "baseline": baseline[2], "optimized": current[2], "outputs_equal": True,
                   "searches_equal": True, "inputs_unchanged": True, "output_sha256": digest(encoded(current[0])), "searches": current[1]}
        if isinstance(current[0], dict): receipt["outputs"] = compact(current[0])
        report["cases"].append(receipt)
        args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": len(cases), "out": str(args.out)}), flush=True)


if __name__ == "__main__": main()
