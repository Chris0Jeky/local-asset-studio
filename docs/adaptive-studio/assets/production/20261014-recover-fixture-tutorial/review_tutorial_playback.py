from pathlib import Path
import argparse,json,time
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();O=a.output.resolve();r=json.loads((O/'media-receipt.json').read_text());duration=float(r['ffprobe']['format']['duration']);shots=[];checks=[]
with sync_playwright() as pw:
 b=pw.chromium.launch()
 for width in [390,1280]:
  ctx=b.new_context(viewport={'width':width,'height':900},reduced_motion='reduce');page=ctx.new_page();requests=[];errors=[]
  page.on('request',lambda r:requests.append(r.url));page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto((O/'index.html').as_uri())
  v=page.locator('video');assert not v.get_attribute('src') and not any(url.endswith('.mp4') for url in requests)
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  page.locator('#load').click();page.wait_for_function('document.querySelector("video").readyState>=4')
  assert v.evaluate('(v)=>v.paused') and abs(v.evaluate('(v)=>v.duration')-duration)<.1
  if width==1280:
   v.scroll_into_view_if_needed();v.evaluate('(v)=>v.play()');start=time.monotonic();i=0
   while time.monotonic()-start<duration+.25:
    state=v.evaluate('(v)=>({time:v.currentTime,paused:v.paused,ended:v.ended,error:v.error&&v.error.message})')
    if i%2==0:
     file=f'playback-{i:02}.png';v.screenshot(path=str(O/file));shots.append(dict(wall_seconds=round(time.monotonic()-start,3),**state,file=file))
    page.wait_for_timeout(500);i+=1
   state=v.evaluate('(v)=>({time:v.currentTime,ended:v.ended,error:v.error&&v.error.message})');assert state['ended'] and state['error'] is None
   checks.append(dict(complete_normal_speed_playback=state,no_seeks_or_pause_during_playback=True))
  page.screenshot(path=str(O/f'player-{width}.png'),full_page=True)
  assert not errors;checks.append(dict(width=width,no_autoplay=True,no_video_request_before_explicit_load=True,no_overflow=True,page_errors=errors));ctx.close()
 b.close()
(O/'PLAYBACK-REVIEW.json').write_text(json.dumps(dict(checks=checks,chronological_frames=shots,visual_acceptance='Not inferred; reviewer must inspect actual decoded and chronological pixels'),indent=2)+'\n');print(json.dumps(dict(duration=duration,chronological_frames=len(shots),checks=checks)))
