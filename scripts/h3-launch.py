"""Launch an opt-in H3 loader experiment without editing installed ComfyUI files."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--comfy-root',required=True)
args=parser.parse_args();root=Path(args.comfy_root).resolve();repo=Path(__file__).resolve().parents[1]
encoder=root/'models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
if not encoder.is_file() or not (root/'main.py').is_file():parser.error('H3 encoder or ComfyUI installation is missing')
runtime=repo/'.runtime/h3-compat';node=runtime/'custom_nodes/studio_h3_loader';node.mkdir(parents=True,exist_ok=True)
source='import sys\nsys.path.insert(0, '+repr(str(repo/'scripts'))+')\nfrom h3_mmap_loader import install\ninstall('+repr(str(encoder))+', read_only=True)\nNODE_CLASS_MAPPINGS = {}\n'
(node/'__init__.py').write_text(source,encoding='utf-8')
paths=runtime/'extra-paths.json';paths.write_text(json.dumps({'studio_h3_loader':{'base_path':str(runtime),'custom_nodes':'custom_nodes'}}),encoding='utf-8')
sys.path.insert(0,str(root));os.chdir(root)
sys.argv=[str(root/'main.py'),'--windows-standalone-build','--disable-auto-launch','--disable-api-nodes','--listen','127.0.0.1','--port','8194','--reserve-vram','2','--extra-model-paths-config',str(paths)]
runpy.run_path(str(root/'main.py'),run_name='__main__')
