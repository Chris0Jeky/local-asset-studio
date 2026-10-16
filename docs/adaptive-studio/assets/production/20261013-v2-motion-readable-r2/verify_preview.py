"""Real-browser acceptance checks for the isolated, source-only motion preview."""
import argparse, hashlib, json, re, tempfile, xml.etree.ElementTree as ET
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageChops

parser=argparse.ArgumentParser()
parser.add_argument('folder',type=Path,nargs='?',default=Path(__file__).resolve().parent)
parser.add_argument('--evidence',type=Path)
args=parser.parse_args()
folder=args.folder.resolve(); evidence=args.evidence or Path(tempfile.mkdtemp(prefix='v2-motion-evidence-'))
evidence.mkdir(parents=True,exist_ok=True)
assert (folder/'preview.js').is_file(), 'Optional preview controller is missing'
assert (folder/'index.html').is_file(), 'Complete static comparison page is missing'
manifest=json.loads((folder/'SOURCE.json').read_text(encoding='utf-8'))
source=folder/manifest['static_file']; root=ET.parse(source).getroot()
assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['sha256']
assert not any(n.tag.rsplit('}',1)[-1] in {'image','script','foreignObject','animate','animateTransform','set'} for n in root.iter())
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
def state(page): return page.locator('[data-motion-preview]').get_attribute('data-state')
def times(page): return page.locator('[data-motion-art]').evaluate('(e)=>e.getAnimations({subtree:true}).map(a=>a.currentTime)')
def paused(page):
    page.wait_for_function('document.querySelector("[data-motion-art]").getAnimations({subtree:true}).every(a=>a.playState==="paused"&&!a.pending)')
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    context=browser.new_context(offline=True,reduced_motion='no-preference')
    page=context.new_page(); errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:requests.append(r.url))
    page.set_viewport_size({'width':1440,'height':1000})
    page.goto((folder/'index.html').as_uri(),wait_until='load')
    page.locator('[data-motion-art]').scroll_into_view_if_needed()
    page.wait_for_timeout(120)
    check('complete initial still',state(page)=='paused')
    initial=times(page); page.wait_for_timeout(150)
    check('no autoplay',times(page)==initial)
    # Identical initial pixels to the standalone script-free master.
    motion=page.locator('[data-motion-art]'); motion.screenshot(path=str(evidence/'initial-still.png'))
    # Compare in the same inline SVG context and pixel position; an <img> SVG uses
    # a separate compositing pipeline and is not a pixel-equivalence oracle.
    motion.evaluate('(e,s)=>{e.innerHTML=s}',source.read_text(encoding='utf-8'))
    motion.screenshot(path=str(evidence/'static-original.png'))
    check('initial still matches original SVG pixels',ImageChops.difference(Image.open(evidence/'initial-still.png').convert('RGB'),Image.open(evidence/'static-original.png').convert('RGB')).getbbox() is None)
    page.reload(wait_until='load');motion=page.locator('[data-motion-art]');motion.scroll_into_view_if_needed();page.wait_for_timeout(100)
    page.get_by_role('button',name='Play',exact=True).click()
    page.wait_for_function('document.querySelector("[data-motion-preview]").dataset.state==="playing"')
    t=times(page);page.wait_for_timeout(220)
    check('Play advances actual animations',any(b>a for a,b in zip(t,times(page))))
    page.get_by_role('button',name='Pause',exact=True).click()
    paused(page)
    t=times(page);page.wait_for_timeout(150)
    check('Pause freezes actual animations',times(page)==t)
    page.get_by_role('button',name='Play',exact=True).click();page.wait_for_timeout(150)
    check('resume preserves elapsed time',all(b>=a for a,b in zip(t,times(page))))
    page.evaluate('window.scrollTo(0,document.body.scrollHeight)')
    page.wait_for_function('document.querySelector("[data-motion-preview]").dataset.state==="offscreen"')
    paused(page)
    t=times(page);page.wait_for_timeout(150)
    check('real offscreen observation pauses time',times(page)==t)
    motion.scroll_into_view_if_needed()
    page.wait_for_function('document.querySelector("[data-motion-preview]").dataset.state==="playing"')
    check('returning onscreen resumes prior Play request',state(page)=='playing')
    # Visibility is an explicit DOM-contract probe, not a physical minimized-window claim.
    page.evaluate('Object.defineProperty(document,"hidden",{configurable:true,get:()=>true});document.dispatchEvent(new Event("visibilitychange"))')
    check('hidden-document contract pauses',state(page)=='hidden')
    paused(page)
    t=times(page);page.wait_for_timeout(150)
    check('hidden-document clock freezes',times(page)==t)
    page.evaluate('delete document.hidden;document.dispatchEvent(new Event("visibilitychange"))')
    page.wait_for_timeout(100)
    check('visible-document contract resumes',state(page)=='playing')
    page.emulate_media(reduced_motion='reduce');page.wait_for_timeout(100)
    check('reduced motion stops and disables Play',state(page)=='reduced' and page.get_by_role('button',name='Play',exact=True).is_disabled())
    check('reduced motion removes animations',times(page)==[])
    page.emulate_media(reduced_motion='no-preference');page.wait_for_timeout(100)
    check('preference change requires fresh Play',state(page)=='paused')
    page.get_by_role('button',name='Play',exact=True).click()
    # Seek real CSS animations only in the test, no production recording API.
    train=page.locator('[data-train-toggle]')
    if train.count():
        train.check();page.wait_for_timeout(50)
        check('optional train creates its own animation',page.locator('.train-piece').evaluate('(e)=>e.getAnimations().some(a=>a.animationName==="train-passage")'))
    def frame(ms,name):
        motion.evaluate('(e,t)=>e.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=t})',ms)
        motion.screenshot(path=str(evidence/name),animations='allow')
    frame(0,'loop-start.png');frame(2000,'motion-midpoint.png');frame(15999,'loop-before.png');frame(16000,'loop-end.png')
    check('loop endpoint matches first frame',ImageChops.difference(Image.open(evidence/'loop-start.png').convert('RGB'),Image.open(evidence/'loop-end.png').convert('RGB')).getbbox() is None)
    before=Image.open(evidence/'loop-before.png').convert('RGB');end=Image.open(evidence/'loop-end.png').convert('RGB')
    diff=ImageChops.difference(before,end);pixels=diff.tobytes();changed=sum(max(pixels[i:i+3])>10 for i in range(0,len(pixels),3))
    check('loop seam has no visible jump',changed/(before.width*before.height)<.001)
    check('motion changes localized pixels',ImageChops.difference(Image.open(evidence/'loop-start.png').convert('RGB'),Image.open(evidence/'motion-midpoint.png').convert('RGB')).getbbox() is not None)
    if train.count():
        for time,label in [(3200,'train-exit'),(4800,'train-reset-left')]:
            frame(time,label+'.png')
            check(label+' is fully outside the fixed window clip',page.locator('.train-piece').evaluate('(e)=>{let b=e.getBBox(),s=getComputedStyle(e).transform,m=new DOMMatrix(s);return b.x+m.e>=1580||b.x+b.width+m.e<=1080}'))
        check('train clip remains on stationary parent',page.locator('[data-motion-art] #last-train').get_attribute('clip-path')=='url(#window-clip)')
    for width in [390,1440]:
        page.set_viewport_size({'width':width,'height':1000});motion.scroll_into_view_if_needed()
        check(f'no horizontal overflow at {width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        motion.screenshot(path=str(evidence/f'preview-{width}.png'))
    check('no page errors',not errors)
    check('offline file-only requests',all(r.startswith('file:') for r in requests))
    # No JavaScript: full initial still survives.
    fallback=browser.new_context(java_script_enabled=False,offline=True)
    still=fallback.new_page();still.goto((folder/'index.html').as_uri())
    check('script-free complete fallback',still.locator('[data-motion-art] svg').count()==1)
    still.locator('[data-motion-art]').screenshot(path=str(evidence/'no-script-still.png'))
    fallback.close()
    unsupported=browser.new_context(offline=True)
    unsupported.add_init_script('delete window.IntersectionObserver')
    old=unsupported.new_page();old.goto((folder/'index.html').as_uri())
    old.evaluate('window.dispatchEvent(new Event("pageshow"));document.dispatchEvent(new Event("visibilitychange"))')
    check('missing visibility observation keeps Play disabled after lifecycle events',old.get_by_role('button',name='Play',exact=True).is_disabled())
    check('missing observation preserves complete still',old.locator('[data-motion-art] svg').count()==1 and old.locator('[data-motion-art]').evaluate('(e)=>e.getAnimations({subtree:true}).length')==0)
    unsupported.close();context.close();browser.close()
result={'asset':manifest['asset'],'static_sha256':manifest['sha256'],'checks':checks,'check_count':len(checks),'loop_seam_changed_fraction':changed/(before.width*before.height),'hidden_test':'explicit DOM visibility contract; actual offscreen via IntersectionObserver','page_errors':errors,'network_requests':0,'production_acceptance_claimed':False}
(evidence/'browser-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
