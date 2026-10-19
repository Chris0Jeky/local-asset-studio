"""Explicit saved-switch resolution through native controls and inert HTTP responses."""
import copy


async def exercise_backend_resolution(page, checks, posts):
    writes=[];before=len(posts)
    base={'active':'primary','busy':False,'operation':{'id':'legacy-switch','status':'running','target':'primary',
          'message':'Checking owned local runtimes'},'profiles':[{'id':'primary','name':'Main library','active':True,'installed':True}],
          'shared_state':{'sha256':'a'*64,'blocker':'Legacy switch needs inspection. Resolve the saved switch in Models & setup.','resolvable':True}}
    observed=copy.deepcopy(base)

    async def read(route):
        await route.fulfill(json=observed)

    async def resolve(route):
        writes.append({'path':route.request.url.rsplit('/',1)[-1],'body':route.request.post_data_json})
        observed['operation']={'id':'legacy-switch','status':'interrupted','message':'Saved switch resolved after inspection.'}
        observed['shared_state']={'sha256':'d'*64,'blocker':None,'resolvable':False}
        await route.fulfill(json=observed)

    await page.route('**/api/backends',read)
    await page.route('**/api/backends/resolve-switch',resolve)
    try:
        await page.evaluate("showView('models')")
        for width in (1440,390):
            await page.set_viewport_size({'width':width,'height':900})
            observed=copy.deepcopy(base)
            start=len(writes)
            await page.evaluate('refreshBackends()')
            assert await page.locator('#backendResolution').is_visible()
            assert await page.locator('#switchBackend').is_disabled()
            assert 'Legacy switch needs inspection' in await page.locator('#backendStatus').inner_text()
            assert 'Switching to' not in await page.locator('#envSummary').inner_text()
            assert await page.locator('#resolveBackendSwitch').is_disabled()
            assert len(writes)==start, 'Reading a legacy record must not resolve it'
            await page.check('#backendStudiosClosed')
            assert await page.locator('#resolveBackendSwitch').is_disabled()
            assert len(writes)==start, 'One acknowledgement must not resolve it'
            await page.check('#backendRuntimesInspected')
            assert await page.locator('#resolveBackendSwitch').is_enabled()
            await page.evaluate('refreshBackends()')
            assert await page.locator('#resolveBackendSwitch').is_enabled(), 'An identical read preserves the deliberate checks'
            observed['shared_state']['sha256']='b'*64
            await page.evaluate('refreshBackends()')
            assert not await page.locator('#backendStudiosClosed').is_checked()
            assert not await page.locator('#backendRuntimesInspected').is_checked()
            assert await page.locator('#resolveBackendSwitch').is_disabled()
            assert len(writes)==start, 'A replacement record requires new acknowledgements'
            await page.check('#backendStudiosClosed');await page.check('#backendRuntimesInspected')
            await page.click('#resolveBackendSwitch')
            await page.wait_for_function('!backendResolving && document.querySelector("#backendResolution").hidden')
            assert writes[start:]==[{'path':'resolve-switch','body':{'expected_sha256':'b'*64,
                   'acknowledge_studios_closed':True,'acknowledge_runtimes_inspected':True}}]
            assert await page.locator('#switchBackend').is_enabled()
            assert await page.locator('#backendStatus').evaluate('node=>node===document.activeElement'), 'Hiding the completed controls keeps focus visible'
            observed=copy.deepcopy(base)
            observed['shared_state']={'sha256':'c'*64,'blocker':'Another Studio still owns the shared switch. Wait for it.','resolvable':False}
            await page.evaluate('refreshBackends()')
            assert not await page.locator('#backendResolution').is_visible()
            assert await page.locator('#switchBackend').is_disabled()
            assert 'Another Studio still owns' in await page.locator('#backendStatus').inner_text()
            assert 'Switching to' not in await page.locator('#envSummary').inner_text()
            assert len(writes)==start+1
            checks.append(f'{width}px legacy resolution requires both checks for the exact record; replacement resets checks, live foreign ownership stays blocked, and only one explicit resolution POST occurs')
        assert {row['path'] for row in posts[before:]}<={'/api/estimate','/api/references/check'}, 'The native resolution fixture never reaches a runtime action or generation route'
    finally:
        await page.unroute('**/api/backends',read)
        await page.unroute('**/api/backends/resolve-switch',resolve)
        await page.evaluate("refreshBackends();showView('create')")
