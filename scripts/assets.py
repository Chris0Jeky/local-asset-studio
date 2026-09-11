"""Local asset finishing: grid slicing, atlases, previews and exact masked edits."""
import argparse, json, math, os
from pathlib import Path
from PIL import Image

def save(image, path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise FileExistsError(f'Refusing to overwrite {path}')
    image.save(path)

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('slice'); s.add_argument('input'); s.add_argument('output'); s.add_argument('--size',type=int,nargs=2,required=True,metavar=('WIDTH','HEIGHT'))
    a=sub.add_parser('atlas'); a.add_argument('output'); a.add_argument('inputs',nargs='+'); a.add_argument('--columns',type=int,default=4); a.add_argument('--padding',type=int,default=2)
    g=sub.add_parser('gif'); g.add_argument('output'); g.add_argument('inputs',nargs='+'); g.add_argument('--ms',type=int,default=150)
    c=sub.add_parser('composite'); c.add_argument('original'); c.add_argument('edited'); c.add_argument('mask'); c.add_argument('output')
    w=sub.add_parser('web'); w.add_argument('input'); w.add_argument('output'); w.add_argument('--width',type=int,default=1200)
    r=sub.add_parser('remove-bg'); r.add_argument('input'); r.add_argument('output')
    args=p.parse_args()
    if args.cmd=='slice':
        im=Image.open(args.input).convert('RGBA'); w,h=args.size
        if min(w,h)<=0 or im.width%w or im.height%h: p.error('Cell size must evenly divide the image; use an unpadded grid.')
        for y in range(0,im.height,h):
            for x in range(0,im.width,w): save(im.crop((x,y,x+w,y+h)),Path(args.output)/f'{y//h:03d}-{x//w:03d}.png')
    elif args.cmd=='atlas':
        frames=[Image.open(f).convert('RGBA') for f in args.inputs]
        if args.columns<=0 or args.padding<0: p.error('Columns must be positive; padding cannot be negative.')
        w=max(f.width for f in frames); h=max(f.height for f in frames); pad=args.padding
        out=Image.new('RGBA',(args.columns*(w+2*pad),math.ceil(len(frames)/args.columns)*(h+2*pad)))
        records=[]
        for i,(im,source) in enumerate(zip(frames,args.inputs)):
            x=i%args.columns*(w+2*pad)+pad; y=i//args.columns*(h+2*pad)+pad
            out.paste(im,(x,y)); records.append(dict(name=Path(source).name,x=x,y=y,width=im.width,height=im.height,pivot=[.5,.5]))
        metadata=Path(args.output).with_suffix('.json')
        if metadata.exists(): raise FileExistsError(metadata)
        save(out,args.output); metadata.write_text(json.dumps(dict(image=Path(args.output).name,frames=records,padding=pad),indent=2))
    elif args.cmd=='gif':
        if Path(args.output).exists(): raise FileExistsError(args.output)
        frames=[]
        for source in args.inputs:
            im=Image.open(source).convert('RGBA'); bg=Image.new('RGBA',im.size,'#17252d'); bg.alpha_composite(im); frames.append(bg.convert('RGB'))
        if len({f.size for f in frames})!=1: p.error('Animation frames must have matching canvas sizes.')
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        frames[0].save(args.output,save_all=True,append_images=frames[1:],duration=args.ms,loop=0)
    elif args.cmd=='composite':
        original=Image.open(args.original).convert('RGBA'); edited=Image.open(args.edited).convert('RGBA'); mask=Image.open(args.mask).convert('L')
        if original.size!=edited.size or original.size!=mask.size: p.error('Original, edit and mask must have identical sizes.')
        save(Image.composite(edited,original,mask),args.output)
    elif args.cmd=='web':
        im=Image.open(args.input).convert('RGBA')
        if args.width<=0: p.error('Width must be positive.')
        if im.width>args.width: im=im.resize((args.width,max(1,round(im.height*args.width/im.width))),Image.Resampling.LANCZOS)
        save(im,args.output)
    else:
        os.environ.setdefault('U2NET_HOME',r'C:\AI\asset-tools\models')
        from rembg import remove,new_session
        im=Image.open(args.input).convert('RGBA'); result=remove(im,session=new_session('u2netp',providers=['CPUExecutionProvider']))
        save(result,args.output)

if __name__=='__main__': main()
