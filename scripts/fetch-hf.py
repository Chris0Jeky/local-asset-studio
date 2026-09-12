"""Download one Hugging Face file into the configured ComfyUI model folder, verified against its LFS oid.

Prints a `.runtime/downloads/receipts.json` receipt and a `models/library.json` entry stub. Standard
library only; nothing is installed unless the SHA-256 matches what the repository tree advertises.
"""
import argparse,hashlib,json,re,time
from pathlib import Path,PurePosixPath
from urllib.error import HTTPError,URLError
from urllib.parse import quote
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
FOLDERS=('checkpoints','diffusion_models','text_encoders','vae','loras','controlnet','clip_vision','upscale_models','embeddings','latent_upscale_models','background_removal')
AGENT={'User-Agent':'LocalAssetStudio/1'}

def load_config(root=ROOT):
 path=root/'config/local.json'
 if not path.is_file():raise SystemExit('config/local.json is missing. Copy config/example.json and set comfy_root.')
 config=json.loads(path.read_text(encoding='utf-8'))
 if not config.get('comfy_root'):raise SystemExit('config/local.json has no comfy_root')
 return config

def resolve_url(repo,path,revision='main'):
 return f'https://huggingface.co/{repo}/resolve/{revision}/{quote(path,safe="/")}'

def tree_url(repo,path,revision='main'):
 parent=PurePosixPath(path).parent.as_posix()
 return f'https://huggingface.co/api/models/{repo}/tree/{revision}'+('' if parent=='.' else '/'+quote(parent,safe='/'))

def lfs_oid(entries,path):
 """Return (sha256, bytes) advertised for path by a /api/models/<repo>/tree listing."""
 for item in entries if isinstance(entries,list) else []:
  if item.get('path')==path:
   lfs=item.get('lfs') or {}
   digest=(lfs.get('oid') or lfs.get('sha256') or '').lower()
   return (digest if re.fullmatch('[a-f0-9]{64}',digest) else None),lfs.get('size') or item.get('size')
 return None,None

def safe_name(name):
 if not name or Path(name).name!=name or name.startswith('.') or len(name)>200 or not name.endswith('.safetensors'):
  raise SystemExit('Destination must be a plain .safetensors filename: '+str(name))
 return name

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

def stub(folder,name,repo,revision,url,size,digest,family='',trigger='',strength=None,terms=''):
 """A models/library.json entry; family/terms/trigger are recorded by hand, never guessed."""
 return {'id':slug(name),'name':name,'file':f'{folder}/{name}','repo':repo,'revision':revision,
         'source':f'https://huggingface.co/{repo}','url':url,'bytes':size,'sha256':digest,
         'license':'','terms':terms or 'TODO: record the licence and territory facts from the model card',
         'family':family,'trigger':trigger,'strength':strength or [1.0,1.0]}

def append_receipt(root,record):
 path=Path(root)/'.runtime/downloads/receipts.json';path.parent.mkdir(parents=True,exist_ok=True)
 existing=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
 if not isinstance(existing,list):raise SystemExit('receipts.json is not a list; inspect it before writing')
 existing.append(record)
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(existing,indent=2),encoding='utf-8',newline='\n');temp.replace(path)
 return record

def fetch_json(url,timeout=60):
 try:
  with urlopen(Request(url,headers=AGENT),timeout=timeout) as response:return json.loads(response.read().decode('utf-8'))
 except HTTPError as error:raise SystemExit(f'{url} returned HTTP {error.code}')
 except URLError as error:raise SystemExit(f'{url} is unreachable: {error.reason}')

def download(url,target,expected_size=None,expected_sha=None,headers=None,chunk=4*1024**2):
 """Stream to <target>.part, hash while writing, and only rename after the checksum matches."""
 if target.exists():raise SystemExit('Destination already exists; nothing downloaded: '+str(target))
 target.parent.mkdir(parents=True,exist_ok=True)
 part=target.with_suffix(target.suffix+'.part')
 if part.exists():raise SystemExit('A partial download is already in place; inspect it first: '+str(part))
 digest=hashlib.sha256();size=0;start=time.time()
 try:
  with urlopen(Request(url,headers=dict(AGENT,**(headers or {}))),timeout=120) as response,part.open('xb') as stream:
   while block:=response.read(chunk):
    stream.write(block);digest.update(block);size+=len(block)
 except HTTPError as error:part.unlink(missing_ok=True);raise SystemExit(f'Download failed with HTTP {error.code}')
 except URLError as error:part.unlink(missing_ok=True);raise SystemExit(f'Download failed: {error.reason}')
 if expected_size and size!=expected_size:raise SystemExit(f'Size mismatch ({size} != {expected_size}); partial file preserved: {part}')
 if expected_sha and digest.hexdigest()!=expected_sha:raise SystemExit('SHA-256 mismatch; partial file preserved: '+str(part))
 if target.exists():raise SystemExit('Destination appeared during the download; both files preserved')
 part.rename(target)
 return size,digest.hexdigest(),round(time.time()-start,1)

def main(argv=None):
 parser=argparse.ArgumentParser(description='Download one Hugging Face file into the ComfyUI model folders.')
 parser.add_argument('--repo',required=True,help='owner/name on huggingface.co')
 parser.add_argument('--path',required=True,help='file path inside the repository')
 parser.add_argument('--dest-folder',default='loras',choices=FOLDERS)
 parser.add_argument('--name',help='destination filename (default: the source basename)')
 parser.add_argument('--revision',default='main')
 parser.add_argument('--family',default='',help='model family recorded in the library stub')
 parser.add_argument('--trigger',default='',help='trigger word recorded in the library stub')
 parser.add_argument('--dry-run',action='store_true')
 args=parser.parse_args(argv)
 name=safe_name(args.name or PurePosixPath(args.path).name)
 target=destination(load_config()['comfy_root'],args.dest_folder,name)
 url=resolve_url(args.repo,args.path,args.revision)
 expected_sha,expected_size=lfs_oid(fetch_json(tree_url(args.repo,args.path,args.revision)),args.path)
 if expected_sha is None:print('WARNING: the repository tree advertises no LFS sha256 for this path; the download cannot be verified against the source.')
 print(json.dumps({'url':url,'destination':str(target),'expected_sha256':expected_sha,'expected_bytes':expected_size},indent=2))
 if args.dry_run:return 0
 size,digest,seconds=download(url,target,expected_size,expected_sha)
 receipt={'file':name,'repo':args.repo,'path':args.path,'url':url,'bytes':size,'sha256':digest,
          'expected_sha256':expected_sha,'verified':bool(expected_sha) and digest==expected_sha,'seconds':seconds,
          'licence':'TODO: read the model card','fetched':time.strftime('%Y-%m-%dT%H:%M:%S')}
 append_receipt(ROOT,receipt)
 print('RECEIPT',json.dumps(receipt,indent=2))
 print('LIBRARY STUB',json.dumps(stub(args.dest_folder,name,args.repo,args.revision,url,size,digest,args.family,args.trigger),indent=2))
 return 0

if __name__=='__main__':raise SystemExit(main())
