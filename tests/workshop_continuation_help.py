"""Read repeated guidance on demand without hiding the current task or changing it."""


async def exercise_continuation_help(page, checks, posts):
    await page.evaluate("selectPreset('anima-portrait',true,true);showView('assets');openAsset('asset-0')")
    await page.click('[data-ux-handoff="asset-0"]')
    await page.click('[data-ux-destination="restyle"]')
    await page.select_option('#uxDestination', 'restyle-wai')
    await page.wait_for_function("!document.querySelector('#uxPrepareHandoff').disabled")
    # Route semantics must remain readable before approving a source copy.
    assert await page.locator('#uxHandoffDetails').is_visible()
    await page.click('#uxPrepareHandoff')
    await page.wait_for_function("continuationState?.preset_id==='restyle-wai' && !document.querySelector('#uxHandoff').open")
    before = await page.evaluate('JSON.stringify(StudioSetupDraft.capture())')
    start_writes = len(posts)
    guidance = page.locator('#uxContinuationGuidance')
    assert not await guidance.is_visible(), 'Repeated continuation guidance should be closed by default'
    help_box = page.locator('#continuationGuidanceHelp')
    original = await guidance.text_content()
    assert len(original.split()) > 70, 'Exercise the real multi-paragraph explanation, not an empty fixture'
    await page.evaluate("window.retainedHelpNodes=[document.querySelector('#uxContinuationGuidance'),document.querySelector('#positive'),document.querySelector('#generate')]")
    for width, height in [(1440, 900), (390, 844)]:
        await page.set_viewport_size({'width': width, 'height': height})
        for layout in ('focus', 'studio', 'immersive'):
            await page.select_option('#workshopLayout', layout, force=True)
            summary = help_box.locator('summary')
            assert not await help_box.evaluate('(n)=>n.open'), (width, layout)
            assert await page.locator('#uxContinuationOrigin').is_visible()
            assert await page.locator('#uxContinuationContract').is_visible(), 'Reset implications must not be hidden'
            assert await page.locator('#uxChangeRoute').is_visible()
            assert await page.locator('#uxLeaveContinuation').is_visible()
            assert await page.locator('#generate').is_disabled(), 'Missing style inputs still block the existing run owner'
            await summary.focus()
            await page.keyboard.press('Enter')
            assert await guidance.is_visible()
            assert await guidance.text_content() == original
            # Existing readiness repaint must not close a disclosure someone is reading.
            await page.evaluate('updateReady()')
            assert await help_box.evaluate('(n)=>n.open')
            await page.keyboard.press('Enter')
            assert not await guidance.is_visible()
            assert await summary.evaluate('(n)=>n===document.activeElement')
            assert await page.evaluate('JSON.stringify(StudioSetupDraft.capture())') == before
            assert await page.evaluate("retainedHelpNodes.every((n,i)=>n===document.querySelector(['#uxContinuationGuidance','#positive','#generate'][i]))")
            assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            checks.append(f'{width}px {layout}: optional continuation explanation; source, reset warning and actions stay visible')
    # Normal typing survives the real owner's guidance repaint and disclosure mounting.
    await help_box.locator('summary').click()
    await page.fill('#positive', 'Keep my revised character description.')
    assert await help_box.evaluate('(n)=>n.open')
    await page.evaluate('CreateProgressiveDisclosure.mount(document);CreateProgressiveDisclosure.mount(document)')
    assert await help_box.count() == 1
    assert await page.locator('#positive').input_value() == 'Keep my revised character description.'
    assert {row['path'] for row in posts[start_writes:]} <= {'/api/estimate'}, 'Reading guidance must not stage, save, switch, install or run'
    assert not [row for row in posts if row['path']=='/api/jobs']
    await page.evaluate("selectPreset('anima-portrait',true,true)")
    assert not await help_box.is_visible(), 'Leaving a continuation removes its entire context, not just the image'
    checks.append('typing and node identity survive disclosure use; leaving hides context; no mutation-capable request')
