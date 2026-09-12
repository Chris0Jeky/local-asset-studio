"""CLI for versioned AV edits, plans, QC and explicitly requested CPU rendering."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_av.project import read_json, write_new, validate, edit, safe_path
from studio_av.render import compile_project, render, inspect_wav

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ('validate','plan','render'):
        c=sub.add_parser(name);c.add_argument('project');c.add_argument('--workspace',required=True)
        if name=='render':c.add_argument('--out',required=True)
    c=sub.add_parser('edit');c.add_argument('project');c.add_argument('--expected',required=True);c.add_argument('--section',required=True);c.add_argument('--clip',required=True);c.add_argument('--field',required=True);c.add_argument('--value',required=True,help='JSON value');c.add_argument('--out',required=True)
    c=sub.add_parser('audio-qc');c.add_argument('path');c.add_argument('--workspace',required=True)
    a=p.parse_args()
    try:
        if a.command=='audio-qc': result=inspect_wav(safe_path(a.workspace,a.path))
        else:
            project=read_json(a.project)
            if a.command=='validate':result=validate(project,a.workspace)
            elif a.command=='plan':result=compile_project(project,a.workspace)
            elif a.command=='render':result=render(project,a.workspace,a.out)
            else:
                result=edit(project,a.expected,a.section,a.clip,a.field,json.loads(a.value));write_new(a.out,result['project'])
        print(json.dumps(result,indent=2,allow_nan=False));return 0
    except Exception as exc:
        print(json.dumps({'error':str(exc),'type':type(exc).__name__}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
