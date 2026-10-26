"""Bounded diagnostic receipts must preserve the original browser failure."""
import json
from pathlib import Path
import tempfile
import unittest

from studio_guide_diagnostics import GuideNavigationDiagnostics


class Page:
    url='http://127.0.0.1:8191/?guide=synthetic'
    viewport_size={'width':1440,'height':1000}
    def __init__(self):self.listeners={};self.screenshots=[];self.navigations=[]
    def on(self,event,callback):self.listeners[event]=callback
    def remove_listener(self,event,callback):self.listeners.pop(event,None)
    def emit(self,event,*args):self.listeners[event](*args)
    def goto(self,url,**options):self.navigations.append((url,options));return 'response'
    def is_closed(self):return False
    def screenshot(self,**options):
        # The useful receipt must already exist if screenshot collection fails.
        assert Path(options['path']).with_name('navigation.json').is_file()
        self.screenshots.append(options)
        raise RuntimeError('synthetic screenshot failure')


class Request:
    method='GET';resource_type='image';failure=None
    def __init__(self,url):self.url=url


class GuideDiagnosticTests(unittest.TestCase):
    def test_original_failure_and_pending_load_survive_screenshot_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            page=Page();out=Path(folder);original=TimeoutError('original navigation timeout')
            with self.assertRaises(TimeoutError) as raised:
                with GuideNavigationDiagnostics(page,out,lambda:[('GET','/'),('GET','/held.png')]) as evidence:
                    self.assertEqual(evidence.goto(page.url,timeout=15000),'response')
                    request=Request('http://127.0.0.1:8191/held.png')
                    page.emit('request',request);page.emit('domcontentloaded')
                    raise original
            self.assertIs(raised.exception,original)
            receipt=json.loads((out/'navigation.json').read_text())
            self.assertEqual(receipt['outcome'],'failed')
            self.assertEqual(receipt['pending_requests'][0]['resource_type'],'image')
            self.assertEqual(receipt['pending_requests'][0]['url'],'http://127.0.0.1:8191/held.png')
            self.assertIn('domcontentloaded',[event['event'] for event in receipt['events']])
            self.assertNotIn('load',[event['event'] for event in receipt['events']])
            self.assertEqual(receipt['server_calls'][-1],{'method':'GET','url':'/held.png'})
            self.assertEqual(page.navigations,[(page.url,{'timeout':15000})])
            self.assertEqual(page.screenshots[0]['timeout'],1000)
            self.assertEqual(page.listeners,{})

    def test_completed_requests_and_bounded_redacted_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            page=Page();out=Path(folder)
            calls=[('GET','/synthetic?review=private-value')]*400
            with GuideNavigationDiagnostics(page,out,lambda:calls) as evidence:
                for index in range(400):
                    request=Request('http://user:password@127.0.0.1:8191/'+str(index)+'?note=private-value#private-fragment')
                    page.emit('request',request)
                    if index%2==0:page.emit('requestfinished',request)
                page.emit('pageerror',RuntimeError('synthetic page error'))
                page.emit('load')
            raw=(out/'navigation.json').read_text();receipt=json.loads(raw)
            self.assertEqual(receipt['outcome'],'passed')
            self.assertEqual(len(receipt['pending_requests']),100)
            self.assertLessEqual(len(receipt['events']),200)
            self.assertEqual(receipt['server_calls_total'],400)
            self.assertEqual(len(receipt['server_calls']),100)
            self.assertGreater(receipt['dropped_events'],0)
            self.assertGreater(receipt['untracked_request_starts'],0)
            self.assertLess(len(raw.encode()),512*1024)
            for private in ('user:password','private-value','private-fragment'):self.assertNotIn(private,raw)
            self.assertEqual(page.screenshots,[])
            self.assertEqual(page.listeners,{})

    def test_receipt_write_failure_does_not_replace_original_error(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'not-a-directory';out.write_text('occupied')
            page=Page();original=AssertionError('original failed assertion')
            with self.assertRaises(AssertionError) as raised:
                with GuideNavigationDiagnostics(page,out,lambda:[]):raise original
            self.assertIs(raised.exception,original)
            self.assertEqual(page.listeners,{})


if __name__=='__main__':unittest.main()
