"""Optional real-browser QA against inert local fixtures. Never connects to ComfyUI.

python tests/review_browser_smoke.py --out <new evidence directory> [--chromium /path/to/chromium]
Install Playwright only in a test environment. The normal unittest suite needs no browser.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from review_fixture import FixtureStudio, seed
from review_http_fixture import serve_fixture


def main():
    from playwright.sync_api import sync_playwright, expect
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--chromium');parser.add_argument('--dispatch-bridge',action='store_true');args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory() as temporary:
        studio=FixtureStudio(Path(temporary));identifier=seed(studio);initial=studio.production.get(identifier)['budget']
        with serve_fixture(studio) as (base,commands),sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.chromium,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':1100},accept_downloads=True)
            page=context.new_page();page.set_default_timeout(8000);errors=[];requests=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:requests.append(request.url))
            page.on('dialog',lambda dialog:dialog.accept())
            def load():
                if args.dispatch_bridge:
                    from review_browser_bridge import load_bridge
                    load_bridge(page,base,identifier)
                else:page.goto(base+'/review.html?project='+identifier, timeout=20000)
            load();expect(page.locator('#open')).to_be_enabled()
            assert [c['action'] for c in commands]==['inspect'];assert not studio.production.reviews.exists(identifier)
            page.locator('#open').click();expect(page.locator('#phase')).to_have_text('Blind review')
            expect(page.locator('#leftCaption')).to_contain_text('settings hidden')
            assert 'PRIVATE-SEED' not in page.content();assert 'inert-prompt' not in page.content()
            # Check same-region crops, side switching, alpha and retained assessment drafts.
            page.locator('[data-crop="centre"]').click();page.locator('#background').select_option('light')
            page.locator('#saveCrop').click();expect(page.locator('#viewStatus')).to_have_text('Saved crop')
            page.locator('#notes').fill('Unsaved candidate note <script>not code</script>')
            page.locator('#mode').select_option('right');expect(page.locator('#leftFigure')).to_be_hidden()
            page.locator('#mode').select_option('pair');page.locator('#swap').click()
            page.locator('#candidate').select_option('B');page.locator('#candidate').select_option('A')
            expect(page.locator('#notes')).to_have_value('Unsaved candidate note <script>not code</script>')
            # Concurrent agent edit makes this tab stale; failed save keeps text.
            desk=studio.production.reviews.inspect(identifier)
            studio.production.review(identifier,{'action':'view','expected_revision':desk['revision'],'crop':[0,0,10000,10000],'background':'dark','reviewer':'local-agent'})
            page.locator('#saveAssessment').click();expect(page.locator('#message')).to_contain_text('conflict')
            expect(page.locator('#notes')).to_have_value('Unsaved candidate note <script>not code</script>')
            with page.expect_download() as pending:page.locator('#saveDraft').click()
            pending.value.save_as(args.out/'unsaved-notes.json')
            page.locator('#reload').click();expect(page.locator('#message')).to_contain_text('Saved review loaded')
            for alias in ('A','B','C'):
                page.locator('#candidate').select_option(alias)
                page.locator('#verdict').select_option('keep' if alias=='A' else 'reject')
                page.locator('#check-constraints').select_option('pass' if alias=='A' else 'fail')
                page.locator('#notes').fill('Procedural QA assessment '+alias+'; not artistic acceptance.')
                if alias=='A':page.locator('#cleanup').fill('0')
                page.locator('#saveAssessment').click();expect(page.locator('#assessmentStatus')).to_have_text('Saved')
            page.screenshot(path=str(args.out/'review-desktop.png'),full_page=True)
            page.locator('#reveal').click();expect(page.locator('#phase')).to_have_text('Settings revealed')
            expect(page.locator('#evidence')).to_contain_text('inert-prompt')
            page.locator('#selected').select_option('A');page.locator('#summary').fill('QA decision only. All sources and rejected results retained.')
            page.locator('#finalize').click();expect(page.locator('#phase')).to_have_text('Decision recorded')
            page.locator('#export').click();expect(page.locator('#downloads a')).to_have_count(3)
            with page.expect_download() as pending:page.get_by_role('link',name='Download review evidence pack',exact=True).click()
            pack=args.out/'review-evidence.zip';pending.value.save_as(pack)
            with zipfile.ZipFile(pack) as archive:
                sums=json.loads(archive.read('checksums.json'))
                for name,receipt in sums['files'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==receipt['sha256']
                assert len([n for n in archive.namelist() if n.startswith('sources/')])==3
                (args.out/'contact-sheet.png').write_bytes(archive.read('contact-sheet.png'))
            # Restore produces a new revision, clears decision, cannot reblind.
            page.get_by_text('Assessment history & restore',exact=True).click()
            previous=page.locator('#restoreRevision option').nth(1).get_attribute('value')
            page.locator('#restoreRevision').select_option(previous);page.locator('#restore').click()
            expect(page.locator('#phase')).to_have_text('Settings revealed');expect(page.locator('#export')).to_be_disabled()
            # Narrow viewport, keyboard access, fresh load must inspect only.
            page.set_viewport_size({'width':390,'height':844})
            if args.dispatch_bridge:
                # Retained page avoids re-registering the test-only bridge. The Reload
                # action still verifies persisted state through actual HTTP/Python.
                page.locator('#reload').click();expect(page.locator('#message')).to_contain_text('Saved review loaded')
            else:page.reload()
            expect(page.locator('#desk')).to_be_visible()
            page.locator('#notes').focus();page.keyboard.type('Keyboard QA note');expect(page.locator('#saveDraft')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow at 390 px'
            page.screenshot(path=str(args.out/'review-mobile.png'),full_page=True)
            assert not errors,errors;assert all(url.startswith((base+'/','data:','blob:','about:')) for url in requests),requests
            assert studio.network_calls==0 and studio.queue.empty() and studio.production.get(identifier)['budget']==initial
            evidence={'scope':'Procedural CPU fixture and real Chromium, not user Windows Studio or model inference','browser':browser.version,
                      'commands':[c['action'] for c in commands],'javascript_errors':errors,'external_requests':0,'generation_calls':0,
                      'core':'Actual Production.review/ReviewDesk/SQLite/media; HTTP wrapper is tests/review_http_fixture.py',
                      'dispatch_bridge':args.dispatch_bridge,'bridge_scope':'Fetch, image decode and download links bridged by tests/review_browser_bridge.py' if args.dispatch_bridge else None,
                      'checks':['page-load inspect only','explicit snapshot','metadata-hidden aliases','matched crop/alpha','draft preservation','stale revision rejection','actual drafts download','all candidates assessed','explicit reveal','final selection','actual ZIP download/hash checks','history restore','390px no overflow','keyboard input']}
            (args.out/'browser-evidence.json').write_text(json.dumps(evidence,indent=2))
            context.close();browser.close()
    print('Browser review workflow passed; evidence in '+str(args.out))


if __name__=='__main__':main()
