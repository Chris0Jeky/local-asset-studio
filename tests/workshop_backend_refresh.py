"""Catalogue observations must not rewind the actual Create editor. No real switch."""


async def exercise_backend_refresh(page, checks, posts):
    await page.wait_for_function('backendActive!==null')
    await page.evaluate("""() => {
      window.__backendOriginalApi=api;window.__backendOriginalActive=backendActive;
      window.__backendExpected=structuredClone(catalog);window.__backendCalls=0;
      api=async(url,options={})=>{
        if(url==='/api/backends')return {active:'fixture-observed',busy:false,profiles:[{id:'fixture-observed',name:'Observed fixture',active:true,installed:true}]};
        if(url==='/api/catalog')return new Promise((resolve,reject)=>{window.__backendRelease=resolve;window.__backendReject=reject;});
        return window.__backendOriginalApi(url,options);
      };
      window.__backendBegin=()=>{
        backendActive='fixture-before';delete window.__backendRelease;window.__backendDone=false;
        window.__backendRefresh=refreshBackends().finally(()=>window.__backendDone=true);
      };
      window.__backendSnapshot=()=>JSON.stringify({controls:values(),refs:attachedReferencePayload(),parents:parentAssets,mapping:parentByInput,claim:continuationState});
    }""")
    start_writes=len(posts)
    try:
        for width in (1440,390):
            await page.set_viewport_size({'width':width,'height':900})
            await page.evaluate("""async()=>{
              selectPreset('qwen-3ref',true,true);
              const copy=await post('/api/assets/reference',{id:'asset-0'});beginContinuation(copy,'qwen-3ref','edit');
              window.__backendRecords=referenceRecords;
              const transfer=new DataTransfer();transfer.items.add(new File(['pending'],'pending.png',{type:'image/png'}));
              document.querySelector('#reference').files=transfer.files;window.__backendFile=document.querySelector('#reference').files[0];
              document.querySelector('#positive').value='Old wording before observation';__backendBegin();
            }""")
            await page.wait_for_function("typeof __backendRelease==='function'")
            await page.fill('#positive','Latest wording while catalogue is pending')
            await page.evaluate("""()=>{
              getControl('seed').value='';getControl('steps').value='19';
              for(let parent=getControl('steps').parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
              getControl('steps').focus();
            }""")
            assert await page.locator('[data-key="steps"]').evaluate('(n)=>n===document.activeElement'), 'Fixture must own numeric focus before refresh'
            before=await page.evaluate('__backendSnapshot()')
            await page.evaluate('__backendRelease(structuredClone(__backendExpected))')
            await page.wait_for_function('__backendDone')
            assert before==await page.evaluate('__backendSnapshot()'), 'Late catalogue replaced the latest live draft'
            assert await page.locator('[data-key="seed"]').input_value()=='', 'Cleared setting regained a default'
            assert await page.locator('[data-key="steps"]').evaluate('(n)=>n===document.activeElement && n.value==="19"')
            assert await page.evaluate('referenceRecords===__backendRecords && document.querySelector("#reference").files[0]===__backendFile')
            checks.append(f'{width}px catalogue refresh preserves latest wording, blank setting, numeric focus, File identity and reference lineage')

            await page.evaluate('__backendBegin()')
            await page.wait_for_function("typeof __backendRelease==='function'")
            await page.evaluate("selectPreset('anima-portrait',true,true)")
            await page.fill('#positive','Wording for my newer recipe')
            before=await page.evaluate('__backendSnapshot()')
            await page.evaluate('__backendRelease(structuredClone(__backendExpected))')
            await page.wait_for_function('__backendDone')
            assert await page.evaluate("selected.id==='anima-portrait'")
            assert before==await page.evaluate('__backendSnapshot()')
            checks.append(f'{width}px recipe selected during the read is not replaced by the old recipe')

            await page.evaluate('__backendBegin();window.__retainedCatalogue=catalog')
            await page.wait_for_function("typeof __backendRelease==='function'")
            before=await page.evaluate('__backendSnapshot()')
            await page.evaluate('__backendRelease({presets:[]})')
            await page.wait_for_function('__backendDone')
            assert await page.evaluate('catalog===__retainedCatalogue')
            assert before==await page.evaluate('__backendSnapshot()')
            assert 'absent' in await page.locator('#backendStatus').text_content()
            checks.append(f'{width}px missing selected recipe leaves the editor intact with a visible error')
        assert {row['path'] for row in posts[start_writes:]}<={'/api/assets/reference','/api/estimate','/api/references/check'}
        assert sum(row['path']=='/api/assets/reference' for row in posts[start_writes:])==2, 'Only the two explicit fixture preparations may copy a source'
    finally:
        await page.evaluate('api=__backendOriginalApi;backendActive=__backendOriginalActive')
