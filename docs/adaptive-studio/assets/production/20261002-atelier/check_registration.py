from PIL import Image, ImageDraw, ImageFont
import numpy as np
from scipy.ndimage import gaussian_filter, sobel
from scipy.signal import correlate2d
from pathlib import Path
import json, hashlib
import sys
base=Path(sys.argv[1]).resolve()
(base/'qa').mkdir(exist_ok=True)
p0=base/'originals/atelier-master--candidate-1.png'; p1=base/'originals/atelier-quiet--candidate-1.png'
a=np.asarray(Image.open(p0).convert('L'),dtype=np.float64)/255
b=np.asarray(Image.open(p1).convert('L'),dtype=np.float64)/255
# High-pass removes broad illumination differences while retaining local contours.
aha=a-gaussian_filter(a,3); bhb=b-gaussian_filter(b,3)
landmarks=[('Left pot rim',99,687),('Left pot shoulder',133,720),('Left leaf tip',210,365),('Wall-floor left corner',247,773),('Window top-left hinge',1236,46),('Window horizontal mullion',1291,189),('Window centre mullion',1291,302),('Lamp arm elbow',1081,377),('Lamp shade neck',1192,326),('Desk top left corner',958,530),('Paper left corner',1090,520),('Rolled paper opening',1422,528),('Desk right corner',1550,500),('Stool seat left',1114,624),('Stool crossbar',1183,749),('Basket rim',1551,670),('Door lower hinge',1335,618),('Desk foot left',1000,744),('Desk foot right',1451,803),('Courtyard stone corner',1619,478)]
r=20;s=12;rows=[]
for name,x,y in landmarks:
 t=aha[y-r:y+r+1,x-r:x+r+1]; t=t-t.mean()
 search=bhb[y-r-s:y+r+s+1,x-r-s:x+r+s+1]
 numerator=correlate2d(search,t,mode='valid')
 ones=np.ones(t.shape); n=t.size
 sm=correlate2d(search,ones,mode='valid'); ss=correlate2d(search**2,ones,mode='valid')
 denom=np.sqrt(np.maximum(ss-sm**2/n,1e-16)*np.sum(t*t))
 cc=numerator/denom
 j,i=np.unravel_index(np.argmax(cc),cc.shape);dx=int(i-s);dy=int(j-s)
 rows.append({'name':name,'master_xy':[x,y],'quiet_best_xy':[x+dx,y+dy],'shift_xy_px':[dx,dy],'shift_distance_px':round(float(np.hypot(dx,dy)),4),'ncc':round(float(cc[j,i]),5),'identity_ncc':round(float(cc[s,s]),5)})
shifts=np.array([r['shift_distance_px'] for r in rows]); corr=np.array([r['ncc'] for r in rows])
report={'method':'20 manually chosen architectural/object landmarks; 41x41 grayscale high-pass templates (Gaussian sigma 3), normalized cross-correlation in ±12 px search on unscaled originals. No warping, rotation or resampling. Coordinates and measured shifts are integer pixels.','dimensions':[a.shape[1],a.shape[0]],'summary':{'landmarks':len(rows),'median_shift_px':float(np.median(shifts)),'max_shift_px':float(shifts.max()),'median_ncc':round(float(np.median(corr)),5),'min_ncc':round(float(corr.min()),5)},'landmarks':rows,'limits':['Local template test samples named points, not every pixel; lighting changes and generative local redraw prevent a claim of pixel identity.','The source images have matching canvas dimensions, and exact registration is not guaranteed beyond the measured samples.','The production plan requests pixel-for-pixel registration. This sampled check is source-art evidence, not whole-image registration or runtime acceptance.']}
(base/'qa/quiet-registration.json').write_text(json.dumps(report,indent=2)+'\n')
# Labeled side-by-side compact landmark preview.
w=836;h=471; sheet=Image.new('RGB',(w*2,h+44),'#f6f0e7'); d=ImageDraw.Draw(sheet)
for k,p in enumerate([p0,p1]):
 im=Image.open(p).resize((w,h),Image.Resampling.LANCZOS); sheet.paste(im,(w*k,44)); d.text((12+w*k,12),'MASTER / warm' if k==0 else 'QUIET / morning — sampled landmarks',fill='#24211c')
 for idx,row in enumerate(rows):
  x,y=row['master_xy'] if k==0 else row['quiet_best_xy']; x=x*.5+w*k;y=y*.5+44
  d.ellipse((x-3,y-3,x+3,y+3),outline='#ff1aa5',width=2);d.text((x+5,y-9),str(idx+1),fill='#ec168f',stroke_width=1,stroke_fill='#fffef8')
sheet.save(base/'qa/quiet-landmarks.jpg',quality=91)
# Edge overlap: red=master, cyan=quiet. Near-neutral marks aligned edges.
def edge(im):
 sm=gaussian_filter(im,1); g=np.hypot(sobel(sm,0),sobel(sm,1)); return np.clip(g/.16,0,1)
ea=edge(a); eb=edge(b)
over=np.stack([ea,eb,eb],axis=-1); ov=Image.fromarray(np.uint8(over*255))
ov.save(base/'qa/quiet-edge-overlay.png')
print(json.dumps(report['summary'],indent=2)); print('\n'.join(f"{x['name']}: {x['shift_xy_px']} NCC {x['ncc']}" for x in rows))
