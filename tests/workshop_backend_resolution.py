"""Explicit saved-switch resolution through native controls and inert HTTP responses."""
import copy


async def exercise_backend_work_refusal(page, checks, posts):
    """A work-only mismatch keeps its explicit repair available on both Generate surfaces."""
    writes=[];before=len(posts)
    reason='The saved backend selection differs from this Studio. Switch explicitly in Models & setup or restart Studio after inspection before starting work.'
    observed={'active':'primary','busy':False,'operation':{'status':'completed','target':'hidream','message':'Previous switch completed.'},
              'profiles':[{'id':'primary','name':'Main library','active':True,'installed':True},
                          {'id':'hidream','name':'HiDream O1 · isolated','active':False,'installed':True}],
              'shared_state':{'sha256':'f'*64,'blocker':None,'resolvable':False},'work_blocker':None}

    async def read(route):await route.fulfill(json=observed)

    async def switch(route):
        writes.append(route.request.post_data_json)
        assert writes[-1]=={'id':'primary'}
        observed['work_blocker']=None
        observed['operation']={'status':'completed','target':'primary','message':'Explicit fixture reselection completed.'}
        await route.fulfill(json=observed)

    async def looks(route):
        await route.fulfill(json={'looks':[{'id':'look-wai-fantasy-portrait','name':'Work-admission fixture look','kind':'look','revision':0,
                                          'body':{'preset_id':'zimage-fast','controls':{},'scene_example':'A quiet garden'}}]})

    await page.route('**/api/backends',read)
    await page.route('**/api/backends/switch',switch)
    await page.route('**/api/looks',looks)
    try:
        await page.evaluate("refreshBackends()")
        await page.evaluate("showView('make')")
        await page.click('[data-make-goal="character"]')
        if await page.locator('[data-make-change]').count():await page.click('[data-make-change]')
        await page.click('[data-make-look="look-wai-fantasy-portrait"]')
        for width in (1440,390):
            await page.set_viewport_size({'width':width,'height':900})
            observed['work_blocker']=None
            await page.evaluate("async()=>{await refreshBackends();selectPreset('anima-portrait',true,true);showView('create');}")
            await page.fill('#positive','Keep the Create draft while inspecting the environment')
            await page.evaluate('()=>{for(let parent=getControl("seed").parentElement;parent;parent=parent.parentElement)if(parent.tagName==="DETAILS")parent.open=true;}')
            await page.fill('[data-key="seed"]','')
            await page.locator('#positive').focus()
            await page.wait_for_function('!document.querySelector("#generate").disabled')
            draft=await page.evaluate('JSON.stringify({preset:selected.id,controls:values(),refs:attachedReferencePayload(),parents:parentAssets})')
            start=len(writes)
            observed['work_blocker']=reason
            await page.evaluate('refreshBackends()')
            assert await page.locator('#generate').is_disabled()
            assert await page.locator('#positive').evaluate('node=>node===document.activeElement')
            await page.wait_for_function('(reason)=>document.querySelector("#workshopReadiness").textContent===reason',arg=reason)
            assert await page.locator('#workshopReadiness').is_visible()
            await page.click('#workshopReview')
            assert reason in await page.locator('#uxBlockers').inner_text()
            repair=page.locator('[data-readiness-code="backend-work"] [data-ux-resolve="models"]')
            await repair.focus();await page.evaluate('refreshBackends()')
            assert await repair.evaluate('node=>node===document.activeElement'), 'An identical read preserves the repair action and its focus'
            await repair.click()
            assert await page.locator('#backendChoice').is_enabled()
            assert await page.locator('#switchBackend').is_enabled()
            assert await page.locator('#backendChoice').evaluate('node=>node===document.activeElement')
            assert await page.locator('.environment-panel').evaluate('node=>node.open')
            assert reason==await page.locator('#backendStatus').inner_text()
            assert not await page.locator('#backendResolution').is_visible()
            assert len(writes)==start, 'Observing and showing the repair must not switch'
            assert draft==await page.evaluate('JSON.stringify({preset:selected.id,controls:values(),refs:attachedReferencePayload(),parents:parentAssets})')
            checks.append(f'{width}px work-only refusal disables Create Generate, preserves its draft and focused repair action, and opens enabled explicit Switch controls without a POST')

            await page.evaluate("showView('make')")
            await page.fill('#makeScene','Keep the Make draft while inspecting the environment')
            observed['work_blocker']=None;await page.evaluate('refreshBackends()')
            assert await page.locator('#makeGenerate').is_enabled()
            await page.locator('#makeScene').focus()
            await page.evaluate('window.__workRefusalComposer=document.querySelector("#makeComposer");window.__workRefusalDraft=document.querySelector("#makeScene")')
            observed['work_blocker']=reason;await page.evaluate('refreshBackends()')
            assert await page.locator('#makeGenerate').is_disabled()
            assert reason==await page.locator('#makeWhy').inner_text()
            assert await page.evaluate('document.querySelector("#makeComposer")===__workRefusalComposer && document.querySelector("#makeScene")===__workRefusalDraft && document.activeElement===__workRefusalDraft')
            assert await page.locator('#makeScene').input_value()=='Keep the Make draft while inspecting the environment'
            await page.locator('#makeWhy a').click()
            await page.select_option('#backendChoice','primary')
            await page.click('#switchBackend')
            await page.wait_for_function('!backendSwitching && !backendWorkBlocker')
            assert writes[start:]==[{'id':'primary'}]
            await page.evaluate("showView('create')")
            assert await page.locator('#generate').is_enabled()
            assert draft==await page.evaluate('JSON.stringify({preset:selected.id,controls:values(),refs:attachedReferencePayload(),parents:parentAssets})')
            checks.append(f'{width}px an open Make composer observes work refusal without replacing its draft or focus; one intercepted native Switch clears the reason and restores ordinary Create readiness')
        assert {row['path'] for row in posts[before:]}<={'/api/estimate','/api/references/check'}, 'Work-refusal inspection never reaches a runtime action or generation route'
    finally:
        await page.unroute('**/api/backends',read)
        await page.unroute('**/api/backends/switch',switch)
        await page.unroute('**/api/looks',looks)


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
        if observed['operation']['status']=='completed':
            observed['active']='hidream'
            for profile in observed['profiles']:profile['active']=profile['id']=='hidream'
        else:observed['operation']={'id':'legacy-switch','status':'interrupted','message':'Saved switch resolved after inspection.'}
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
            await page.locator('#resolveBackendSwitch').focus()
            await page.evaluate('refreshBackends()')
            assert await page.locator('#resolveBackendSwitch').is_enabled(), 'An identical read preserves the deliberate checks'
            assert await page.locator('#resolveBackendSwitch').evaluate('node=>node===document.activeElement')
            observed['shared_state']['sha256']='b'*64
            await page.evaluate('refreshBackends()')
            assert not await page.locator('#backendStudiosClosed').is_checked()
            assert not await page.locator('#backendRuntimesInspected').is_checked()
            assert await page.locator('#resolveBackendSwitch').is_disabled()
            assert await page.locator('#backendStatus').evaluate('node=>node===document.activeElement'), 'Replacement transfers focus before disabling Resolve'
            assert len(writes)==start, 'A replacement record requires new acknowledgements'
            await page.locator('#backendStudiosClosed').focus()
            observed['shared_state']['sha256']='c'*64
            await page.evaluate('refreshBackends()')
            assert await page.locator('#backendStudiosClosed').evaluate('node=>node===document.activeElement'), 'A still-visible checkbox keeps focus across replacement'
            await page.check('#backendStudiosClosed');await page.check('#backendRuntimesInspected')
            await page.click('#resolveBackendSwitch')
            await page.wait_for_function('!backendResolving && document.querySelector("#backendResolution").hidden')
            assert writes[start:]==[{'path':'resolve-switch','body':{'expected_sha256':'c'*64,
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
            checks.append(f'{width}px legacy resolution requires both checks for the exact record; replacement resets checks and moves disabled-button focus to status while preserving checkbox focus; live foreign ownership stays blocked; only one explicit resolution POST occurs')
            observed=copy.deepcopy(base)
            observed['operation']={'id':'completed-switch','status':'completed','target':'hidream','message':'Completed switch saved; publication acknowledgement was lost.'}
            observed['profiles'].append({'id':'hidream','name':'HiDream O1 · isolated','active':False,'installed':True})
            observed['shared_state']={'sha256':'e'*64,'blocker':'Completion publication is unconfirmed; inspect the saved switch.','resolvable':True}
            await page.evaluate('refreshBackends()')
            disclosure=await page.locator('#backendResolution').inner_text()
            assert 'restores the saved environment for subsequent work' in disclosure
            assert 'Other resolutions keep the current environment' in disclosure
            assert 'Finish or reconcile active work first' in disclosure
            assert await page.locator('#activeBackend').inner_text()=='Main library'
            await page.check('#backendStudiosClosed');await page.check('#backendRuntimesInspected')
            await page.click('#resolveBackendSwitch')
            await page.wait_for_function('!backendResolving && backendActive==="hidream"')
            assert await page.locator('#activeBackend').inner_text()=='HiDream O1 · isolated'
            assert 'Active: HiDream O1' in await page.locator('#envSummary').inner_text()
            assert not await page.locator('#backendResolution').is_visible()
            assert writes[start+1:]==[{'path':'resolve-switch','body':{'expected_sha256':'e'*64,
                   'acknowledge_studios_closed':True,'acknowledge_runtimes_inspected':True}}]
            checks.append(f'{width}px completed resolution discloses saved-environment restoration, then displays that environment after its single explicit acknowledgement without switching or generating')
        await exercise_backend_work_refusal(page, checks, posts)
        assert {row['path'] for row in posts[before:]}<={'/api/estimate','/api/references/check'}, 'The native resolution fixture never reaches a runtime action or generation route'
    finally:
        await page.unroute('**/api/backends',read)
        await page.unroute('**/api/backends/resolve-switch',resolve)
        await page.evaluate("refreshBackends();showView('create')")
