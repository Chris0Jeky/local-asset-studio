#!/usr/bin/env python3
"""Propose, preview and extract source-bound rectangular repair panels.

No semantic detection, segmentation, model calls or art approval. All coordinates
are half-open boxes on the verified normalized source, never resized master data.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts import repair_source as source

SCHEMA='studio.repair-panels/v1'
MAX_PANELS=64
MAX_TOTAL_PIXELS=48_000_000
MAX_LAYOUT_BYTES=256*1024
MAX_ANALYSIS_PIXELS=2_000_000


def _fields(value, names):
    if type(value) is not dict or set(value)!=set(names.split()): raise ValueError('Layout requires exact supported fields')


def _integer(value, low, high):
    if type(value) is not int or not low<=value<=high: raise ValueError('Expected a bounded integer')
    return value


def _name(value):
    if type(value) is not str or not re.fullmatch(r'[a-z][a-z0-9-]{1,63}',value): raise ValueError('Invalid layout identifier')
    return value


def _box(value, size):
    if type(value) is not list or len(value)!=4 or any(type(v) is not int for v in value): raise ValueError('Expected integer crop coordinates')
    a,b,c,d=value
    if not 0<=a<c<=size[0] or not 0<=b<d<=size[1]: raise ValueError('Crop is outside normalized source')
    return value


def _identity(receipt, raw_receipt):
    normalized=receipt['normalization']['normalized']
    return {'sha256':normalized['sha256'],'size':normalized['size'],'receipt_sha256':source.digest(raw_receipt)}


def _json(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False,indent=2)+'\n').encode()


def _proposal(receipt, raw_receipt, boxes, method, sheet_id):
    layout={'schema':SCHEMA,'sheet_id':_name(sheet_id),'source':_identity(receipt,raw_receipt),
        'method':method,'panels':[{'id':f'panel-{i:02d}','box':b,'role':'view','label':f'Panel {i}',
        'instance_id':f'instance-{i:02d}','canon_id':None,'visibility':'unknown'} for i,b in enumerate(boxes,1)],'overlaps':[]}
    validate_layout(layout,receipt,raw_receipt)
    return layout


def grid(packet: Path, *, rows: int, columns: int, gutter=None, region=None, sheet_id='repair-sheet') -> dict:
    _,receipt,raw_receipt=source.load_packet(packet)
    size=receipt['normalization']['normalized']['size']
    rows=_integer(rows,1,64); columns=_integer(columns,1,64)
    if rows*columns>MAX_PANELS: raise ValueError('Too many panels')
    gutter=[0,0] if gutter is None else gutter
    if type(gutter) is not list or len(gutter)!=2: raise ValueError('Expected x/y gutter widths')
    gx,gy=[_integer(v,0,max(size)) for v in gutter]
    x0,y0,x1,y1=_box(region if region is not None else [0,0,*size],size)
    w=x1-x0-gx*(columns-1); h=y1-y0-gy*(rows-1)
    if w<columns or h<rows: raise ValueError('Gutters leave empty panels')
    boxes=[[x0+c*w//columns+c*gx,y0+r*h//rows+r*gy,
            x0+(c+1)*w//columns+c*gx,y0+(r+1)*h//rows+r*gy] for r in range(rows) for c in range(columns)]
    return _proposal(receipt,raw_receipt,boxes,'grid-v1',sheet_id)


def suggest(packet: Path, *, min_gutter=4, sheet_id='repair-sheet') -> dict:
    """Conservative full-resolution near-white separators; never a subject detector."""
    raw,receipt,raw_receipt=source.load_packet(packet)
    _integer(min_gutter,1,128)
    with Image.open(BytesIO(raw)) as image:
        if image.width*image.height>MAX_ANALYSIS_PIXELS:
            raise ValueError('Gutter analysis is limited to 2 MP; use grid/manual boxes for a larger source')
        with Image.new('RGBA',image.size,'white') as white, Image.alpha_composite(white,image) as visible:
            red,green,blue,alpha=visible.split()
            try:
                with ImageChops.darker(red,green) as rg, ImageChops.darker(rg,blue) as minimum:
                    foreground=minimum.point(lambda v: 0 if v>=248 else 255)
            finally:
                for channel in (red,green,blue,alpha): channel.close()
        def recurse(rect,depth=0):
            if depth>=8: return [rect]
            x0,y0,x1,y1=rect
            for axis in (1,0):
                start,end=(y0,y1) if axis else (x0,x1)
                runs=[]; first=None
                for n in range(start,end+1):
                    empty=False
                    if n<end:
                        b=(x0,n,x1,n+1) if axis else (n,y0,n+1,y1)
                        with foreground.crop(b) as strip: empty=strip.getbbox() is None
                    if empty and first is None: first=n
                    if not empty and first is not None:
                        if n-first>=min_gutter and first>start and n<end: runs.append((first,n))
                        first=None
                if not runs: continue
                edges=[(start,runs[0][0])]+[(runs[i-1][1],runs[i][0]) for i in range(1,len(runs))]+[(runs[-1][1],end)]
                if len(edges)>MAX_PANELS: raise ValueError('Too many gutter candidates; use manual boxes')
                if any(b-a<2 for a,b in edges): continue
                boxes=[]
                for a,b in edges:
                    boxes.extend(recurse([x0,a,x1,b] if axis else [a,y0,b,y1],depth+1))
                    if len(boxes)>MAX_PANELS: raise ValueError('Too many gutter candidates; use manual boxes')
                return boxes
            return [rect]
        try: boxes=recurse([0,0,image.width,image.height])
        finally: foreground.close()
    return _proposal(receipt,raw_receipt,boxes,'whitespace-v1',sheet_id)


def validate_layout(layout: dict, receipt: dict, raw_receipt: bytes) -> dict:
    _fields(layout,'schema sheet_id source method panels overlaps')
    if layout['schema']!=SCHEMA or layout['method'] not in ('grid-v1','whitespace-v1','manual'): raise ValueError('Unsupported panel layout version/method')
    _name(layout['sheet_id'])
    if _json(layout['source'])!=_json(_identity(receipt,raw_receipt)): raise ValueError('Layout source or normalization receipt changed')
    panels=layout['panels']; size=receipt['normalization']['normalized']['size']
    if type(panels) is not list or not 1<=len(panels)<=MAX_PANELS: raise ValueError('Expected 1 to 64 panels')
    ids=set(); instances=set(); total=0
    for entry in panels:
        _fields(entry,'id box role label instance_id canon_id visibility')
        name=_name(entry['id'])
        if name in ids: raise ValueError('Duplicate panel ID')
        ids.add(name); a,b,c,d=_box(entry['box'],size); total+=(c-a)*(d-b)
        if entry['role'] not in ('view','portrait','action'): raise ValueError('Unsupported panel role')
        if type(entry['label']) is not str or not 1<=len(entry['label'])<=64 or any(ord(c)<32 for c in entry['label']): raise ValueError('Invalid panel label')
        if entry['visibility'] not in ('unknown','complete','occluded','out_of_frame','ambiguous'): raise ValueError('Unsupported visibility declaration')
        if entry['instance_id'] is not None:
            instance=_name(entry['instance_id'])
            if instance in instances: raise ValueError('Repeated appearances need distinct instance IDs')
            instances.add(instance)
        if entry['canon_id'] is not None:
            _name(entry['canon_id'])
            if entry['instance_id'] is None: raise ValueError('Canon binding needs an instance ID')
    if total>MAX_TOTAL_PIXELS: raise ValueError('Total crop pixels exceed packet budget')
    actual=set()
    for i,a in enumerate(panels):
        for b in panels[i+1:]:
            x,y,z,w=a['box']; j,k,l,m=b['box']
            if max(x,j)<min(z,l) and max(y,k)<min(w,m): actual.add(tuple(sorted((a['id'],b['id']))))
    declared=set(); overlaps=layout['overlaps']
    if type(overlaps) is not list or len(overlaps)>MAX_PANELS*(MAX_PANELS-1)//2: raise ValueError('Invalid overlap declarations')
    for pair in overlaps:
        if type(pair) is not list or len(pair)!=2 or any(type(v) is not str or v not in ids for v in pair) or pair[0]==pair[1]: raise ValueError('Invalid overlap pair')
        key=tuple(sorted(pair))
        if key in declared: raise ValueError('Duplicate overlap declaration')
        declared.add(key)
    if actual!=declared: raise ValueError('Overlapping boxes require exact explicit pair declarations')
    return {'total_crop_pixels':total,'overlap_pairs':len(actual)}


def _load(packet, path, *, reject_symlink=False):
    normalized,receipt,raw_receipt=source.load_packet(packet)
    raw=source.read_bounded(path,MAX_LAYOUT_BYTES,reject_symlink=reject_symlink); layout=source.strict_json(raw)
    validate_layout(layout,receipt,raw_receipt)
    return normalized,receipt,raw_receipt,raw,layout


def _warnings():
    return ['Rectangular crops retain background and neighboring fragments; no segmentation was performed.',
            'Visibility, instance and canon assignments are caller declarations, not inferred anatomy or approval.',
            'Source-edge contact does not prove a body part is missing. Review crop boundaries before extraction.']


def preview(packet: Path, layout_path: Path, output: Path) -> dict:
    raw,receipt,raw_receipt,raw_layout,layout=_load(packet,layout_path)
    with Image.open(BytesIO(raw)) as image:
        thumb=ImageOps.contain(image,(min(1280,image.width),min(1280,image.height)))
        try:
            draw=ImageDraw.Draw(thumb); sx=thumb.width/image.width; sy=thumb.height/image.height
            font=ImageFont.load_default(size=12)
            for index,entry in enumerate(layout['panels'],1):
                a,b,c,d=entry['box']; x0,y0=int(a*sx),int(b*sy); x1,y1=max(x0,int(c*sx)-1),max(y0,int(d*sy)-1)
                draw.rectangle((x0,y0,x1,y1),outline=(220,30,50,255),width=2)
                draw.text((x0+3,y0+2),str(index),fill=(220,30,50,255),font=font,stroke_width=1,stroke_fill=(255,255,255,255))
            with BytesIO() as out: thumb.save(out,format='PNG'); rendered=out.getvalue()
        finally: thumb.close()
    result={'schema':'studio.repair-panel-preview/v1','source':layout['source'],'layout_sha256':source.digest(raw_layout),
            'preview_sha256':source.digest(rendered),'neural_inference':False,'review_state':'unreviewed',
            'display_only':True,'colour_managed':False,'warnings':_warnings()}
    return source.publish_packet(output,{'preview.png':rendered,'layout.json':raw_layout},result)


def _record(entry, raw, image, size):
    a,b,c,d=entry['box']
    edges=[name for name,yes in [('left',a==0),('top',b==0),('right',c==size[0]),('bottom',d==size[1])] if yes]
    return {**entry,'path':'panel-'+entry['id']+'.png','sha256':source.digest(raw),'bytes':len(raw),
            'size':list(image.size),'pixel_sha256':source.digest(image.tobytes()),'source_edges':edges}


def _legacy(layout):
    return {'schema_version':1,'sheet_id':layout['sheet_id'],
            'source':{'path':'master.png','sha256':layout['source']['sha256'],'size':layout['source']['size']},
            'panels':layout['panels']}


def _receipt(layout, raw_layout, records):
    return {'schema':'studio.repair-extraction/v1','source':layout['source'],'layout_sha256':source.digest(raw_layout),
            'panels':records,'neural_inference':False,'review_state':'unreviewed',
            'scope_acknowledgement':'caller_supplied_exact_layout_digest','warnings':_warnings()}


def extract(packet: Path, layout_path: Path, output: Path, reviewed_layout_sha256: str) -> dict:
    raw,receipt,raw_receipt,raw_layout,layout=_load(packet,layout_path)
    if type(reviewed_layout_sha256) is not str or reviewed_layout_sha256!=source.digest(raw_layout):
        raise ValueError('Exact reviewed layout digest required; preview the changed layout again')
    colours=[(k,v) for k,v in source.scan_png(raw) if k in source.COLOUR]
    artifacts={'master.png':raw,'layout.json':raw_layout,'source-receipt.json':raw_receipt,'legacy-manifest.json':_json(_legacy(layout))}
    records=[]; byte_count=sum(map(len,artifacts.values()))
    with Image.open(BytesIO(raw)) as master:
        for entry in layout['panels']:
            with master.crop(entry['box']) as crop:
                encoded=source.encode_rgba(crop,colours); byte_count+=len(encoded)
                if byte_count>source.MAX_OUTPUT_BYTES: raise ValueError('Extraction output exceeds byte budget')
                record=_record(entry,encoded,crop,master.size); records.append(record); artifacts[record['path']]=encoded
    return source.publish_packet(output,artifacts,_receipt(layout,raw_layout,records))


def verify_extraction(packet: Path, folder: Path) -> dict:
    raw,receipt,raw_receipt,raw_layout,layout=_load(packet,folder/'layout.json',reject_symlink=True)
    read=lambda name,limit: source.read_bounded(folder/name,limit,reject_symlink=True)
    result=source.strict_json(read('receipt.json',source.MAX_METADATA_BYTES))
    if read('master.png',source.MAX_OUTPUT_BYTES)!=raw or read('source-receipt.json',source.MAX_METADATA_BYTES)!=raw_receipt:
        raise ValueError('Extraction master/source receipt changed')
    if read('legacy-manifest.json',MAX_LAYOUT_BYTES)!=_json(_legacy(layout)): raise ValueError('Legacy manifest changed')
    colours=[(k,v) for k,v in source.scan_png(raw) if k in source.COLOUR]; records=[]
    used=len(raw)+len(raw_layout)+len(raw_receipt)+len(_json(_legacy(layout)))
    if used>source.MAX_OUTPUT_BYTES: raise ValueError('Extraction output exceeds byte budget')
    with Image.open(BytesIO(raw)) as master:
        for entry in layout['panels']:
            encoded=read('panel-'+entry['id']+'.png',source.MAX_OUTPUT_BYTES-used)
            used+=len(encoded)
            chunks=source.scan_png(encoded)
            if any(k not in (*source.COLOUR,b'IHDR',b'IDAT',b'IEND') for k,_ in chunks) or [(k,v) for k,v in chunks if k in source.COLOUR]!=colours:
                raise ValueError('Unexpected crop metadata')
            with Image.open(BytesIO(encoded)) as actual, master.crop(entry['box']) as expected:
                if actual.mode!='RGBA' or actual.size!=expected.size or actual.tobytes()!=expected.tobytes():
                    raise ValueError('Extracted pixels differ from the source box')
                records.append(_record(entry,encoded,actual,master.size))
    if _json(result)!=_json(_receipt(layout,raw_layout,records)): raise ValueError('Extraction receipt differs from verified artifacts')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    g=sub.add_parser('grid'); g.add_argument('--rows',type=int,required=True); g.add_argument('--columns',type=int,required=True)
    g.add_argument('--gutter',type=int,nargs=2,default=[0,0]); g.add_argument('--region',type=int,nargs=4)
    s=sub.add_parser('suggest'); s.add_argument('--min-gutter',type=int,default=4)
    v=sub.add_parser('preview'); e=sub.add_parser('extract'); check=sub.add_parser('verify')
    for c in (g,s,v,e,check): c.add_argument('--source',type=Path,required=True)
    for c in (g,s): c.add_argument('--sheet-id',default='repair-sheet')
    for c in (v,e): c.add_argument('--layout',type=Path,required=True); c.add_argument('--out',type=Path,required=True)
    e.add_argument('--reviewed-layout-sha256',required=True); check.add_argument('--packet',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='grid': result=grid(args.source,rows=args.rows,columns=args.columns,gutter=args.gutter,region=args.region,sheet_id=args.sheet_id)
        elif args.command=='suggest': result=suggest(args.source,min_gutter=args.min_gutter,sheet_id=args.sheet_id)
        elif args.command=='preview': result=preview(args.source,args.layout,args.out)
        elif args.command=='extract': result=extract(args.source,args.layout,args.out,args.reviewed_layout_sha256)
        else: result=verify_extraction(args.source,args.packet)
        print(_json(result).decode('ascii'),end=''); return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'error':str(exc),'neural_inference':False,'review_state':'unreviewed'},ensure_ascii=True)); return 2

if __name__=='__main__': raise SystemExit(main())
