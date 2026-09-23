"""Actual keyboard traversal of optional prompt helpers; sanitized discovery only."""

import json

# Match discovery's public shape, not private prompt lists or model output.
WILDCARDS = [{'name': f'style_{index:03d}', 'count': 3} for index in range(100)]


async def exercise_wildcards(page, checks, posts):
    first_request = len(posts)
    await page.evaluate("selectPreset('anima-portrait')")
    original_nodes = await page.evaluate("""() => {
        window.wildcardOriginals = [document.querySelector('#positive'), document.querySelector('#wildcardChips'),
                                   document.querySelector('#generate')];
        return document.querySelectorAll('#wildcardChips [data-wildcard]').length;
    }""")
    assert original_nodes == 100, 'The fixture must include the discovery data missing from the earlier journey'
    for width, height in [(1440, 900), (1365, 910), (390, 844)]:
        await page.set_viewport_size({'width': width, 'height': height})
        for layout in ('focus', 'studio', 'immersive'):
            await page.select_option('#workshopLayout', layout)
            await page.fill('#positive', 'Before AFTER')
            await page.focus('#positive')
            await page.keyboard.press('Tab')
            assert not await page.evaluate("!!document.activeElement.closest('#wildcardChips')"), (width, layout, 'Closed helpers stole the next Tab')
            summary = page.locator('#promptWildcards > summary')
            assert await summary.evaluate('(n)=>n===document.activeElement'), (width, layout)
            assert not await page.locator('#promptWildcards').evaluate('(n)=>n.open')
            await page.wait_for_function("document.querySelector('#workshopEta').textContent.includes('42')")
            await page.evaluate('window.scrollTo(0,0)')
            for selector in ('#generate', '#workshopReadiness', '#workshopEta'):
                box = await page.locator(selector).bounding_box()
                assert box and 0 <= box['y'] and box['y'] + box['height'] <= height, (width, layout, selector, box)
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, layout)
            # Count native focus movements, not tabIndex values of invisible descendants.
            for key in ('Tab', 'Shift+Tab'):
                await page.focus('#positive')
                for _ in range(14):
                    await page.keyboard.press(key)
                    assert not await page.evaluate("!!document.activeElement.closest('#wildcardChips, #workshopRecipeDialog')"), (width, layout, key)
            await summary.focus()
            await page.keyboard.press('Enter')
            await page.keyboard.press('Tab')
            assert await page.locator('[data-wildcard="style_000"]').evaluate('(n)=>n===document.activeElement')
            # Keyboard insertion uses the original caret and the existing handler.
            await page.locator('#positive').evaluate('(n)=>n.setSelectionRange(7,7)')
            await page.keyboard.press('Enter')
            assert await page.locator('#positive').input_value() == 'Before __style_000__ AFTER'
            assert await page.locator('#positive').evaluate('(n)=>n===document.activeElement')
            assert await page.locator('#positive').evaluate('(n)=>n.selectionStart===n.selectionEnd && n.selectionStart===20')
            await page.locator('[data-wildcard="style_099"]').focus()
            assert await page.locator('#wildcardChips').evaluate('(n)=>n.clientHeight<=322'), (width, layout, 'Expanded helpers must remain bounded')
            await page.keyboard.press('Escape')
            assert not await page.locator('#promptWildcards').evaluate('(n)=>n.open')
            assert await summary.evaluate('(n)=>n===document.activeElement')
            assert await page.evaluate("wildcardOriginals.every((n,i)=>n===document.querySelector(['#positive','#wildcardChips','#generate'][i]))")
            assert not [row for row in posts if row['path'] == '/api/jobs']
            checks.append(f'{width}px {layout}: closed helper traversal, caret insertion, bounded list and Escape focus')
    # Re-rendered helpers invalidate only the disclosure, not the current text.
    await page.locator('#promptWildcards > summary').click()
    await page.locator('[data-wildcard="style_000"]').focus()
    await page.evaluate('renderWildcardChips()')
    await page.wait_for_function("!document.querySelector('#promptWildcards').open")
    assert await page.locator('#positive').input_value() == 'Before __style_000__ AFTER'
    # No discovery entries means there is no misleading empty helper control.
    await page.evaluate('catalog.wildcards=[];renderWildcardChips()')
    await page.locator('#promptWildcards').wait_for(state='hidden')
    await page.evaluate('catalog.wildcards=' + json.dumps(WILDCARDS) + ';renderWildcardChips()')
    await page.locator('#promptWildcards').wait_for(state='visible')
    assert not await page.locator('#promptWildcards').evaluate('(n)=>n.open')
    # A late catalog repaint must not take focus away from active typing.
    await page.locator('#promptWildcards > summary').click()
    await page.focus('#positive')
    await page.evaluate('renderWildcardChips()')
    await page.wait_for_function("!document.querySelector('#promptWildcards').open")
    assert await page.locator('#positive').evaluate('(n)=>n===document.activeElement')
    await page.evaluate("selectPreset('trellis-auto-cutout')")
    await page.locator('#promptWildcards').wait_for(state='hidden')
    await page.evaluate("selectPreset('anima-portrait')")
    await page.locator('#promptWildcards').wait_for(state='visible')
    assert not await page.locator('#promptWildcards').evaluate('(n)=>n.open')
    # An authored variant can replace wording without repainting the wildcard host.
    await page.locator('#promptWildcards > summary').click()
    await page.evaluate("window.retainedWildcard=document.querySelector('#wildcardChips [data-wildcard]')")
    await page.evaluate("applyRecipe({preset_id:'anima-portrait',name:'Same preset variation',controls:{positive:'Same-preset authored wording'}})")
    assert await page.evaluate("retainedWildcard===document.querySelector('#wildcardChips [data-wildcard]')"), 'The regression must exercise the no-repaint recipe path'
    assert not await page.locator('#promptWildcards').evaluate('(n)=>n.open'), 'A same-preset recipe change closes optional helpers too'
    assert await page.locator('#positive').input_value() == 'Same-preset authored wording'
    await page.focus('#positive')
    await page.keyboard.press('Tab')
    assert await page.locator('#promptWildcards > summary').evaluate('(n)=>n===document.activeElement')
    await page.keyboard.press('Tab')
    assert not await page.evaluate("!!document.activeElement.closest('#wildcardChips')")
    checks.append('same-preset authored recipe changes close helpers without repainting their host or sending a job')
    assert {row['path'] for row in posts[first_request:]} <= {'/api/estimate'}, 'Helper interaction may estimate only, not stage, install, switch or submit'
    checks.append('new lists collapse; missing/text-free recipes hide helpers; active typing retains focus; only read-only timing requests')
