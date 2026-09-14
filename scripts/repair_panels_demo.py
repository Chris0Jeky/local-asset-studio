#!/usr/bin/env python3
"""Create an original synthetic nine-panel fixture and exercise real CPU intake.

Outputs are mechanical test evidence, not generated artwork or accepted anatomy.
"""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts import repair_source as source
from scripts import repair_panels as panels


def run(output: Path) -> dict:
    output.parent.mkdir(parents=True,exist_ok=True); output.mkdir()
    boxes=[[20+c*202,30+r*246,212+c*202,264+r*246] for r in range(2) for c in range(3)]
    boxes += [[640,30,780,170],[640,190,780,330],[640,350,780,510]]
    with Image.new('RGBA',(800,540),(247,247,244,255)) as image:
        draw=ImageDraw.Draw(image); font=ImageFont.load_default(size=15)
        for i,(a,b,c,d) in enumerate(boxes,1):
            draw.rectangle((a,b,c-1,d-1),fill=(224+i*2,229,237-i*2,255))
            mid=(a+c)//2; top=b+40
            draw.ellipse((mid-18,top-18,mid+18,top+18),fill=(45,65,87,255))
            if i<=6:
                draw.line((mid,top+18,mid,top+95),fill=(45,65,87,255),width=14)
                draw.line((mid-45,top+55,mid,top+35,mid+45,top+60),fill=(45,65,87,255),width=9)
                draw.line((mid-30,d-28,mid,top+95,mid+30,d-28),fill=(45,65,87,255),width=10)
                draw.rectangle((a+8,d-20,a+28,d-8),fill=(170,30,100,0))
            draw.text((a+8,b+7),f'Fixture {i}',font=font,fill=(30,45,60,255))
        draw.text((20,515),'Synthetic geometry only / not anatomy or artistic acceptance',font=font,fill=(30,45,60,255))
        info=PngImagePlugin.PngInfo(); info.add_text('fixture','original synthetic repair intake example')
        image.save(output/'original.png',pnginfo=info)
    packet=output/'source'; source.capture(output/'original.png',packet)
    _,receipt,raw_receipt=source.load_packet(packet)
    layout={'schema':panels.SCHEMA,'sheet_id':'synthetic-sheet','method':'manual',
        'source':{'sha256':receipt['normalization']['normalized']['sha256'],
                  'size':receipt['normalization']['normalized']['size'],'receipt_sha256':source.digest(raw_receipt)},
        'panels':[{'id':f'fixture-{i:02d}','box':box,'role':'view' if i<=6 else 'portrait','label':f'Fixture {i}',
                   'instance_id':f'instance-{i:02d}','canon_id':'synthetic-canon','visibility':'unknown'} for i,box in enumerate(boxes,1)],'overlaps':[]}
    layout_path=output/'layout.json'; layout_path.write_text(json.dumps(layout,indent=2)+'\n',encoding='utf-8')
    preview=panels.preview(packet,layout_path,output/'preview')
    result=panels.extract(packet,layout_path,output/'extracted',preview['layout_sha256'])
    panels.verify_extraction(packet,output/'extracted')
    proof={'schema':'studio.repair-intake-demo/v1','panels':len(result['panels']),
           'verified_exact_crops':True,'neural_inference':False,'review_state':'unreviewed',
           'layout_sha256':preview['layout_sha256'],'pillow_version':Image.__version__}
    with (output/'result.json').open('x',encoding='utf-8') as stream: json.dump(proof,stream,indent=2)
    return proof


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try: print(json.dumps(run(args.out),indent=2)); return 0
    except (ValueError,OSError) as exc: print(json.dumps({'error':str(exc),'neural_inference':False})); return 2

if __name__=='__main__': raise SystemExit(main())
