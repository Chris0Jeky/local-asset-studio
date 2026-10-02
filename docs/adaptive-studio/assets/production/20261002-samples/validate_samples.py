#!/usr/bin/env python3
"""Offline mechanical verification for the controlled sample attachment bundle.
Usage: python validate_samples.py /path/to/extracted/bundle
This tests file facts and exact deterministic derivatives; it does not qualify art,
licenses, a model, an app route, a device, or release selection.
"""
import hashlib,json,sys
from pathlib import Path
from PIL import Image
import numpy as np
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent/'package'
prod=root/'docs/adaptive-studio/assets/production/20261002-samples'
receipts=root/'docs/adaptive-studio/assets/receipts'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=load(prod/'ROLE-MANIFEST.json');trans=load(prod/'DERIVATIVES.json');gens=load(prod/'GENERATION-PROVENANCE.json')
expected={'sample-character-canon','sample-pose-pair','sample-outfit-study','sample-lighting-pair','sample-composition-pair','sample-sequence-strip'}
assert set(manifest['included_sample_ids'])==expected
assert {x['asset_id'] for x in manifest['samples']}==expected
assert [x['asset_id'] for x in manifest['excluded']]==['sample-repair-pair']
checks=[];seen=set();thumbs=set();recipe_checks=0

def check_file(m):
 p=root/m['relative_path'];assert p.is_file(),p
 assert sha(p)==m['sha256'],p
 assert p.stat().st_size==m['bytes'],p
 if m.get('width'):
  with Image.open(p) as i:
   i.load();assert i.size==(m['width'],m['height']),p
   assert i.mode==m['mode'],p
   assert i.format.lower()==m['format'],p
 seen.add(m['relative_path'])
for m in load(prod/'FILE-INVENTORY.json')['files']:check_file(m)
for c in load(prod/'REVIEW-COMPOSITES.json'):
 check_file(c['output'])
 for f in c['inputs']:check_file(f)
 code=root/'docs/adaptive-studio/assets'/c['exact_layout_source']['relative_path']
 assert sha(code)==c['exact_layout_source']['sha256']
for item in manifest['samples']:
 assert item['art_selection']['status']=='selected'
 for r in item['comparison']:check_file(r['file']);check_file(r['thumbnail']);thumbs.add(r['thumbnail']['relative_path'])
 check_file(item['contact_sheet'])
for asset in expected:
 r=load(receipts/f'{asset}--20261002.json')
 assert r['requested_asset_id']==asset
 assert r['source']['review_status']=='not-reviewed'
 assert r['runtime_review']['status']=='not-qualified'
 assert r['release_selection']['status']=='not-selected'
 assert r['art_selection']['status']=='selected'
 for f in r['files']:check_file(f)
 for f in r['production']['input_anchors']:check_file(f)
for asset,g in gens.items():
 assert g['reported_model'] is None and g['reported_seed'] is None and g['produced_at'] is None and g['provider_job_id'] is None
 assert g['input_evidence']['status']=='confirmed'
 assert hashlib.sha256(g['prompt_record']['text'].encode()).hexdigest()==g['prompt_record']['sha256']
 for f in g['input_anchors']:check_file(f)
for t in trans:
 inp=root/t['input_relative_path'];out=root/t['output_relative_path']
 assert sha(inp)==t['input_sha256'] and sha(out)==t['output_sha256']
 a=Image.open(inp);b=Image.open(out);a.load();b.load()
 assert list(a.size)==t['from_dimensions'] and list(b.size)==t['to_dimensions']
 assert t['upscale'] is False
 assert b.width<=a.width and b.height<=a.height
 if 'crop_box' in t:
  assert np.array_equal(np.asarray(a.crop(t['crop_box'])),np.asarray(b));recipe_checks+=1
 elif t['operation'].startswith('Set RGB'):
  assert np.array_equal(np.asarray(a.getchannel('A')),np.asarray(b.getchannel('A')))
  assert not np.asarray(b)[:,:,:3].any();recipe_checks+=1
 else:
  assert max(b.size)==320 and out.stat().st_size<=61440 and b.format=='WEBP'
  assert ('A' in a.getbands())==('A' in b.getbands())
  thumbs.add(t['output_relative_path'])
  assert a.width*b.height-a.height*b.width in range(-a.height,a.height+1)
for p in (root/'thumbnails').glob('*.webp'):
 assert p.relative_to(root).as_posix() in thumbs
assert len(thumbs)==16 and recipe_checks==6
originals=load(prod/'output-map.json')
for m in originals:
 p=root/'originals'/m['filename'];assert sha(p)==m['sha256'] and p.stat().st_size==m['bytes']
 assert Image.open(p).size==(m['width'],m['height'])
assert len(list((root/'originals').glob('*.png')))==4
assert len(list((root/'components').glob('*.png')))==6
assert len(list((root/'inputs').glob('*.png')))==6
assert len(list((root/'contact-sheets').glob('*.jpg')))==7
assert len(list((root/'qa').glob('*.jpg')))==2
print(json.dumps({'status':'passed','scope':'Offline file integrity, decode, dimensions, budgets, roles, prompt/input provenance, exact crop/silhouette derivation and unchanged gates','sample_count':len(expected),'binary_files_checked':len(seen),'unaltered_generated_originals':4,'unaltered_reference_inputs':6,'exact_pixel_derivatives':recipe_checks,'thumbnails_checked':len(thumbs),'thumbnail_max_bytes':max((root/p).stat().st_size for p in thumbs),'contact_sheets':7,'alpha_qa_sheets':2,'source_terms':'not-reviewed','runtime':'not-qualified','release':'not-selected'},indent=2))
