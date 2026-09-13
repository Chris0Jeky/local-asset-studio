"""Inspect finished .safetensors downloads and copy reviewed candidates into ComfyUI.

Offline: it inspects the safetensors header (metadata plus tensor key shapes), never the network. Files are
copied without overwriting destinations; originals stay in place. Each copy has a durable intake journal. Standard library only.
"""
import argparse,json,re,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
# One folder allow-list for the whole repo: drifting copies let a script write where the
# Models view cannot read, and three copies had already diverged (9, 9 and 11 entries).
from model_library import FOLDERS as _FOLDERS
from model_intake import import_candidate, source_snapshot, target_path
FOLDERS=tuple(_FOLDERS)
LORA_MARKERS=('.lora_a.','.lora_b.','.lora_down.','.lora_up.','.lora.down.','.lora.up.','.lora_magnitude','.hada_w','.lokr_','.oft_','.diff_b')
LORA_PREFIXES=('lora_unet_','lora_te_','lora_te1_','lora_te2_','lora_transformer_')
VAE_PARTS={'decoder','encoder','conv1','conv2','quant_conv','post_quant_conv','quantize','loss'}

def load_config(root=ROOT):
 path=root/'config/local.json'
 if not path.is_file():raise SystemExit('config/local.json is missing. Copy config/example.json and set comfy_root.')
 config=json.loads(path.read_text(encoding='utf-8'))
 if not config.get('comfy_root'):raise SystemExit('config/local.json has no comfy_root')
 return config

def read_header(path,limit=100*1024**2):
 """Return the safetensors JSON header. Raises ValueError on anything that is not one."""
 with Path(path).open('rb') as stream:
  raw=stream.read(8)
  if len(raw)<8:raise ValueError('not a safetensors file: no header length')
  length=int.from_bytes(raw,'little')
  if not 0<length<=limit:raise ValueError(f'unreasonable safetensors header length: {length}')
  body=stream.read(length)
 if len(body)!=length:raise ValueError('truncated safetensors header')
 try:header=json.loads(body.decode('utf-8'))
 except (UnicodeDecodeError,json.JSONDecodeError) as error:raise ValueError('unreadable safetensors header: '+str(error))
 if not isinstance(header,dict):raise ValueError('safetensors header is not an object')
 return header

def classify(header):
 """Return a folder hint or None, never identity/compatibility proof. LoRA evidence wins."""
 meta=header.get('__metadata__') if isinstance(header.get('__metadata__'),dict) else {}
 keys=[str(key).lower() for key in header if key!='__metadata__']
 architecture=str(meta.get('modelspec.architecture') or '').lower()
 if 'lora' in architecture.split('/') or {'ss_network_module','lora_rank','lora_alpha','ss_network_dim'}&set(meta):return 'loras'
 if any(key.startswith(LORA_PREFIXES) for key in keys):return 'loras'
 if any(marker in key for key in keys for marker in LORA_MARKERS):return 'loras'
 parts={key.split('.')[0] for key in keys}
 if 'first_stage_model' in parts and parts&{'conditioner','cond_stage_model'}:return 'checkpoints'
 if parts and parts<=VAE_PARTS and 'decoder' in parts:return 'vae'
 if any(key.startswith(('text_model.','model.embed_tokens','shared.','encoder.block.')) for key in keys):return 'text_encoders'
 # Positive fixture-backed backbone signature; unknown families require operator review.
 # A filename, metadata title or unrecognised tensor key is not diffusion evidence.
 backbone=[key.removeprefix('model.diffusion_model.').removeprefix('diffusion_model.') for key in keys]
 if all(any(key.startswith(prefix) for key in backbone) for prefix in ('blocks.','img_in.','final_layer.')):return 'diffusion_models'
 return None

def plan(paths,folder=None):
 """Classify each candidate without moving anything; errors are carried, not raised."""
 items=[]
 for path in paths:
  item={'path':Path(path),'folder':folder,'error':None,'folder_basis':'operator-selected' if folder is not None else 'unknown'}
  try:
   item['source_identity']=source_snapshot(path)
   if folder is None:
    item['folder']=classify(read_header(path))
    if item['folder'] is None:
     item['error']='Unknown model role: no supported header signature. File preserved; inspect the source and use --dest-folder only after review.'
    else:item['folder_basis']='header-hint'
   if source_snapshot(path)!=item['source_identity']:raise ValueError('Source changed during header inspection; original preserved')
  except (ValueError,OSError) as error:item.update(error=str(error),folder_basis='unreadable-header')
  items.append(item)
 return items

def safe_name(name):
 base=Path(str(name or '')).name
 cleaned=re.sub(r'_+','_',re.sub(r'[^A-Za-z0-9._-]+','_',base)).strip('._-')
 if not cleaned.endswith('.safetensors') or len(cleaned)>200:raise SystemExit('Cannot derive a safe filename from '+str(name))
 return cleaned

def destination(comfy_root,folder,name):
 if folder not in FOLDERS:raise SystemExit('Unsupported destination folder: '+str(folder))
 try:return target_path(comfy_root,folder,safe_name(name))
 except ValueError as error:raise SystemExit(str(error)) from error

def slug(name):
 value=re.sub(r'[^a-z0-9]+','-',re.sub(r'\.safetensors$','',str(name).lower())).strip('-')
 if not value:raise SystemExit('Cannot derive an asset id from '+str(name))
 return value

def stub(folder,name,size,digest,source='',family='',trigger='',strength=None):
 return {'id':slug(name),'name':name,'file':f'{folder}/{name}','source':source,'url':source,'bytes':size,'sha256':digest,
         'license':'','terms':'TODO: record where this file came from and its licence before relying on it',
         'family':family,'trigger':trigger,'strength':strength or [1.0,1.0]}

def main(argv=None):
 parser=argparse.ArgumentParser(description='Copy reviewed .safetensors downloads into ComfyUI; preserve browser originals.')
 parser.add_argument('--from',dest='source',type=Path,default=Path.home()/'Downloads')
 parser.add_argument('--dest-folder',choices=FOLDERS,help='operator-selected folder; bypasses header classification, not proof of model compatibility')
 parser.add_argument('--name',help='rename a single file on the way in')
 parser.add_argument('--dry-run',action='store_true')
 args=parser.parse_args(argv)
 if not args.source.is_dir():raise SystemExit('No such folder: '+str(args.source))
 candidates=sorted(path for path in args.source.glob('*.safetensors') if path.is_file())
 if args.name and len(candidates)!=1:raise SystemExit('--name needs exactly one candidate file; found '+str(len(candidates)))
 if not candidates:print('Nothing to intake in '+str(args.source));return 0
 comfy_root=load_config()['comfy_root'];copied=0
 for item in plan(candidates,args.dest_folder):
  path=item['path']
  if item['error']:print('SKIP',path.name,'-',item['error']);continue
  target=destination(comfy_root,item['folder'],args.name or path.name)
  print(f'{path.name} -> {target}')
  print('  Folder basis: '+item['folder_basis']+'; identity and runtime compatibility are unverified.')
  if args.dry_run:continue
  if target.exists():print('SKIP',path.name,'- destination already exists; nothing was overwritten');continue
  receipt=import_candidate(ROOT,comfy_root,path,item['folder'],target.name,item['source_identity'],item['folder_basis']);copied+=1
  print('RECEIPT',json.dumps(receipt,indent=2))
  print('LIBRARY STUB',json.dumps(stub(item['folder'],target.name,receipt['bytes'],receipt['sha256']),indent=2))
 print(f'{len(candidates)} candidate(s); {copied} copied. Browser originals retained. Copies are not source-verified; inspect the per-operation intake receipts.')
 return 0

if __name__=='__main__':raise SystemExit(main())
