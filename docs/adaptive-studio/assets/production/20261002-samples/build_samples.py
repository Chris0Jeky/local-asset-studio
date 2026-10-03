#!/usr/bin/env python3
"""Build deterministic attachment-only controlled sample components and text evidence.
Runs from this directory with the four unaltered originals plus named sibling input packs.
No generation, background removal, retouching, alpha normalization or upscaling occurs.
"""
from pathlib import Path
import csv, hashlib, io, json, math, shutil, sys
from PIL import Image, ImageDraw, ImageFont, __version__ as PIL_VERSION
import numpy as np

ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent
PACK=ROOT/'package'
ASSET_REL=Path('docs/adaptive-studio/assets')
PROD_REL=ASSET_REL/'production/20261002-samples'
REPO=ROOT/'repo-tree'
PROD=REPO/PROD_REL
for p in [PACK/'originals',PACK/'inputs',PACK/'components',PACK/'thumbnails',PACK/'contact-sheets',PACK/'qa',PROD,REPO/ASSET_REL/'receipts']:
 p.mkdir(parents=True,exist_ok=True)
PROMPTS=json.loads((ROOT/'generation-prompts.json').read_text())
OUTPUTS=json.loads((ROOT/'output-map.json').read_text())
OMAP={x['asset_id']:x for x in OUTPUTS}
IDS=['sample-character-canon','sample-pose-pair','sample-outfit-study','sample-lighting-pair','sample-composition-pair','sample-sequence-strip']
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,x): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def font(size): return ImageFont.truetype(FONT,size)
def meta(rel,role=None):
 p=PACK/rel
 m={'relative_path':rel,'sha256':sha(p),'bytes':p.stat().st_size}
 try:
  with Image.open(p) as i:
   m.update(width=i.width,height=i.height,format=i.format.lower(),mode=i.mode,alpha=('A' in i.getbands()),duration_seconds=None,codec=None)
 except Exception: m.update(width=None,height=None,format=p.suffix[1:],mode=None,alpha=None,duration_seconds=None,codec=None)
 if role:m['role']=role
 return m
SOURCES={
 'portrait':WORK/'las-wave2/anchors/reference-identity--1024x1536--candidate-3.png',
 'pose':WORK/'las-firstwave-recovered/inbox/reference-pose--1024x1536--candidate-1.png',
 'light_left':WORK/'las-firstwave-recovered/inbox/reference-lighting--1254x1254--candidate-2.png',
 'composition':WORK/'las-firstwave-recovered/inbox/reference-composition--1254x1254--candidate-2.png',
 'outfit_reference':WORK/'las-wave2/originals/reference-outfit--1024x1536--candidate-1.png',
 'background_reference':WORK/'las-firstwave-recovered/inbox/reference-background--1254x1254--candidate-1.png',
}
ORIGINALS={x['asset_id']:ROOT/'originals'/x['filename'] for x in OUTPUTS}
PATH={}
for key,p in SOURCES.items():
 rel='inputs/'+p.name;shutil.copyfile(p,PACK/rel);PATH[key]=rel
for key,p in ORIGINALS.items():
 assert sha(p)==OMAP[key]['sha256'],f'Original changed: {p}'
 rel='originals/'+p.name;shutil.copyfile(p,PACK/rel);PATH[key]=rel
PATH['canon']=PATH['sample-character-canon'];PATH['outfit_blue']=PATH['sample-outfit-study'];PATH['light_right']=PATH['sample-lighting-pair'];PATH['sequence_sheet']=PATH['sample-sequence-strip']

TRANSFORMS=[]
def transformation(inp,out,operation,**kwargs):
 t={'operation':operation,'tool':f'Pillow {PIL_VERSION}','input_relative_path':inp,'input_sha256':sha(PACK/inp),'output_relative_path':out,'output_sha256':sha(PACK/out),'from_dimensions':list(Image.open(PACK/inp).size),'to_dimensions':list(Image.open(PACK/out).size),'upscale':False,**kwargs}
 TRANSFORMS.append(t);return t

# Exact source alpha retained; hidden RGB is replaced with black everywhere.
a=Image.open(PACK/PATH['canon']).getchannel('A')
i=Image.new('RGBA',a.size,(0,0,0,0));i.putalpha(a)
PATH['silhouette']='components/sample-character-canon--silhouette--1024x1536.png';i.save(PACK/PATH['silhouette'])
transformation(PATH['canon'],PATH['silhouette'],'Set RGB to (0,0,0); copy exact alpha channel byte-for-byte',alpha_normalized=False,alpha_threshold=None,crop=False,resampling=None)

BOX=(170,125,1194,1149)
PATH['composition_crop']='components/sample-composition-pair--crop--1024x1024.png'
Image.open(PACK/PATH['composition']).crop(BOX).save(PACK/PATH['composition_crop'])
transformation(PATH['composition'],PATH['composition_crop'],'Deterministic pixel crop only',crop_box=list(BOX),coordinate_convention='[left, top, right, bottom), origin upper-left; right/bottom exclusive',resampling=None,claim='Tighter camera framing by crop; no regenerated viewpoint or model test')

# Uniform safe inner panel boxes observed from the white cross and boundary pixels.
PANEL_BOXES=[(0,0,621,621),(633,0,1254,621),(0,633,621,1254),(633,633,1254,1254)]
for n,box in enumerate(PANEL_BOXES,1):
 k=f'panel_{n}';rel=f'components/sample-sequence-strip--panel-{n:02d}--621x621.png';PATH[k]=rel
 Image.open(PACK/PATH['sequence_sheet']).crop(box).save(PACK/rel)
 transformation(PATH['sequence_sheet'],rel,'Deterministic panel extraction and common-square inner trim',crop_box=list(box),coordinate_convention='[left, top, right, bottom), origin upper-left; right/bottom exclusive',resampling=None,observed_gutters={'solid_white_columns_inclusive':[622,631],'solid_white_rows_inclusive':[622,630],'trim_note':'Conservative 621px square interior avoids partial boundary lines at x621/x632 and y621/y631/y632. At most 1–2 additional image-edge pixels are omitted to keep common square panel dimensions.'})

THUMBS={}
for rel in sorted(set(PATH.values())):
 with Image.open(PACK/rel) as src:
  i=src.copy();i.thumbnail((320,320),Image.Resampling.LANCZOS)
  out='thumbnails/'+Path(rel).stem+'--longedge320.webp'
  q=85
  while True:
   b=io.BytesIO();i.save(b,format='WEBP',quality=q,method=6,exact=True)
   if len(b.getvalue())<=60*1024:break
   q-=5
   assert q>=30
  (PACK/out).write_bytes(b.getvalue());THUMBS[rel]=out
  transformation(rel,out,'Lazy/review thumbnail downscale and WebP encode',resampling='Lanczos',crop=False,aspect_ratio='Preserved to nearest integer dimensions',encoder={'format':'WebP','quality':q,'method':6,'lossless':False,'exact':True},byte_budget_inclusive=60*1024,metadata='No EXIF/ICC copied',purpose='Lazy candidate thumbnail; runtime integration remains unqualified')

# Proper two-dimensional checkerboards reveal alpha; these are QA views only.
def checker(size,colors,cell=32):
 w,h=size;xx,yy=np.meshgrid(np.arange(w)//cell,np.arange(h)//cell);a=np.empty((h,w,4),dtype=np.uint8)
 for n,c in enumerate(colors):a[(xx+yy)%2==n]=(*c,255)
 return Image.fromarray(a,'RGBA')
def flatten(i,dark=False):
 if 'A' in i.getbands():
  colors=[(26,31,42),(64,72,88)] if dark else [(245,245,245),(204,208,214)]
  return Image.alpha_composite(checker(i.size,colors),i.convert('RGBA')).convert('RGB')
 return i.convert('RGB')
QA_ALPHA={}
for key in ['canon','outfit_blue']:
 src=Image.open(PACK/PATH[key]);alpha=np.asarray(src.getchannel('A'))
 counts={str(x):int((alpha==x).sum()) for x in [0,1,127,128,200,253,254,255]}
 QA_ALPHA[key]={'source_relative_path':PATH[key],'minimum':int(alpha.min()),'maximum':int(alpha.max()),'bbox_any_alpha':list(src.getchannel('A').getbbox()),'exact_counts':counts,'zero_alpha_fraction':float((alpha==0).mean()),'border_alpha_maximum':int(max(alpha[0].max(),alpha[-1].max(),alpha[:,0].max(),alpha[:,-1].max())),'note':'Real transparent background; subject interior predominantly alpha 253/255, no fully opaque pixels. Low-alpha fringe retained without cleanup or normalization.'}
 out=Image.new('RGB',(1040,830),'white');d=ImageDraw.Draw(out);d.text((16,10),key+' | actual alpha over light and dark checkers',font=font(20),fill='#222222')
 for n,dark in enumerate([False,True]):
  p=flatten(src,dark);p.thumbnail((512,768));out.paste(p,(8+520*n,48))
 rel='qa/'+Path(PATH[key]).stem+'--alpha-check.jpg';out.save(PACK/rel,quality=92,subsampling=0);PATH[key+'_alpha_check']=rel

ROLES={
 'sample-character-canon':[
  ('portrait','identity_portrait','Selected adult explorer identity portrait'),('canon','identity_full_body','New illustrative full-body canon, olive outfit'),('silhouette','silhouette','Exact-alpha black silhouette derived from full-body canon')],
 'sample-pose-pair':[
  ('canon','identity_source','Adult explorer full-body identity input'),('pose','pose_reference','Separate jointed mannequin geometry input')],
 'sample-outfit-study':[
  ('canon','outfit_a','Olive field jacket outfit'),('outfit_blue','outfit_b','Slate-blue work jacket and cream knit outfit')],
 'sample-lighting-pair':[
  ('light_left','lighting_a','Selected plaster study with upper-left light'),('light_right','lighting_b','Generated upper-right light variant')],
 'sample-composition-pair':[
  ('composition','wide_source','Selected three-mass composition source'),('composition_crop','tight_crop','1024px close crop retaining all three masses')],
 'sample-sequence-strip':[
  ('sequence_sheet','source_sheet','Unaltered four-panel storyboard sheet'),('panel_1','frame_01','Relaxed forward gaze'),('panel_2','frame_02','One hand adjusts the satchel strap'),('panel_3','frame_03','Looks toward the track'),('panel_4','frame_04','Returns to forward gaze')]
}
CAPTIONS={
 'sample-character-canon':'Illustrative adult character canon: portrait, full-body source and exact-alpha silhouette. Not a measured consistency result.',
 'sample-pose-pair':'Two separate example inputs: identity and mannequin pose. No pose-transfer output or model execution is shown.',
 'sample-outfit-study':'Illustrative clothing variation using the same adult character source. Approximate visual continuity, not a measured model capability.',
 'sample-lighting-pair':'Illustrative opposing light directions on an approximately consistent plaster study. Geometry is not pixel-registered.',
 'sample-composition-pair':'One source and a deterministic tighter crop. The view was cropped, not regenerated or moved in 3D.',
 'sample-sequence-strip':'Four extracted illustrative storyboard stills with minor visible continuity drift. Not a temporal-consistency benchmark or generated video.'
}
CONCERNS={
 'sample-character-canon':['Full body and all limbs remain inside 1024x1536 canvas; facial hair/eye/scar features follow the selected portrait closely, subject to illustration-level variation.','Both feet are fully visible but the rightmost boot has only about 15px bottom clearance in the source.','Real alpha is present; maximum alpha 254 and interior mostly 253 leaves slight global translucency and faint low-alpha fringe. Exact alpha is deliberately retained in silhouette.'],
 'sample-pose-pair':['Inputs are deliberately different poses and distinct source roles. No transfer was executed.','Mannequin hands/feet remain visible; it is an illustrative jointed figure, not a validated anatomical skeleton.','The identity input inherits the canon alpha caveat.'],
 'sample-outfit-study':['Face, hair silhouette, relaxed body stance and hand positions are close between source and edit; clothing differences are clear.','Hands appear plausible at source size; no skeleton or hand-accuracy measurement was performed.','The changed sleeves, boot tops, trouser shape and bag contour are expected wardrobe differences. Minor rendered face/hair details differ.','Both originals have genuine alpha but mostly alpha 253 interiors and low-alpha fringe; light/dark checker composites are included.'],
 'sample-lighting-pair':['Upper-left versus upper-right illumination and opposing cast shadows read clearly.','Head silhouette, facial planes, wall texture and shadow form show small deviations; not an exact registered light-only edit.','Both remain 1254x1254; no digital mirror or registered comparison is claimed.'],
 'sample-composition-pair':['Chosen crop [170,125,1194,1149) is pixel-exact at 1024x1024; it replaced the initial proposed 800px crop after visual comparison.','A useful amount of the dominant block, the complete middle cube and the distant slab remain; the left edge deliberately clips the foreground block. The 800px proposal left only a narrow strip and was rejected for weaker balance.','The 1024px square target is met by existing source pixels without upscaling. No parallax, camera movement, regenerated viewpoint or measured model ability is implied.'],
 'sample-sequence-strip':['Source is 1254x1254, below prompt target 2048x2048. Common-square extracted frames are 621x621, below the 1024px sample target.','Four actions read in row-major order and identity/outfit/environment remain recognizable.','Boot positions, stance/leg contours, shoulder/bag edges and hair change slightly; canopy/column/rail and foliage details shift. Fixed-camera, exact foot placement and pixel registration were not achieved.','Facial scar/eye details are not reliably resolvable at frame size. No temporal or identity capability benchmark is supported.','White gutters and boundary pixels are excluded by the documented crop boxes; whole sheet retained.']
}
RECOMMEND={x:'usable illustrative source set with disclosed limitations' for x in IDS}
RECOMMEND['sample-composition-pair']='recommended deliberate close crop preserving all three masses'
RECOMMEND['sample-sequence-strip']='usable illustrative storyboard; does not meet requested size or exact-continuity targets'

CONTACTS={}
def make_contact(asset,entries):
 cols=3 if len(entries)>=3 else 2;rows=math.ceil(len(entries)/cols);tilew=400;tileh=580 if asset in ['sample-character-canon','sample-pose-pair','sample-outfit-study'] else 440
 canvas=Image.new('RGB',(cols*tilew+32,rows*tileh+112),'#f4f5f7');d=ImageDraw.Draw(canvas)
 d.text((16,14),asset,font=font(24),fill='#1c2230');d.text((16,49),'Illustrative source components | actual pixels | no model qualification',font=font(16),fill='#495163')
 for idx,(key,role,label) in enumerate(entries):
  x=16+(idx%cols)*tilew;y=90+(idx//cols)*tileh
  img=flatten(Image.open(PACK/PATH[key]));img.thumbnail((tilew-24,tileh-74))
  canvas.paste(img,(x+(tilew-24-img.width)//2,y));d.text((x,y+tileh-62),role,font=font(18),fill='#1c2230')
  dims=Image.open(PACK/PATH[key]).size;d.text((x,y+tileh-35),f'{dims[0]} x {dims[1]} px',font=font(16),fill='#495163')
 rel='contact-sheets/'+asset+'.jpg';canvas.save(PACK/rel,quality=90,subsampling=0);CONTACTS[asset]=rel
for asset,entries in ROLES.items():make_contact(asset,entries)
# Six-sample contact sheet; panels are explicitly review graphics, never source assets.
canvas=Image.new('RGB',(1440,1230),'#f4f5f7');d=ImageDraw.Draw(canvas);d.text((20,18),'Local Asset Studio | six controlled illustrative sample sets',font=font(28),fill='#1c2230')
for idx,asset in enumerate(IDS):
 x=20+(idx%3)*473;y=75+(idx//3)*570
 im=Image.open(PACK/CONTACTS[asset]);im.thumbnail((450,510));canvas.paste(im,(x,y));d.text((x,y+520),asset.replace('sample-',''),font=font(21),fill='#1c2230')
OVERVIEW='contact-sheets/six-samples-overview.jpg';canvas.save(PACK/OVERVIEW,quality=90,subsampling=0)

# Input-reference declarations must be confirmed against actual generation calls.
INPUTS={
 'sample-character-canon':[('portrait','identity'),('outfit_reference','clothing_reference')],
 'sample-outfit-study':[('canon','edit_source')],
 'sample-lighting-pair':[('light_left','edit_source')],
 'sample-sequence-strip':[('canon','identity_outfit_reference'),('background_reference','environment_reference')]
}
CONFIRM=ROOT/'generation-input-confirmation.json'
confirmation=json.loads(CONFIRM.read_text()) if CONFIRM.exists() else {'status':'awaiting root confirmation of actual tool input files'}
GEN={}
for asset,entries in INPUTS.items():
 o=OMAP[asset];text=PROMPTS[o['prompt_key']]
 GEN[asset]={'method':'reference-conditioned generation' if asset in ['sample-character-canon','sample-sequence-strip'] else 'reference-conditioned edit','provider':'OpenAI image_gen.imagegen (dot-run)','tool_action':'image_gen.imagegen','reported_model':None,'reported_seed':None,'provider_job_id':None,'output_id':o['output_id'],'output_id_kind':'Local dot tool output handle; not a provider job ID','produced_at':None,'prompt_record':{'relative_path':'production/20261002-samples/generation-prompts.json','relative_path_base':'docs/adaptive-studio/assets (repository asset root)','json_key':o['prompt_key'],'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),'hash_scope':'Exact prompt string encoded as UTF-8, no added newline'},'input_anchors':[dict(asset_role=role,**meta(PATH[key])) for key,role in entries],'input_evidence':confirmation}

MANIFEST={'schema':'studio.controlled-samples.manifest/v1-proposed','scope':'Six illustrative source sets; no actual model route execution receipt','included_sample_ids':IDS,'excluded':[{'asset_id':'sample-repair-pair','reason':'Deferred; requires actual repair route execution evidence. Concept artwork is not such evidence.'}],'binary_path_base':'Root after extracting all delivery parts together; all image paths are attachment-only, not committed to Git','repo_text_path_base':'Repository root','profile_evidence':json.loads((ROOT/'profile-evidence.json').read_text()),'source_gates':{'source_terms':'not-reviewed','runtime':'not-qualified','release':'not-selected'},'samples':[]}
SOURCE_MANIFEST=[]
for key,p in SOURCES.items():
 SOURCE_MANIFEST.append({'source_key':key,'copied_from_local_path':str(p.relative_to(WORK)),'file':meta(PATH[key]),'method':'Unaltered byte-for-byte copy of prior selected/generated reference','source_terms_review':'not-reviewed','prior_receipt_relative_path':f'receipts/{p.stem}.json','prior_receipt_scope':'Prior reference production and selection; this pack does not change its gates'})
for asset,entries in ROLES.items():
 roles=[]
 for key,role,label in entries:
  roles.append({'role':role,'label':label,'source_key':key,'file':meta(PATH[key]),'thumbnail':meta(THUMBS[PATH[key]]),'intended_use':'Separate selectable source input/component','target_1024px_note':'actual size retained; no upscale'})
 item={'asset_id':asset,'caption':CAPTIONS[asset],'comparison':roles,'contact_sheet':meta(CONTACTS[asset]),'visual_qa':{'status':'reviewed-with-limitations','reviewer':'dot independent sample-preparation review','recommendation':RECOMMEND[asset],'findings':CONCERNS[asset]},'art_selection':{'status':'selected','selected_by':'dot (owner-delegated root art selector)','evidence':'Root visually reviewed all six sample sets, individual lighting and storyboard sheets, alpha QA, and composition alternatives, then explicitly selected all six for illustrative source delivery on 2026-10-02. The chosen composition crop is [170,125,1194,1149).','scope':'Art selection only; source, rendition, runtime and release gates remain unchanged'},'rendition_review':{'status':'not-reviewed','technical_status':'mechanical checks pending validation script'},'runtime_review':{'status':'not-qualified'},'release_selection':{'status':'not-selected'}}
 if asset in ['sample-character-canon','sample-outfit-study']:
  keys=['canon'] if asset=='sample-character-canon' else ['canon','outfit_blue']
  item['alpha_qa']=[{'statistics':QA_ALPHA[k],'comparison_view':meta(PATH[k+'_alpha_check'])} for k in keys]
 MANIFEST['samples'].append(item)

# Each receipt enumerates its source-role components, upstream reference dependencies,
# thumbnails, QA images, contact sheet and every deterministic transformation involved.
for item in MANIFEST['samples']:
 asset=item['asset_id'];keys=[a for a,b,c in ROLES[asset]]
 relevant=set(PATH[k] for k in keys)
 gen_ids=[asset] if asset in GEN else []
 if asset in ['sample-pose-pair','sample-outfit-study','sample-sequence-strip'] and 'sample-character-canon' not in gen_ids:gen_ids.insert(0,'sample-character-canon')
 for g in gen_ids:
  for key,role in INPUTS[g]:relevant.add(PATH[key])
 relevant.update(THUMBS[x] for x in list(relevant) if x in THUMBS)
 relevant.add(CONTACTS[asset])
 if asset in ['sample-character-canon','sample-outfit-study']:
  relevant.add(PATH['canon_alpha_check'])
  if asset=='sample-outfit-study':relevant.add(PATH['outfit_blue_alpha_check'])
 trans=[t for t in TRANSFORMS if t['output_relative_path'] in relevant]
 production=GEN.get(asset,{'method':'curation of two separate existing sources' if asset=='sample-pose-pair' else 'curation and deterministic crop','provider':None,'tool_action':'Local file curation with Pillow deterministic derivatives','reported_model':None,'reported_seed':None,'provider_job_id':None,'output_id':None,'produced_at':None,'prompt_record':None,'input_anchors':[dict(asset_role=role,**meta(PATH[key])) for key,role,label in ROLES[asset] if key!='composition_crop']})
 receipt={'schema':'studio.theme-asset.receipt/v1-proposed','status':'candidate-produced','requested_asset_id':asset,'brief_revision':'catalog sample row + production/20261002-samples/profile-evidence.json','production':production,'upstream_generation_records':[GEN[g] for g in gen_ids if g!=asset],'source':{'item_id':None,'original_page':None,'creator_credit':None,'terms_evidence':None,'retrieved_at':None,'review_status':'not-reviewed'},'files':[meta(x) for x in sorted(relevant)],'source_roles':item['comparison'],'transformations':trans,'art_review':item['visual_qa'],'art_selection':item['art_selection'],'rendition_review':item['rendition_review'],'runtime_review':{'status':'not-qualified','app_commit':None,'device':None,'checks':[]},'release_selection':{'status':'not-selected','selected_by':None},'caption':CAPTIONS[asset],'limitations':CONCERNS[asset],'delivery_base':{'binary_storage':'PR delivery attachments only; binary files are not committed','archive_relative_path_base':'Root after extracting all delivery parts together','text_path_base':'docs/adaptive-studio/assets'},'unknowns':['Model build, seed, provider job ID and generation timestamps were not exposed; null values are deliberate.','Local filesystem time is not evidence of generation time.','Source/license terms have not been independently reviewed; no clearance is asserted.','No local model execution, measured capability, runtime/device qualification or release selection is established.']}
 write_json(REPO/ASSET_REL/'receipts'/f'{asset}--20261002.json',receipt)
write_json(PROD/'ROLE-MANIFEST.json',MANIFEST)
write_json(PROD/'SOURCE-MANIFEST.json',SOURCE_MANIFEST)
write_json(PROD/'GENERATION-PROVENANCE.json',GEN)
write_json(PROD/'DERIVATIVES.json',TRANSFORMS)
write_json(PROD/'ALPHA-QA.json',QA_ALPHA)
for name in ['generation-prompts.json','output-map.json','profile-evidence.json']:
 shutil.copyfile(ROOT/name,PROD/name)
# Minimal sample catalog snapshot preserves original planned method without claiming it was followed.
with (WORK/'las-wave3/repo-reference/catalog.csv').open() as f:rows=list(csv.DictReader(f))
selected=[r for r in rows if r['id'] in IDS]
write_json(PROD/'catalog-sample-rows.json',{'source':'docs/adaptive-studio/assets/catalog.csv (existing local reference snapshot)','rows':selected,'method_note':'Catalog is a plan. Actual receipt methods distinguish generation, curation and deterministic crop.'})
shutil.copyfile(ROOT/'build_samples.py',PROD/'build_samples.py')
print(json.dumps({'samples':len(IDS),'sources':len(SOURCES),'generated_originals':len(ORIGINALS),'deterministic_components':6,'thumbnails':len(THUMBS),'contact_sheets':7,'generation_input_confirmation':confirmation,'package_bytes':sum(p.stat().st_size for p in PACK.rglob('*') if p.is_file())},indent=2))
