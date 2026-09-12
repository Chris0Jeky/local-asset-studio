"""Sort finished .safetensors downloads into the right ComfyUI model folder by reading their header.

Offline: it inspects the safetensors header (metadata plus tensor key shapes), never the network. Files are
moved, never overwritten; each move prints a receipt and a `models/library.json` entry stub. Standard library only.
"""
import argparse,hashlib,json,re,shutil,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
# One folder allow-list for the whole repo: drifting copies let a script write where the
# Models view cannot read, and three copies had already diverged (9, 9 and 11 entries).
from model_library import FOLDERS as _FOLDERS
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
 """Map a safetensors header to a ComfyUI model folder. LoRA evidence wins over every other shape."""
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
 return 'diffusion_models'

def plan(paths,folder=None):
 """Classify each candidate without moving anything; errors are carried, not raised."""
 items=[]
 for path in paths:
  item={'path':Path(path),'folder':folder,'error':None}
  if folder is None:
   try:item['folder']=classify(read_header(path))
   except (ValueError,OSError) as error:item['error']=str(error)
  items.append(item)
 return items

def sha256(path,chunk=8*1024**2):
 digest=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(chunk),b''):digest.update(block)
 return digest.hexdigest()

def safe_name(name):
 base=Path(str(name or '')).name
 cleaned=re.sub(r'_+','_',re.sub(r'[^A-Za-z0-9._-]+','_',base)).strip('._-')
 if not cleaned.endswith('.safetensors') or len(cleaned)>200:raise SystemExit('Cannot derive a safe filename from '+str(name))
 return cleaned

def destination(comfy_root,folder,name):
 if folder not in FOLDERS:raise SystemExit('Unsupported destination folder: '+str(folder))
 models=(Path(comfy_root)/'models').resolve()
 target=(models/folder/safe_name(name)).resolve()
 if not target.is_relative_to(models):raise SystemExit('Destination escapes the model library')
 return target

def slug(name):
 value=re.sub(r'[^a-z0-9]+','-',re.sub(r'\.safetensors$','',str(name).lower())).strip('-')
 if not value:raise SystemExit('Cannot derive an asset id from '+str(name))
 return value

def stub(folder,name,size,digest,source='',family='',trigger='',strength=None):
 return {'id':slug(name),'name':name,'file':f'{folder}/{name}','source':source,'url':source,'bytes':size,'sha256':digest,
         'license':'','terms':'TODO: record where this file came from and its licence before relying on it',
         'family':family,'trigger':trigger,'strength':strength or [1.0,1.0]}

def append_receipt(root,record):
 path=Path(root)/'.runtime/downloads/receipts.json';path.parent.mkdir(parents=True,exist_ok=True)
 existing=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
 if not isinstance(existing,list):raise SystemExit('receipts.json is not a list; inspect it before writing')
 existing.append(record)
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(existing,indent=2),encoding='utf-8',newline='\n');temp.replace(path)
 return record

def main(argv=None):
 parser=argparse.ArgumentParser(description='Move finished .safetensors downloads into the ComfyUI model folders.')
 parser.add_argument('--from',dest='source',type=Path,default=Path.home()/'Downloads')
 parser.add_argument('--dest-folder',choices=FOLDERS,help='skip header classification and use this folder')
 parser.add_argument('--name',help='rename a single file on the way in')
 parser.add_argument('--dry-run',action='store_true')
 args=parser.parse_args(argv)
 if not args.source.is_dir():raise SystemExit('No such folder: '+str(args.source))
 candidates=sorted(path for path in args.source.glob('*.safetensors') if path.is_file())
 if args.name and len(candidates)!=1:raise SystemExit('--name needs exactly one candidate file; found '+str(len(candidates)))
 if not candidates:print('Nothing to intake in '+str(args.source));return 0
 comfy_root=load_config()['comfy_root'];moved=0
 for item in plan(candidates,args.dest_folder):
  path=item['path']
  if item['error']:print('SKIP',path.name,'-',item['error']);continue
  target=destination(comfy_root,item['folder'],args.name or path.name)
  print(f'{path.name} -> {target}')
  if args.dry_run:continue
  if target.exists():print('SKIP',path.name,'- destination already exists; nothing was overwritten');continue
  size=path.stat().st_size;digest=sha256(path)
  target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():print('SKIP',path.name,'- destination appeared while hashing');continue
  shutil.move(str(path),str(target));moved+=1
  receipt={'file':target.name,'origin':str(path),'bytes':size,'sha256':digest,'expected_sha256':None,'verified':False,
           'folder':item['folder'],'licence':'TODO: record the source and licence','fetched':time.strftime('%Y-%m-%dT%H:%M:%S')}
  append_receipt(ROOT,receipt)
  print('RECEIPT',json.dumps(receipt,indent=2))
  print('LIBRARY STUB',json.dumps(stub(item['folder'],target.name,size,digest),indent=2))
 print(f'{len(candidates)} candidate(s); {moved} moved. A moved file is not a verified one: a browser download has no source checksum.')
 return 0

if __name__=='__main__':raise SystemExit(main())
