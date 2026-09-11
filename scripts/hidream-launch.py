"""Isolated HiDream server; reuse ROCm Torch without modifying the primary environment."""
import argparse, os, runpy, sys
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--install-root',default='C:/AI/experiments/hidream-o1')
args=parser.parse_args()
root=Path(args.install_root).resolve()/'ComfyUI'
if not (root/'python_packages/transformers').is_dir():
    parser.error('Isolated dependencies are missing; see docs/HIDREAM.md')
sys.path.insert(0,str(root/'python_packages'))
sys.path.insert(0,str(root))
os.chdir(root)
sys.argv=[str(root/'main.py'),'--windows-standalone-build','--disable-auto-launch','--disable-api-nodes','--listen','127.0.0.1','--port','8192','--reserve-vram','2']
runpy.run_path(str(root/'main.py'),run_name='__main__')
