"""Exercise the standalone behavior specification. No screenshots or media.

Requires Playwright and Chromium; does not connect to LAS, ComfyUI or a provider.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent


def run(output, injected=False):
    checks, errors, network = [], [], []
    with sync_playwright() as pw:
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser = pw.chromium.launch(**({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width':1440,'height':900})
        page.set_default_timeout(5000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: network.append(request.url) if request.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
        if injected:
            page.set_content((ROOT/'index.html').read_text(encoding='utf-8'))
        else:
            page.goto((ROOT/'index.html').as_uri())
        page.wait_for_selector('#nextAction')
        assert page.locator('#tasks button').count() == 5
        assert page.locator('img,video,audio,iframe').count() == 0
        for selector in ('#brief','#reviewPlan'):
            box=page.locator(selector).bounding_box()
            assert box and box['y']>=0 and box['y']+box['height']<=900,(selector,box)
        checks.append('desktop default shows brief and review control; no media elements')

        page.fill('#brief','Keep this draft across every lens and visual choice.')
        page.evaluate("window.originalBrief=document.getElementById('brief')")
        page.click('[data-task="pose"]')
        assert page.locator('#route').input_value() == 'words'
        assert 'task-compatible' in page.locator('#nextTitle').inner_text()
        page.click('#nextAction')
        page.keyboard.press('Escape')
        expect(page.locator('#nextAction')).to_be_focused()
        assert page.locator('#route').input_value() == 'words'
        page.click('#nextAction')
        page.click('#applyExample')
        expect(page.locator('#brief')).to_be_focused()
        assert page.locator('#route').input_value() == 'pose'
        assert page.locator('#brief').input_value().startswith('Keep this draft')
        checks.append('task lens preserves route; cancelled/accepted example change returns correct focus')

        page.click('#nextAction')
        assert page.locator('#simulation').evaluate('n=>n.open')
        assert page.locator('#refs').evaluate('n=>n===document.activeElement')
        page.select_option('#refs','4')
        assert 'extra sources' in page.locator('#nextTitle').inner_text()
        assert page.locator('#refs').input_value()=='4'
        page.select_option('#refs','2')
        assert page.locator('#nextTitle').inner_text()=='Review the planned action'
        checks.append('required-source action reveals the real scenario field; overflow never truncates')

        page.select_option('#job','uncertain')
        page.check('#conflict')
        page.select_option('#assistance','expert')
        assert page.locator('#nextTitle').inner_text()=='Inspect the original request'
        assert page.locator('#secondary').is_visible(), 'blocking conflict must remain visible in Expert during uncertainty'
        assert 'draft conflict' in page.locator('#secondary').inner_text()
        page.click('#reviewPlan')
        assert 'demo-request-17' in page.locator('#reviewText').inner_text()
        assert page.locator('#applyExample').is_hidden()
        page.keyboard.press('Escape')
        expect(page.locator('#reviewPlan')).to_be_focused()
        page.select_option('#job','idle')
        page.check('#conflict')
        assert 'conflicting' in page.locator('#nextTitle').inner_text()
        page.uncheck('#conflict')
        checks.append('uncertain receipt and draft conflict remain visible in Expert')

        page.select_option('#assistance','studio')
        page.uncheck('#internet')
        assert page.locator('#nextTitle').inner_text()=='Review the planned action'
        page.locator('#appearance > summary').click()
        page.select_option('#motion','cinematic')
        page.select_option('#media','local-loop')
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='local-loop'
        page.select_option('#backend','unavailable')
        assert 'backend' in page.locator('#nextTitle').inner_text()
        page.select_option('#backend','ready')
        checks.append('internet/backend distinction; local loop eligibility does not require internet')

        for selector in ('#reduced','#economy','#paused'):
            page.check(selector)
            assert page.locator('#mediaDecision').get_attribute('data-mode')=='still',selector
            page.uncheck(selector)
        page.uncheck('#visible')
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='paused'
        page.check('#visible')
        page.select_option('#job','running')
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='still'
        page.select_option('#job','idle')
        page.emulate_media(reduced_motion='reduce')
        expect(page.locator('#mediaDecision')).to_have_attribute('data-mode','still')
        assert 'OS reduced motion: on' in page.locator('#osMotion').inner_text()
        page.emulate_media(reduced_motion='no-preference')
        expect(page.locator('#mediaDecision')).to_have_attribute('data-mode','local-loop')
        checks.append('user, OS, visibility, economy and active-job motion precedence')

        page.select_option('#media','remote-available')
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='still'
        page.check('#remoteAllowed')
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='remote-loop'
        page.uncheck('#poster')
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='tokens'
        page.check('#poster')
        page.select_option('#media','failed')
        assert page.locator('#nextTitle').inner_text()=='Review the planned action'
        assert page.locator('#mediaDecision').get_attribute('data-mode')=='still'
        checks.append('remote permission, poster prerequisite and nonblocking media failure')

        page.select_option('#skin','atelier')
        page.click('#simulateLoad')
        page.select_option('#skin','sakura')
        page.select_option('#skin','atelier')
        expect(page.locator('#loadReceipt')).to_contain_text('Ignored obsolete')
        assert page.locator('#assetId').inner_text()=='atelier-poster'
        checks.append('delayed A-B-A asset result is rejected without any media request')

        # Collapse lab controls before measuring the normal workspace.
        page.locator('#simulation > summary').click()
        page.locator('#appearance > summary').click()
        skins=['atelier','arcade','sakura','retro-anime','minimal-pro','sci-fi-noir']
        for width,height in ((1440,900),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            for layout in ('focus','studio','bench'):
                page.select_option('#layout',layout)
                for skin in skins:
                    page.locator('#appearance > summary').click()
                    page.select_option('#skin',skin)
                    page.locator('#appearance > summary').click()
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,layout,skin)
                    assert page.evaluate("window.originalBrief===document.getElementById('brief')")
                    assert page.locator('#brief').input_value()=='Keep this draft across every lens and visual choice.'
                    box=page.locator('#reviewPlan').bounding_box()
                    assert box and box['y']>=0 and box['y']+box['height']<=height,(width,layout,skin,box)
        checks.append('36 layout/skin/viewport combinations preserve draft identity and keep review reachable')
        page.set_viewport_size({'width':1440,'height':900})
        page.evaluate("document.body.style.zoom='2'")
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate("document.body.style.zoom='1'")
        checks.append('200% zoom retains page width')
        assert not errors, errors
        assert not network, network
        checks.append('zero page errors and zero network requests')
        browser.close()
    report={'scope':'standalone synthetic behavior specification; no production adapter or actual media', 'checks':checks,'passed':len(checks),'page_errors':errors,'network_requests':network,'screenshots_created':False,'document_mode':'injected exact HTML' if injected else 'native file navigation'}
    if output:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--injected',action='store_true',help='Inject exact HTML when native file navigation is blocked; not file-origin qualification.')
    args=parser.parse_args()
    run(args.output,args.injected)
