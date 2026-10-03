"""Native UI round trips for prepared routes, using fixture API only."""
import copy
import json
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_browser_smoke as fixture

SAVED = []


class Handler(fixture.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/api/setups':
            return self.json(SAVED)
        return super().do_GET()

    def do_POST(self):
        if self.path in ('/api/setups', '/api/recipe-check'):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            fixture.POSTS.append({'path': self.path, 'data': body})
            if self.path == '/api/recipe-check':
                return self.json({'template_sha256': 'e'*64})
            row = {'id': str(len(SAVED)), 'name': body['name'], 'recipe': body['recipe']}
            SAVED.append(row)
            return self.json(row)
        return super().do_POST()


def main():
    from playwright.sync_api import sync_playwright
    tile_id = next(p['id'] for p in fixture.CATALOG['presets'] if p.get('tile_route'))
    parallax_id = next(p['id'] for p in fixture.CATALOG['presets'] if p.get('parallax_route'))
    common = {'version': 1, 'source_asset_id': 'asset-0', 'source_sha256': 'a'*64}
    plans = [('tile', dict(common, preset_id=tile_id, rolled_file='b'*32+'_seam.png', rolled_sha256='c'*64,
                           size=512, band_px=112, feather_px=12, flatten_sigma_px=48)),
             ('parallax', dict(common, preset_id=parallax_id, source_file='b'*32+'_room.png', plan_id='c'*64,
                               stage='isolate', width=512, height=512, objects='the desk', view_polygons=[]))]
    errors = []
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path=os.environ.get('CHROMIUM_PATH'))
                try:
                    for width in (1536, 390):
                        page = browser.new_page(viewport={'width': width, 'height': 1060})
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(f'http://127.0.0.1:{server.server_port}/')
                        page.wait_for_function("typeof StudioSetupDraft !== 'undefined' && !!selected && schemaAvailable")
                        page.evaluate("showView('create')")
                        for kind, plan in plans:
                            recipe = {'preset': plan['preset_id'], kind: plan, 'batch': 1, 'parent_assets': ['asset-0'],
                                      'parent_by_input': {'reference': 'asset-0'},
                                      'controls': {'reference': plan.get('rolled_file') or plan['source_file'],
                                                   'positive': 'A reviewed prepared edit.', 'width': 512, 'height': 512}}
                            page.evaluate('(r) => applySaved(r)', recipe)
                            assert page.evaluate('continuationBlockers()') == []
                            captured = page.evaluate('StudioSetupDraft.capture()')
                            assert captured['recipe'][kind] == plan
                            page.evaluate('(d) => applySaved(d.recipe)', captured)
                            assert page.evaluate('(k) => (k === "tile" ? tilePayload() : parallaxPayload())[k]', kind) == plan
                            before = len(SAVED)
                            page.evaluate("() => { document.querySelector('#saveName').value='Prepared browser test';document.querySelector('#save').click(); }")
                            page.wait_for_function("!savingSetup && document.querySelector('#setupStatus').textContent.includes('Setup saved')")
                            assert len(SAVED) == before + 1
                            assert SAVED[-1]['recipe'][kind] == plan
                            # The actual recipe import handler must preserve the checked envelope too.
                            exported = dict(copy.deepcopy(recipe), preset_id=recipe['preset'], batch_count=1)
                            page.locator('#importRecipe').set_input_files({'name': 'recipe.json', 'mimeType': 'application/json', 'buffer': json.dumps(exported).encode()})
                            page.wait_for_function("recipeTemplateHash === 'e'.repeat(64)")
                            assert page.evaluate('(k) => (k === "tile" ? tilePayload() : parallaxPayload())[k]', kind) == plan
                            page.evaluate("uploaded='changed.png';updateReady()")
                            assert page.locator('#generate').is_disabled()
                            assert 'prepared picture' in ' '.join(page.evaluate('continuationBlockers()'))
                        page.close()
                    assert not errors, errors
                    allowed = {'/api/setups', '/api/recipe-check', '/api/estimate', '/api/references/check'}
                    assert all(row['path'] in allowed for row in fixture.POSTS), fixture.POSTS
                    print('Prepared drafts: tile/parallax capture, restore, named save, checked import, stale-source hold at desktop/mobile; no generation')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
