"""Isolated MOSS-Image server: a ComfyUI v0.42.1 checkout that reuses ROCm Torch unchanged.

The primary ComfyUI (v0.35.0) has no MOSS-Image text encoder type or model class (added in v0.42.0). This checkout adds it
without upgrading the shared runtime: the packages v0.42.1 pins newer (comfy-kitchen, comfy-aimdo, the frontend) live in
the checkout's own python_packages overlay, and its extra_model_paths.yaml points at the main model library.
docs/MOSS-IMAGE.md.
"""
import argparse, os, runpy, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--comfy-root',default='C:/AI/experiments/moss-image/ComfyUI')
parser.add_argument('--reserve-vram',default='2')
args=parser.parse_args()
root=Path(args.comfy_root).resolve()
if not (root/'main.py').is_file() or not (root/'comfy/text_encoders/moss_image.py').is_file():
    parser.error('The isolated ComfyUI checkout is missing or predates MOSS-Image (v0.42.0+); see docs/MOSS-IMAGE.md')
if not (root/'python_packages/comfy_kitchen').is_dir():
    parser.error('Isolated dependencies are missing; see docs/MOSS-IMAGE.md')
sys.path.insert(0,str(root/'python_packages'))
sys.path.insert(0,str(root))
os.chdir(root)
sys.argv=[str(root/'main.py'),'--windows-standalone-build','--disable-auto-launch','--disable-api-nodes','--preview-method','latent2rgb',
          '--listen','127.0.0.1','--port','8198','--reserve-vram',str(args.reserve_vram),'--disable-pinned-memory']
runpy.run_path(str(root/'main.py'),run_name='__main__')
