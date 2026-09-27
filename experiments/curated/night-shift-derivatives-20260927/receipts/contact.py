# As-run script (27 Sep 2026), kept as a receipt; hardcodes this machine's local paths and is not a portable reproduction.
from PIL import Image, ImageDraw
PK='C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research/nightshift-20260927/'
L=lambda p: Image.open(PK+p).convert('RGB')
s=Image.new('RGB',(1300,1700),'white'); d=ImageDraw.Draw(s)
def put(im,x,y,w,label):
    im=im.resize((w,round(im.size[1]*w/im.size[0])),Image.LANCZOS); s.paste(im,(x,y+14)); d.text((x+2,y),label,fill='black'); return y+14+im.size[1]
y=put(L('retro-anime-master/renditions/retro-anime-master--1280x720--preview.webp'),0,0,640,'retro-anime-master 3840x2160 (ESRGAN raw 4x -> Lanczos, MA) [keep]')
put(L('retro-anime-quiet/renditions/retro-anime-quiet--1280x720--poster.webp'),650,0,640,'retro-anime-quiet 3840x2160 (r1-2, warped + same upscale) [keep]')
y2=put(L('retro-anime-quiet/review/crossfade-50--1280x720.png'),0,y+6,640,'review: 50% crossfade master/quiet')
put(L('retro-anime-quiet/review/registration-edges-over-quiet--1280x720.png'),650,y+6,640,'review: master edges (red) over quiet')
y3=put(L('retro-anime-hero/renditions/retro-anime-hero--1920x800--wide.webp'),0,y2+6,860,'retro-anime-hero 3840x1600 (box 0,360,3840,1960) [keep]')
put(L('retro-anime-poster/renditions/retro-anime-poster--640x360--still.webp'),870,y2+6,420,'retro-anime-poster 1280x720 / 640x360 [keep]')
x=0; yy=y3+6
for n,v in (('tight','keep, 1st'),('wide','keep, 2nd')):
    put(L('retro-anime-card/renditions/retro-anime-card--256x256--%s.webp'%n),x,yy,256,'card %s [%s]'%(n,v)); put(L('retro-anime-card/review/at-96px--%s.png'%n),x+262,yy,96,'at 96 px'); x+=380
s=s.crop((0,0,1300,yy+14+256+4)); s.save('pack-contact.jpg',quality=85); print(s.size)
