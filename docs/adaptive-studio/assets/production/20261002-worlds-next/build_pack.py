"""Build auditable source-art packs; never modifies the planning inventory or app."""
from PIL import Image, ImageDraw, ImageFont, features
from pathlib import Path
import hashlib, json, shutil, csv

B=Path(__file__).resolve().parent
M=B/'repo-text/docs/adaptive-studio/assets/production/20261002-worlds-next'
REF='4ef2d9742084c7f506ef0df413021c129fd76dbe'
PREPARED='2026-10-02T15:40:40Z'  # Trusted clock tool observation; not a generation timestamp.
PROMPTS=json.loads((B/'prompts.json').read_text())
PROFILES=json.loads((B/'reference/profiles.json').read_text())
CATALOG=list(csv.DictReader((B/'reference/catalog.csv').read_text().splitlines()))
HANDLES={
 'arcade':{'master':'exec-d1c0a268-8fa9-486c-8851-7d59dec56ece','quiet':'exec-668bc162-f9c3-4f04-97e6-570929364e18','wall':'exec-2f7263eb-80f9-48ec-a1c7-f5ac6b654a1d'},
 'sakura':{'master':'exec-fff47e83-02da-489d-aa6b-aebaf724be36','quiet':'exec-92ebac81-37ae-4e46-8208-f44e7ac5ca5b','wall':'exec-ca8b8011-69b6-499f-9171-a40d3b5d47f6'}
}
CONFIG={
 'arcade':{'title':'ARCADE / Indigo repair workshop','hero':[2,130,1670,825],'heading':[.08,.16,.42,.62],'focal':[.78,.54],'wallzone':[.10,.10,.84,.73],'accent':'#72ddeb','description':'Two original unbranded arcade cabinets with cyan grid horizons, dark indigo walls and a compact repair bench.','quiet_note':'Same-room daylight alternative; strong diagonal sun/shadow bands cross the left wall. The requested diffuse light and low-contrast heading zone are not fully met. Use a separate solid heading surface pending real-slot review.','caveats':['The low-detail heading proposal spans 34% of source width, not the requested 60%; plants, shelving and cabinets begin near x .43.','Strongly lit quiet alternative is not a low-contrast header.','Wall seams cross the nominal central 70%; they are subtle in this dark source but not absent.','Full 12% overscan is not met: right workbench and lower furniture approach or intersect canvas edges.'],'portrait':[931,0,1636.75,941],'portrait_note':'Keeps both cabinet identities and front stool while trimming much of the repair bench; no left heading zone remains.'},
 'sakura':{'title':'SAKURA / Blossom courtyard studio','hero':[2,100,1670,795],'heading':[.16,.13,.49,.48],'focal':[.78,.65],'wallzone':[.12,.10,.79,.82],'accent':'#dfa1b3','description':'Plum-grey plaster, dark timber, a blank-paper drawing desk and a wet blossom courtyard.','quiet_note':'Subtle brighter daylight edit with the same main furniture and architecture. Fine texture and reflected light differ; no pixel-identity or runtime crossfade claim.','caveats':['The conservative heading proposal spans 33% of source width, not the requested 60%; left blossoms, texture and right vase/desk intrude beyond it.','The wall has visible tactile plaster texture and daylight falloff; real controls may require a solid or translucent surface.','Full 12% overscan is not met: blossoms, right desktop and foreground furniture are intentionally cropped.'],'portrait':[936,0,1641.75,941],'portrait_note':'Keeps pen cup, blank paper, chair and courtyard/blossoms, while deliberately losing most quiet wall and part of the desktop.'}
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
font=lambda n:ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',n)

for world,cfg in CONFIG.items():
 P=B/'delivery'/f'{world}-source-art-20261002'
 for p in [P/'originals',P/'masters',P/'renditions',P/'review',P/'metadata',M/world]:p.mkdir(parents=True,exist_ok=True)
 def obj(p):
  im=Image.open(p);im.load()
  return {'relative_path':str(p.relative_to(P)),'sha256':sha(p),'bytes':p.stat().st_size,'width':im.width,'height':im.height,'format':im.format,'mode':im.mode,'duration_seconds':None,'codec':None}
 def write(name,v):
  text=json.dumps(v,indent=2,ensure_ascii=False)+'\n' if not isinstance(v,str) else v
  for dest in [M/world/name,P/'metadata'/name]:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
 images={};outputs={};trans=[]
 for key in ['master','quiet','wall']:
  src=B/'originals'/f'{world}-{key}--candidate-1.png';dst=P/'originals'/src.name;shutil.copyfile(src,dst)
  images[key]=Image.open(dst).convert('RGB');outputs[f'{world}-{key}']=[obj(dst)]
 scene=[0,.25,1672,940.75];hero=cfg['hero'];card=[731,0,1672,941]
 def derive(asset,key,size,box,variant,budget=None,lossless=False):
  inp=P/'originals'/f'{world}-{key}--candidate-1.png'
  if lossless:
   assert all(int(x)==x for x in box)
   im=images[key].crop(tuple(box));assert im.size==tuple(size)
   dest=P/'masters'/f'{asset}--{size[0]}x{size[1]}--{variant}.png';im.save(dest,optimize=True)
   enc={'format':'PNG','lossless':True,'optimize':True,'quality':None}
  else:
   sx=size[0]/(box[2]-box[0]);sy=size[1]/(box[3]-box[1]);assert abs(sx-sy)<1e-10 and sx<=1
   im=images[key].resize(tuple(size),Image.Resampling.LANCZOS,box=tuple(box))
   dest=P/'renditions'/f'{asset}--{size[0]}x{size[1]}--{variant}.webp'
   for q in [88,85,82,80,78,75,72,68,64,60]:
    im.save(dest,format='WEBP',quality=q,method=6)
    if dest.stat().st_size<=budget:break
   assert dest.stat().st_size<=budget
   enc={'format':'WebP','lossless':False,'quality':q,'method':6}
  entry=obj(dest);entry['budget_bytes']=budget;entry['budget_pass']=None if budget is None else entry['bytes']<=budget
  outputs.setdefault(asset,[]).append(entry)
  trans.append({'asset_id':asset,'input_path':str(inp.relative_to(P)),'input_sha256':sha(inp),'output_path':entry['relative_path'],'output_sha256':entry['sha256'],'source_canvas':list(images[key].size),'crop_box_xyxy':box,'crop_coordinates':'Original pixel edges; right and bottom exclusive. Fractional edges preserve exact aspect ratio in a single resampling operation.','output_dimensions':size,'operation':'integer crop without resampling' if lossless else 'single crop-and-downsample directly from original','resample':None if lossless else 'Pillow LANCZOS','encoding':enc,'upscaled':False,'distorted':False})
 for key in ['master','quiet']:
  for sz in [[1280,720],[960,540]]:derive(f'{world}-{key}',key,sz,scene,'preview',300*1024)
 derive(f'{world}-hero','master',[1668,695],hero,'native-wide-crop',lossless=True)
 derive(f'{world}-hero','master',[960,400],hero,'wide',250*1024)
 for sz in [[1200,800],[600,400]]:derive(f'{world}-wall','wall',sz,[0,0,1536,1024],'panel',180*1024)
 for sz,budget in [([1280,720],220*1024),([640,360],90*1024)]:derive(f'{world}-poster','master',sz,scene,'fallback',budget)
 derive(f'{world}-card','master',[941,941],card,'native-square-crop',lossless=True)
 for sz,budget in [([512,512],80*1024),([256,256],30*1024)]:derive(f'{world}-card','master',sz,card,'picker',budget)
 reg=json.loads((B/'qa'/f'{world}-quiet-registration.json').read_text())
 if world=='arcade':
  reg['interpretation']='Most sampled structural points match at 0 or 1 pixel. The 41px screen-edge template has a 7.2801px best-match offset along a similar contour; this is local correspondence uncertainty, not proof of a camera shift. Keep the raw result. Larger-patch diagnostics below and visual review support same-room still use only.'
 else:reg['interpretation']='Sampled offsets are 0 to 1.4142 pixels. Architecture and furniture read as the same scene, with local relighting/detail changes. This supports a still alternative, not a pixel-exact crossfade claim.'
 write('QUIET-REGISTRATION.json',reg)
 for kind in ['quiet-landmarks.jpg','quiet-edge-overlay.jpg']:
  shutil.copyfile(B/'qa'/f'{world}-{kind}',P/'review'/f'{world}-{kind}')
 if world=='arcade':shutil.copyfile(B/'qa/arcade-screen-detail.jpg',P/'review/arcade-screen-detail.jpg')
 # Review annotation only; never changes source or rendered assets.
 im=images['master'].copy();d=ImageDraw.Draw(im);x0,y0,x1,y1=cfg['heading'];rect=[round(x0*1672),round(y0*941),round(x1*1672),round(y1*941)]
 d.rectangle(rect,outline=cfg['accent'],width=4)
 d.text((rect[0]+10,rect[1]+9),'Proposed heading zone only',font=font(19),fill='white',stroke_width=2,stroke_fill='#252329')
 d.rectangle(hero,outline='#ffd761',width=3);d.text((18,hero[1]+8),'Native hero crop 1668 x 695',font=font(20),fill='#ffe580',stroke_width=2,stroke_fill='#252329')
 fx,fy=cfg['focal'];x=fx*1672;y=fy*941;d.ellipse([x-12,y-12,x+12,y+12],outline='#ff90dc',width=4)
 im.thumbnail((1254,706),Image.Resampling.LANCZOS);im.save(P/'review'/f'{world}-composition.jpg',quality=92)
 sheet=Image.new('RGB',(1280,1240),'#f3f1ed');d=ImageDraw.Draw(sheet)
 d.text((32,18),cfg['title'],font=font(27),fill='#272732')
 d.text((32,59),'Six source-art IDs / originals + deterministic crops / runtime not qualified',font=font(18),fill='#62626b')
 items=[('master','Native 1672 x 941',images['master']),('quiet','Native 1672 x 941 / same-room daylight',images['quiet']),('wall','Native 1536 x 1024 / panel adaptation',images['wall']),('hero','Exact master crop / native 1668 x 695',Image.open(P/'masters'/f'{world}-hero--1668x695--native-wide-crop.png')),('poster','Exact master / 1280 x 720 and 640 x 360',Image.open(P/'renditions'/f'{world}-poster--1280x720--fallback.webp')),('card','Exact master crop / 512 and 256; 96px check',Image.open(P/'renditions'/f'{world}-card--512x512--picker.webp'))]
 for i,(key,subtitle,im) in enumerate(items):
  x=32+(i%2)*624;y=107+(i//2)*360;d.text((x,y),f'{world}-{key}',font=font(21),fill='#292732');d.text((x,y+29),subtitle,font=font(15),fill='#62626b')
  if key=='card':
   sheet.paste(im.resize((260,260),Image.Resampling.LANCZOS),(x,y+59));sheet.paste(im.resize((96,96),Image.Resampling.LANCZOS),(x+291,y+59));d.text((x+291,y+163),'96 px',font=font(15),fill='#62626b')
  else:
   tile=im.copy();tile.thumbnail((590,288),Image.Resampling.LANCZOS);sheet.paste(tile,(x,y+59))
 d.text((32,1190),'Targets short: native 4K, 1920 x 800 hero and 1024px card master. No upscaling.',font=font(18),fill='#7a493b')
 sheet.save(P/'review'/f'{world}-contact-sheet.jpg',quality=92)
 shortfalls=[{'asset_id':f'{world}-{key}','requested':requested,'actual':actual,'reason':'Actual native provider dimensions; no upscaling.'} for key,requested,actual in [('master','3840x2160','1672x941'),('quiet','3840x2160','1672x941'),('wall','2400x1600','1536x1024'),('hero','3840x1600 lossless and 1920x800 encoded','1668x695 lossless crop and 960x400 encoded'),('card','1024x1024 master','941x941 lossless crop; 512/256 targets fulfilled')]]
 write('TRANSFORMATIONS.json',{'schema':'studio.theme-asset.transformations/v1','prepared_at':PREPARED,'reference_commit':REF,'software':{'Pillow':Image.__version__,'WebP_encoder':features.version('webp')},'transformations':trans,'unfulfilled_targets':shortfalls,'scope':'Deterministic local source-art derivatives; no runtime integration.'})
 prompt_subset={'world':world,'master':PROMPTS['masters'][world],'edits':[x for x in PROMPTS['edits'] if x['world']==world]}
 write('generation-prompts.json',prompt_subset)
 # Preserve the exact original combined prompt-record bytes as supplied.
 for dest in [M/'generation-prompts-original.json',P/'metadata/generation-prompts-original.json']:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(B/'prompts.json',dest)
 write('CROP-PLAN.json',{'coordinate_convention':'Normalized source-canvas regions; crops use original pixel edges, right/bottom exclusive.','source_dimensions':[1672,941],'focal_point':{'x':fx,'y':fy},'scene_and_poster_crop':scene,'scene_crop_note':'Remove 0.25 source pixel from each vertical edge for exact 16:9, then one isotropic LANCZOS downsample; original untouched.','hero_crop':hero,'hero_focal_point':[(fx*1672-hero[0])/1668,(fy*941-hero[1])/695],'card_crop':card,'heading_zone':{'box_xyxy':cfg['heading'],'status':'Conservative visual proposal; contrast, HTML controls and actual slots untested.'},'wall_control_zone':{'box_xyxy':cfg['wallzone'],'status':'Conservative visual proposal; central texture/seams remain.'},'portrait_plan':{'status':'Plan only; no portrait asset shipped or tested.','art_only_crop_3_by_4_xyxy':cfg['portrait'],'native_extent':[705.75,941],'proposed_small_output':[600,800],'composition':cfg['portrait_note'],'heading':'Place actual heading above the artwork on a solid theme surface; the art-only crop has no left heading zone.','390x844_note':'Use a bounded artwork region, not a full viewport cover. Actual slot needs testing.'},'quiet_note':cfg['quiet_note'],'caveats':cfg['caveats']+['Any CSS scrim or solid heading surface is a recommendation only, not tested contrast.']})
 write('FILE-INVENTORY.json',{'asset_outputs':outputs,'review_files':[obj(p) for p in sorted((P/'review').glob('*.jpg'))]})
 write('catalog-selected-rows.json',[r for r in CATALOG if r['id'] in outputs])
 write('profile-evidence.json',{'reference_commit':REF,'reference_url':f'https://github.com/Chris0Jeky/local-asset-studio/blob/{REF}/docs/adaptive-studio/assets/profiles.json','profiles':{k:PROFILES['profiles'][k] for k in ['scene','hero','wall','quiet','poster','card']}})
 masterfile=outputs[f'{world}-master'][0]
 for asset,files in outputs.items():
  key=asset.removeprefix(world+'-');generated=key in HANDLES[world];method='generate' if key=='master' else 'edit' if key in ['quiet','wall'] else 'derive'
  anchors=[] if key=='master' else [{'asset_id':f'{world}-master','relative_path':masterfile['relative_path'],'sha256':masterfile['sha256'],'role':'exact input image' if generated else 'exact deterministic source'}]
  prompt_pointer='generation-prompts.json#/master' if key=='master' else 'generation-prompts.json#/edits/'+str(0 if key=='quiet' else 1)+'/prompt' if generated else None
  notes=cfg['quiet_note'] if key=='quiet' else 'Selected as source art by the lead assistant after preview review, with native-size, crop and safe-zone caveats.'
  receipt={'schema':'studio.theme-asset.receipt/v1-proposed','status':'art-reviewed','requested_asset_id':asset,'brief_revision':REF,'production':{'method':method,'provider':'OpenAI' if generated else 'local deterministic image processing','tool_action':'image_gen.imagegen' if generated else 'Pillow crop/resize/WebP encode','execution_surface':'dot-run' if generated else 'dot cloud workspace','reported_model':None,'seed':None,'output_id':None,'produced_at':None,'prompt_record':prompt_pointer,'input_anchors':anchors,'orchestration_handle':HANDLES[world].get(key),'orchestration_handle_is_provider_job_id':False},'source':{'item_id':None,'original_page':None,'creator_credit':None,'terms_evidence':None,'retrieved_at':None,'review_status':'provenance-recorded; source/license clearance not asserted'},'files':files,'transformations':[x for x in trans if x['asset_id']==asset],'art_review':{'status':'source-art-selected-with-caveats','reviewer':'independent QA assistant; lead assistant visual selection','notes':notes,'selection_record':'Lead assistant reviewed both six-ID contact sheets and selected all twelve source-art IDs on 2026-10-02. This is not runtime or release selection.'},'rendition_review':{'status':'encoded-size-and-budget-checks-passed-with-target-shortfalls','checks':['Every listed image decodes at its recorded dimensions.','All 11 encoded variants meet individual profile budgets.','Crops preserve aspect ratio; no upscaling or nonuniform scaling.','Native source and large hero/card-master targets remain unmet as recorded.']},'runtime_review':{'status':'not-qualified','app_commit':None,'device':None,'checks':[]},'release_selection':{'status':'not-selected','selected_by':None},'unknowns':['Provider model/build, seed, provider output/job ID and generation timestamp were not exposed.','Source terms/license clearance is not asserted.','No actual slot, text contrast, accessibility, memory/loading, active inference or crossfade test was performed.']}
  write(f'receipts/{asset}--20261002.json',receipt)
 write('SOURCE-MANIFEST.json',{'schema':'studio.theme-asset.source-pack/v1','pack':world,'prepared_at':PREPARED,'requested_asset_ids':list(outputs),'source_count':3,'independent_generations':1,'reference_edits':2,'deterministic_derivative_ids':[f'{world}-{k}' for k in ['hero','poster','card']],'sources':[outputs[f'{world}-{k}'][0] for k in ['master','quiet','wall']],'input_confirmation':{f'{world}-{k}':{'input_id':f'{world}-master','input_sha256':masterfile['sha256'],'source':'Parent generation record: exact candidate-1 master supplied as image edit input.'} for k in ['quiet','wall']},'source_art_selection':{'status':'selected-with-caveats','selected_by':'lead assistant under user-delegated aesthetic choice','date':'2026-10-02','evidence':'Lead assistant viewed both six-ID contact sheets and selected all twelve source-art IDs.'},'runtime_qualified':False,'selected_for_release':False,'planning_files_modified':False})
 summary=f'''{cfg['title']}

Six logical asset IDs are prepared: master, quiet, wall, hero, poster and card.
Three unchanged original PNGs; two native lossless crops; eleven budget-checked WebP renditions.
All crops are from the exact recorded master or wall original. No upscaling or geometric distortion.

Native dimensions: scene and quiet 1672 x 941; wall 1536 x 1024.
Hero: 1668 x 695 native wide crop plus 960 x 400 WebP. The 1920 x 800 target is intentionally absent.
Card: 941 x 941 native square plus 512/256 WebP; 1024px master target is not met.

Quiet review: {cfg['quiet_note']}
Sampled registration: median {reg['summary']['median_shift_px']}px; maximum {reg['summary']['max_shift_px']}px over 20 local points.
Read QUIET-REGISTRATION.json for method, uncertainty and diagnostic details. No pixel-identity or actual crossfade acceptance.

Composition limits:
'''+''.join('- '+x+'\n' for x in cfg['caveats'])+'''
Acceptance boundaries: source-art selected by the lead assistant after contact-sheet review. Source/license clearance is separate and not asserted. All existing encoded outputs pass dimensions and per-file byte budgets, with larger target shortfalls recorded. No runtime qualification, release selection, pilot replacement, layer/loop/promo/audio work or planning inventory edits.

Review contact sheet includes a 96px card check. Hero/card native crops and all encodes retain exact source identity and checksums. Prompt bytes and local orchestration handles are retained; handles are not provider job IDs. Unknown provider model, seed and generation timestamps remain null.
'''
 write('README.txt',summary)
 print(world,json.dumps({k:[{'dimensions':[e['width'],e['height']],'bytes':e['bytes']} for e in v] for k,v in outputs.items()}))

M.mkdir(parents=True,exist_ok=True)
for script in ['build_pack.py','check_registration.py']:
 shutil.copyfile(B/script,M/script)
 for world in CONFIG:shutil.copyfile(B/script,B/'delivery'/f'{world}-source-art-20261002'/'metadata'/script)
