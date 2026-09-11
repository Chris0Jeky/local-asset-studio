from PIL import Image,ImageDraw
from pathlib import Path
import json,shutil,hashlib
out=Path(__file__).resolve().parent;files=sorted((out/'renders').glob('*.png'));assert len(files)==96
small=[Image.open(p).convert('RGBA').resize((64,64),Image.Resampling.NEAREST) for p in files]
sample=Image.new('RGB',(64*len(small),64),(0,0,0))
for i,im in enumerate(small): sample.paste(im,(i*64,0))
palette=sample.quantize(colors=31,method=Image.Quantize.MEDIANCUT)
atlas=Image.new('RGBA',(68*8,68*12));frames={};pixels=out/'sprites';pixels.mkdir(exist_ok=True)
for i,(p,im) in enumerate(zip(files,small)):
 q=im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE).convert('RGBA');q.putalpha(im.getchannel('A').point(lambda x:255 if x>=128 else 0));q.save(pixels/p.name)
 x=(i%8)*68+2;y=(i//8)*68+2
 # Duplicate edge texels into the 2px gutter; the frame itself stays 64x64.
 tile=q.resize((68,68),Image.Resampling.NEAREST)
 tile.paste(q,(2,2));tile.paste(q.crop((0,0,1,64)).resize((2,64)),(0,2));tile.paste(q.crop((63,0,64,64)).resize((2,64)),(66,2));tile.paste(q.crop((0,0,64,1)).resize((64,2)),(2,0));tile.paste(q.crop((0,63,64,64)).resize((64,2)),(2,66));atlas.paste(tile,(x-2,y-2))
 frames[p.stem]={'frame':{'x':x,'y':y,'w':64,'h':64},'pivot':{'x':.5,'y':.5},'duration_ms':160}
atlas.save(out/'sprites.png');(out/'sprites.json').write_text(json.dumps({'image':'sprites.png','size':[atlas.width,atlas.height],'filter':'nearest','frames':frames},indent=2))
preview=Image.new('RGB',(960,440),'#101d23');draw=ImageDraw.Draw(preview);draw.text((24,18),'LANTERNKEEPER / 3 skins / 8 directions / 4 bob frames',fill='#e8d7af')
for row,skin in enumerate(['moss','amethyst','ember']):
 draw.text((20,65+row*120),skin.upper(),fill='#e8d7af')
 for d in range(8):
  im=Image.open(pixels/f'{skin}-{d}-1.png').resize((100,100),Image.Resampling.NEAREST);preview.paste(im,(130+d*100,40+row*120),im)
preview.save(out/'contact-sheet.png')
print('Packed 96 sprites')
