"""Extend the existing synthetic transform demo with a verifiable scope review."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))


def create(root):
    from scripts.repair_transform_demo import create as transform_demo
    from scripts.character_study import read_json
    from scripts.repair_scope_review import create_review, verify_review
    proof = transform_demo(root)
    plan = read_json(root/'transform-plan.json'); request = read_json(root/'transform-request.json')
    report = create_review(root, plan, request, 'scaled-context', 'scope-review')
    verify_review(root, plan, request, 'scaled-context', 'scope-review')
    return {**proof, 'scope_review': str(root/'scope-review/scope-review.html'),
            'scope_packet_verified': True, 'expected_effective_write_sha256': report['expected_effective_write_sha256'],
            'neural_inference': False, 'semantic_approval': False, 'review_state': 'unreviewed'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try: print(json.dumps(create(args.out), ensure_ascii=True, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc: parser.exit(2, f'repair-scope-demo: {exc}\n')
