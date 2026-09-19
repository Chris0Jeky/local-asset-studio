"""Presentation contracts against a deterministic, explicitly non-generating DOM fixture.

Run: python tests/workshop_browser.py --output .runtime/workshop-qa
Uses Playwright's Chromium, or STUDIO_BROWSER_EXECUTABLE for a system browser.
This is not a live ComfyUI or full application qualification.
"""
import argparse
import re
import json
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def _resolve_css(path: Path, stack=()) -> str:
    path = path.resolve()
    if path in stack:
        raise RuntimeError(f"circular CSS import: {path}")
    css = path.read_text(encoding="utf-8")
    return re.sub(
        r"@import\s+url\(['\"]?([^'\")]+)['\"]?\)\s*;",
        lambda match: _resolve_css(path.parent / match.group(1), stack + (path,)),
        css,
    )


def immersive_css() -> str:
    return _resolve_css(ROOT / "app/static/workshop-immersive.css")


def attach_page_observers(page, errors, requests, allowed_origins=()):
    page.on("pageerror", lambda error: errors.append(str(error)))

    def record(request):
        url = request.url
        if not url.startswith(("http:", "https:", "ws:", "wss:")):
            return
        if any(url.startswith(origin) for origin in allowed_origins):
            return
        requests.append(url)

    page.on("request", record)


def presentation_geometry_cases(layouts, skins, widths=((390, 844), (1440, 900))):
    return [
        {
            "width": width,
            "height": height,
            "layout": layout,
            "skin": skin,
            "ambience": ambience,
        }
        for width, height in widths
        for layout in layouts
        for skin in skins
        for ambience in ("none", "night-shift")
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-qa')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    def load(page):
        # Inline the exact production script/styles: this also runs in offline browser sandboxes.
        html = (ROOT / 'tests/workshop_fixture.html').read_text(encoding='utf-8')
        html = html.replace(
            '<script src="/static/workshop.js"></script>',
            '<script>' + (ROOT / 'app/static/presentation-context.js').read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>'
            + '<script>' + (ROOT / 'app/static/workshop.js').read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>',
        )
        styles = (
            '<style id="workshopStyles">' + (ROOT / 'app/static/workshop.css').read_text(encoding='utf-8') + '</style>'
            '<style id="workshopImmersiveStyles">' + immersive_css() + '</style>'
        )
        html = html.replace('</style>', '</style>' + styles, 1)
        page.set_content(html)

    checks = []
    with sync_playwright() as p:
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        requests = []
        attach_page_observers(page, errors, requests)
        load(page)
        page.wait_for_selector('#workshopRecipeChange', timeout=5000)
        page.wait_for_timeout(100)
        assert page.evaluate('submitted') == 0
        assert page.evaluate("Object.entries(originalNodes).every(([id,node])=>document.getElementById(id)===node)")
        assert page.evaluate("document.querySelector('#i2vMode') && document.querySelector('#i2vMode').closest('.wk-control-group') === null"), 'I2V mode must stay outside the 2-column control groups'
        assert page.evaluate("!!document.querySelector('#controls > label:has(#i2vMode)')")
        assert page.evaluate("document.getElementById('jobProblemsHost') && !document.getElementById('workshopResults').contains(document.getElementById('jobProblemsHost'))")
        page.evaluate("document.getElementById('jobProblemsHost').innerHTML='<details id=\"jobProblems\"><summary>Problems</summary><button id=\"observeFix\">Check known batch receipts</button></details>'")
        assert not page.locator('#workshopResults').evaluate('(el)=>el.open')
        assert page.locator('#jobProblems > summary').is_visible()
        page.locator('#jobProblems > summary').click()
        assert page.locator('#observeFix').is_visible()
        assert not page.locator('.ux-parameters').evaluate('(el)=>el.open')
        assert not page.locator('#negativeWrap').evaluate('(el)=>el.open')
        assert page.locator('#workshopLayout option').evaluate_all('(els)=>els.map(e=>e.value)') == ['focus', 'studio', 'immersive']
        assert page.locator('#workshopSkin option').evaluate_all('(els)=>els.map(e=>e.value)') == ['atelier', 'arcade', 'sakura', 'retro-anime']
        assert page.locator('#workshopAmbience option').evaluate_all('(els)=>els.map(e=>e.value)') == ['none', 'night-shift', 'quiet-morning']
        assert page.locator('#workshopAmbienceHero').is_hidden()
        height = page.evaluate('document.documentElement.scrollHeight')
        assert height < 1700, height
        assert page.locator('#generate').bounding_box()['y'] < 900
        assert page.locator('#positive').bounding_box()['y'] < 900
        page.screenshot(path=str(args.output / 'focus-atelier.png'), full_page=True)
        checks.append({'name': 'desktop first viewport + original controls + no submission', 'height': height})

        page.locator('#positive').fill('My unsaved private draft')
        page.locator('#workshopRecipeChange').click()
        assert page.locator('#workshopRecipeDialog').evaluate('(el)=>el.open')
        assert page.locator('#presetSearch').evaluate('(el)=>el===document.activeElement')
        page.keyboard.press('Escape')
        assert page.locator('#workshopRecipeChange').evaluate('(el)=>el===document.activeElement')
        assert page.locator('#positive').input_value() == 'My unsaved private draft'
        page.locator('#workshopRecipeChange').click()
        page.locator('[data-id="ink"]').click()
        assert page.evaluate('selectionCount') == 0
        assert page.locator('#positive').input_value() == 'My unsaved private draft'
        page.locator('#workshopRecipeChange').click()
        page.once('dialog', lambda d: d.dismiss())
        page.locator('[data-id="refine"]').click()
        assert page.evaluate('selectionCount') == 0
        assert page.locator('#positive').input_value() == 'My unsaved private draft'
        page.once('dialog', lambda d: d.accept())
        page.locator('[data-id="refine"]').click()
        assert page.evaluate('selectionCount') == 1
        assert not page.locator('#workshopRecipeDialog').evaluate('(el)=>el.open')
        checks.append({'name': 'native focus return + cancelled and accepted recipe replacement'})

        page.select_option('#workshopLayout', 'immersive')
        # A slot-less reference recipe is not a readiness prerequisite in app.js (referencesReady() returns
        # true and the recipe's example stands until replaced), so guidance must not invent one here.
        assert page.evaluate("document.querySelector('#workshopGuidanceAction')?.dataset.intent") != 'review-sources'
        checks.append({'name': 'a slot-less reference recipe reports no invented source prerequisite'})
        page.locator('#reference').set_input_files({'name': 'source.png', 'mimeType': 'image/png', 'buffer': b'fixture'})
        page.wait_for_function("document.querySelector('#workshopGuidanceAction')?.dataset.intent==='review-sources'")
        source_submissions = page.evaluate('submitted')
        page.locator('#workshopGuidanceAction').click()
        assert page.locator('#reference').evaluate('(el)=>el===document.activeElement')
        assert page.evaluate('submitted') == source_submissions
        page.evaluate("uploaded='source.png';document.dispatchEvent(new Event('studio:recipe'))")
        page.wait_for_function("document.querySelector('#workshopGuidanceAction')?.dataset.intent==='review-readiness'")
        await_value = page.locator('#positive').input_value()
        layouts = page.locator('#workshopLayout option').evaluate_all('(els)=>els.map(e=>e.value)')
        skins = page.locator('#workshopSkin option').evaluate_all('(els)=>els.map(e=>e.value)')
        ambiences = page.locator('#workshopAmbience option').evaluate_all('(els)=>els.map(e=>e.value)')
        for layout in layouts:
            for skin in skins:
                for ambience in ambiences:
                    page.select_option('#workshopLayout', layout)
                    page.select_option('#workshopSkin', skin)
                    page.select_option('#workshopAmbience', ambience)
                    assert page.locator('#positive').input_value() == await_value
                    assert page.locator('#reference').evaluate('(el)=>el.files[0].name') == 'source.png'
                    assert page.evaluate("document.getElementById('positive')===originalNodes.positive")
                    assert page.evaluate("document.getElementById('reference')===originalNodes.reference")
                    assert page.evaluate('submitted') == 0
        checks.append({'name': 'all presentation combinations preserve draft and input identity', 'layouts': layouts, 'skins': skins, 'ambiences': ambiences})

        page.select_option('#workshopLayout', 'immersive')
        page.locator('[data-workshop-skin-choice="retro-anime"]').click()
        page.select_option('#workshopAmbience', 'night-shift')
        assert page.locator('#workshopSkin').input_value() == 'retro-anime'
        assert page.locator('[data-workshop-skin-choice="retro-anime"]').get_attribute('aria-pressed') == 'true'
        assert page.locator('#workshopAmbienceHero').is_visible()
        assert page.evaluate("getComputedStyle(document.querySelector('#workshopAmbienceHero'),'::after').backgroundImage.includes('data:image/svg+xml')")
        page.evaluate('scrollTo(0,0)')
        page.wait_for_timeout(70)
        setup_box = page.locator('#workshopSetupRail').bounding_box()
        editor_box = page.locator('#createView .editor').bounding_box()
        guidance_box = page.locator('#workshopGuidance').bounding_box()
        assert setup_box and editor_box and guidance_box
        assert setup_box['x'] < editor_box['x'] < guidance_box['x'], (setup_box, editor_box, guidance_box)
        checks.append({'name': 'Immersive Studio uses local ambience and three live-control columns'})

        blocked_submission_count = page.evaluate('submitted')
        assert page.locator('#workshopGuidanceAction').get_attribute('data-intent') == 'review-readiness'
        page.locator('#workshopGuidanceAction').click()
        assert page.locator('#workshopChecks').evaluate('(el)=>el.open')
        assert page.evaluate('submitted') == blocked_submission_count
        assert page.evaluate("createView.__workshop.presentationView().authorizesSubmission===false")
        assert page.evaluate("createView.__workshop.presentationView().commands.length===0")
        assert 'private' not in page.evaluate("JSON.stringify(createView.__workshop.presentationView())")
        old_intent = page.evaluate("createView.__workshop.presentationView().primaryAction")
        old_stamp = old_intent['contextStamp']
        page.locator('#positive').fill('A different private draft with the same presentation')
        page.wait_for_function("stamp => createView.__workshop.presentationView().contextStamp !== stamp", arg=old_stamp)
        stale = page.evaluate("intent => createView.__workshop.dispatchIntent(intent)", old_intent)
        assert stale == {'ok': False, 'reason': 'stale-context'}
        assert page.evaluate('submitted') == blocked_submission_count

        page.evaluate("document.getElementById('uxBlockers').innerHTML='<div class=ux-blocker><p>Review image size</p><button data-ux-resolve=parameters>Review settings</button></div>'")
        page.locator('#workshopReview').click()
        page.locator('[data-ux-resolve="parameters"]').click()
        assert page.locator('[data-key="width"]').evaluate('(el)=>el===document.activeElement')
        assert page.locator('.ux-parameters').evaluate('(el)=>el.open')
        checks.append({'name': 'readiness action still reveals and focuses original control'})

        page.evaluate("document.getElementById('uxBlockers').replaceChildren();document.getElementById('generate').disabled=false")
        page.wait_for_function("document.querySelector('#workshopGuidanceAction').dataset.intent==='focus-generate'")
        page.locator('#workshopGuidanceAction').click()
        assert page.locator('#generate').evaluate('(el)=>el===document.activeElement')
        assert page.evaluate('submitted') == blocked_submission_count
        page.evaluate("document.getElementById('gallery').innerHTML='<article class=\"imageCard\">result</article>'")
        page.wait_for_function("document.querySelector('#workshopGuidanceAction').dataset.intent==='open-results'")
        page.locator('#workshopGuidanceAction').click()
        assert page.locator('#workshopResults').evaluate('(el)=>el.open')
        assert page.evaluate('submitted') == blocked_submission_count
        checks.append({'name': 'contextual guidance only reveals/focuses existing controls'})

        page.evaluate("document.getElementById('createView').hidden=true")
        assert not page.locator('#generate').is_visible()
        page.evaluate("document.getElementById('createView').hidden=false")
        assert page.locator('#generate').is_visible()
        assert not page.locator('#generate').is_disabled()
        page.locator('#generate').click()
        assert page.evaluate('submitted') == 1
        checks.append({'name': 'route hiding and exactly one original explicit Generate handler'})
        page.close()

        geometry = []
        for case in presentation_geometry_cases(layouts, skins):
            width = case["width"]
            viewport_height = case["height"]
            layout = case["layout"]
            skin = case["skin"]
            ambience = case["ambience"]
            page = browser.new_page(viewport={"width": width, "height": viewport_height})
            attach_page_observers(page, errors, requests)
            load(page)
            page.wait_for_selector('#workshopRecipeChange')
            page.select_option('#workshopLayout', layout)
            page.select_option('#workshopSkin', skin)
            page.select_option('#workshopAmbience', ambience)
            page.wait_for_timeout(70)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), case
            box = page.locator('#generate').bounding_box()
            assert box['y'] >= 0 and box['y'] + box['height'] <= viewport_height, (box, case)
            assert page.evaluate('submitted') == 0
            assert page.locator('#workshopAmbienceHero').is_visible() == (ambience != 'none')
            if layout == 'immersive':
                assert page.locator('#workshopSetupRail').is_visible()
                assert page.locator('#workshopGuidance').is_visible()
                setup_width = page.locator('#workshopSetupRail').bounding_box()['width']
                editor_width = page.locator('#createView .editor').bounding_box()['width']
                if width < 600:
                    assert setup_width >= width - 40, (width, setup_width)
                    assert editor_width >= width - 40, (width, editor_width)
                else:
                    assert setup_width >= 230, (width, setup_width)
                    assert editor_width >= 480, (width, editor_width)
            if (layout, skin) in {('focus','atelier'), ('studio','sakura'), ('immersive','retro-anime')}:
                page.screenshot(
                    path=str(args.output / f'{layout}-{skin}-{ambience}-{width}.png'),
                    full_page=True,
                )
            geometry.append(dict(case))
            page.close()
        assert not errors, errors
        assert not requests, requests
        checks.append({'name': 'desktop/mobile layout × skin × ambience geometry and no page errors', 'cases': geometry})
        browser.close()

    (args.output / 'report.json').write_text(json.dumps({'fixture': 'workshop_fixture.html', 'live_comfyui': False, 'network_requests': requests, 'checks': checks}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
