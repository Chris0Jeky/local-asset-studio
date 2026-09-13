"""Download one civitai model version into the configured ComfyUI model folder, verified by its listed SHA-256.

The API token is read ONLY from the environment variable CIVITAI_API_TOKEN: never from argv, never from
config, never printed, and never forwarded to a redirect target on another host. Prints a receipt and a
`models/library.json` entry stub. Standard library only.
"""
import argparse,hashlib,json,os,re,stat,sys,time
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler,Request,build_opener,urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
# One folder allow-list for the whole repo: drifting copies let a script write where the
# Models view cannot read, and three copies had already diverged (9, 9 and 11 entries).
from model_library import FOLDERS as _FOLDERS
FOLDERS=tuple(_FOLDERS)
AGENT={'User-Agent':'LocalAssetStudio/1'}
TOKEN_ENV='CIVITAI_API_TOKEN'
VERSION_API='https://civitai.com/api/v1/model-versions/'

class DropAuth(HTTPRedirectHandler):
 """civitai redirects downloads to a CDN host; the Authorization header must not travel with them."""
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  request=super().redirect_request(req,fp,code,msg,headers,newurl)
  if request is not None and urlparse(newurl).hostname!=urlparse(req.full_url).hostname:request.remove_header('Authorization')
  return request

def read_token(environ=None):
 value=(environ if environ is not None else os.environ).get(TOKEN_ENV,'').strip()
 if not value:
  raise SystemExit(f'{TOKEN_ENV} is not set. Create a personal API key at https://civitai.com/user/account and put it in '
                   f'that environment variable for this shell only. Do not pass it on the command line and do not write it '
                   f'into config/local.json. Public metadata can still be read with --dry-run.')
 return value

def load_config(root=ROOT):
 path=root/'config/local.json'
 if not path.is_file():raise SystemExit('config/local.json is missing. Copy config/example.json and set comfy_root.')
 config=json.loads(path.read_text(encoding='utf-8'))
 if not config.get('comfy_root'):raise SystemExit('config/local.json has no comfy_root')
 return config

def safe_name(name):
 """civitai filenames carry spaces and '(1)' suffixes; ComfyUI is happier with a plain basename."""
 base=Path(str(name or '')).name
 if not base.endswith('.safetensors'):raise SystemExit('Only .safetensors model files are installed automatically: '+str(name))
 cleaned=re.sub(r'_+','_',re.sub(r'[^A-Za-z0-9._-]+','_',base)).strip('._-')
 if not cleaned.endswith('.safetensors') or len(cleaned)>200:raise SystemExit('Cannot derive a safe filename from '+str(name))
 return cleaned

def destination(comfy_root,folder,name):
 if folder not in FOLDERS:raise SystemExit('Unsupported destination folder: '+str(folder))
 models=(Path(comfy_root)/'models').resolve()
 target=(models/folder/safe_name(name)).resolve()
 if not target.is_relative_to(models):raise SystemExit('Destination escapes the model library')
 return target

def pick_file(version,file_id=None):
 """Choose the file to download from a /api/v1/model-versions/<id> payload."""
 files=[item for item in (version.get('files') or []) if isinstance(item,dict)]
 if not files:raise SystemExit('This model version lists no files')
 if file_id is not None:
  chosen=[item for item in files if item.get('id')==file_id]
  if not chosen:raise SystemExit('No file with id %s in this version: %s'%(file_id,[item.get('id') for item in files]))
 else:
  models=[item for item in files if item.get('type')=='Model' and str(item.get('name','')).endswith('.safetensors')]
  chosen=[item for item in models if item.get('primary')] or models
  if not chosen:raise SystemExit('No primary safetensors file in this version; pass --file-id from the listing')
 item=chosen[0];size=item.get('sizeKB');digest=str((item.get('hashes') or {}).get('SHA256') or '').lower()
 return {'id':item.get('id'),'name':item.get('name'),'sha256':digest if re.fullmatch('[a-f0-9]{64}',digest) else None,
         'bytes':int(round(float(size)*1024)) if size else None,'url':item.get('downloadUrl') or ''}

def terms_note(version):
 """Repeat the listing's own permission flags; never soften or infer them."""
 model=version.get('model') or {}
 if 'allowCommercialUse' not in model:
  return (f'civitai version {version.get("id")} of model {version.get("modelId")}: the version payload carries no permission flags; '
          f'read https://civitai.com/models/{version.get("modelId")} (or /api/v1/models/{version.get("modelId")}) before any commercial use. Base model {version.get("baseModel")!r}.')
 allowed=model.get('allowCommercialUse') or []
 return (f'civitai listing for model {version.get("modelId")} version {version.get("id")}: allowCommercialUse '
         f'{", ".join(allowed) if allowed else "none listed"}; derivatives '
         f'{"allowed" if model.get("allowDerivatives") else "NOT allowed"}; different licence '
         f'{"allowed" if model.get("allowDifferentLicense") else "NOT allowed"}. Base model {version.get("baseModel")!r}. '
         f'Read the model page before any commercial use.')

def explain_http(status,body=''):
 text=str(body or '')[:400]
 if status==401:return f'civitai rejected the request (401). Check that {TOKEN_ENV} holds a current personal API key; its value is never printed here.'
 if status==403:
  if 'REGION' in text.upper():return 'civitai refused this download from your region (403 REGION_BLOCKED). Download it from the website instead and run scripts/intake-downloads.py.'
  return 'civitai refused the request (403). Some versions are early access or require accepting terms on the website first.'
 if status==404:return 'No such model version (404). Check the version id from the model page URL (modelVersionId=...).'
 if status==429:return 'civitai is rate limiting (429). Wait and try again; do not loop.'
 return f'civitai returned HTTP {status}. Nothing was installed.'

def fetch_version(version_id,token=None,timeout=60):
 headers=dict(AGENT,**({'Authorization':'Bearer '+token} if token else {}))
 try:
  with urlopen(Request(VERSION_API+str(version_id),headers=headers),timeout=timeout) as response:
   return json.loads(response.read().decode('utf-8'))
 except HTTPError as error:raise SystemExit(explain_http(error.code,error.read(400).decode('utf-8','replace')))
 except URLError as error:raise SystemExit(f'civitai is unreachable: {error.reason}')

def slug(name):
 value=re.sub(r'[^a-z0-9]+','-',re.sub(r'\.safetensors$','',str(name).lower())).strip('-')
 if not value:raise SystemExit('Cannot derive an asset id from '+str(name))
 return value

def stub(folder,name,version,chosen,family='',trigger='',strength=None):
 triggers=version.get('trainedWords') or []
 return {'id':slug(name),'name':name,'file':f'{folder}/{name}',
         'source':f'https://civitai.com/models/{version.get("modelId")}?modelVersionId={version.get("id")}',
         'url':f'https://civitai.com/api/download/models/{version.get("id")}','bytes':chosen['bytes'],
         'sha256':chosen['sha256'],'license':'','terms':terms_note(version),'family':family or str(version.get('baseModel') or ''),
         'trigger':trigger or (triggers[0] if triggers else ''),'strength':strength or [1.0,1.0]}

def append_receipt(root,record):
 path=Path(root)/'.runtime/downloads/receipts.json';path.parent.mkdir(parents=True,exist_ok=True)
 existing=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
 if not isinstance(existing,list):raise SystemExit('receipts.json is not a list; inspect it before writing')
 existing.append(record)
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(existing,indent=2),encoding='utf-8',newline='\n');temp.replace(path)
 return record

def _resume_partial(part,target,expected_size):
 if not part.exists() and not part.is_symlink():raise SystemExit(f'--resume requires an existing partial file: {part}')
 try:info=part.lstat()
 except OSError as error:raise SystemExit(f'Cannot inspect the partial download: {part} ({error})')
 if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or getattr(info,'st_nlink',1)!=1:
  raise SystemExit(f'Resume requires an unshared regular partial file: {part}')
 if part.resolve().parent!=target.parent.resolve():
  raise SystemExit(f'Partial download is outside the intended model directory: {part}')
 if expected_size is None:raise SystemExit('Cannot resume without the pinned file size')
 if info.st_size>expected_size:
  raise SystemExit(f'Partial download is larger than the pinned size ({info.st_size} > {expected_size}): {part}')
 digest=hashlib.sha256();size=0
 with part.open('rb') as stream:
  while block:=stream.read(4*1024**2):digest.update(block);size+=len(block)
 if size!=info.st_size:raise SystemExit(f'Partial download changed while it was being hashed: {part}')
 return size,digest

def _validate_resume_response(response,offset,expected_size):
 if getattr(response,'status',None)!=206:
  raise SystemExit(f'Resume server response must be HTTP 206, got {getattr(response,"status",None)}; partial file preserved')
 content_range=response.headers.get('Content-Range','')
 expected_range=f'bytes {offset}-{expected_size-1}/{expected_size}'
 if content_range!=expected_range:
  raise SystemExit(f'Resume Content-Range mismatch ({content_range!r} != {expected_range!r}); partial file preserved')
 try:content_length=int(response.headers.get('Content-Length',''))
 except (TypeError,ValueError):content_length=-1
 if content_length!=expected_size-offset:
  raise SystemExit(f'Resume Content-Length mismatch ({content_length} != {expected_size-offset}); partial file preserved')
 if response.headers.get('Content-Encoding','').strip().lower() not in ('','identity'):
  raise SystemExit('Resume requires identity content encoding; partial file preserved')

def download(url,target,token,expected_size=None,expected_sha=None,chunk=4*1024**2,resume=False,opener=None):
 if target.exists():raise SystemExit('Destination already exists; nothing downloaded: '+str(target))
 target.parent.mkdir(parents=True,exist_ok=True)
 part=target.with_suffix(target.suffix+'.part')
 if (part.exists() or part.is_symlink()) and not resume:raise SystemExit('A partial download is already in place; inspect it first: '+str(part))
 start=time.time()
 if resume:size,digest=_resume_partial(part,target,expected_size)
 else:size,digest=0,hashlib.sha256()
 if resume and size==expected_size:
  if not expected_sha:raise SystemExit('Cannot publish a complete partial without a pinned SHA-256; partial file preserved: '+str(part))
  actual=digest.hexdigest()
  if actual!=expected_sha:raise SystemExit('SHA-256 mismatch for complete partial; partial file preserved: '+str(part))
  if target.exists():raise SystemExit('Destination appeared during resume; both files preserved')
  part.rename(target)
  return size,actual,round(time.time()-start,1)
 headers=dict(AGENT,Authorization='Bearer '+token,**{'Accept-Encoding':'identity'})
 if resume:headers['Range']=f'bytes={size}-'
 opener=opener or build_opener(DropAuth())
 try:
  with opener.open(Request(url,headers=headers),timeout=120) as response:
   if resume:_validate_resume_response(response,size,expected_size)
   with part.open('ab' if resume else 'xb') as stream:
    while block:=response.read(chunk):
     stream.write(block);digest.update(block);size+=len(block)
 except HTTPError as error:raise SystemExit(explain_http(error.code,error.read(400).decode('utf-8','replace'))+' Partial file preserved: '+str(part))
 except URLError as error:raise SystemExit(f'Download failed: {error.reason}. Partial file preserved: {part}')
 if expected_size is not None and size!=expected_size:raise SystemExit(f'Size mismatch ({size} != {expected_size}); partial file preserved: {part}')
 if expected_sha and digest.hexdigest()!=expected_sha:raise SystemExit('SHA-256 mismatch; partial file preserved: '+str(part))
 if expected_sha is None:print('WARNING: this version lists no SHA-256; the download could not be verified against the source.')
 if target.exists():raise SystemExit('Destination appeared during the download; both files preserved')
 part.rename(target)
 return size,digest.hexdigest(),round(time.time()-start,1)

def main(argv=None):
 parser=argparse.ArgumentParser(description='Download one civitai model version. The API token comes from $'+TOKEN_ENV+' only.')
 parser.add_argument('--version-id',type=int,required=True,help='modelVersionId from the model page URL')
 parser.add_argument('--file-id',type=int,help='pick a specific file from the version listing')
 parser.add_argument('--dest-folder',default='loras',choices=FOLDERS)
 parser.add_argument('--name',help='destination filename (default: the sanitised civitai filename)')
 parser.add_argument('--family',default='');parser.add_argument('--trigger',default='')
 parser.add_argument('--dry-run',action='store_true',help='read the public metadata only; no token needed')
 parser.add_argument('--resume',action='store_true',help='resume an existing .part file after strict range validation; never starts a fresh transfer')
 args=parser.parse_args(argv)
 token=None if args.dry_run else read_token()
 version=fetch_version(args.version_id,token)
 chosen=pick_file(version,args.file_id)
 name=safe_name(args.name or chosen['name'])
 target=destination(load_config()['comfy_root'],args.dest_folder,name)
 print(json.dumps({'model':(version.get('model') or {}).get('name'),'version':version.get('name'),'file_id':chosen['id'],
                   'destination':str(target),'expected_sha256':chosen['sha256'],'expected_bytes':chosen['bytes'],
                   'terms':terms_note(version)},indent=2,ensure_ascii=False))
 if args.dry_run:return 0
 size,digest,seconds=download(chosen['url'] or f'https://civitai.com/api/download/models/{args.version_id}',target,token,chosen['bytes'],chosen['sha256'],resume=args.resume)
 receipt={'file':name,'source':f'https://civitai.com/models/{version.get("modelId")}?modelVersionId={version.get("id")}',
          'url':f'https://civitai.com/api/download/models/{version.get("id")}','bytes':size,'sha256':digest,
          'expected_sha256':chosen['sha256'],'verified':bool(chosen['sha256']) and digest==chosen['sha256'],
          'seconds':seconds,'licence':terms_note(version),'fetched':time.strftime('%Y-%m-%dT%H:%M:%S')}
 append_receipt(ROOT,receipt)
 print('RECEIPT',json.dumps(receipt,indent=2,ensure_ascii=False))
 print('LIBRARY STUB',json.dumps(stub(args.dest_folder,name,version,dict(chosen,bytes=size,sha256=digest),args.family,args.trigger),indent=2,ensure_ascii=False))
 return 0

if __name__=='__main__':raise SystemExit(main())
