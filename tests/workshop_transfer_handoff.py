"""Verify the Prompt Lab text handoff stays near the top of every Create presentation.

The fixture loads the production workshop styles against the real direct-child order. It
has no API, executor, storage or model connection and therefore cannot submit work.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'app' / 'static'


def _styles():
    wrapper = (STATIC / 'workshop-immersive.css').read_text(encoding='utf-8')
    core = (STATIC / 'workshop-immersive-core.css').read_text(encoding='utf-8')
    wrapper = wrapper.replace("@import url('workshop-immersive-core.css');", core)
    return '\n'.join([
        (STATIC / 'style.css').read_text(encoding='utf-8'),
        (STATIC / 'studio.css').read_text(encoding='utf-8'),
        (STATIC / 'workshop.css').read_text(encoding='utf-8'),
        wrapper,
        """
        body {margin:0}
        .studio-main main {max-width:none}
        #uxTransfer {grid-column:1/-1}
        #uxTransfer pre {min-height:58px}
        #createView .editor textarea {min-height:310px}
        """
    ])


def _document():
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{_styles()}</style></head>
<body class="studio-shell studio-main workshop-active" data-workshop-skin="atelier" data-workshop-ambience="none">
<main>
  <div id="createView" class="workspace view workshop" data-workshop-layout="focus" data-workshop-ambience="none">
    <div class="ux-create-heading"><div><span class="eyebrow">CREATE</span><h1>Follow the idea.</h1></div><div class="ux-stage-track"><span>Prepare</span><span>Run</span></div></div>
    <section id="uxTransfer" class="panel ux-transfer"><h2>Text from Prompt Lab</h2><p id="uxTransferNotice">A reviewed Prompt Lab draft is ready.</p><pre id="uxTransferPreview">A lantern-lit city workshop.</pre><button id="uxApplyPrompt" class="primary">Apply text to the selected recipe</button><button>Dismiss</button></section>
    <section id="workshopAmbienceHero" class="wk-immersive-hero" hidden><div class="wk-hero-copy"><span class="eyebrow">LOCAL / PRIVATE / YOURS</span><h2>Turn your ideas into something real.</h2><p>The same working draft.</p></div><div class="wk-hero-art"></div></section>
    <nav class="wk-modebar"><button class="active">Generate</button><a href="#">Prompt Lab</a><a href="#">Runs & review</a></nav>
    <div class="wk-toolbar"><div class="wk-select-controls"><label class="wk-select-control">Layout<select><option>Focus</option></select></label><label class="wk-select-control">Ambience<select><option>None</option></select></label></div><div class="wk-skin-control"><span class="wk-control-label">Skin</span><div class="wk-skin-picker"><button class="wk-skin-choice active">Atelier</button></div></div></div>
    <aside id="workshopSetupRail" class="wk-setup-rail"><div class="wk-rail-heading"><span class="eyebrow">RECIPE & READINESS</span><h2>Run setup</h2></div><div class="wk-recipe"><span class="wk-recipe-mark">✦</span><div><small>ACTIVE RECIPE</small><strong>Fixture recipe</strong></div><button>Change recipe</button></div><button class="wk-quick-tune">Fine-tune the recipe</button><div class="wk-setup-status"><strong>No blockers reported</strong><span>Runtime estimate unavailable</span></div></aside>
    <section class="panel editor"><label id="positiveWrap">Describe your idea<textarea id="positive">Fixture prompt</textarea></label><details class="ux-parameters"><summary>Fine-tune the recipe</summary><div id="controls"></div></details><details id="workshopChecks" class="wk-disclosure"><summary>Readiness & run details</summary></details></section>
    <aside id="workshopGuidance" class="wk-guidance"><span class="eyebrow">ONE NEXT ACTION</span><h2>Ready when you are</h2><p>The existing Generate control is enabled.</p><button>Focus Generate</button></aside>
    <div id="jobProblemsHost"></div>
    <details id="workshopResults" class="wk-results"><summary>Recent runs</summary><section class="panel gallery-panel"><div id="gallery" class="galleryEmpty">No outputs</div></section></details>
  </div>
</main>
</body></html>"""


def _rects(page):
    return page.evaluate(
        """() => {
          const rect = selector => {
            const element = document.querySelector(selector);
            const box = element.getBoundingClientRect();
            return {
              top: box.top, bottom: box.bottom, left: box.left, right: box.right,
              width: box.width, height: box.height,
              visible: getComputedStyle(element).display !== 'none' && box.width > 0 && box.height > 0
            };
          };
          return {
            create: rect('#createView'), heading: rect('.ux-create-heading'),
            hero: rect('#workshopAmbienceHero'), modes: rect('.wk-modebar'),
            transfer: rect('#uxTransfer'), apply: rect('#uxApplyPrompt'),
            toolbar: rect('.wk-toolbar'), editor: rect('#createView .editor')
          };
        }"""
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-transfer')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks, page_errors, requests = [], [], []

    with sync_playwright() as playwright:
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
        for width, height in [(1440, 900), (390, 844)]:
            for layout in ['focus', 'studio', 'immersive']:
                for ambience in ['none', 'night-shift']:
                    page = browser.new_page(viewport={'width': width, 'height': height})
                    page.on('pageerror', lambda error: page_errors.append(str(error)))
                    page.on('request', lambda request: requests.append(request.url))
                    page.set_content(_document(), wait_until='load')
                    page.evaluate(
                        """([layout, ambience]) => {
                          const create = document.querySelector('#createView');
                          create.dataset.workshopLayout = layout;
                          create.dataset.workshopAmbience = ambience;
                          document.body.dataset.workshopAmbience = ambience;
                          document.querySelector('#workshopAmbienceHero').hidden = ambience === 'none';
                        }""",
                        [layout, ambience]
                    )
                    page.wait_for_timeout(50)

                    rects = _rects(page)
                    assert rects['transfer']['visible'], (width, layout, ambience, rects)
                    assert rects['apply']['visible'], (width, layout, ambience, rects)
                    assert rects['transfer']['top'] < rects['editor']['top'], (width, layout, ambience, rects)
                    assert rects['apply']['bottom'] <= height, (width, layout, ambience, rects['apply'])
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, layout, ambience)
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
                        page.screenshot(path=str(args.output / f'transfer-{layout}.png'), full_page=True)
                    checks.append({
                        'width': width, 'height': height, 'layout': layout,
                        'ambience': ambience, 'apply_bottom': rects['apply']['bottom']
                    })
                    page.close()
        browser.close()

    assert not page_errors, page_errors
    assert not requests, requests
    (args.output / 'report.json').write_text(json.dumps({
        'synthetic_component': True,
        'live_comfyui': False,
        'checks': checks,
        'page_errors': page_errors,
        'network_requests': requests,
        'job_submissions': []
    }, indent=2) + '\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
