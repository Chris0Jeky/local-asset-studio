"""Verify, restore and index the local-only example media listed in examples/<folder>/MANIFEST.json.

The adult-lab JPEGs are deliberately gitignored: the Studio serves them from disk through
/api/examples/<folder>/<file>, and the manifest is the tracked record of what should be there.

  verify   every manifest entry is present locally and its sha256 matches
  restore  rebuild missing or corrupted files from the job PNGs (or from a git ref)
  index    write a gitignored examples/<folder>/index.html contact sheet from the manifest

verify and index are stdlib only. Restoring from a PNG re-encodes it with Pillow using the
manifest's encoding block (quality 85, optimize) and then re-verifies the sha256, so a
successful restore is byte-identical to the file the manifest describes.
"""
import argparse, hashlib, html, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDERS=('nsfw-lab','civitai-intake')

def _root(args):
    return Path(args.repo_root).resolve() if getattr(args,'repo_root',None) else ROOT

def manifest(root,folder):
    path=root/'examples'/folder/'MANIFEST.json'
    if not path.is_file(): raise SystemExit('No manifest: '+str(path))
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('version')!=1 or not isinstance(data.get('entries'),list): raise SystemExit('Unsupported manifest: '+str(path))
    return data

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def status(root,folder,entry):
    """'ok', 'missing' or 'corrupt' for one manifest entry."""
    path=root/'examples'/folder/entry['file']
    if not path.is_file(): return 'missing'
    return 'ok' if digest(path)==entry['sha256'] else 'corrupt'

def comfy_output(root):
    """ComfyUI output folder from config/local.json, or None when the Studio is not configured here."""
    path=root/'config/local.json'
    if not path.is_file(): return None
    root=json.loads(path.read_text(encoding='utf-8')).get('comfy_root')
    return Path(str(root).replace('\\','/'))/'output' if root else None

def from_ref(root,ref,folder,entry):
    """Exact bytes of the file as it was committed on another git ref."""
    result=subprocess.run(['git','show','%s:examples/%s/%s'%(ref,folder,entry['file'])],cwd=root,capture_output=True)
    if result.returncode!=0: return None,(result.stderr.decode('utf-8','replace').strip() or 'git show failed')
    return result.stdout,None

def from_png(output,encoding,entry):
    """Re-encode the job PNG with the manifest's encoding settings."""
    if output is None: return None,'no comfy_root in config/local.json (pass --comfy-output)'
    if not entry.get('source_png'): return None,'manifest records no source PNG'
    source=output/entry['source_png']
    if not source.is_file(): return None,'source PNG is gone: '+str(source)
    try:
        import io
        from PIL import Image
    except Exception as error: return None,'Pillow is needed to rebuild from a PNG (%s)'%error
    buffer=io.BytesIO()
    with Image.open(source) as image: image.convert('RGB').save(buffer,encoding.get('format','JPEG'),quality=encoding.get('quality',85),optimize=encoding.get('optimize',True))
    return buffer.getvalue(),None

def verify(args):
    root=_root(args);bad=0
    for folder in args.folders:
        data=manifest(root,folder);counts={'ok':0,'missing':0,'corrupt':0}
        for entry in data['entries']:
            state=status(root,folder,entry);counts[state]+=1
            if state!='ok': print('%-8s %s/%s'%(state.upper(),folder,entry['file']))
        print('%s: %d entries, %d ok, %d missing, %d corrupt'%(folder,len(data['entries']),counts['ok'],counts['missing'],counts['corrupt']))
        bad+=counts['missing']+counts['corrupt']
    if bad: print('Rebuild them with: python scripts/lab-media.py restore')
    return 1 if bad else 0

def restore(args):
    root=_root(args)
    output=Path(args.comfy_output) if args.comfy_output else comfy_output(root)
    failed=0
    for folder in args.folders:
        data=manifest(root,folder);encoding=data.get('encoding',{});done=skipped=broke=0
        for entry in data['entries']:
            if status(root,folder,entry)=='ok': skipped+=1;continue
            raw,error=from_ref(root,args.from_ref,folder,entry) if args.from_ref else from_png(output,encoding,entry)
            if raw is None: print('FAILED   %s/%s: %s'%(folder,entry['file'],error));broke+=1;continue
            if hashlib.sha256(raw).hexdigest()!=entry['sha256']: print('FAILED   %s/%s: rebuilt bytes do not match the manifest sha256'%(folder,entry['file']));broke+=1;continue
            path=root/'examples'/folder/entry['file'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            print('RESTORED %s/%s'%(folder,entry['file']));done+=1
        failed+=broke;print('%s: %d restored, %d already present, %d failed'%(folder,done,skipped,broke))
    return verify(args) or (1 if failed else 0)

PAGE="""<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;margin:24px;background:#141418;color:#e8e8ea}}
h1{{font-size:20px;margin:0 0 4px}}
p.lede{{color:#a6a6ad;margin:0 0 20px;max-width:70em}}
ul{{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px;padding:0;margin:0}}
li{{background:#1d1d23;border:1px solid #2c2c35;border-radius:8px;padding:10px}}
img{{width:100%;height:auto;border-radius:4px;background:#000;display:block}}
.gone{{padding:28px 10px;border:1px dashed #5a5a6a;border-radius:4px;color:#c8c8d0;font-size:12px;text-align:center}}
b{{display:block;margin:8px 0 4px}}
code{{font-size:11px;color:#9fd0ff;word-break:break-all}}
.note{{color:#c8c8d0;margin:6px 0 0}}
.meta{{color:#8a8a94;font-size:11px;margin-top:6px}}
</style>
<h1>{title}</h1>
<p class="lede">{lede}</p>
<ul>
{cards}
</ul>
"""
CARD="""<li>
<img src="{file}" alt="{id}" loading="lazy" onerror="this.outerHTML='<div class=&quot;gone&quot;>missing: {id}<br>job {job}<br>python scripts/lab-media.py restore</div>'">
<b>{id}</b>
<div class="note">{note}</div>
<div class="meta">job {job}<br>prompt {prompt}<br>{width}&times;{height}, {bytes} bytes<br>examples/{folder}/{file}<br>source PNG {png}</div>
</li>"""

def index(args):
    root=_root(args)
    for folder in args.folders:
        data=manifest(root,folder);cards=[]
        for entry in data['entries']:
            cards.append(CARD.format(folder=html.escape(folder),file=html.escape(entry['file']),id=html.escape(entry['id']),
                note=html.escape(entry.get('note') or ''),job=html.escape(entry.get('job_id') or 'unknown'),
                prompt=html.escape(entry.get('prompt_id') or 'unknown'),width=entry.get('width'),height=entry.get('height'),
                bytes=entry.get('bytes'),png=html.escape(entry.get('source_png') or 'unknown')))
        lede=('%d images. The files themselves are local-only and gitignored; this page and the JPEGs beside it are '
              'never committed. Missing tiles show the restore command. Generated is not accepted art and not licence clearance.'%len(data['entries']))
        page=PAGE.format(title=html.escape('%s — local example media'%folder),lede=html.escape(lede),cards='\n'.join(cards))
        path=root/'examples'/folder/'index.html';path.write_text(page,encoding='utf-8',newline='\n')
        print('wrote %s (%d entries)'%(path,len(data['entries'])))
    return 0

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command',choices=('verify','restore','index'))
    parser.add_argument('--folder',action='append',choices=FOLDERS,help='default: both lab folders')
    parser.add_argument('--from-ref',help='restore exact bytes from a git ref instead of the job PNGs')
    parser.add_argument('--comfy-output',help='ComfyUI output folder; default comes from config/local.json')
    parser.add_argument('--repo-root',help='repository root holding examples/<folder>/MANIFEST.json; default is this checkout')
    args=parser.parse_args(argv)
    args.folders=args.folder or list(FOLDERS)
    return {'verify':verify,'restore':restore,'index':index}[args.command](args)

if __name__=='__main__': sys.exit(main())
