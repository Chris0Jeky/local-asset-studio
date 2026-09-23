"""Isolated Qwen-Image-2.1 server: a ComfyUI v0.37.0 checkout that reuses ROCm Torch unchanged.

The primary ComfyUI (v0.35.0) has no Qwen-Image-2.1 model class. This checkout adds it without
upgrading the shared runtime: the three packages v0.37.0 pins newer (comfy-kitchen, comfy-aimdo,
the frontend) live in the checkout's own python_packages overlay. docs/QWEN-IMAGE-21.md.
"""
import argparse, os, runpy, shutil, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--comfy-root',default='C:/AI/experiments/qwen-image-21/ComfyUI')
args=parser.parse_args()
root=Path(args.comfy_root).resolve()
if not (root/'main.py').is_file() or not (root/'comfy/text_encoders/qwen_image21.py').is_file():
    parser.error('The isolated ComfyUI checkout is missing or predates Qwen-Image-2.1; see docs/QWEN-IMAGE-21.md')
if not (root/'python_packages/comfy_kitchen').is_dir():
    parser.error('Isolated dependencies are missing; see docs/QWEN-IMAGE-21.md')
# The recipes' authored example pictures, as Start-Studio.ps1 stages them for the primary; existing files are kept.
(root/'input').mkdir(exist_ok=True)
for picture in (Path(__file__).resolve().parents[1]/'examples/references').iterdir():
    if picture.is_file() and not (root/'input'/picture.name).exists():shutil.copyfile(picture,root/'input'/picture.name)
sys.path.insert(0,str(root/'python_packages'))
sys.path.insert(0,str(root))
os.chdir(root)
sys.argv=[str(root/'main.py'),'--windows-standalone-build','--disable-auto-launch','--disable-api-nodes','--preview-method','latent2rgb',
          '--listen','127.0.0.1','--port','8196','--reserve-vram','0.6','--disable-pinned-memory']
runpy.run_path(str(root/'main.py'),run_name='__main__')
