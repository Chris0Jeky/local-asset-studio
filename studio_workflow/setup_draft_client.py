"""Explicit setup authoring and read-only request recovery; never retries writes."""
from __future__ import annotations
import argparse
from http.client import HTTPException
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from .client import ClientError, read_response
from .core import canonical, decode, digest, need
from .commands import identifier
from .setup_drafts import PREFIX,MAX_COMMAND,validate_command


class UnknownSetupOutcome(ValueError):
    def __init__(self,request_id,message):
        self.request_id=request_id
        super().__init__(message+' Inspect request '+request_id+'; no write was retried.')


def validate_record(result):
    need(type(result) is dict and result.get('generation_submitted') is False,'Invalid setup response')
    if 'draft' in result:
        from .setup_proposal import validate_draft
        validate_draft(result['draft']);record=decode(result['record_json'])
        need(digest(record)==result['record_sha256'] and all(record[k]==result[k] for k in ('draft','inputs','runtime'))
             and digest(result['draft'])==result['draft_sha256'],'Setup revision identity does not match its contents')
        need(type(result.get('revision')) is int and type(result.get('head_revision')) is int
             and 1<=result['revision']<=result['head_revision'],'Invalid setup revision')
    if 'receipt_json' in result:
        receipt=decode(result['receipt_json'])
        need(digest(receipt)==result.get('receipt_sha256') and all(result.get(k)==v for k,v in receipt.items()),'Setup receipt does not match its projection')
    return result


class SetupDraftClient:
    def __init__(self,transport):self.transport=transport
    def _request(self,path,value=None):
        try:return self.transport(path,value) if value is not None else self.transport(path)
        except HTTPError as exc:
            try:
                with exc:result=decode(read_response(exc,65536))
            except (ValueError,OSError,HTTPException):result={'error':'Unverified setup error; inspect the original request receipt'}
            raise ClientError(exc.code,result) from exc
    def list(self):return self._request(PREFIX)
    def get(self,key,revision=None):
        path=PREFIX+'/'+identifier(key)
        if revision is not None:
            need(type(revision) is int and 1<=revision<=256,'Invalid setup revision');path+='/revisions/'+str(revision)
        return validate_record(self._request(path))
    def check(self,key,revision):
        need(type(revision) is int and 1<=revision<=256,'Invalid setup revision')
        return validate_record(self._request(PREFIX+'/'+identifier(key)+'/check/'+str(revision)))
    def recover(self,key):
        result=validate_record(self._request(PREFIX+'/requests/'+identifier(key)))
        need(result.get('request_id')==key,'Receipt belongs to another request')
        return result
    def command(self,value):
        q=validate_command(value)
        try:
            r=validate_record(self._request(PREFIX,q))
            need(r.get('request_id')==q['request_id'] and r.get('workspace_id')==q['workspace_id']
                 and r.get('action')==q['action'] and r.get('request_sha256')==digest(q),'Reply belongs to another setup request')
            need(r.get('status') in ('committed','failed','checking','staging','abandoned'),'Unknown setup operation state')
            if q['action']!='create':need(r.get('draft_id')==q['draft_id'],'Reply belongs to another setup draft')
            if r['status']=='committed':
                need('draft' in r and r['revision']==(1 if q['action']=='create' else q['expected_revision']+1),'Committed setup has the wrong revision')
            return r
        except ClientError as exc:
            if exc.status>=500:raise UnknownSetupOutcome(q['request_id'],'Setup server failure may follow a committed write: '+str(exc)) from exc
            raise
        except (ValueError,KeyError,TypeError,OSError,HTTPException) as exc:
            raise UnknownSetupOutcome(q['request_id'],'Setup result is unknown: '+str(exc)) from exc
    def create(self,draft,*,workspace_id,request_id):
        return self.command({'action':'create','workspace_id':workspace_id,'request_id':request_id,'draft':draft})
    def replace(self,key,draft,*,workspace_id,expected_revision,request_id):
        return self.command({'action':'replace','draft_id':key,'workspace_id':workspace_id,'request_id':request_id,'expected_revision':expected_revision,'draft':draft})
    def apply(self,key,proposal,*,workspace_id,expected_revision,request_id):
        return self.command({'action':'apply','draft_id':key,'workspace_id':workspace_id,'request_id':request_id,'expected_revision':expected_revision,
                             'proposal_json':proposal['proposal_json'],'approved_proposal_sha256':proposal['proposal_sha256']})
    def restore(self,key,revision,*,workspace_id,expected_revision,request_id):
        return self.command({'action':'restore','draft_id':key,'workspace_id':workspace_id,'request_id':request_id,'expected_revision':expected_revision,'revision':revision})


def main(argv=None):
    parser=argparse.ArgumentParser(description='Explicit shared setup drafts. Apply copies references but never starts generation.')
    parser.add_argument('--url',default='http://127.0.0.1:8191')
    subs=parser.add_subparsers(dest='action',required=True)
    subs.add_parser('list');subs.add_parser('command').add_argument('file',type=Path)
    subs.add_parser('recover').add_argument('request_id')
    get=subs.add_parser('get');get.add_argument('draft_id');get.add_argument('--revision',type=int)
    args=parser.parse_args(argv);q=None;sent=False
    try:
        from .client import Client
        c=SetupDraftClient(Client(args.url).request)
        if args.action=='command':
            with args.file.open('rb') as stream:raw=stream.read(MAX_COMMAND+1)
            need(len(raw)<=MAX_COMMAND,'Setup command exceeds 1 MiB');q=validate_command(decode(raw));sent=True;r=c.command(q)
        elif args.action=='recover':r=c.recover(args.request_id)
        elif args.action=='get':r=c.get(args.draft_id,args.revision)
        else:r=c.list()
        print(json.dumps(r,ensure_ascii=False,allow_nan=False))
        return 0 if r.get('status','committed')=='committed' else 3
    except (ValueError,OSError,HTTPException) as exc:
        unknown=isinstance(exc,UnknownSetupOutcome) or sent and not isinstance(exc,ClientError)
        error={'error':str(exc),'code':'setup_outcome_unknown' if unknown else getattr(exc,'code','invalid_setup_request'),'generation_submitted':False}
        if q:error['request_id']=q['request_id'];error['recovery']='Use recover with this original request ID. No write is replayed.'
        print(json.dumps(error),file=sys.stderr);return 3 if unknown else 2


if __name__=='__main__':raise SystemExit(main())
