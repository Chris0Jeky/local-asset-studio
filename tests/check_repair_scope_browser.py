"""Optional Chromium display probe for the pure synthetic scope fixture.

Requires Playwright and an already installed Chromium executable. No downloads,
Studio server, file navigation, model calls or user artwork. Generated HTML is
supplied via set_content; this is display/keyboard evidence, not native intake.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from test_repair_scope_review import fixture
from scripts.repair_scope_review import render_html, scope_views


def probe(output, browser_path, no_sandbox=False):
    from playwright.sync_api import sync_playwright
    original, images, geometry = fixture()
    multiplier = 20
    original = original.resize((original.width*multiplier, original.height*multiplier), Image.Resampling.NEAREST)
    for key, image in images.items():
        images[key] = image.resize((image.width*multiplier, image.height*multiplier), Image.Resampling.NEAREST)
    geometry = {key: [value*multiplier for value in vector] for key, vector in geometry.items()}
    draw = ImageDraw.Draw(original)
    draw.ellipse((125, 60, 180, 115), fill=(48, 59, 69, 255))
    draw.line((155, 115, 155, 230), fill=(48, 59, 69, 255), width=20)
    draw.line((110, 165, 155, 145, 210, 165), fill=(48, 59, 69, 255), width=12)
    draw.ellipse((335, 65, 390, 120), fill=(145, 61, 181, 255))
    draw.line((365, 120, 365, 280), fill=(145, 61, 181, 255), width=30)
    views, summary = scope_views(original, images, geometry)
    html = render_html(views, summary, {'request_sha256': 'a'*64, 'expected_effective_write_sha256': 'b'*64,
        'fixture': 'independent synthetic display only; not a prepared or accepted model request'}).decode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True); output.mkdir()
    (output/'scope-review.html').write_text(html, encoding='utf-8')
    observations = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(browser_path), headless=True,
                                     args=['--no-sandbox'] if no_sandbox else [])
        try:
            for label, width in (('desktop', 1280), ('mobile', 390)):
                page = browser.new_page(viewport={'width': width, 'height': 900})
                page.set_default_timeout(10000)
                requests, errors = [], []
                page.on('request', lambda request: requests.append(request.url))
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/*', lambda route: route.abort())
                page.set_content(html); page.wait_for_load_state('load')
                assert page.locator('img').count() == 3
                assert page.locator('img').evaluate_all('(els) => els.every(el => el.complete && el.naturalWidth > 0)')
                assert page.locator('[data-stat]').count() == 4
                digest = page.get_by_label('Effective write-mask SHA-256')
                assert digest.input_value() == 'b'*64 and digest.evaluate('(el) => el.readOnly')
                evidence = page.locator('#raw-evidence')
                assert evidence.get_attribute('open') is None
                evidence.locator('summary').focus(); page.keyboard.press('Enter')
                assert evidence.get_attribute('open') is not None
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.keyboard.press('Space'); assert evidence.get_attribute('open') is None
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not any(url.startswith(('http:', 'https:')) for url in requests), requests
                assert not errors, errors
                page.screenshot(path=str(output/(label+'.png')), full_page=True)
                observations[label] = {'width': width, 'loaded_images': 3, 'scope_statistics': 4,
                    'readonly_digest': True, 'keyboard_disclosure': True, 'horizontal_overflow': False,
                    'external_requests': 0, 'page_errors': errors}
                page.close()
            observations['browser_version'] = browser.version
        finally: browser.close()
    observations['evidence_scope'] = 'Chromium set_content of synthetic authored HTML; not file navigation, Studio shell or neural evidence'
    (output/'browser-result.json').write_text(json.dumps(observations, indent=2)+'\n', encoding='utf-8')
    return observations


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--no-sandbox', action='store_true', help='Only for an isolated container that requires this launch flag')
    args = parser.parse_args()
    try: print(json.dumps(probe(args.out, args.browser, args.no_sandbox), indent=2))
    except (ImportError, OSError, ValueError) as exc: parser.exit(2, f'scope-browser-probe: {exc}\n')
