"""Small agent client for the same prompt-project commands; writes never retry."""
from __future__ import annotations
import argparse
from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.error import HTTPError
from studio_workflow.client import Client,ClientError,read_response
from .schema import decode,need,read_json,write_new
from .projects import REQUEST_LIMIT,bounded

PREFIX='/api/prompt/projects/'


class PromptProjectClient(Client):
    def _call(self,path,body=None):
        if body is not None:bounded(body,REQUEST_LIMIT)
        try:return self.request(PREFIX+path,body)
        except HTTPError as error:
            with error:raw=read_response(error,1024*1024)
            try:result=decode(raw)
            except ValueError:result={'error':'Studio returned an unreadable error response'}
            raise ClientError(error.code,result) from error
    def capabilities(self):return self._call('capabilities')
    def list(self,workspace_id):return self._call('list?'+urlencode({'workspace_id':workspace_id}))
    def get(self,workspace_id,key,revision=None):
        params={'workspace_id':workspace_id,'id':key}
        if revision is not None:params['revision']=revision
        return self._call('read?'+urlencode(params))
    def history(self,workspace_id,key,before=None):
        params={'workspace_id':workspace_id,'id':key}
        if before is not None:params['before']=before
        return self._call('history?'+urlencode(params))
    def status(self,workspace_id,request_id):return self._call('status?'+urlencode({'workspace_id':workspace_id,'request_id':request_id}))
    def command(self,action,value):
        need(action in ('create','save','restore'),'Unknown prompt project command');return self._call(action,value)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Read or explicitly save a shared Prompt Lab document; no model calls.')
    parser.add_argument('--base',default='http://127.0.0.1:8191');parser.add_argument('--output',type=Path)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('capabilities')
    for action in ('list','read','history','status'):
        part=sub.add_parser(action);part.add_argument('--workspace-id',required=True)
        if action in ('read','history'):part.add_argument('--id',required=True)
        if action=='read':part.add_argument('--revision',type=int)
        if action=='history':part.add_argument('--before',type=int)
        if action=='status':part.add_argument('--request-id',required=True)
    for action in ('create','save','restore'):sub.add_parser(action).add_argument('--request',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output:need(not args.output.exists() and args.output.parent.is_dir(),'Output must be a new file in an existing directory')
        client=PromptProjectClient(args.base)
        if args.action=='capabilities':result=client.capabilities()
        elif args.action=='list':result=client.list(args.workspace_id)
        elif args.action=='read':result=client.get(args.workspace_id,args.id,args.revision)
        elif args.action=='history':result=client.history(args.workspace_id,args.id,args.before)
        elif args.action=='status':result=client.status(args.workspace_id,args.request_id)
        else:result=client.command(args.action,read_json(args.request))
        if args.output:write_new(args.output,result)
        else:print(json.dumps(result,ensure_ascii=True))
        return 0
    except (ValueError,KeyError,TypeError,RecursionError,OSError,HTTPException) as error:
        print(json.dumps({'error':str(error),'code':getattr(error,'code','client_error'),'replayed':False}),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
