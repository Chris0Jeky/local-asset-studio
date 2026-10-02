"""Source-art registration evidence, not runtime/crossfade acceptance."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter, sobel
from scipy.signal import correlate2d
import json, hashlib

import sys
B=Path(sys.argv[1]).resolve()
Q=Path(sys.argv[2]).resolve()
if Q==B or B in Q.parents: raise SystemExit('Use an output directory outside the pack')
Q.mkdir(parents=True,exist_ok=True)
LANDMARKS={'minimal-pro': [('Skylight frame lower junction', 1493, 194), ('Skylight inner bevel corner', 1454, 264), ('Room upper corner', 1438, 327), ('Leaning board upper corner', 1566, 373), ('Lamp shade upper corner', 1483, 422), ('Lamp arm bend', 1601, 427), ('Lamp base right edge', 1629, 593), ('Desk back-left corner', 1026, 568), ('Desk near-right corner', 1584, 669), ('Desk left foot corner', 1024, 795), ('Book stack left edge', 1146, 553), ('Tray left corner', 1390, 557), ('Pen cup upper edge', 1354, 535), ('Paper left corner', 1167, 581), ('Paper front corner', 1381, 617), ('Chair back upper left', 1124, 591), ('Chair back upper bend', 1228, 624), ('Chair seat left edge', 1131, 745), ('Chair front-leg edge', 1220, 857), ('Wall-floor line texture', 511, 746)], 'sci-fi-noir': [('Window upper frame joint', 1107, 127), ('Planet right limb', 1543, 283), ('Planet crater detail', 1413, 151), ('Left conduit elbow', 78, 330), ('Wall seam first fastener', 307, 279), ('Wall seam second fastener', 681, 313), ('Left floor frame lamp', 93, 755), ('Workbench front-left corner', 1039, 610), ('Lamp shade top', 1215, 488), ('Lamp elbow', 1141, 544), ('Instrument barrel left', 1272, 479), ('Instrument right joint', 1440, 521), ('Instrument base edge', 1375, 614), ('Stool seat left', 1150, 665), ('Stool foot left', 1138, 778), ('Case upper-left corner', 907, 611), ('Window lower elbow', 1059, 482), ('Canister upper-left', 1010, 655), ('Right toolbox upper edge', 1565, 652), ('Ceiling conduit joint', 961, 62)]}
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
for world,landmarks in LANDMARKS.items():
 p0=B/'originals'/f'{world}-master--candidate-1.png';p1=B/'originals'/f'{world}-quiet--candidate-1.png'
 if not (p0.exists() and p1.exists()): continue
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
