"""Replay recorded local crops/encodes into a separate output directory."""
import hashlib,json,sys
from pathlib import Path
from PIL import Image

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
if source==out or source in out.parents:
    raise SystemExit("Choose an output directory outside the source pack")
manifest=json.loads((source/'metadata/TRANSFORMATIONS.json').read_text())
for t in manifest['transformations']:
    inp=source/t['input_path'];assert sha(inp)==t['input_sha256'],str(inp)
    im=Image.open(inp).convert('RGB');enc=t['encoding']
    if enc['format']=='PNG':result=im.crop(tuple(t['crop_box_xyxy']))
    else:result=im.resize(tuple(t['output_dimensions']),Image.Resampling.LANCZOS,box=tuple(t['crop_box_xyxy']))
    dest=out/t['output_path'];dest.parent.mkdir(parents=True,exist_ok=True)
    if enc['format']=='PNG':result.save(dest,optimize=enc['optimize'])
    else:result.save(dest,format='WEBP',quality=enc['quality'],method=enc['method'])
    assert sha(dest)==t['output_sha256'],'Output byte mismatch: '+str(dest)
    print('Verified',t['output_path'])
