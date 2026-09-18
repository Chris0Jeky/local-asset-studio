"""Browser qualification for the local static ambience policy.

This uses the deterministic workshop fixture. It does not connect to ComfyUI,
load remote media, or authorize generation.
"""
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def stylesheet(path: Path, stack=()) -> str:
    path = path.resolve()
    if path in stack:
        raise RuntimeError(f'circular CSS import: {path}')
    css = path.read_text(encoding='utf-8')
    return re.sub(
        r"@import\s+url\(['\"]?([^'\")]+)['\"]?\)\s*;",
        lambda match: stylesheet(path.parent / match.group(1), stack + (path,)),
        css,
    )


def inline_fixture() -> str:
    html = (ROOT / 'tests/workshop_fixture.html').read_text(encoding='utf-8')
    scripts = [
        ('/static/presentation-context.js', ROOT / 'app/static/presentation-context.js'),
        ('/static/workshop-ambience-policy.js', ROOT / 'app/static/workshop-ambience-policy.js'),
        ('/static/workshop.js', ROOT / 'app/static/workshop.js'),
        ('/static/workshop-ambience.js', ROOT / 'app/static/workshop-ambience.js'),
    ]
    for source, path in scripts:
        body = path.read_text(encoding='utf-8').replace('</script', '<\\/script')
        html = html.replace(f'<script src="{source}"></script>', f'<script>{body}</script>')
    styles = ''.join([
        '<style id="workshopStyles">' + stylesheet(ROOT / 'app/static/workshop.css') + '</style>',
        '<style id="workshopImmersiveStyles">' + stylesheet(ROOT / 'app/static/workshop-immersive.css') + '</style>',
        '<style id="workshopAmbiencePolicyStyles">' + stylesheet(ROOT / 'app/static/workshop-ambience.css') + '</style>',
    ])
    return html.replace('</style>', '</style>' + styles, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-ambience')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    checks = []
    errors = []
    requests = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url)
                if request.url.startswith(('http:', 'https:', 'ws:', 'wss:')) else None)
        page.set_content(inline_fixture())
        page.wait_for_selector('#workshopRecipeChange')
        page.wait_for_function("document.querySelector('#createView').__workshopAmbience")

        prompt = page.locator('#positive').element_handle()
        source = page.locator('#reference').element_handle()
        page.select_option('#workshopLayout', 'immersive')
        page.select_option('#workshopAmbience', 'night-shift')
        page.wait_for_function("createView.__workshopAmbience.snapshot().renderMode === 'poster'")
        decision = page.evaluate('createView.__workshopAmbience.snapshot()')
        assert decision['assetId'] == 'night-shift'
        assert decision['authorizesExecution'] is False
        assert decision['commands'] == []
        assert decision['motionEligible'] is False
        assert page.locator('#workshopAmbienceHero').is_visible()
        assert 'Local static poster' in page.locator('#workshopAmbienceStatus').inner_text()
        assert page.evaluate('submitted') == 0
        checks.append({'name': 'available local poster is visible without execution authority'})

        missing = page.evaluate("createView.__workshopAmbience.setAssetState('missing')")
        assert missing['renderMode'] == 'tokens'
        assert page.locator('#workshopAmbienceHero').is_visible()
        assert page.evaluate("getComputedStyle(workshopAmbienceHero,'::after').backgroundImage === 'none'")
        assert page.locator('#positive').element_handle() == prompt
        assert page.locator('#reference').element_handle() == source
        assert page.evaluate('submitted') == 0
        checks.append({'name': 'missing poster falls back to tokens and preserves controls'})

        page.evaluate("createView.__workshopAmbience.setAssetState('available')")
        context.set_offline(True)
        page.evaluate('createView.__workshopAmbience.refresh()')
        assert page.evaluate("createView.__workshopAmbience.snapshot().renderMode") == 'poster'
        context.set_offline(False)
        checks.append({'name': 'local poster remains available while internet is offline'})

        page.emulate_media(forced_colors='active')
        page.wait_for_function("createView.__workshopAmbience.snapshot().renderMode === 'tokens'")
        assert page.evaluate("getComputedStyle(workshopAmbienceHero,'::after').backgroundImage === 'none'")
        page.emulate_media(forced_colors='none')
        page.wait_for_function("createView.__workshopAmbience.snapshot().renderMode === 'poster'")
        checks.append({'name': 'forced colours use token fallback and restore the poster'})

        page.select_option('#workshopAmbience', 'none')
        page.wait_for_function("createView.__workshopAmbience.snapshot().renderMode === 'none'")
        assert page.locator('#workshopAmbienceHero').is_hidden()
        assert page.evaluate('submitted') == 0
        checks.append({'name': 'None removes the decorative surface without submitting'})

        assert not errors, errors
        assert not requests, requests
        page.screenshot(path=str(args.output / 'ambience-policy.png'), full_page=True)
        browser.close()

    report = {
        'fixture':'workshop_fixture.html',
        'live_comfyui':False,
        'network_requests':requests,
        'page_errors':errors,
        'checks':checks,
    }
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
