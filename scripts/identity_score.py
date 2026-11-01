#!/usr/bin/env python3
"""Measure how close renders are to a reference character with CCIP. Lower is closer.

Needs its own environment, never the shared ComfyUI runtime:
    py -3.12 -m venv C:/AI/agent-tools/identity
    C:/AI/agent-tools/identity/Scripts/pip install dghs-imgutils==0.19.0 onnxruntime==1.31.1

    C:/AI/agent-tools/identity/Scripts/python scripts/identity_score.py reference.png render1.png render2.png
    ... --group "rg([0-9.]+)_"   # also report the mean per regex capture

CCIP is trained on illustrations. It measures character identity only: it barely moves for changes of form, so a good
score does not mean better art, and renders of 3D models read further away than the same character drawn. Publish the
threshold beside any score; it belongs to the CCIP model snapshot, deepghs/ccip_onnx `eb2acdd2` as of 1 November 2026.
Calibrate with an unrelated character when a number will decide something.
"""
import argparse, json, re, statistics, sys


def group_means(scores, pattern):
    groups = {}
    for path, value in scores.items():
        match = re.search(pattern, path)
        if match: groups.setdefault(match.group(1), []).append(value)
    return {key: {"n": len(values), "mean": round(statistics.mean(values), 4), "min": min(values), "max": max(values)} for key, values in groups.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reference")
    parser.add_argument("renders", nargs="+")
    parser.add_argument("--group", help="regex with one capture; report the mean per capture")
    args = parser.parse_args()
    from imgutils.metrics import ccip_batch_differences, ccip_default_threshold, ccip_extract_feature
    reference = ccip_extract_feature(args.reference)
    scores = {path: round(float(ccip_batch_differences([reference, ccip_extract_feature(path)])[0, 1]), 4) for path in args.renders}
    result = {"threshold": ccip_default_threshold(), "scores": scores}
    if args.group: result["groups"] = group_means(scores, args.group)
    json.dump(result, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
