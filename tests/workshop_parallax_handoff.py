"""Late automatic parallax handoffs preserve the actual Create editor. No inference."""


async def exercise_parallax_handoff(page, checks):
    await page.wait_for_function('!!window.StudioSetupDraft && backendActive!==null')
    await page.evaluate("""() => {
      window.__parallaxApi=api;window.__parallaxRefresh=refresh;refresh=async()=>{};
      window.__parallaxPlate={preset_id:'parallax-edit',stage:'plate',words:'Clean plate fixture wording',
        file:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa_fixture.png',width:1344,height:768,flag:'Synthetic fixture',
        plan:{plan_id:'fixture-plan',source_asset_id:'asset-0'},
        claim:{plan_id:'fixture-plan',preset_id:'parallax-edit',stage:'plate'},context:{title:'Fixture room'}};
      api=async(url,options={})=>{
        if(url==='/api/jobs'){
          __parallaxRuns++;window.__parallaxSubmitted=JSON.parse(options.body);
          if(__parallaxWait===url)await new Promise(resolve=>window.__parallaxRelease=resolve);
          return {id:'fixture-plate-job',message:'Queued fixture'};
        }
        if(url==='/api/parallax/stage'){
          if(__parallaxWait===url)await new Promise(resolve=>window.__parallaxRelease=resolve);
          return {...__parallaxPlate,stage:'isolate',claim:{...__parallaxPlate.claim,stage:'isolate'},words:'Isolate fixture wording'};
        }
        return __parallaxApi(url,options);
      };
      window.__parallaxStart=wait=>{
        beginParallax(__parallaxPlate);window.__parallaxWait=wait;window.__parallaxRuns=0;
        delete window.__parallaxRelease;window.__parallaxDone=false;
        document.querySelector('#generate').onclick().finally(()=>window.__parallaxDone=true);
      };
    }""")
    try:
        for width in (1440, 390):
            await page.set_viewport_size({'width':width,'height':900})
            for wait_at in ('/api/jobs', '/api/parallax/stage'):
                await page.evaluate('__parallaxStart', wait_at)
                await page.wait_for_function("typeof __parallaxRelease==='function'")
                await page.fill('#positive', 'Newer Create words while queued')
                await page.evaluate("getControl('seed').value='77';getControl('width').value='512'")
                before = await page.evaluate('JSON.stringify([StudioSetupDraft.stamp(),parallaxState])')
                await page.evaluate('__parallaxRelease()')
                await page.wait_for_function('__parallaxDone')
                assert await page.evaluate('JSON.stringify([StudioSetupDraft.stamp(),parallaxState])') == before
                assert await page.evaluate('__parallaxRuns') == 1
                assert await page.evaluate('__parallaxSubmitted.controls.positive') == 'Clean plate fixture wording'
                assert await page.evaluate('activeJobId') == 'fixture-plate-job'
                assert 'Load the isolate edit' in await page.locator('#status').inner_text()
                checks.append(f'{width}px: edits across {wait_at} survive; original job retained once')
        await page.evaluate("__parallaxStart('none')")
        await page.wait_for_function('__parallaxDone')
        assert await page.evaluate('parallaxState.stage') == 'isolate'
        assert await page.locator('#positive').input_value() == 'Isolate fixture wording'
        assert await page.evaluate('__parallaxRuns') == 1
        checks.append('unchanged Create loads the isolate once without generating it')
    finally:
        await page.evaluate('api=__parallaxApi;refresh=__parallaxRefresh')
