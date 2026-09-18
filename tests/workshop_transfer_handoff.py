"""Verify the Prompt Lab text handoff stays near the top of every Create presentation.

This uses the real frontend and native loopback HTTP with the existing synthetic API.
It never invokes ComfyUI or accepts a generation request.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture

ROOT = Path(__file__).resolve().parents[1]


def _rects(page):
    return page.evaluate(
        """() => {
          const rect = selector => {
            const element = document.querySelector(selector);
            const box = element.getBoundingClientRect();
            return {
              top: box.top,
              bottom: box.bottom,
              left: box.left,
              right: box.right,
              width: box.width,
              height: box.height,
              visible: getComputedStyle(element).display !== 'none' && box.width > 0 && box.height > 0
            };
          };
          return {
            create: rect('#createView'),
            heading: rect('.ux-create-heading'),
            hero: rect('#workshopAmbienceHero'),
            modes: rect('.wk-modebar'),
            transfer: rect('#uxTransfer'),
            apply: rect('#uxApplyPrompt'),
            toolbar: rect('.wk-toolbar'),
            editor: rect('#createView .editor')
          };
        }"""
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-transfer')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    fixture.POSTS.clear()
    server = ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    checks = []
    page_errors = []

    try:
        with sync_playwright() as playwright:
            executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
            browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))

            for width, height in [(1440, 900), (390, 844)]:
                for layout in ['focus', 'studio', 'immersive']:
                    for ambience in ['none', 'night-shift']:
                        page = browser.new_page(viewport={'width': width, 'height': height})
                        page.on('pageerror', lambda error: page_errors.append(str(error)))
                        page.goto(origin + '/#create')
                        page.wait_for_function(
                            "!!selected && schemaAvailable && !!document.querySelector('#workshopRecipeChange')"
                        )
                        page.wait_for_function(
                            "!!document.querySelector('#workshopImmersiveStyles')?.sheet"
                        )
                        page.select_option('#workshopLayout', layout)
                        page.select_option('#workshopAmbience', ambience)
                        page.evaluate(
                            """() => {
                              const transfer = document.querySelector('#uxTransfer');
                              transfer.hidden = false;
                              document.querySelector('#uxTransferNotice').textContent = 'A reviewed Prompt Lab draft is ready.';
                              document.querySelector('#uxTransferPreview').textContent = 'A lantern-lit city workshop.';
                            }"""
                        )
                        page.wait_for_timeout(100)

                        rects = _rects(page)
                        assert rects['transfer']['visible'], (width, layout, ambience, rects)
                        assert rects['apply']['visible'], (width, layout, ambience, rects)
                        assert rects['transfer']['top'] < rects['editor']['top'], (
                            width, layout, ambience, rects
                        )
                        assert rects['apply']['bottom'] <= height, (
                            width, layout, ambience, rects['apply']
                        )
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (
                            width, layout, ambience
                        )

                        # The transfer is a full-width handoff above the ordinary working surfaces.
                        assert abs(rects['transfer']['left'] - rects['create']['left']) <= 2, rects
                        assert abs(rects['transfer']['right'] - rects['create']['right']) <= 2, rects

                        if layout in {'focus', 'studio'}:
                            assert rects['heading']['visible'], rects
                            assert rects['transfer']['top'] >= rects['heading']['bottom'] - 1, rects
                            next_surface = rects['hero'] if ambience == 'night-shift' else rects['toolbar']
                            assert next_surface['visible'], rects
                            assert rects['transfer']['bottom'] <= next_surface['top'] + 1, rects
                        else:
                            assert not rects['heading']['visible'], rects
                            assert rects['modes']['visible'], rects
                            assert rects['transfer']['top'] >= rects['modes']['bottom'] - 1, rects
                            assert rects['transfer']['bottom'] <= rects['toolbar']['top'] + 1, rects

                        if width == 1440 and ambience == 'night-shift':
                            page.screenshot(
                                path=str(args.output / f'transfer-{layout}.png'),
                                full_page=True
                            )
                        checks.append({
                            'width': width,
                            'height': height,
                            'layout': layout,
                            'ambience': ambience,
                            'apply_bottom': rects['apply']['bottom']
                        })
                        page.close()

            assert not page_errors, page_errors
            assert not [row for row in fixture.POSTS if row['path'] == '/api/jobs']
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        (args.output / 'report.json').write_text(
            json.dumps({
                'synthetic_api': True,
                'live_comfyui': False,
                'checks': checks,
                'page_errors': page_errors,
                'job_submissions': [row for row in fixture.POSTS if row['path'] == '/api/jobs']
            }, indent=2) + '\n'
        )

    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
