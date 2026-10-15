from pathlib import Path
import argparse,json
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();O=a.output.resolve();expected=json.loads((O/'media-receipt.json').read_text())['caption_cues'];results=[]
with sync_playwright() as pw:
 b=pw.chromium.launch()
 for width in [390,1280]:
  page=b.new_page(viewport={'width':width,'height':900});page.goto((O/'index.html').as_uri());assert not page.locator('video').get_attribute('src');page.locator('#load').click()
  page.wait_for_function('document.querySelector("video").readyState>=4')
  page.wait_for_function('(n)=>document.querySelector("video").textTracks[0]?.cues?.length===n',arg=expected,timeout=4000)
  state=page.locator('video').evaluate('(v)=>({cueCount:v.textTracks[0].cues.length,mode:v.textTracks[0].mode,paused:v.paused})');assert state['paused'] and state['mode']=='showing'
  results.append(dict(width=width,**state));page.close()
 b.close()
(O/'CAPTION-CHECKS.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
