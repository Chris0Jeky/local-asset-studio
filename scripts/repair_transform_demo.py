"""Create a synthetic scaled repair packet and composite; no model or native app."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_edit_demo import create as create_fixture
from scripts.character_edit import make_plan
from scripts.character_study import file_sha, read_json, sha, write_json
from scripts import repair_source as source, repair_pixel_transforms as pixels


def create(root):
    create_fixture(root)  # Refuses an existing directory; originals remain intact.
    source.capture(root / 'source.png', root / 'normalized-source')
    plan = read_json(root / 'plan.json')
    plan['document']['source'] = {'path': 'normalized-source/normalized.png',
                                'sha256': file_sha(root / 'normalized-source/normalized.png')}
    plan['intent']['document_sha256'] = sha(plan['document'])
    plan = make_plan(plan['document'], plan['intent'], plan['catalog'])
    write_json(root / 'transform-plan.json', plan)
    request = {'schema': pixels.REQUEST_SCHEMA, 'plan_sha256': plan['plan_sha256'],
               'source_packet': {'path': 'normalized-source',
                   'receipt_sha256': file_sha(root / 'normalized-source/receipt.json'),
                   'normalized_sha256': plan['document']['source']['sha256']},
               'authored_write': plan['intent']['edit_mask'], 'protection': plan['intent']['protect_mask'],
               'transform': {'version': pixels.VERSION, 'box': plan['intent']['context_box'],
                             'scale': [3, 2], 'padding': [2, 1, 3, 1], 'alignment': 1}}
    write_json(root / 'transform-request.json', request)
    bundle = pixels.prepare(root, plan, request, 'scaled-context')
    candidate = Image.new('RGBA', tuple(bundle['geometry']['work_size']), (211, 35, 79, 127))
    candidate.save(root / 'scaled-candidate.png')
    result = pixels.apply(root, plan, request, 'scaled-context',
        {'path': 'scaled-candidate.png', 'sha256': file_sha(root / 'scaled-candidate.png')}, 'scaled-result')
    proof = Image.new('RGB', (1160, 286), 'white'); draw = ImageDraw.Draw(proof)
    for x, name, label in ((0, 'normalized-source/normalized.png', 'Original synthetic source'),
                            (390, 'scaled-context/context.png', 'Prepared context'),
                            (550, 'scaled-candidate.png', 'Supplied test pixels'),
                            (776, 'scaled-result/result.png', 'Protected composite')):
        draw.text((x + 4, 4), label, fill='black')
        with Image.open(root / name) as image: proof.paste(image.convert('RGB'), (x, 25))
    proof.save(root / 'scaled-comparison.png')
    return {'schema': 'studio.repair-transform-demo/v1', 'fixture': 'synthetic_cpu_only',
            'request_file_sha256': file_sha(root / 'transform-request.json'),
            'changed_pixels': result['changed_pixels'], 'outside_mask_changed_pixels': result['outside_mask_changed_pixels'],
            'protected_changed_pixels': result['protected_changed_pixels'], 'neural_inference': False,
            'semantic_approval': False, 'comparison': str(root / 'scaled-comparison.png')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try: print(json.dumps(create(args.out), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc: parser.exit(2, f'repair-transform-demo: {exc}\n')
