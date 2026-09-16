"""Native-page pose replacement regressions over synthetic HTTP data, never ComfyUI.

This intentionally has no --base-url: all writes go to the owned fixture server.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_use_cases as ux

ROOT = Path(__file__).resolve().parents[1]
SKELETON = 'combine-klein-9b-skeleton'
SNAPSHOT = '''() => ({recipe:selected.id, keep:lastUploaded, parents:[...parentAssets],
  claim:JSON.parse(JSON.stringify(continuationState)), refs:JSON.parse(JSON.stringify(referenceRecords)),
  controls:values(), batch:document.querySelector('#batch').value,
  fields:[...document.querySelectorAll('[data-ux-fill]')].map(el=>[StudioContinuation.fillMeaning(el.dataset.uxFill),el.value])})'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / '.runtime/pose-handoff-browser')
    parser.add_argument('--chromium')
    args = parser.parse_args(argv)
    args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    Handler, fixture = ux.build_handler()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_port)
    records, errors, posts = [], [], []
    spec = next(case for case in ux.load_cases()['cases'] if case['id'] == 'combine-character-with-another-pose')
    cases = [('depth', 1536), ('copypose', 390), ('missing-slot', 1536), ('corrupt-reply', 390),
             ('stale-workbench', 1536), ('busy-drawing', 390), ('transport-failure', 1536)]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'],
                                       executable_path=args.chromium or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None)
            try:
                for name, width in cases:
                    context = browser.new_context(viewport={'width': width, 'height': 1060}, reduced_motion='reduce')
                    page = context.new_page(); page.set_default_timeout(8000)
                    row = dict(case=name, viewport=width, assertions=[], passed=False)
                    records.append(row)
                    page.on('pageerror', lambda error, case=name: errors.append(case + ': ' + str(error)))
                    page.on('request', lambda request: posts.append(urlsplit(request.url).path) if request.method == 'POST' else None)
                    def check(condition, message):
                        if not condition: raise AssertionError(message)
                        row['assertions'].append(message)
                    try:
                        run = ux.CaseRun(dict(spec, id='pose-handoff-' + name), page, origin, False, args.out / 'setup')
                        ready, detail = ux._combine(run)
                        check(ready, 'Existing Combine source-pair journey is ready: ' + detail)
                        if name == 'copypose':
                            page.locator('[data-ux-engine="combine-klein-9b-copypose"]').click()
                            page.wait_for_function("selected.id==='combine-klein-9b-copypose'")
                        before = page.evaluate(SNAPSHOT)
                        check(page.locator('[data-ux-engine="'+SKELETON+'"]').is_disabled(),
                              'Ordinary engine switch still rejects picture-to-skeleton reinterpretation')
                        check(page.locator('#uxPoseUse').inner_text() == 'Replace pose picture with drawing',
                              'The separate action explicitly names replacement')
                        if name == 'missing-slot':
                            # Inject a disappeared staged source, not a new user journey or a successful upload.
                            page.evaluate("referenceRecords[0].missing=true;syncCreate()")
                            before = page.evaluate(SNAPSHOT)
                        page.locator('#uxPoseStart').select_option('bent')
                        page.locator('[data-ux-joint="4"]').click()
                        page.keyboard.press('ArrowRight')
                        check(page.locator('#uxPoseUse').is_enabled(), 'An explicit new drawing is admissible for this pair')
                        held = []
                        if name in ('corrupt-reply', 'stale-workbench', 'busy-drawing', 'transport-failure'):
                            page.route('**/api/pose/render', lambda route: held.append(route))
                        count_before = posts.count('/api/pose/render')
                        page.locator('#uxPoseUse').click()
                        if held or name in ('corrupt-reply', 'stale-workbench', 'busy-drawing', 'transport-failure'):
                            for _ in range(40):
                                if held: break
                                page.wait_for_timeout(50)
                            check(len(held) == 1, 'Exactly one drawing request is held for fault injection')
                            check(page.locator('#generate').is_disabled(), 'Generate is held while the drawing request is unresolved')
                            check(page.locator('#uxPoseStart').is_disabled(), 'Preset edits are held while the guide is rendering')
                            check(page.locator('#uxPoseUse').is_disabled(), 'A second rendering request is not admitted')
                            request = held[0].request.post_data_json
                            if name == 'stale-workbench':
                                page.locator('#positive').fill(before['controls']['positive'] + ' Newer human wording.')
                            if name == 'busy-drawing':
                                bitmap = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')
                                page.locator('[data-ux-joint="4"]').focus(); page.keyboard.press('ArrowRight')
                                check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == bitmap,
                                      'Keyboard input cannot alter the in-flight geometry')
                            reply = dict(file='f'*32+'_drawn-pose.png', sha256='d'*64, artifact_id='e'*64,
                                         bytes=2048, width=request['width'], height=request['height'],
                                         renderer='studio.coco18-lines/v1', generation_submitted=False)
                            if name == 'corrupt-reply': reply['width'] -= 8
                            if name == 'transport-failure':
                                held[0].fulfill(status=503, content_type='application/json', body='{"error":"fixture render unavailable"}')
                            else: held[0].fulfill(status=201, content_type='application/json', body=json.dumps(reply))
                            page.wait_for_function("!document.querySelector('#uxPoseStart').disabled")
                        failed = name in ('corrupt-reply', 'stale-workbench', 'transport-failure')
                        if failed:
                            page.wait_for_function("document.querySelector('#uxPoseStatus').textContent.length>0")
                            after = page.evaluate(SNAPSHOT)
                            for key in ('recipe', 'keep', 'parents', 'claim', 'refs'):
                                check(after[key] == before[key], 'Rejected response preserves ' + key)
                            check(page.locator('#uxPoseUse').is_enabled(), 'Failure releases the drawing control without retrying')
                            if name == 'stale-workbench':
                                check('Newer human wording.' in page.locator('#positive').input_value(), 'Newer wording is retained')
                        else:
                            page.wait_for_function("selected.id==='"+SKELETON+"' && referenceRecords[0]?.file?.endsWith('_drawn-pose.png')")
                            after = page.evaluate(SNAPSHOT)
                            check(after['keep'] == before['keep'], 'The character attachment is preserved')
                            check(after['claim']['source_asset_id'] == before['claim']['source_asset_id'], 'Character identity remains the continuation source')
                            check(after['claim']['source_asset_id'] in after['parents'], 'Character lineage survives even when both old roles used the same asset')
                            check(after['refs'][0]['sha256'] == 'd'*64 and not after['refs'][0].get('parent_asset'), 'The new guide owns the pose slot, not the old parent claim')
                            for key in ('seed', 'width', 'height'):
                                check(after['controls'][key] == before['controls'][key], key + ' is retained')
                            check(after['batch'] == before['batch'], 'Batch count is retained')
                            check(dict(after['fields']) == dict(before['fields']), 'Named who/pose/clothes answers transfer by meaning')
                            check('[' not in after['controls']['positive'], 'Image-order wording is rebuilt with no unresolved fills')
                            # A subsequent explicit render on the already-selected skeleton path uses the same guarded attachment.
                            if name == 'depth':
                                page.locator('#uxPoseUse').click()
                                page.wait_for_function("!document.querySelector('#uxPoseStart').disabled")
                                check(page.evaluate(SNAPSHOT)['keep'] == before['keep'], 'Already-skeleton replacement also preserves the character')
                                count_before += 1
                        check(posts.count('/api/pose/render') == count_before + 1, 'No implicit retry or duplicate guide render')
                        check(page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'The page has no horizontal overflow')
                        page.locator('#uxPoseEditor').scroll_into_view_if_needed()
                        page.screenshot(path=str(args.out / (name + '.png')))
                        row['passed'] = True
                    except Exception as exc:
                        row['error'] = str(exc)
                        try: page.screenshot(path=str(args.out / (name + '-failure.png')))
                        except Exception: pass
                    finally:
                        context.close()
                    print(('PASS ' if row['passed'] else 'FAIL ') + name + ': ' + row.get('error', str(len(row['assertions'])) + ' assertions'), flush=True)
            finally:
                browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    forbidden = ux.submissions(posts)
    report = dict(mode='native-browser-fixture', cases=records, assertions=sum(len(r['assertions']) for r in records),
                  page_errors=errors, generation_submissions=len(forbidden), posts=posts,
                  passed=all(r['passed'] for r in records) and not errors and not forbidden)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('mode', 'assertions', 'generation_submissions', 'passed')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
