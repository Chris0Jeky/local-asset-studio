"""Original deterministic teaching diagrams, not model outputs or production artwork."""
from pathlib import Path
import hashlib,json
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];O=R/'evidence/continuation-20261014/public-inputs';O.mkdir(exist_ok=True)
common='<rect width="512" height="768" fill="#f3eedf"/><ellipse cx="256" cy="706" rx="140" ry="17" fill="#d4d4be"/>'
head='<g id="adult-head"><circle cx="256" cy="172" r="48" fill="#e5c6a0"/><path d="M211 176Q198 113 258 116Q313 121 302 174L286 147 220 151Z" fill="#354c50"/><path d="M218 169h28m19 0h28M246 169h19" stroke="#355b52" stroke-width="5"/><path d="M243 196q13 8 26 0" fill="none" stroke="#855a44" stroke-width="3"/></g>'
standing=common+head+'<g id="clothed-character"><path d="M216 211h80l28 44-12 213H200l-12-213Z" fill="#93b2a1" stroke="#355b52" stroke-width="6"/><path d="M240 212v232M216 258h38M277 258h26" fill="none" stroke="#e5c575" stroke-width="5"/><path d="M202 239 160 404m153-165 39 163" stroke="#93b2a1" stroke-width="32" stroke-linecap="round"/><path d="M220 467 212 661m80-194 10 194" stroke="#355b52" stroke-width="34"/><path d="M211 666h-35m126 0h36" stroke="#263e44" stroke-width="20" stroke-linecap="round"/><circle cx="160" cy="407" r="15" fill="#e5c6a0"/><circle cx="352" cy="407" r="15" fill="#e5c6a0"/></g>'
pose=common+'<g id="clothed-adult-pose" stroke-linecap="round" stroke-linejoin="round"><circle cx="267" cy="177" r="44" fill="#e5c6a0" stroke="#355b52" stroke-width="5"/><path d="M243 220 293 219 328 442 215 449Z" fill="#93b2a1" stroke="#355b52" stroke-width="6"/><path d="M238 241 179 305 123 251M289 241 354 185 360 91" fill="none" stroke="#93b2a1" stroke-width="29"/><circle cx="123" cy="251" r="15" fill="#e5c6a0" stroke="none"/><circle cx="360" cy="91" r="15" fill="#e5c6a0" stroke="none"/><path d="M237 453 188 543 207 662M298 451 354 543 349 660" fill="none" stroke="#355b52" stroke-width="33"/><path d="M206 666h-37M349 665h36" stroke="#263e44" stroke-width="20"/></g>'
rows=[]
with sync_playwright() as pw:
 b=pw.chromium.launch();page=b.new_page(viewport={'width':512,'height':768},device_scale_factor=1)
 for name,body in [('tutorial-character',standing),('tutorial-pose',pose)]:
  svg=O/(name+'.svg');png=O/(name+'.png');assert not svg.exists() and not png.exists()
  svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="768" viewBox="0 0 512 768"><title>Original fully clothed adult tutorial diagram</title>'+body+'</svg>',encoding='utf-8')
  page.goto(svg.as_uri());page.locator('svg').screenshot(path=str(png))
  from PIL import Image
  with Image.open(png) as im:im.load();assert im.size==(512,768)
  rows.append(dict(file=png.name,width=512,height=768,sha256=hashlib.sha256(png.read_bytes()).hexdigest(),bytes=png.stat().st_size,source='Original deterministic native SVG teaching diagram',generated_by_model=False,public_safe=True))
 b.close()
(O/'PROVENANCE.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows))
