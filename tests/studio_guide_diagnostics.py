"""Failure evidence for the synthetic guide fixture; never changes a browser wait."""
from collections import deque
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit


def _text(value,limit=256):return str(value)[:limit]


def _url(value):
    """Keep bounded route identity, without credentials, query values or media data."""
    try:
        parts=urlsplit(str(value))
        if parts.scheme and parts.scheme not in ('http','https'):return _text(parts.scheme)+':<redacted>'
        host=parts.hostname or ''
        if ':' in host:host='['+host+']'
        origin=(parts.scheme+'://'+host+(':'+str(parts.port) if parts.port else '')) if parts.netloc else ''
        keys=[field.partition('=')[0][:32]+'=<redacted>' for field in parts.query.split('&')[:8] if field]
        return _text(origin+parts.path+('?'+'&'.join(keys) if keys else ''))
    except ValueError:return '<invalid-url>'


class GuideNavigationDiagnostics:
    """Observations only. __exit__ runs before Playwright/server teardown via ExitStack."""
    def __init__(self,page,out,server_calls):
        self.page=page;self.out=Path(out);self.server_calls=server_calls;self.started=time.monotonic()
        self.events=deque(maxlen=200);self.pending={};self.errors=deque(maxlen=20)
        self.dropped_events=0;self.untracked_requests=0;self.request_count=0
        self.listeners={
            'request':self._request,'response':self._response,
            'requestfinished':lambda request:self._finished(request,'requestfinished'),
            'requestfailed':lambda request:self._finished(request,'requestfailed'),
            'domcontentloaded':lambda:self._record('domcontentloaded',url=_url(self.page.url)),
            'load':lambda:self._record('load',url=_url(self.page.url)),
            'pageerror':self._pageerror,'crash':lambda:self._record('crash'),
            'close':lambda:self._record('close')}

    def __enter__(self):
        for event,callback in self.listeners.items():self.page.on(event,callback)
        return self

    def _record(self,event,**fields):
        if len(self.events)==self.events.maxlen:self.dropped_events+=1
        self.events.append({'event':event,'elapsed_ms':round((time.monotonic()-self.started)*1000,3),**fields})

    def _request(self,request):
        self.request_count+=1
        item={'id':self.request_count,'url':_url(request.url),'method':_text(request.method,16),'resource_type':_text(request.resource_type,32)}
        if len(self.pending)<100:self.pending[request]=item
        else:self.untracked_requests+=1
        self._record('request',**item)

    def _response(self,response):
        item=self.pending.get(response.request)
        if item is not None:item['status']=response.status
        self._record('response',id=item['id'] if item else None,url=_url(response.url),status=response.status)

    def _finished(self,request,event):
        item=self.pending.pop(request,None)
        self._record(event,id=item['id'] if item else None,url=_url(request.url),failure=_text(request.failure) if event=='requestfailed' else None)

    def _pageerror(self,error):
        self.errors.append(_text(error));self._record('pageerror',message=_text(error))

    def goto(self,url,**options):
        self._record('navigation',url=_url(url),wait_until=options.get('wait_until','load'),timeout_ms=options.get('timeout'))
        return self.page.goto(url,**options)

    def _write(self,error):
        calls=self.server_calls()
        receipt={'version':1,'synthetic_fixture':True,'outcome':'failed' if error is not None else 'passed',
                 'exception':{'type':type(error).__name__,'message':_text(error,512)} if error is not None else None,
                 'events':list(self.events),'dropped_events':self.dropped_events,
                 'pending_requests':list(self.pending.values()),'untracked_request_starts':self.untracked_requests,
                 'request_count':self.request_count,'page_errors':list(self.errors),
                 'server_calls_total':len(calls),
                 'server_calls':[{'method':_text(method,16),'url':_url(url)} for method,url in calls[-100:]]}
        self.out.mkdir(parents=True,exist_ok=True)
        (self.out/'navigation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print('Guide navigation evidence saved: '+str(self.out/'navigation.json'),flush=True)
        # Keep the receipt even if the renderer cannot answer a screenshot request.
        if error is not None and not self.page.is_closed():
            try:
                viewport=self.page.viewport_size or {'width':960,'height':640}
                self.page.screenshot(path=str(self.out/'navigation-failure.png'),timeout=1000,animations='disabled',
                                     clip={'x':0,'y':0,'width':min(viewport['width'],960),'height':min(viewport['height'],640)})
            except Exception as screenshot_error:
                print('Guide diagnostic screenshot unavailable: '+_text(screenshot_error),file=sys.stderr,flush=True)

    def __exit__(self,kind,error,traceback):
        try:
            if error is None:self._write(None)
            else:
                try:self._write(error)
                except Exception as evidence_error:
                    print('Guide diagnostic receipt unavailable: '+_text(evidence_error),file=sys.stderr,flush=True)
        finally:
            for event,callback in self.listeners.items():self.page.remove_listener(event,callback)
        return False
