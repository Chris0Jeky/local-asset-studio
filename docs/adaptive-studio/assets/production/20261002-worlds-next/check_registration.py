"""Source-art registration evidence, not runtime/crossfade acceptance."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter, sobel
from scipy.signal import correlate2d
import json, hashlib

B=Path(__file__).resolve().parent
Q=B/'qa'; Q.mkdir(exist_ok=True)
LANDMARKS={
 'arcade':[
  ('Left pipe elbow',73,29),('Ceiling beam corner',497,59),('Upper wall pipe bracket',817,99),
  ('Wall panel seam',302,436),('Wall floor seam',519,647),('Shelf top-left',874,249),
  ('Shelf middle corner',953,366),('Plant pot top-left',778,576),('Rear stool seat',965,552),
  ('Left cabinet top corner',1186,238),('Left cabinet side elbow',1059,322),('Left cabinet joystick',1051,482),
  ('Right cabinet top corner',1406,175),('Right cabinet screen corner',1429,299),('Right cabinet joystick',1227,480),
  ('Front stool seat-left',1129,612),('Front stool crossbar',1184,755),('Workbench front-left corner',1361,547),
  ('Lamp shade top',1577,314),('Right cabinet lower corner',1343,778)
 ],
 'sakura':[
  ('Left beam top edge',90,23),('Left vase shoulder',69,580),('Side-table top right',105,658),
  ('Wall floor seam left',265,675),('Wall floor seam right',900,656),('Left frame lattice',1078,217),
  ('Right frame lattice',1119,392),('Blind left tassel',1197,91),('Blind right tassel',1249,111),
  ('Rear vase left shoulder',994,514),('Desk back-left corner',949,562),('Pen cup rim',1224,517),
  ('Ink pot lid',1273,552),('Paper left corner',1120,605),('Paper right corner',1484,636),
  ('Chair back-left joint',934,608),('Chair back-right joint',1091,648),('Chair seat corner',1320,839),
  ('Courtyard stone point',1277,373),('Far doorway lintel',1454,247)
 ]
}
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
for world,landmarks in LANDMARKS.items():
 p0=B/'originals'/f'{world}-master--candidate-1.png';p1=B/'originals'/f'{world}-quiet--candidate-1.png'
 a=np.asarray(Image.open(p0).convert('L'),dtype=np.float64)/255
 b=np.asarray(Image.open(p1).convert('L'),dtype=np.float64)/255
 assert a.shape==b.shape
 aa=a-gaussian_filter(a,3);bb=b-gaussian_filter(b,3)
 radius=20;search_radius=12;rows=[]
 for name,x,y in landmarks:
  # Points near the canvas edge use the largest symmetric patch available.
  r=min(radius,x-search_radius,y-search_radius,a.shape[1]-1-x-search_radius,a.shape[0]-1-y-search_radius)
  assert r>=8
  t=aa[y-r:y+r+1,x-r:x+r+1];t=t-t.mean()
  s=bb[y-r-search_radius:y+r+search_radius+1,x-r-search_radius:x+r+search_radius+1]
  numerator=correlate2d(s,t,mode='valid');ones=np.ones(t.shape);n=t.size
  sums=correlate2d(s,ones,mode='valid');squares=correlate2d(s*s,ones,mode='valid')
  denominator=np.sqrt(np.maximum(squares-sums*sums/n,1e-16)*np.sum(t*t))
  cc=numerator/denominator
  j,i=np.unravel_index(np.argmax(cc),cc.shape);dx=int(i-search_radius);dy=int(j-search_radius)
  rows.append({'name':name,'master_xy':[x,y],'quiet_best_xy':[x+dx,y+dy],'patch_size_px':2*r+1,'shift_xy_px':[dx,dy],'shift_distance_px':round(float(np.hypot(dx,dy)),4),'ncc':round(float(cc[j,i]),5),'identity_ncc':round(float(cc[search_radius,search_radius]),5),'search_boundary_hit':abs(dx)==search_radius or abs(dy)==search_radius})
 shifts=np.array([r['shift_distance_px'] for r in rows]);correlations=np.array([r['ncc'] for r in rows])
 report={'world':world,'method':'20 manually selected architectural/object landmarks; up to 41x41 grayscale high-pass templates (Gaussian sigma 3), normalized cross-correlation within +/-12 source pixels. Border-adjacent points use a smaller symmetric patch, recorded per point. Original unscaled coordinates; no warp or registration correction.','dimensions':[a.shape[1],a.shape[0]],'inputs':[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [p0,p1]],'summary':{'landmarks':len(rows),'median_shift_px':float(np.median(shifts)),'max_shift_px':float(shifts.max()),'median_ncc':round(float(np.median(correlations)),5),'min_ncc':round(float(correlations.min()),5),'search_boundary_hits':sum(x['search_boundary_hit'] for x in rows)},'landmarks':rows,'limits':['Sampled measurements describe local correspondence only; lighting and generative detail redraw preclude a pixel-identity claim.','A +/-12px local search cannot rule out larger displacement or incorrect matches. Low correlation and boundary matches require visual interpretation.','The source-art plan requests pixel-for-pixel crossfade registration. These samples and edge overlays do not fulfill a whole-image or actual runtime crossfade acceptance gate.','No transform has been applied to either delivered original.']}
 if world=='arcade':
  diagnostics=[]
  for r in [30,40,50]:
   x,y=1429,299;s=12;t=aa[y-r:y+r+1,x-r:x+r+1];t=t-t.mean()
   q=bb[y-r-s:y+r+s+1,x-r-s:x+r+s+1];ones=np.ones(t.shape);n=t.size
   cc=correlate2d(q,t,'valid')/np.sqrt(np.maximum(correlate2d(q*q,ones,'valid')-correlate2d(q,ones,'valid')**2/n,1e-16)*np.sum(t*t))
   j,i=np.unravel_index(np.argmax(cc),cc.shape)
   diagnostics.append({'master_xy':[x,y],'patch_size_px':2*r+1,'shift_xy_px':[int(i-s),int(j-s)],'ncc':round(float(cc[j,i]),10),'identity_ncc':round(float(cc[s,s]),10)})
  report['diagnostic_larger_patches']=diagnostics
  sheet=Image.new('RGB',(600,320),'white');draw=ImageDraw.Draw(sheet)
  for i,p in enumerate([p0,p1]):
   sheet.paste(Image.open(p).crop((1380,250,1480,350)).resize((300,300)),(i*300,20));draw.text((i*300+6,3),'MASTER' if i==0 else 'QUIET',fill='black')
  sheet.save(Q/'arcade-screen-detail.jpg',quality=91)
 (Q/f'{world}-quiet-registration.json').write_text(json.dumps(report,indent=2)+'\n')
 sheet=Image.new('RGB',(1672,515),'#f4f1ec');d=ImageDraw.Draw(sheet)
 for k,p in enumerate([p0,p1]):
  im=Image.open(p);im.thumbnail((836,471),Image.Resampling.LANCZOS);sheet.paste(im,(836*k,44))
  d.text((12+836*k,13),f'{world.upper()} / '+('MASTER' if k==0 else 'QUIET: sampled positions'),font=font,fill='#252529')
  for idx,row in enumerate(rows):
   x,y=row['master_xy'] if k==0 else row['quiet_best_xy'];x=x*.5+836*k;y=y*.5+44
   d.ellipse([x-3,y-3,x+3,y+3],outline='#ff1ca8',width=2);d.text((x+5,y-10),str(idx+1),font=font,fill='#f31298',stroke_width=1,stroke_fill='white')
 sheet.save(Q/f'{world}-quiet-landmarks.jpg',quality=91)
 def edge(a):
  s=gaussian_filter(a,1);g=np.hypot(sobel(s,0),sobel(s,1));return np.clip(g/.16,0,1)
 ea=edge(a);eb=edge(b);overlay=Image.fromarray(np.uint8(np.stack([ea,eb,eb],axis=-1)*255))
 overlay.save(Q/f'{world}-quiet-edge-overlay.png')
 overlay.save(Q/f'{world}-quiet-edge-overlay.jpg',quality=91)
 print(world,json.dumps(report['summary']))
 print('\n'.join(f"{r['name']}: shift {r['shift_xy_px']}; NCC {r['ncc']}" for r in rows))
