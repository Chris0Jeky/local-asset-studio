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
SDXL = 'wai-skeleton'
SNAPSHOT = '''() => ({recipe:selected.id, keep:lastUploaded, parents:[...parentAssets],
  claim:JSON.parse(JSON.stringify(continuationState)), refs:JSON.parse(JSON.stringify(referenceRecords)),
  controls:values(), batch:document.querySelector('#batch').value,
  fields:[...document.querySelectorAll('[data-ux-fill]')].map(el=>[StudioContinuation.fillMeaning(el.dataset.uxFill),el.value])})'''



def precision_checks(page, check):
    before = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')
    initial = [page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')]
    page.locator('#uxPoseX').fill('0'); page.locator('#uxPoseY').fill('123.45')
    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == before, 'Typing alone does not apply a geometry edit')
    check(page.locator('#uxPoseUse').is_disabled() and page.locator('#generate').is_disabled(), 'Unapplied coordinates visibly hold use and generation')
    check(page.locator('[data-ux-joint="5"]').is_disabled(), 'A joint switch cannot discard unapplied coordinates')
    page.evaluate("document.querySelector('#positive').dispatchEvent(new Event('change',{bubbles:true}))")  # Simulate the same readiness refresh used after inspection/polling.
    check(page.locator('#uxPoseX').input_value() == '0', 'Readiness refresh preserves an unfinished coordinate draft')
    page.locator('#uxPoseY').press('Enter')
    check(page.locator('#uxPoseUse').is_enabled(), 'Enter applies the explicit edit and releases the hold')
    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') != before, 'The accepted exact position changes the drawing')
    applied = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')
    for control in ('#uxPosePositionApply', '#uxPoseUse', '#uxPoseUndo'):
        page.locator(control).focus(); page.keyboard.press('ArrowRight')
        check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == applied,
              'Arrow keys on ' + control + ' do not nudge the drawing')
    page.locator('#uxPoseUndo').click()
    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == initial, 'Undo restores both displayed coordinates')
    undone = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')
    page.locator('#uxPoseRedo').focus(); page.keyboard.press('ArrowRight')
    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == undone, 'Arrow keys on Redo do not nudge the drawing')
    page.locator('#uxPoseRedo').click()
    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == ['0', '123.45'], 'Redo restores both displayed coordinates')
    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == applied, 'Redo restores the exact drawing')
    page.locator('#uxPoseUndo').click()
    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == initial, 'Undo remains available after redo')
    page.locator('#uxPoseX').fill(''); page.locator('#uxPosePositionApply').click()
    check(page.locator('#uxPoseX').get_attribute('aria-invalid') == 'true', 'Empty typed input is refused, not coerced to zero')
    page.locator('#uxPosePositionReset').click()
    check(page.locator('#uxPoseX').input_value() == initial[0], 'Reset restores the unapplied fields without changing geometry')
    page.locator('#uxPoseUnknown').click()
    check(page.locator('#uxPoseX').is_disabled() and page.locator('#uxPoseY').is_disabled(), 'Unknown points cannot acquire accidental numeric coordinates')
    page.locator('#uxPoseUnknown').click()
    before = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')
    page.locator('#uxPoseX').press('ArrowUp')
    check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == before, 'Number-input arrows edit the field, not the skeleton')
    page.locator('#uxPosePositionReset').click()
    page.locator('#uxPoseX').fill('0'); page.locator('#uxPoseY').fill('123.45')
    page.locator('#uxPosePositionApply').click()
    check(page.locator('#uxPoseX').input_value() == '0', 'Coordinate zero remains a valid authored joint')
    page.locator('#uxPoseY').fill('123.4501'); page.locator('#uxPosePositionApply').click()
    check(page.locator('#uxPoseY').input_value() == '123.45' and page.locator('#uxPoseUse').is_enabled(), 'A rounded no-op clears the field hold without adding a geometry change')


def sdxl_in_place(page, origin, out, check, drawings, posts):
    """#445/#761: an SDXL skeleton recipe draws in place: its own renderer, its own pose slot, no recipe switch, no job."""
    run = ux.CaseRun(dict(id='pose-handoff-sdxl-in-place'), page, origin, False, out / 'setup')
    run.boot('#create'); run.select_preset(SDXL)
    page.wait_for_function("selected.id==='" + SDXL + "' && !document.querySelector('#uxPoseEditor').hidden")
    check(page.locator('#uxPoseUse').inner_text() == 'Use this pose', 'The SDXL recipe draws in place, not as a replacement')
    check(page.locator('#generate').is_disabled(), 'Generate waits for a guide on the pose slot')
    count_before = posts.count('/api/pose/render')
    page.locator('#uxPoseStart').select_option('bent')
    page.locator('#uxPoseUse').click()
    page.wait_for_function("selected.id==='" + SDXL + "' && referenceRecords[0]?.file?.endsWith('_drawn-pose.png')")
    check(drawings[-1].get('renderer') == 'studio.coco18-openpose-xinsir/v1', 'The guide request names the recipe renderer')
    check(set(drawings[-1]) == {'width', 'height', 'keypoints', 'renderer'}, 'The request carries the drawing and nothing else')
    state = page.evaluate("({role:referenceRecords[0].role,renderer:referenceRecords[0].renderer,reference:typeof uploaded!=='undefined'?uploaded:null})")
    check(state['role'] == 'pose' and state['renderer'] == 'studio.coco18-openpose-xinsir/v1', 'The pose slot holds the OpenPose guide')
    check(state['reference'] is None, 'The single-reference control is left alone')
    check(page.locator('#generate').is_enabled(), 'Generate is ready and was never pressed')
    check(posts.count('/api/pose/render') == count_before + 1, 'One render, no retry')
    # #844: the attached guide is a picture of one canvas; a new Width holds Generate until the guide is drawn again.
    drawn = page.evaluate('[referenceRecords[0].width,referenceRecords[0].height]')
    resized = drawn[0] - 192 if drawn[0] > 512 else drawn[0] + 192
    page.evaluate("document.querySelector('[data-key=\"width\"]').closest('details').open=true")  # Width lives under the folded parameters.
    page.locator('[data-key="width"]').fill(str(resized))
    page.wait_for_function('!!document.querySelector(\'[data-readiness-code="pose-size"]\')')
    check(page.locator('#generate').is_disabled(), 'A changed Width holds Generate on the stale guide')
    hold = page.locator('[data-readiness-code="pose-size"] p').text_content()  # The blocker list sits in a folded disclosure.
    check(page.locator('#uxPoseReason').inner_text() == hold, 'The same hold is shown beside Use this pose')
    check('drawn at %d×%d' % tuple(drawn) in hold and 'Use this pose' in hold, 'The hold names the drawn size and the button that clears it: ' + hold)
    check(posts.count('/api/pose/render') == count_before + 1, 'A size change renders nothing by itself')
    page.locator('#uxPoseUse').click()
    page.wait_for_function('referenceRecords[0]?.width===%d && !document.querySelector(\'[data-readiness-code="pose-size"]\')' % resized)
    check(drawings[-1]['width'] == resized and drawings[-1]['height'] == drawn[1], 'Use this pose again renders the guide at the new size')
    check(page.locator('#generate').is_enabled(), 'The re-drawn guide releases Generate, which was never pressed')
    check(posts.count('/api/pose/render') == count_before + 2, 'One explicit re-render, no implicit one')


HOLD = '[data-readiness-code="pose-size"]'
REPLACE_GUIDE = "guide=>{referenceRecords[0]=Object.assign({},referenceRecords[0],guide);document.querySelector('#positive').dispatchEvent(new Event('change',{bubbles:true}));}"


def set_width(page, value):
    page.evaluate("document.querySelector('[data-key=\"width\"]').closest('details').open=true")  # Width lives under the folded parameters.
    page.locator('[data-key="width"]').fill(str(value))


def hold_text(page, contains):
    page.wait_for_function("document.querySelector('%s p')?.textContent.includes(%s)" % (HOLD, json.dumps(contains)))
    return page.locator(HOLD + ' p').text_content()  # The blocker list sits in a folded disclosure.


def restored_guide(page, origin, out, check, drawings, posts, spec):
    """#947/#952 on the Klein route: a guide restored with its picture but not its drawing, a disabled Replace button, and a
    Width change on combine-klein-9b-skeleton. The restored record is injected exactly as a saved setup or draft leaves it."""
    run = ux.CaseRun(dict(spec, id='pose-handoff-restored-guide'), page, origin, False, out / 'setup')
    ready, detail = ux._combine(run)
    check(ready, 'Existing Combine source-pair journey is ready: ' + detail)
    page.locator('[data-ux-engine="combine-klein"]').click()  # A two-picture board: its second slot can block the replacement.
    page.wait_for_function("selected.id==='combine-klein' && !document.querySelector('#uxPoseEditor').hidden")
    check(page.locator('#uxPoseUse').inner_text() == 'Replace pose picture with drawing', 'A picture recipe offers the replacement')
    held, lost = 'a' * 64, 'b' * 64
    joints = page.evaluate('StudioPoseEditor.JOINTS')
    # Multiples of 64 across a 1024-wide canvas, so the 832-wide redraw is exact to the hundredth.
    stored = {name: None if index == 16 else dict(x=64 * (index % 14 + 1), y=80 * (index + 1), confidence=None, origin='manual')
              for index, name in enumerate(joints)}
    artifact = dict(schema='studio.pose-artifact/v1', id=held, canvas=dict(width=1024, height=1536), joints=stored, parent_id=None,
                    authority='none', review='unreviewed',
                    source=dict(sha256='c' * 64, format='openpose-coco18', person_index=0, coordinate_space='pixels'))
    reads = []
    def artifact_route(route):
        reads.append(urlsplit(route.request.url).path)
        if route.request.url.endswith('/' + held): route.fulfill(status=200, content_type='application/json', body=json.dumps(artifact))
        else: route.fulfill(status=400, content_type='application/json', body='{"error":"Editable pose artifact is unavailable"}')
    page.route('**/api/pose/artifacts/*', artifact_route)
    guide = dict(file='a' * 32 + '_drawn-pose.png', sha256='a' * 64, bytes=2048, width=1024, height=1536, artifact_id=held,
                 renderer='studio.coco18-lines/v1', parent_asset=None, missing=False)
    renders = posts.count('/api/pose/render')
    page.evaluate(REPLACE_GUIDE, guide)
    page.wait_for_function("document.querySelector('#uxPoseStatus').textContent.includes('back in the editor')")
    check(reads == ['/api/pose/artifacts/' + held], 'The restored guide reads its own stored drawing once: ' + str(reads))
    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == ['64', '80'], 'The editor now holds the guide drawing, not the default figure')
    check(page.locator('#uxPoseUndo').is_enabled(), 'Loading the stored drawing is one undoable edit')
    set_width(page, 832)
    hold = hold_text(page, 'drawn at 1024×1536')
    check(hold == 'The pose guide was drawn at 1024×1536; press Replace pose picture with drawing again for the new size (832×1536).',
          'The held drawing is promised as a resize: ' + hold)
    check(page.locator('#uxPoseReason').inner_text() == hold, 'The same hold is shown beside the button')
    # #952: a second board picture disables the replacement; the hold names that step first and its button shows the reason.
    page.locator('[data-ref-file="1"]').set_input_files({'name': 'extra.png', 'mimeType': 'image/png',
                                                         'buffer': (ROOT / 'examples/references/lantern-reference.png').read_bytes()})
    page.wait_for_function('referencePending===0 && !!referenceRecords[1]?.file')
    check(page.locator('#uxPoseUse').is_disabled(), 'The extra board picture disables the replacement')
    hold = hold_text(page, 'Remove the extra board picture')
    check(hold.index('Remove the extra board picture') < hold.index('Then press Replace pose picture with drawing again'),
          'The hold names the enabled next step before the disabled button: ' + hold)
    check(page.locator(HOLD + ' button').text_content() == 'Show the pose editor', 'The readiness button does not name a disabled control')
    page.evaluate("document.querySelector('%s button').click()" % HOLD)
    check(page.evaluate('document.activeElement?.id') == 'uxPoseReason', 'Showing the step lands on the reason, not on the disabled button')
    page.locator('[data-ref-clear="1"]').click()
    page.wait_for_function("!document.querySelector('#uxPoseUse').disabled")
    check(posts.count('/api/pose/render') == renders, 'Nothing rendered by itself')
    page.locator('#uxPoseUse').click()
    page.wait_for_function("selected.id==='%s' && referenceRecords[0]?.width===832 && !document.querySelector('%s')" % (SKELETON, HOLD))
    expected = [None if point is None else [point['x'] * 832 / 1024, point['y']] for point in stored.values()]
    check(drawings[-1]['width'] == 832 and drawings[-1]['keypoints'] == expected, 'The replacement redraws the restored pose at the new size, not the default figure')
    # #952: the Klein skeleton route holds on a Width change and clears on one explicit redraw.
    set_width(page, 1024)
    hold = hold_text(page, 'drawn at 832×1536')
    check(hold == 'The pose guide was drawn at 832×1536; press Use this pose again for the new size (1024×1536).', 'The skeleton route names its own button: ' + hold)
    check(page.locator('#generate').is_disabled(), 'The stale guide holds Generate on the skeleton recipe')
    check(posts.count('/api/pose/render') == renders + 1, 'A size change renders nothing by itself')
    page.locator('#uxPoseUse').click()
    page.wait_for_function("referenceRecords[0]?.width===1024 && !document.querySelector('%s')" % HOLD)
    check(drawings[-1]['width'] == 1024 and posts.count('/api/pose/render') == renders + 2, 'One explicit redraw at the new size clears the hold')
    # A guide whose drawing cannot be read is never promised as a resize, and the editor keeps what it holds.
    before = [page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')]
    page.evaluate(REPLACE_GUIDE, dict(guide, file='b' * 32 + '_drawn-pose.png', sha256='b' * 64, width=640, artifact_id=lost))
    page.wait_for_function("document.querySelector('#uxPoseStatus').textContent.includes('could not be read')")
    hold = hold_text(page, 'does not hold that drawing')
    check(hold == 'The pose guide was drawn at 640×1536, not the new size (1024×1536), and the editor does not hold that drawing. '
          'Set Width and Height back to 640×1536, or redraw the pose and press Use this pose.', 'An unreadable drawing is not promised as a resize: ' + hold)
    check([page.locator('#uxPose' + key).input_value() for key in ('X', 'Y')] == before, 'The editor keeps its drawing when the stored one cannot be read')
    check(reads.count('/api/pose/artifacts/' + lost) == 1, 'One read per guide, no retry loop')
    check(posts.count('/api/pose/render') == renders + 2, 'No implicit render')


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
    records, errors, posts, drawings = [], [], [], []
    spec = next(case for case in ux.load_cases()['cases'] if case['id'] == 'combine-character-with-another-pose')
    cases = [('depth', 1536), ('copypose', 390), ('missing-slot', 1536), ('corrupt-reply', 390),
             ('stale-workbench', 1536), ('busy-drawing', 390), ('transport-failure', 1536), ('newer-role-upload', 390)]
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
                    page.on('request', lambda request: drawings.append(request.post_data_json) if request.method == 'POST' and urlsplit(request.url).path == '/api/pose/render' else None)
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
                            page.evaluate("referenceRecords[0].missing=true;document.querySelector('#positive').dispatchEvent(new Event('change',{bubbles:true}))")
                            before = page.evaluate(SNAPSHOT)
                        page.locator('#uxPoseStart').select_option('bent')
                        page.locator('[data-ux-joint="4"]').click()
                        page.keyboard.press('ArrowRight')
                        if name in ('depth', 'copypose'): precision_checks(page, check)
                        check(page.locator('#uxPoseUse').is_enabled(), 'An explicit new drawing is admissible for this pair')
                        held, uploads = [], []
                        if name in ('corrupt-reply', 'stale-workbench', 'busy-drawing', 'transport-failure', 'newer-role-upload'):
                            page.route('**/api/pose/render', lambda route: held.append(route))
                        count_before = posts.count('/api/pose/render')
                        page.locator('#uxPoseUse').click()
                        if held or name in ('corrupt-reply', 'stale-workbench', 'busy-drawing', 'transport-failure', 'newer-role-upload'):
                            for _ in range(40):
                                if held: break
                                page.wait_for_timeout(50)
                            check(len(held) == 1, 'Exactly one drawing request is held for fault injection')
                            check(page.locator('#generate').is_disabled(), 'Generate is held while the drawing request is unresolved')
                            check(page.locator('#uxPoseStart').is_disabled(), 'Preset edits are held while the guide is rendering')
                            check(page.locator('#uxPoseX').is_disabled() and page.locator('#uxPosePositionApply').is_disabled(), 'Numeric edits are held during rendering')
                            check(page.locator('#uxPoseUse').is_disabled(), 'A second rendering request is not admitted')
                            request = held[0].request.post_data_json
                            if name == 'stale-workbench':
                                page.locator('#positive').fill(before['controls']['positive'] + ' Newer human wording.')
                            if name == 'busy-drawing':
                                bitmap = page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()')
                                page.locator('#uxPoseCanvas').focus(); page.keyboard.press('ArrowRight')
                                check(page.locator('#uxPoseCanvas').evaluate('(el)=>el.toDataURL()') == bitmap,
                                      'Keyboard input cannot alter the in-flight geometry')
                            if name == 'newer-role-upload':
                                page.route('**/api/upload', lambda route: uploads.append(route))
                                page.locator('[data-ref-file="0"]').set_input_files({
                                    'name': 'newer.png', 'mimeType': 'image/png',
                                    'buffer': (ROOT / 'examples/references/lantern-reference.png').read_bytes()})
                                page.wait_for_function('referencePending>0')
                                for _ in range(40):
                                    if uploads: break
                                    page.wait_for_timeout(50)
                                check(len(uploads) == 1, 'A newer real role-slot upload is pending before the guide reply')
                            reply = dict(file='f'*32+'_drawn-pose.png', sha256='d'*64, artifact_id='e'*64,
                                         bytes=2048, width=request['width'], height=request['height'],
                                         renderer='studio.coco18-lines/v1', generation_submitted=False)
                            if name == 'corrupt-reply': reply['width'] -= 8
                            if name == 'transport-failure':
                                held[0].fulfill(status=503, content_type='application/json', body='{"error":"fixture render unavailable"}')
                            else: held[0].fulfill(status=201, content_type='application/json', body=json.dumps(reply))
                            page.wait_for_function("!document.querySelector('#uxPoseStart').disabled")
                        failed = name in ('corrupt-reply', 'stale-workbench', 'transport-failure', 'newer-role-upload')
                        if failed:
                            page.wait_for_function("document.querySelector('#uxPoseStatus').textContent.length>0")
                            after = page.evaluate(SNAPSHOT)
                            for key in ('recipe', 'keep', 'parents', 'claim', 'refs'):
                                check(after[key] == before[key], 'Rejected response preserves ' + key)
                            if name == 'newer-role-upload':
                                check(page.locator('#uxPoseUse').is_disabled(), 'The newer pending attachment retains its own readiness hold')
                                uploaded = dict(file='c'*32+'_newer.png', sha256='c'*64, bytes=1024,
                                                width=256, height=256)
                                uploads[0].fulfill(status=201, content_type='application/json', body=json.dumps(uploaded))
                                page.wait_for_function("referencePending===0 && referenceRecords[0]?.file?.endsWith('_newer.png')")
                                current = page.evaluate(SNAPSHOT)
                                check(current['recipe'] == before['recipe'] and current['keep'] == before['keep'],
                                      'The newer upload finishes on the original recipe with the character retained')
                                check(current['refs'][0]['sha256'] == 'c'*64, 'The new donor is attached instead of the stale drawn guide')
                            check(page.locator('#uxPoseUse').is_enabled(), 'Failure releases the drawing control without retrying')
                            if name == 'stale-workbench':
                                check('Newer human wording.' in page.locator('#positive').input_value(), 'Newer wording is retained')
                        else:
                            page.wait_for_function("selected.id==='"+SKELETON+"' && referenceRecords[0]?.file?.endsWith('_drawn-pose.png')")
                            after = page.evaluate(SNAPSHOT)
                            if name in ('depth', 'copypose'):
                                check(drawings[-1]['keypoints'][4] == [0, 123.45], 'The exact edited wrist reaches the guide request')
                            check(after['keep'] == before['keep'], 'The character attachment is preserved')
                            check(after['claim']['source_asset_id'] == before['claim']['source_asset_id'], 'Character identity remains the continuation source')
                            check(after['claim']['source_asset_id'] in after['parents'], 'Character lineage survives even when both old roles used the same asset')
                            check(after['refs'][0]['sha256'] == 'd'*64 and not after['refs'][0].get('parent_asset'), 'The new guide owns the pose slot, not the old parent claim')
                            for key in ('seed', 'width', 'height'):
                                check(after['controls'][key] == before['controls'][key], key + ' is retained')
                            check(after['batch'] == before['batch'], 'Batch count is retained')
                            before_fields, after_fields = dict(before['fields']), dict(after['fields'])
                            check(after_fields.get('who') == before_fields.get('who'), 'Who transfers by meaning')
                            check(after_fields.get('clothes') == before_fields.get('clothes'), 'Clothes transfer by meaning')
                            check(not (after_fields.get('pose') or '').strip(), 'The old pose picture’s wording is not kept')
                            check('[' in after['controls']['positive'], 'The pose fill stays as a bracket until the drawing is described')
                            check(page.locator('#generate').is_disabled(), 'Generate waits for pose wording that matches the drawing')
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
                context = browser.new_context(viewport={'width': 1536, 'height': 1060}, reduced_motion='reduce')
                page = context.new_page(); page.set_default_timeout(8000)
                row = dict(case='sdxl-in-place', viewport=1536, assertions=[], passed=False); records.append(row)
                page.on('pageerror', lambda error: errors.append('sdxl-in-place: ' + str(error)))
                page.on('request', lambda request: posts.append(urlsplit(request.url).path) if request.method == 'POST' else None)
                page.on('request', lambda request: drawings.append(request.post_data_json) if request.method == 'POST' and urlsplit(request.url).path == '/api/pose/render' else None)
                def check_sdxl(condition, message):
                    if not condition: raise AssertionError(message)
                    row['assertions'].append(message)
                try:
                    sdxl_in_place(page, origin, args.out, check_sdxl, drawings, posts)
                    page.locator('#uxPoseEditor').scroll_into_view_if_needed(); page.screenshot(path=str(args.out / 'sdxl-in-place.png'))
                    row['passed'] = True
                except Exception as exc:
                    row['error'] = str(exc)
                    try: page.screenshot(path=str(args.out / 'sdxl-in-place-failure.png'))
                    except Exception: pass
                finally:
                    context.close()
                print(('PASS ' if row['passed'] else 'FAIL ') + 'sdxl-in-place: ' + row.get('error', str(len(row['assertions'])) + ' assertions'), flush=True)
                context = browser.new_context(viewport={'width': 1536, 'height': 1060}, reduced_motion='reduce')
                page = context.new_page(); page.set_default_timeout(8000)
                row = dict(case='restored-guide', viewport=1536, assertions=[], passed=False); records.append(row)
                page.on('pageerror', lambda error: errors.append('restored-guide: ' + str(error)))
                page.on('request', lambda request: posts.append(urlsplit(request.url).path) if request.method == 'POST' else None)
                page.on('request', lambda request: drawings.append(request.post_data_json) if request.method == 'POST' and urlsplit(request.url).path == '/api/pose/render' else None)
                def check_restored(condition, message):
                    if not condition: raise AssertionError(message)
                    row['assertions'].append(message)
                try:
                    restored_guide(page, origin, args.out, check_restored, drawings, posts, spec)
                    page.locator('#uxPoseEditor').scroll_into_view_if_needed(); page.screenshot(path=str(args.out / 'restored-guide.png'))
                    row['passed'] = True
                except Exception as exc:
                    row['error'] = str(exc)
                    try: page.screenshot(path=str(args.out / 'restored-guide-failure.png'))
                    except Exception: pass
                finally:
                    context.close()
                print(('PASS ' if row['passed'] else 'FAIL ') + 'restored-guide: ' + row.get('error', str(len(row['assertions'])) + ' assertions'), flush=True)
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
