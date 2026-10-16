from pathlib import Path
import json
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];E=R/'evidence/continuation-20261014';rows=[]
with sync_playwright() as pw:
 b=pw.chromium.launch()
 for kind in ['compare','pose']:
  ctx=b.new_context(viewport={'width':390,'height':844},storage_state=str(E/f'tutorial-{kind}/browser-storage.json'));page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8191/#create',wait_until='networkidle')
  if kind=='compare':
   page.locator('#planComparison').click();page.locator('#experimentAxis').select_option('cfg');page.locator('#experimentValues').fill('3, 4, 5');page.locator('#experimentBudget').fill('3');page.locator('#experimentMinutes').fill('10');page.locator('#experimentSummary').evaluate('(e)=>e.scrollIntoView({block:"center"})')
  else:
   imported=json.loads((E/'POSE-IMPORT-RECEIPT.json').read_text(encoding='utf-8-sig'))['asset']
   page.goto('http://127.0.0.1:8191/#assets',wait_until='networkidle');page.locator('[data-asset-open="'+imported['id']+'"]').first.click();page.locator('[data-ux-handoff="'+imported['id']+'"]').click();page.locator('[data-ux-destination="combine"]').click();page.locator('#uxDestination').select_option('combine-klein-9b-copypose');page.wait_for_function('!document.querySelector("#uxPrepareHandoff").disabled');page.locator('#uxPrepareHandoff').click();page.wait_for_function('!document.querySelector("#uxHandoff").open')
   page.locator('[data-ref-file="0"]').set_input_files(str(E/'public-inputs/tutorial-pose.png'));page.wait_for_function('referenceRecords[0]?.file')
   page.locator('#referenceCards').evaluate('(e)=>e.scrollIntoView({block:"center"})')
   assert page.evaluate('referenceRecords[0].role')=='pose' and page.evaluate('parentAssets.length')==1
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors
  page.screenshot(path=str(E/f'{kind}-actual-ui-390.png'));rows.append(dict(tutorial=kind,width=390,no_overflow=True,page_errors=errors,source_kind='Real current application using retained browser draft; no generation'))
  ctx.close()
 b.close()
(E/'PHONE-UI-CHECKS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
