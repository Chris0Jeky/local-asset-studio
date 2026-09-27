# As-run driver (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
import json, time
from playwright.sync_api import sync_playwright
JID = 'f9687adc-0cab-4406-8241-b17df32c6c44'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(viewport={'width': 1440, 'height': 1000})
    pg.goto('http://127.0.0.1:8191/#create'); pg.wait_for_timeout(2500)
    pg.locator('#workshopResults > summary').click(); pg.wait_for_timeout(1500)
    card = pg.locator('article.jobStatus[data-problem="%s"]' % JID)
    out = {'t': round(time.time(), 3), 'card_count': card.count(), 'card_text': card.first.inner_text() if card.count() else None,
           'cancel_button': card.locator('button.cancelJob').count(), 'disabled_reason': card.locator('.disabledReason').inner_text() if card.locator('.disabledReason').count() else None}
    if card.count(): card.first.evaluate("e => e.scrollIntoView({block: 'center'})"); pg.wait_for_timeout(300); card.first.screenshot(path='ui-04-settled-card.png')
    print(json.dumps(out, indent=1)); json.dump(out, open('ui-settled-card.json', 'w'), indent=1); b.close()
