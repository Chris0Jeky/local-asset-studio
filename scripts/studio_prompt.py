"""Compile, inspect or propose. This CLI never submits an asset-generation job."""
from pathlib import Path
import argparse
import http.client
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_prompt.core import read_json,write_new,new_brief,profiles,compile_brief,apply_proposal,bind_graph,experiment_plan
from studio_prompt.metadata import inspect_png,FILE_CAP
from studio_prompt.recipe_intake import inspect_media,TEXT_CAP
from studio_prompt.local_helper import request_payload,run_local


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('profiles')
    c=sub.add_parser('new');c.add_argument('description');c.add_argument('--task',default='image');c.add_argument('--out',required=True)
    for name in ('compile','request-helper','run-helper','experiment'):
        c=sub.add_parser(name);c.add_argument('brief');c.add_argument('--out')
        if name in ('compile','experiment'):c.add_argument('--profile',required=True)
        if name=='experiment':c.add_argument('--seed',action='append',type=int,required=True);c.add_argument('--max-jobs',type=int,default=6)
        if name in ('request-helper','run-helper'):
            c.add_argument('--model',required=True);c.add_argument('--workspace');c.add_argument('--images',action='store_true')
        if name=='run-helper':c.add_argument('--port',type=int,default=11434);c.add_argument('--idle-confirmed',action='store_true');c.add_argument('--cache',action='store_true')
    c=sub.add_parser('inspect-png');c.add_argument('image');c.add_argument('--out')
    c=sub.add_parser('inspect-media');c.add_argument('image');c.add_argument('--out');c.add_argument('--sidecar');c.add_argument('--output-node')
    c=sub.add_parser('apply');c.add_argument('brief');c.add_argument('proposal');c.add_argument('--accept',action='append',required=True);c.add_argument('--out',required=True)
    c=sub.add_parser('bind');c.add_argument('compiled');c.add_argument('graph');c.add_argument('binding');c.add_argument('--out',required=True)
    a=p.parse_args(argv)
    try:
        if a.command=='profiles':value={'profiles':list(profiles().values())}
        elif a.command=='new':value=new_brief(a.description,a.task)
        elif a.command=='inspect-png':
            with Path(a.image).open('rb') as f:value=inspect_png(f.read(FILE_CAP+1))
        elif a.command=='inspect-media':
            with Path(a.image).open('rb') as f:raw=f.read(FILE_CAP+1)
            sidecar=None
            if a.sidecar:
                with Path(a.sidecar).open('rb') as f:sidecar=f.read(TEXT_CAP+1)
            value=inspect_media(raw,sidecar,a.output_node)
        elif a.command=='apply':
            prop=read_json(a.proposal); prop=prop.get('proposal',prop)
            value=apply_proposal(read_json(a.brief),prop,a.accept)['intent']
        elif a.command=='bind':value=bind_graph(read_json(a.compiled),read_json(a.graph),read_json(a.binding))
        else:
            brief=read_json(a.brief)
            if a.command=='compile':value=compile_brief(brief,a.profile)
            elif a.command=='experiment':value=experiment_plan(brief,a.profile,a.seed,a.max_jobs)
            elif a.command=='request-helper':value=request_payload(brief,a.model,a.workspace,a.images)
            else:value=run_local(brief,a.model,a.port,a.workspace,a.images,a.idle_confirmed,a.cache)
        write_new(a.out,value) if getattr(a,'out',None) else print(__import__('json').dumps(value,indent=2,ensure_ascii=False))
        return 0
    except (ValueError,KeyError,TypeError,OSError,RecursionError,http.client.HTTPException) as exc:
        print(__import__('json').dumps({'error':str(exc),'generation_submitted':False}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
