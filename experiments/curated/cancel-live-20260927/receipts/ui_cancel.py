# As-run driver (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1138 UI proof: one cheap SFW wai job, cancelled by clicking the running card's Cancel button in a real (headless) browser."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927')
import drive
from playwright.sync_api import sync_playwright
OUT = drive.OUT
ev = drive.ev

def main():
    drive.pre('ui')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []; dialogs = []; posts = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: posts.append((round(time.time(), 3), r.method, r.url)) if r.method == 'POST' else None)
        def on_dialog(d):
            dialogs.append({'t': round(time.time(), 3), 'type': d.type, 'message': d.message}); d.accept()
        page.on('dialog', on_dialog)
        page.goto(drive.S + '/#create', wait_until='domcontentloaded'); page.wait_for_timeout(2500)
        page.locator('#workshopResults > summary').click(); page.wait_for_timeout(500)   # open the 'Recent runs' disclosure as the owner would
        ev('ui_page', results_open=page.evaluate("() => document.getElementById('workshopResults').open"), gallery_visible=page.locator('#gallery').is_visible(), url=page.url)
        assert page.locator('#gallery').is_visible(), 'Recent runs not visible'
        jid = drive.create('cancel-proof-ui-click', 1, 120, 927304)
        card = page.locator('article.jobStatus[data-problem="%s"]' % jid)
        # wait until ComfyUI runs exactly this job's prompt and the card offers an enabled Cancel
        end = time.time() + 180
        while time.time() < end:
            j = drive.job(jid); r, pq = drive.queue()
            if j.get('prompt_ids') and r == j['prompt_ids'][:1] and not pq and card.count() and card.locator('button.cancelJob:not([disabled])').count() and card.first.is_visible(): break
            if int(time.time()*10) % 10 < 3: print('dbg', j['status'], r, card.count(), card.locator('button.cancelJob').count(), card.first.is_visible() if card.count() else None, page.locator('#gallery article.jobStatus').count(), page.locator('#cancelRun').is_visible() if page.locator('#cancelRun').count() else None, flush=True)
            if j['status'] not in drive.ACTIVE: raise SystemExit('finished before the card offered Cancel: ' + j['status'])
            time.sleep(0.3)
        else: raise SystemExit('card never offered Cancel')
        card.scroll_into_view_if_needed()
        before = {'card_text': card.inner_text(), 'consequence': card.locator('.cancelConsequence').inner_text(),
                  'run_dock_reason': page.locator('#cancelRunReason').inner_text() if page.locator('#cancelRunReason').count() else None,
                  'queue_running': r, 'prompt_id': j['prompt_ids'][0]}
        ev('ui_before_click', **before)
        card.screenshot(path=OUT + '/ui-01-running-card.png')
        t_click = time.time(); card.locator('button.cancelJob').click(); ev('ui_clicked', at=round(t_click, 3))
        # wait for the card to leave the running state: the settled job shows as cancelled
        end = time.time() + 180
        while time.time() < end:
            j = drive.job(jid)
            if j['status'] == 'cancelled': break
            time.sleep(0.3)
        page.wait_for_timeout(3000)   # one UI poll
        after_card = page.locator('article.jobStatus[data-problem="%s"]' % jid)
        after = {'card_count': after_card.count(), 'card_text': after_card.first.inner_text() if after_card.count() else None,
                 'status_line': page.locator('p#status').inner_text() if page.locator('p#status').count() else None}
        if after_card.count(): after_card.first.screenshot(path=OUT + '/ui-02-after.png')
        page.screenshot(path=OUT + '/ui-03-page.png', full_page=False)
        ev('ui_after', **after, dialogs=dialogs, page_errors=errors, page_posts=[x for x in posts if '/api/' in x[2]])
        browser.close()
    drive.dump('ui', jid, {'dialogs': dialogs, 'page_errors': errors, 'page_posts': posts, 'before': before, 'after': after})
    drive.post('ui')

if __name__ == '__main__':
    try: main()
    finally: json.dump(drive.events, open(OUT + '/events-ui.json', 'w', encoding='utf-8'), indent=1)
