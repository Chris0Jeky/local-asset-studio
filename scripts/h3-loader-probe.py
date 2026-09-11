"""Construct the local H3 encoder with a selected loader; never generate video."""
import argparse
import faulthandler
import json
from pathlib import Path
import sys
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--comfy-root',required=True)
parser.add_argument('--report',required=True)
parser.add_argument('--construct',action='store_true')
parser.add_argument('--read-only',action='store_true')
parser.add_argument('--diffusion',action='store_true')
args=parser.parse_args();faulthandler.enable()
root=Path(args.comfy_root).resolve();sys.path.insert(0,str(Path(__file__).resolve().parent));sys.path.insert(0,str(root))
sys.argv=[sys.argv[0],'--cpu']
import comfy.options
comfy.options.enable_args_parsing()
import torch
torch.set_num_threads(4)
import comfy.utils
from h3_mmap_loader import install
encoder=root/'models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
target=root/'models/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors' if args.diffusion else encoder
install(target,read_only=args.read_only);start=time.time()
result={'loader':'stdlib '+('read-only' if args.read_only else 'copy-on-write')+' mmap','model_file':str(target),'construct_requested':args.construct,'inference':False}
try:
    if args.construct:
        import comfy.sd
        print('BEGIN bounded CPU '+('diffusion' if args.diffusion else 'encoder')+' construction',flush=True)
        if args.diffusion:
            model=comfy.sd.load_diffusion_model(str(target))
            result.update(constructed=True,model_class=type(model.model).__name__,patcher_class=type(model).__name__)
        else:
            clip=comfy.sd.load_clip([str(encoder)],embedding_directory=[str(root/'models/embeddings')],clip_type=comfy.sd.CLIPType.MINIMAX,model_options={'load_device':torch.device('cpu'),'offload_device':torch.device('cpu')})
            result.update(constructed=True,clip_class=type(clip.cond_stage_model).__name__)
    else:
        state=comfy.utils.load_torch_file(str(target));result['tensor_count']=len(state)
    result['status']='completed'
except Exception as exc:
    result.update(status='failed',error=type(exc).__name__+': '+str(exc))
    import traceback;traceback.print_exc()
finally:
    result.update(seconds=time.time()-start,cuda_initialized=torch.cuda.is_initialized())
    report=Path(args.report);report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
