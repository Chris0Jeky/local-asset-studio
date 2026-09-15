#!/usr/bin/env python3
"""Native Chromium contracts for the local, non-generating figure splitter."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "app/static/addressable-figures.js"
PENDING_KEY = "studio.addressable-figures.pending.v1"

HTML = r'''<!doctype html><html><head><meta charset="utf-8"></head><body>
<dialog id="assetDialog" open>
  <div id="assetHandoffs"></div>
  <div id="assetDetailMedia"><img alt=""></div>
</dialog>
<script>
const __storage=new Map();let storageFail=false;
Object.defineProperty(window,'sessionStorage',{configurable:true,value:{
  getItem:k=>__storage.has(k)?__storage.get(k):null,
  setItem:(k,v)=>{if(storageFail)throw Error('quota');__storage.set(k,String(v));},
  removeItem:k=>__storage.delete(k)
}});
function source(id,sha,title){return {id,sha256:sha,workspace_id:'11111111111111111111111111111111',url:'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="100"/%3E',title,media_type:'image',trashed_at:null};}
let activeAsset=source('asset-a','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','Sheet A');
let calls=[],messages=[],opened=[],refreshed=0,mode='success',failRefresh=false,deferredResolve=null,postCount=0;
window.confirm=()=>true;
function receipt(body){return {status:'created',action:'split_figures',workspace_id:body.workspace_id,parent_asset_id:body.asset_id,request_id:body.request_id,generation_submitted:false,created:body.rectangles.map((_,i)=>(i+1).toString(16).padStart(32,'0')),figures:body.rectangles.map((_,i)=>({index:i+1,asset_id:(i+1).toString(16).padStart(32,'0')}))};}
async function api(path,options={}){
  const body=options.body?JSON.parse(options.body):null;calls.push({path,method:options.method||'GET',body:options.body||null});
  if(path.startsWith('/api/assets/commands/'))return {status:'unknown',request_id:path.split('/').pop().split('?')[0]};
  postCount++;
  if(mode==='ambiguous'&&postCount===1){const error=Error('gateway unavailable');error.status=503;throw error;}
  if(mode==='deferred')return await new Promise(resolve=>{deferredResolve=()=>resolve(receipt(body));});
  return receipt(body);
}
async function refreshAssets(){refreshed++;if(failRefresh)throw Error('library refresh failed');}
function openAsset(id){opened.push(id);}
function assetMessage(text,error=false){messages.push({text,error});}
</script></body></html>'''

async def page_for(browser):
    page = await browser.new_page(viewport={"width": 960, "height": 720})
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.set_content(HTML)
    await page.add_script_tag(content=MODULE.read_text(encoding="utf-8"))
    await page.wait_for_selector("[data-figure-split-open]")
    return page, errors

async def add_default(page, second=False):
    await page.click("[data-figure-split-open]")
    await page.click("#figureSplitAdd button[type=submit]")
    if second:
        await page.fill('#figureSplitAdd input[name="x"]', "5000")
        await page.fill('#figureSplitAdd input[name="width"]', "5000")
        await page.click("#figureSplitAdd button[type=submit]")

async def scenario_success(browser):
    page, errors = await page_for(browser)
    await add_default(page, second=True)
    await page.click("#figureSplitCreate")
    await page.wait_for_function("refreshed===1")
    posts = await page.evaluate("calls.filter(c=>c.method==='POST')")
    assert len(posts) == 1 and len(json.loads(posts[0]["body"])["rectangles"]) == 2, posts
    assert await page.locator("[data-figure-child]").count() == 2
    assert "parent is unchanged" in (await page.text_content("#figureSplitChildren")).lower()
    assert not errors, errors
    await page.close()
    return {"posts": 1, "children": 2}

async def scenario_ambiguous(browser):
    page, errors = await page_for(browser)
    await page.evaluate("mode='ambiguous'")
    await add_default(page)
    await page.click("#figureSplitCreate")
    await page.wait_for_function("document.querySelector('[data-figure-check]') && !document.querySelector('[data-figure-check]').disabled")
    first = await page.evaluate("calls.find(c=>c.method==='POST').body")
    await page.click("[data-figure-check]")
    await page.wait_for_function("calls.some(c=>c.method==='GET')")
    assert "still unconfirmed" in (await page.text_content("#figureSplitStatus")).lower()
    await page.evaluate("mode='success'")
    await page.click("[data-figure-retry]")
    await page.wait_for_function("refreshed===1")
    posts = await page.evaluate("calls.filter(c=>c.method==='POST').map(c=>c.body)")
    assert posts == [first, first], posts
    assert await page.locator("[data-figure-child]").count() == 1
    assert not errors, errors
    await page.close()
    return {"post_attempts": 2, "status_reads": 1, "byte_identical_retry": True}

async def scenario_storage_failure(browser):
    page, errors = await page_for(browser)
    await page.evaluate("storageFail=true")
    await add_default(page)
    await page.click("#figureSplitCreate")
    await page.wait_for_timeout(50)
    assert await page.evaluate("calls.length") == 0
    assert "no request was sent" in (await page.text_content("#figureSplitStatus")).lower()
    assert not errors, errors
    await page.close()
    return {"writes": 0}

async def scenario_cross_source_guard(browser):
    page, errors = await page_for(browser)
    await page.evaluate("mode='ambiguous'")
    await add_default(page)
    await page.click("#figureSplitCreate")
    await page.wait_for_selector("[data-figure-check]")
    await page.evaluate("activeAsset=source('asset-b','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','Sheet B')")
    await page.click("[data-figure-split-open]")
    assert "Sheet A" in await page.text_content("#figureSplitSource")
    message = await page.evaluate("messages.at(-1)?.text||''")
    assert "unconfirmed figure split belongs" in message, message
    assert not errors, errors
    await page.close()
    return {"replacement_blocked": True}

async def scenario_late_response_binding(browser):
    page, errors = await page_for(browser)
    await page.evaluate("mode='deferred'")
    await add_default(page)
    await page.click("#figureSplitCreate")
    await page.wait_for_function("typeof deferredResolve==='function'")
    # Force the normally blocked state transition so the async callback itself is tested.
    await page.evaluate(f"sessionStorage.removeItem('{PENDING_KEY}');activeAsset=source('asset-b','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','Sheet B')")
    await page.click("[data-figure-split-open]")
    assert "Sheet B" in await page.text_content("#figureSplitSource")
    await page.evaluate("deferredResolve()")
    await page.wait_for_function("refreshed===1")
    await page.wait_for_timeout(30)
    assert await page.locator("[data-figure-child]").count() == 0
    assert "Sheet B" in await page.text_content("#figureSplitSource")
    assert "Split confirmed" not in (await page.text_content("#figureSplitStatus"))
    message = await page.evaluate("messages.at(-1)?.text||''")
    assert "Sheet A" in message and "confirmed" in message, message
    assert not errors, errors
    await page.close()
    return {"stale_children_rendered": 0, "origin_message": True}

async def scenario_refresh_failure(browser):
    page, errors = await page_for(browser)
    await page.evaluate("failRefresh=true")
    await add_default(page)
    await page.click("#figureSplitCreate")
    await page.wait_for_function("refreshed===1")
    await page.wait_for_timeout(30)
    status = await page.text_content("#figureSplitStatus")
    assert "split confirmed" in status.lower(), status
    assert "refresh" in status.lower(), status
    assert "not confirmed" not in status.lower(), status
    assert await page.locator("[data-figure-retry]").count() == 0
    assert await page.evaluate(f"sessionStorage.getItem('{PENDING_KEY}')") is None
    assert not errors, errors
    await page.close()
    return {"receipt_remains_confirmed": True, "pending_cleared": True}

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        executable = shutil.which("chromium") or shutil.which("chromium-browser")
        kwargs = {"headless": True, "args": ["--no-sandbox"]}
        if executable:
            kwargs["executable_path"] = executable
        browser = await playwright.chromium.launch(**kwargs)
        try:
            scenarios = {
                "success": await scenario_success(browser),
                "ambiguous": await scenario_ambiguous(browser),
                "storage_failure": await scenario_storage_failure(browser),
                "cross_source_guard": await scenario_cross_source_guard(browser),
                "late_response_binding": await scenario_late_response_binding(browser),
                "refresh_failure": await scenario_refresh_failure(browser),
            }
        finally:
            await browser.close()
    receipt = {
        "mode": "native Chromium; inert transport; no model execution",
        "scenarios": scenarios,
        "module_sha256": hashlib.sha256(MODULE.read_bytes()).hexdigest(),
    }
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    asyncio.run(main())
