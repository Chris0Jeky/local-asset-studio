"""Procedural AV fixtures for editor/render tests, not AI voice or music samples."""
from pathlib import Path
import argparse
import math
import random
import struct
import sys
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_av.project import file_hash,write_new
from studio_av.render import render

def create(root,do_render=False):
    from PIL import Image,ImageDraw,ImageFont
    root=Path(root);root.mkdir(parents=True,exist_ok=False);(root/'media').mkdir()
    for i,(title,small,color) in enumerate([('THE OBSERVATORY','01 / Establish the scene',(29,56,72)),('THE SIGNAL','02 / Motion cue and layered sound',(52,66,53)),('THE RESPONSE','03 / Edit the mix; keep the source',(70,49,55))]):
        im=Image.new('RGB',(640,360),color);d=ImageDraw.Draw(im)
        for x in range(0,640,40):d.line((x,0,x,360),fill=(70,90,96),width=1)
        d.ellipse((355,35,585,265),outline=(207,223,172),width=3);d.line((330,150,610,150),fill=(207,223,172),width=2)
        d.rectangle((25,272,615,336),fill=(12,20,25))
        d.text((42,282),title,fill='white',font=ImageFont.load_default(23));d.text((42,314),small,fill=(204,218,196),font=ImageFont.load_default(13))
        im.save(root/f'media/shot-{i}.png')
    im=Image.new('RGBA',(200,32));d=ImageDraw.Draw(im);d.rounded_rectangle((0,0,199,31),8,fill=(232,202,129,255));d.text((12,8),'PROCEDURAL QA / NOT TTS',fill=(20,25,30),font=ImageFont.load_default(11));im.save(root/'media/label.png')
    rng=random.Random(20260911);rate=48000
    for name in ('music','fx','ambience'):
        with wave.open(str(root/f'media/{name}.wav'),'wb') as w:
            w.setparams((1,2,rate,0,'NONE','not compressed'))
            for second in range(6):
                raw=bytearray()
                for i in range(rate):
                    t=second+i/rate
                    if name=='music':val=.22*math.sin(2*math.pi*[220,261.63,293.66][int(t/2)%3]*t)+.08*math.sin(2*math.pi*110*t)
                    elif name=='ambience':val=.1*(rng.random()*2-1)
                    else:
                        phase=t%1.5;val=.45*math.sin(2*math.pi*660*t)*max(0,1-phase/.13) if phase<.13 else 0
                    raw.extend(struct.pack('<h',round(val*32767)))
                w.writeframes(raw)
    assets={}
    for i in range(3):assets[f'shot{i}']={'path':f'media/shot-{i}.png','kind':'image'}
    assets['label']={'path':'media/label.png','kind':'image'}
    for n in ('music','fx','ambience'):assets[n]={'path':f'media/{n}.wav','kind':'audio'}
    for a in assets.values():a['sha256']=file_hash(root/a['path'])
    p={'schema_version':1,'name':'Observatory / AV pipeline proof','fps':[24,1],'size':[640,360],'sample_rate':48000,'assets':assets,
       'shots':[{'id':f'shot{i}','asset':f'shot{i}','source_in':0,'frames':f,'transition_frames':tr} for i,(f,tr) in enumerate([(60,0),(60,12),(48,12)])],
       'overlays':[{'id':'qa-label','asset':'label','start':0,'frames':144,'x':22,'y':20,'width':200,'height':32,'opacity':.9}],
       'audio':[{'id':n+'-clip','asset':n,'bus':n,'start_sample':0,'source_sample':0,'samples':288000,'gain_db':gain,'fade_in':9600,'fade_out':24000,'mute':False} for n,gain in [('music',-12),('fx',-6),('ambience',-20)]],
       'master_gain_db':-3}
    write_new(root/'project.json',p)
    if do_render:render(p,root,root/'render')
    return p
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True);p.add_argument('--render',action='store_true');a=p.parse_args();create(a.out,a.render)
