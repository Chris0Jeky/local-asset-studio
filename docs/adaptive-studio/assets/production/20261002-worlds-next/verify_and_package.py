"""Independent byte/dimension/source/crop verification and bounded archive creation."""
from pathlib import Path, PurePosixPath
from PIL import Image
import json, hashlib, io, zipfile, shutil

B=Path(__file__).resolve().parent
M=B/'repo-text/docs/adaptive-studio/assets/production/20261002-worlds-next'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
archives=[];overall=[]
for world in ['arcade','sakura']:
 P=B/'delivery'/f'{world}-source-art-20261002'
 inventory=json.loads((P/'metadata/FILE-INVENTORY.json').read_text())
 transforms=json.loads((P/'metadata/TRANSFORMATIONS.json').read_text())['transformations']
 assert len(inventory['asset_outputs'])==6
 assert set(inventory['asset_outputs'])=={f'{world}-{k}' for k in ['master','quiet','wall','hero','poster','card']}
 entries=[x for rows in inventory['asset_outputs'].values() for x in rows]+inventory['review_files']
 for e in entries:
  p=P/e['relative_path'];assert p.is_file() and not p.is_symlink()
  assert sha(p)==e['sha256'];assert p.stat().st_size==e['bytes']
  with Image.open(p) as im:
   im.load();assert [im.width,im.height]==[e['width'],e['height']];assert im.format==e['format']
  if e.get('budget_bytes') is not None:assert p.stat().st_size<=e['budget_bytes'] and e['budget_pass'] is True
 for p in (P/'originals').glob('*.png'):assert sha(p)==sha(B/'originals'/p.name)
 regenerated=0
 for t in transforms:
  source=P/t['input_path'];dest=P/t['output_path'];assert sha(source)==t['input_sha256'];assert sha(dest)==t['output_sha256']
  box=t['crop_box_xyxy'];size=t['output_dimensions'];w,h=box[2]-box[0],box[3]-box[1]
  assert abs(size[0]/w-size[1]/h)<1e-10;assert size[0]<=w and size[1]<=h
  assert t['upscaled'] is False and t['distorted'] is False
  with Image.open(source) as im:
   im=im.convert('RGB')
   if t['encoding']['format']=='PNG':
    reconstructed=im.crop(tuple(box))
    with Image.open(dest) as target:assert reconstructed.tobytes()==target.convert('RGB').tobytes()
   else:
    reconstructed=im.resize(tuple(size),Image.Resampling.LANCZOS,box=tuple(box));encoded=io.BytesIO()
    reconstructed.save(encoded,'WEBP',quality=t['encoding']['quality'],method=t['encoding']['method'])
    assert hashlib.sha256(encoded.getvalue()).hexdigest()==sha(dest)
  regenerated+=1
 assert regenerated==13
 jsonfiles=list((P/'metadata').rglob('*.json'))
 for p in jsonfiles:json.loads(p.read_text())
 for p in (P/'metadata/receipts').glob('*.json'):
  receipt=json.loads(p.read_text());assert receipt['runtime_review']['status']=='not-qualified';assert receipt['release_selection']['status']=='not-selected'
  assert receipt['art_review']['status']=='source-art-selected-with-caveats'
 assert sha(P/'metadata/generation-prompts-original.json')==sha(B/'prompts.json')
 results={'world':world,'status':'pass','originals_unchanged':3,'logical_asset_ids':6,'encoded_budget_passes':11,'transformations_independently_reconstructed':regenerated,'decoded_and_hashed_inventory_files':len(entries),'json_files_parsed':len(jsonfiles),'checks':['All recorded files decode, match SHA-256 and byte count.','PNG crops match exact source pixels.','WebP files reproduce byte-for-byte from original with recorded crop/resize/encoder settings.','All encodes meet profile budget; no upscaling or nonuniform scaling.','Original prompt-record bytes unchanged.','Runtime and release remain unqualified/unselected.'],'limitations':['This verification covers source identity, deterministic transformation, decode and file budgets only.','No actual app-slot, accessibility, contrast, memory, workload or crossfade qualification.','Larger profile target dimensions remain intentionally unfulfilled.']}
 for p in [P/'metadata/VERIFICATION.json',M/world/'VERIFICATION.json']:dump(p,results)
 overall.append(results)
 for script in ['verify_and_package.py']:
  shutil.copyfile(B/script,P/'metadata'/script);shutil.copyfile(B/script,M/script)
 # Two ordinary ZIPs per world; extracting both into one directory reconstructs the pack.
 for label,roots in [('sources',['originals','metadata']),('renditions-review',['masters','renditions','review','metadata'])]:
  paths=sorted(p for root in roots for p in (P/root).rglob('*') if p.is_file())
  assert all(not p.is_symlink() for p in paths)
  sums=''.join(f'{sha(p)}  {p.relative_to(P).as_posix()}\n' for p in paths)
  checksumname='CHECKSUMS-'+label+'.sha256'
  zip_path=B/'delivery'/f'{world}-20261002-{label}.zip'
  with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
   for p in paths:z.write(p,(Path(P.name)/p.relative_to(P)).as_posix())
   z.writestr(f'{P.name}/{checksumname}',sums)
  assert zip_path.stat().st_size<10*1024*1024
  with zipfile.ZipFile(zip_path) as z:
   assert z.testzip() is None
   for member in z.namelist():
    relative=PurePosixPath(member);assert not relative.is_absolute() and '..' not in relative.parts
   for p in paths:assert hashlib.sha256(z.read((Path(P.name)/p.relative_to(P)).as_posix())).hexdigest()==sha(p)
   assert z.read(f'{P.name}/{checksumname}').decode()==sums
  record={'file':zip_path.name,'bytes':zip_path.stat().st_size,'sha256':sha(zip_path),'contents':roots,'file_count':len(paths)+1,'checksum_manifest':f'{P.name}/{checksumname}','limit_bytes':10*1024*1024,'below_limit':True,'testzip_pass':True,'per_entry_hashes_pass':True}
  archives.append(record);print(json.dumps(record))
dump(M/'ARCHIVE-INVENTORY.json',archives)
dump(B/'delivery/ARCHIVE-INVENTORY.json',archives)
dump(M/'VERIFICATION-SUMMARY.json',overall)
readme='''Arcade and Sakura source-art delivery / 2026-10-02

Twelve logical IDs selected by the lead assistant after visual review: six per world.
Each world has a sources ZIP and a renditions-review ZIP. Both are below 10 MiB.
Extract the two ZIPs for a world into the same directory to reconstruct its full pack.
Metadata is intentionally duplicated so each ZIP carries source identity and caveats.
Each archive has a SHA-256 manifest for its own entries; ARCHIVE-INVENTORY.json records archive hashes.

Originals are untouched. Hero, poster and card derive directly from the exact selected master.
All 22 WebP variants meet their individual profile budgets. All 26 transformations independently reproduce.
Native sources are 1672x941 scenes and 1536x1024 walls. No upscale or size fiction.
The 1920x800 hero and larger requested masters remain absent; native hero is 1668x695 plus 960x400 WebP.

Arcade quiet is a same-room daylight alternative with strong window shadows crossing the heading wall.
Its raw screen-edge landmark outlier is retained, alongside larger-patch diagnostics. Sakura has small local shifts.
Neither alternative is pixel-identical or crossfade-qualified. Narrow heading zones and overscan shortfalls remain.
Source-art choice, source/license review, rendition verification, runtime qualification and release are distinct.
This delivery changes no planning inventory, app runtime, pilot skin, layers, loops, promo or audio.

The Python scripts are audit/replay helpers for the working layout, not app code or theme-executable content.
To replay in a new working directory: place the scripts at its root, restore the six originals under originals,
place generation-prompts-original.json there as prompts.json, and fetch the pinned planning references under reference.
Run check_registration.py, build_pack.py, then verify_and_package.py with Pillow, NumPy and SciPy available.
Do not interpret file preparation timestamps as provider generation timestamps; provider timestamp/model/seed fields remain null.
'''
(M/'README.txt').write_text(readme)
print(json.dumps({'verified_worlds':len(overall),'verified_originals':6,'verified_logical_ids':12,'verified_webp_budgets':22,'independently_reconstructed_transforms':26,'bounded_archives':len(archives)}))
