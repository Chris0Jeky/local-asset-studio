#!/usr/bin/env python3
"""Local pose import/correction/export. No Studio or ComfyUI connection."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studio_workflow import pose_artifact as pose


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def read(path):
    with Path(path).open('rb') as source:
        return source.read(pose.MAX_BYTES + 1)


def main(argv=None):
    try:
        parser = Parser(description=__doc__)
        commands = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
        for command in ('import', 'inspect', 'revise', 'export-json', 'render'):
            sub = commands.add_parser(command); sub.add_argument('source', type=Path)
            if command != 'inspect': sub.add_argument('--out', type=Path, required=True)
            if command == 'import':
                sub.add_argument('--width', type=int, required=True); sub.add_argument('--height', type=int, required=True)
                sub.add_argument('--coordinate-space', choices=('pixels', 'normalized'), required=True)
                sub.add_argument('--person-index', type=int)
            if command == 'revise':
                sub.add_argument('--expected-id', required=True); sub.add_argument('--edits', type=Path, required=True)
            if command in ('render', 'export-json'): sub.add_argument('--threshold', type=float, default=.3)
        args = parser.parse_args(argv)
        raw = read(args.source)
        if args.command == 'import':
            a = pose.import_openpose(raw, width=args.width, height=args.height,
                                     coordinate_space=args.coordinate_space, person_index=args.person_index)
        else: a = pose.validate(pose.loads(raw))
        if args.command == 'revise': a = pose.revise(a, args.expected_id, pose.loads(read(args.edits)))
        threshold = getattr(args, 'threshold', .3)
        native = pose.export_openpose(a, threshold)
        report = dict(id=a['id'], authority='none', generation_submitted=False, review=a['review'],
                      canvas=a['canvas'], missing_joints=[k for k, v in a['joints'].items() if v is None],
                      filtered_joints=[k for k, v in a['joints'].items() if v is not None and
                                       v['origin'] == 'estimated' and v['confidence'] < threshold],
                      manual_joints=[k for k, v in a['joints'].items() if v is not None and v['origin'] == 'manual'])
        if args.command == 'inspect':
            report['artifact'] = a
        else:
            if args.command == 'render':
                from studio_workflow.pose_raster import RENDERER, render_png
                payload = render_png(a, threshold); report['renderer'] = RENDERER
                report['native_control_qualified'] = False
            else:
                payload = pose.canonical(native if args.command == 'export-json' else a) + b'\n'
            if args.command in ('render', 'export-json'):
                report['threshold'] = threshold; report['manual_confidence_is_presence_sentinel'] = True
            with args.out.open('xb') as output:
                output.write(payload)
            report['output_sha256'] = hashlib.sha256(payload).hexdigest()
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps(dict(error=str(exc), authority='none', generation_submitted=False)), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
