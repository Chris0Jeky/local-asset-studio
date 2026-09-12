"""Create procedural pixels plus deliberately fabricated recipe claims; no inference."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio_prompt.recipe_intake import inspect_media


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New directory; existing directories are never overwritten')
    args = parser.parse_args(argv)
    graph = json.loads(Path(__file__).with_name('graph.json').read_text(encoding='utf-8'))
    recorded = json.dumps(graph, sort_keys=True).encode('ascii')
    rows = b''.join(b'\0' + b''.join(bytes((40 + x * 20, 40 + y * 20, 100, 255)) for x in range(8)) for y in range(8))
    raw = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 6, 0, 0, 0))
           + chunk(b'tEXt', b'prompt\0' + recorded) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
    alternate = copy.deepcopy(graph)
    alternate['positive']['inputs']['text'] = 'CONFLICTING SIDECAR: a different costume.'
    sidecar = {'schema_version': 1, 'image_sha256': hashlib.sha256(raw).hexdigest(),
               'producer': {'name': 'Synthetic recipe-inspection demo (not Comfy execution)', 'version': '1'},
               'entries': [{'keyword': 'prompt', 'value': json.dumps(alternate, sort_keys=True)}]}
    sidecar_bytes = json.dumps(sidecar, indent=2).encode('utf-8') + b'\n'
    reports = {'source-report.json': inspect_media(raw),
               'selected-report.json': inspect_media(raw, output_node='final'),
               'conflict-report.json': inspect_media(raw, sidecar_bytes),
               'sidecar-only-report.json': inspect_media(sidecar_bytes)}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'source.png').write_bytes(raw)
    (args.output / 'source.sidecar.json').write_bytes(sidecar_bytes)
    for name, value in reports.items():
        (args.output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'image_sha256': sidecar['image_sha256'],
                      'files': 6, 'generation_submitted': False}))


if __name__ == '__main__': main()
