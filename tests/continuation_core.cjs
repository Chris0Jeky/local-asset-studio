'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const C=require('../app/static/continuation-core.js');global.StudioContinuation=C;
const U=require('../app/static/studio-core.js');
const source={version:1,asset_id:'source-asset',sha256:'a'.repeat(64),positive:'An adult traveller at the station.',negative:'blur',prompt_origin:'submitted-output',prompt_role:'description',preset_id:'anima-portrait'};
const file='a'.repeat(32)+'_source.png';
const cap={version:1,consumes_source:true,operation:'image-to-image',prompt_role:'description',reference_count:1,template_sha256:'b'.repeat(64)};
const p={id:'refine',name:'Refine',positive:['4','text'],reference:['6','image'],continuation_capability:cap};
const claim=C.initial(source,p,'repair',file).claim;
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
test('source description is copied literally, not mixed with destination example',()=>{
  const out=C.initial(source,{...p,defaults:{positive:'Example witch',negative:'example tags'}},'repair',file);
  assert.equal(out.positive,source.positive);assert.equal(out.negative,source.negative);
});
test('instructions and motion never receive a misleading image caption',()=>{
  for(const [role,operation,intent]of [['instruction','instruction-edit','edit'],['motion','image-to-video','animate'],['none','upscale','repair']]){
    const out=C.initial(source,{...p,continuation_capability:{...cap,prompt_role:role,operation}},intent,file);assert.equal(out.positive,'');assert.equal(out.negative,'');
  }
});
test('old edit instructions and missing descriptions are not treated as captions',()=>{
  for(const item of [{...source,prompt_role:'instruction'},{...source,prompt_origin:'unavailable',positive:null}])assert.equal(C.initial(item,p,'repair',file).positive,'');
});
test('source-free routes, unknown capabilities, wrong intents and unprepared masks are rejected',()=>{
  for(const dest of [{...p,continuation_capability:null},{...p,continuation_capability:{...cap,consumes_source:false}},{...p,continuation_capability:{...cap,requires_mask:true}}])assert.throws(()=>C.initial(source,dest,'repair',file));
  assert.throws(()=>C.initial(source,p,'mesh',file));assert.throws(()=>C.initial(source,p,'repair','../source.png'));
});
test('bounded versioned envelope rejects unknown fields and malformed hashes',()=>{
  assert.deepEqual(C.normalize(claim),claim);
  for(const fields of [{version:true},{version:2},{command:'run now'},{source_sha256:'unknown'},{template_sha256:'b'.repeat(63)},{source_asset_id:42},{intent:'invent'}])assert.equal(C.normalize({...claim,...fields}),null);
});
const full=JSON.parse(fs.readFileSync(path.join(__dirname,'../presets/catalog.json'))).presets.find(p=>p.id==='krea-refine');
const graph=JSON.parse(fs.readFileSync(path.join(__dirname,'..',full.graph)));
full.defaults=Object.fromEntries(Object.entries(full).filter(([,value])=>Array.isArray(value)&&value.length===2&&graph[value[0]]&&typeof value[1]==='string').map(([key,value])=>[key,graph[value[0]].inputs[value[1]]]));
test('full8 then light touch restores current authored distill and schedule atomically',()=>{
  const before={...full.defaults,positive:source.positive,reference:file,seed:'9223372036854775800'};
  const eight=C.settings(full,full.variants[2].controls,before);assert.equal(eight.lora3,0);assert.equal(eight.steps,8);assert.equal(eight.denoise,.4);
  const light=C.settings(full,full.variants[0].controls,eight);assert.equal(light.lora3,.85);assert.equal(light.steps,4);assert.equal(light.denoise,.25);
  assert.equal(light.positive,source.positive);assert.equal(light.reference,file);assert.equal(light.seed,before.seed);assert.equal(before.steps,4);
});
test('same-preset examples cannot overwrite source or user-edited prompts',()=>{
  const out=C.settings(full,{positive:'Example witch',negative:'example',reference:'bad.png',denoise:.5},{positive:'My revised station portrait',negative:'Keep mine',reference:file});
  assert.equal(out.positive,'My revised station portrait');assert.equal(out.negative,'Keep mine');assert.equal(out.reference,file);
});
test('variant explanations show effective schedule not an implied full redraw',()=>{
  assert.match(C.variantHelp(full,full.variants[2]),/Denoise 0.4/);assert.match(C.variantHelp(full,full.variants[2]),/8 sampling/);assert.match(C.variantHelp(full,full.variants[2]),/Switches off adapter 3/);
  assert.doesNotMatch(C.variantHelp(full,full.variants[2]),/full-noise/);
});
test('actionable blockers distinguish missing source from missing wording',()=>{
  assert.deepEqual(C.blockers(claim,p,{positive:source.positive,reference:file},['source-asset']),[]);
  assert.match(C.blockers(claim,p,{positive:'',reference:file},['source-asset']).join(),/Describe/);
  assert.match(C.blockers(claim,p,{positive:'yes',reference:'other.png'},['source-asset']).join(),/Reference no longer holds the picture you chose/);
  assert.deepEqual(C.blockerItems(claim,p,{positive:'',reference:'other.png'},['source-asset']).map(i=>i.code),['source','wording']);
});
test('multi-input continuation cannot retain an authored last frame',()=>{
  const multi={...p,last_reference:['7','image'],last_reference_label:'Last frame',continuation_capability:{...cap,reference_count:2}};
  assert.match(C.blockers(claim,multi,{positive:source.positive,reference:file},['source-asset']).join(),/Last frame is empty/);
  assert.deepEqual(C.blockers(claim,multi,{positive:source.positive,reference:file,last_reference:'b'.repeat(32)+'_last.png'},['source-asset']),[]);
});
const boardCap={...cap,operation:'restyle',reference_count:4,source_input:'last_reference',board_min:1};
const board={id:'style-pose-nova',name:'Style + Pose (Nova)',family:'Nova',positive:['2','text'],reference_slots:[{role:'style',binding:['10','image']},{role:'style',binding:['30','image']},{role:'style',binding:['31','image']}],reference_board:{min:1},last_reference:['11','image'],last_reference_label:'Pose picture',continuation_capability:boardCap};
const styleFile='c'.repeat(32)+'_style.png';
test('restyle puts the source on the pose picture and needs one board picture',()=>{
  const prepared=C.initial(source,board,'restyle',file);assert.equal(prepared.claim.intent,'restyle');assert.equal(prepared.positive,source.positive);
  assert.equal(C.sourceInput(boardCap),'last_reference');assert.equal(C.sourceLabel(board),'Pose picture');
  const empty=[{role:'style',file:null},{role:'style',file:null},{role:'style',file:null}];
  assert.deepEqual(C.blockerItems(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],empty).map(i=>i.code),['board']);
  assert.match(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],empty).join(),/Picture 1/);
  const one=[{role:'style',file:styleFile},{role:'style',file:null},{role:'style',file:null}];
  assert.deepEqual(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],one),[]);
  assert.match(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:'other.png'},['source-asset'],one).join(),/Pose picture no longer holds/);
  assert.match(C.blockers(prepared.claim,board,{positive:source.positive,last_reference:file},['source-asset'],[{role:'style',file:styleFile,missing:true},{role:'style',file:null},{role:'style',file:null}]).join(),/board picture is missing/);
  assert.throws(()=>C.initial(source,board,'edit',file));assert.throws(()=>C.initial(source,p,'restyle',file));
  assert.deepEqual(C.destinations('restyle',[p,board,{...board,id:'other',name:'Other'}],source).map(x=>x.id),['style-pose-nova','other']);
  assert.match(C.guidance(board,source).join(' '),/pose picture/i);assert.doesNotMatch(C.guidance(board,source).join(' '),/Picture 1 only/);
  const keeps={...board,id:'restyle-wai',last_reference_label:'Picture to restyle',continuation_capability:{...boardCap,keeps_picture:true}};
  assert.match(C.guidance(keeps,source).join(' '),/Keeps this picture \(layout, pose, costume, colours/);assert.match(C.guidance(keeps,source).join(' '),/Style weight says \(0 = off\)/);assert.match(C.guidance(keeps,source).join(' '),/picture to restyle/);assert.match(C.guidance(keeps,source).join(' '),/face pass/);assert.doesNotMatch(C.guidance(keeps,source).join(' '),/Restyle a picture recipe/);
  assert.match(C.guidance(board,source).join(' '),/paints a new image/);assert.match(C.guidance(board,source).join(' '),/choose a Restyle a picture recipe/);
  assert.deepEqual(C.destinations('restyle',[p,board,keeps],source).map(x=>x.id),['restyle-wai','style-pose-nova']);
  assert.deepEqual(C.destinations('restyle',[board,{...keeps,family:'Other'}],{...source,preset_id:'style-pose-nova'}).map(x=>x.id),['restyle-wai','style-pose-nova'],'keeps_picture outranks the source family');
});
test('family matching never resurrects a text-only graph as a refinement',()=>{
  const same={...p,id:'same',family:'Anima'},different={...p,id:'different',family:'Krea'};
  const presets=[{id:'anima-portrait',name:'Source',family:'Anima'},{id:'new',name:'New',family:'Anima',continuation_capability:{...cap,consumes_source:false}},different,same];
  assert.deepEqual(C.destinations('repair',presets,source).map(item=>item.id),['same','different']);
});
test('draft roundtrip keeps the guard rather than downgrading to a normal recipe',()=>{
  const draft={version:1,updatedAt:123,recipe:{preset:p.id,controls:{positive:source.positive,reference:file},batch:1,parent_assets:['source-asset'],continuation:claim}};
  const normalized=U.normalizeDraft(draft);assert.deepEqual(normalized.recipe.continuation,claim);
  assert.equal(U.normalizeDraft({...draft,recipe:{...draft.recipe,continuation:{...claim,version:2}}}),null);
  assert.equal(U.normalizeDraft({...draft,recipe:{...draft.recipe,preset:'new'}}),null);
});
test('dead worker cannot be masked by enhanced run presentation',()=>{
  assert.equal(U.readiness({preset:p,online:true,schemaAvailable:true,workerAlive:false}).ready,false);
});
test('a declared restyle keeps the picture without a board, prepares its own wording and fits the canvas',()=>{
  const klein={id:'restyle-klein',name:'Restyle a picture (Klein)',modality:'image',reference:['14','image'],reference_label:'Picture to restyle',positive:['4','text'],width:['10','width'],height:['10','height'],dimension_multiple:16,defaults:{},continuation_operation:'restyle',continuation_prompt:'Redraw this image as a soft look. Keep everything else.{source}',continuation_capability:{...cap,operation:'restyle',prompt_role:'instruction',reference_count:1,source_input:'reference',board_min:0,keeps_picture:true}};
  const keeps={...board,id:'restyle-wai',last_reference_label:'Picture to restyle',continuation_capability:{...boardCap,keeps_picture:true}};
  const prepared=C.initial(source,klein,'restyle',file);
  assert.equal(prepared.claim.intent,'restyle');assert.equal(prepared.positive,'Redraw this image as a soft look. Keep everything else. The picture shows: An adult traveller at the station.');
  assert.equal(C.promptFor(klein,{...source,prompt_origin:'unavailable',positive:null}),'Redraw this image as a soft look. Keep everything else.');
  assert.equal(C.promptFor(keeps,source),null,'recipes without authored continuation wording keep the copy rule');
  assert.deepEqual(C.destinations('restyle',[board,keeps,klein],source).map(x=>x.id),['restyle-klein','restyle-wai','style-pose-nova']);
  assert.deepEqual(C.blockers(prepared.claim,klein,{positive:prepared.positive,reference:file},['source-asset']),[]);
  assert.match(C.blockers(prepared.claim,klein,{positive:prepared.positive,reference:'other.png'},['source-asset']).join(),/Picture to restyle no longer holds/);
  const text=C.guidance(klein,source).join(' ');
  assert.match(text,/no style board/i);assert.match(text,/Picture to restyle/);assert.doesNotMatch(text,/Style weight/);assert.doesNotMatch(text,/add one to three pictures/);
  assert.deepEqual(C.canvasFor({...source,width:832,height:1216},klein),{width:1040,height:1520});
  assert.deepEqual(C.canvasFor({...source,width:1216,height:832},klein),{width:1520,height:1040});
  assert.deepEqual(C.canvasFor({...source,width:4000,height:4000},klein),{width:1248,height:1248});
  assert.deepEqual(C.canvasFor({...source,width:1920,height:1080},klein),{width:1536,height:864},'the long edge hits the limit and the short edge follows');
  assert.deepEqual(C.canvasFor({...source,width:1080,height:1920},klein),{width:864,height:1536});
  assert.equal(C.promptFor(klein,{...source,positive:'A $& witch with $1 gold'}),'Redraw this image as a soft look. Keep everything else. The picture shows: A $& witch with $1 gold.','replacement patterns stay literal');
  assert.equal(C.promptFor(klein,{...source,positive:'x'.repeat(7990)}),'Redraw this image as a soft look. Keep everything else.','a description that would pass the 8000-character prompt limit is left out');
  assert.equal(C.canvasFor({...source,width:832,height:1216},keeps),null,'a board restyle keeps its own canvas rule');
  assert.equal(C.canvasFor({...source,width:832,height:1216},p),null);
  assert.deepEqual(U.recipesFor('restyle',[klein,board,p]).map(x=>x.id),['restyle-klein','style-pose-nova']);
});
test('a Klein board combines two pictures: source stays image 1, the pose picture goes on the board, placeholders block until replaced',()=>{
  const klein={id:'restyle-klein',name:'Restyle a picture (Klein)',modality:'image',reference:['14','image'],reference_label:'Picture to restyle',positive:['4','text'],continuation_operation:'restyle',continuation_prompt:'Redraw this image as a soft look. Keep everything else.{source}',continuation_capability:{...cap,operation:'restyle',prompt_role:'instruction',reference_count:1,source_input:'reference',board_min:0,keeps_picture:true}};
  const combineCap={...boardCap,operation:'combine',prompt_role:'instruction',reference_count:3,keeps_picture:false};
  const combine={id:'combine-klein',name:'Put this character in another picture’s pose (Klein)',modality:'image',positive:['4','text'],width:['10','width'],height:['10','height'],dimension_multiple:16,defaults:{},reference_slots:[{role:'pose',binding:['20','image']},{role:'pose',binding:['24','image']}],reference_board:{min:1},last_reference:['14','image'],last_reference_label:'Picture to keep (image 1)',reference_board_label:'Pose picture (image 2)',continuation_operation:'combine',continuation_prompt:'Redraw [who] from image 1 in the pose of image 2: [say the pose]. Keep image 1.',continuation_placeholder:['[who]','[say the pose]'],continuation_capability:combineCap};
  const look={...combine,id:'restyle-klein-picture',name:'Restyle in another picture’s look (Klein)',continuation_operation:'restyle',continuation_prompt:'Copy how image 2 is drawn.{source}',continuation_placeholder:undefined,continuation_capability:{...combineCap,operation:'restyle',keeps_picture:true}};
  const prepared=C.initial(source,combine,'combine',file);
  assert.equal(prepared.claim.intent,'combine');assert.equal(prepared.positive,'Redraw [who] from image 1 in the pose of image 2: [say the pose]. Keep image 1.','no {source}: the description names the source pose and would undo the transfer');
  assert.throws(()=>C.initial(source,combine,'restyle',file),'a combine board is not a restyle destination');assert.throws(()=>C.initial(source,klein,'combine',file));
  const empty=[{role:'pose',file:null},{role:'pose',file:null}],one=[{role:'pose',file:styleFile},{role:'pose',file:null}];
  assert.deepEqual(C.blockerItems(prepared.claim,combine,{positive:prepared.positive,last_reference:file},['source-asset'],empty).map(i=>i.code),['board','wording']);
  assert.match(C.blockers(prepared.claim,combine,{positive:prepared.positive,last_reference:file},['source-asset'],empty).join(),/picture whose pose you want to Picture 1/);
  assert.match(C.blockers(prepared.claim,combine,{positive:prepared.positive,last_reference:file},['source-asset'],one).join(),/replace “\[who\]” and “\[say the pose\]” in the prompt/);
  assert.match(C.blockers(prepared.claim,combine,{positive:'Redraw the witch from image 1 in the pose of image 2: [say the pose]. Keep image 1.',last_reference:file},['source-asset'],one).join(),/replace “\[say the pose\]” in the prompt/,'each unreplaced placeholder is named');
  assert.deepEqual(C.blockers(prepared.claim,combine,{positive:'Redraw the witch from image 1 in the pose of image 2: leaning forward. Keep image 1.',last_reference:file},['source-asset'],one),[]);
  assert.deepEqual(C.destinations('combine',[p,board,klein,look,combine],source).map(x=>x.id),['combine-klein']);
  assert.deepEqual(C.destinations('restyle',[p,board,combine,look,klein],source).map(x=>x.id),['restyle-klein','restyle-klein-picture','style-pose-nova'],'the look board follows the wording restyle; the combine board is not offered');
  const text=C.guidance(combine,source).join(' ');
  assert.match(text,/pose of the picture you put on the board/);assert.match(text,/Picture to keep \(image 1\)/);assert.match(text,/Picture 1 \(image 2\)/);assert.doesNotMatch(text,/style board/);
  // The 9B recipe keeps the pose picture as image 1 and swaps the character in as image 2: the guidance and blocker follow the labels, one slot means no third-picture warning.
  const nine={...combine,id:'combine-klein-9b',reference_slots:[{role:'pose',binding:['14','image']}],last_reference:['20','image'],last_reference_label:'Picture to keep (image 2)',reference_board_label:'Pose picture (image 1)'};
  const nineText=C.guidance(nine,source).join(' ');assert.match(nineText,/Picture to keep \(image 2\)/);assert.match(nineText,/whose pose you want to Picture 1 \(image 1\)/);assert.doesNotMatch(nineText,/image 3/);assert.match(nineText,/clothes and colours/);
  assert.match(C.blockers(prepared.claim,nine,{positive:prepared.positive,last_reference:file},['source-asset'],empty).join(),/whose pose you want to Picture 1 \(image 1\)/);
  // The depth-map recipe leads the Combine route (nothing of the pose picture leaks), then pose-first 9B, then 4B.
  const depth={...nine,id:'combine-klein-9b-depth',reference_board_label:'Depth map of the pose picture (image 1)'};
  assert.deepEqual(C.destinations('combine',[p,combine,board,nine,depth,look],source).map(x=>x.id),['combine-klein-9b-depth','combine-klein-9b','combine-klein']);
  assert.match(C.guidance(depth,source).join(' '),/whose pose you want to Picture 1 \(image 1\)/);
  assert.match(C.guidance(depth,source).join(' '),/read as a depth map: only the silhouette reaches the model/);assert.doesNotMatch(C.guidance(depth,source).join(' '),/background follows the pose picture/);
  assert.match(nineText,/shoe or stocking from it can ghost in/);
  const lookText=C.guidance(look,source).join(' ');
  assert.match(lookText,/copy how image 2 is drawn/);assert.match(lookText,/Colours can drift/);assert.doesNotMatch(lookText,/Style weight/);assert.doesNotMatch(lookText,/add one to three pictures/);
  assert.equal(C.promptFor(look,source),'Copy how image 2 is drawn. Image 1 shows: An adult traveller at the station.','a board recipe numbers its source');
  assert.equal(C.promptFor(klein,{...source,prompt_role:'instruction',positive:'Redraw this image as a soft look. Keep everything else.'}),'Redraw this image as a soft look. Keep everything else.','an instruction-role source prompt is not appended as a description (it compounded the previous pass)');
  assert.match(C.guidance(klein,{...source,preset_id:'restyle-klein'}).join(' '),/same wording and seed give the same picture again/);
  assert.doesNotMatch(C.guidance(klein,source).join(' '),/same wording and seed/);
  assert.deepEqual(C.canvasFor({...source,width:832,height:1216},look),{width:1040,height:1520},'a board restyle that keeps the picture fits the canvas');
  assert.equal(C.canvasFor({...source,width:832,height:1216},combine),null,'a combine changes the pose and keeps the recipe canvas');
  const edit={...p,id:'flux-edit',continuation_prompt:'Change one thing: [say what changes]. Keep the rest.{source}',continuation_placeholder:'[say what changes]',continuation_capability:{...cap,operation:'instruction-edit',prompt_role:'instruction'}};
  const editPrepared=C.initial(source,edit,'edit',file);
  assert.equal(editPrepared.positive,'Change one thing: [say what changes]. Keep the rest. The picture shows: An adult traveller at the station.');
  assert.deepEqual(C.blockerItems(editPrepared.claim,edit,{positive:editPrepared.positive,reference:file},['source-asset']).map(i=>i.code),['wording']);
  assert.deepEqual(C.blockerItems(editPrepared.claim,edit,{positive:'Change one thing: a red hat. Keep the rest.',reference:file},['source-asset']),[]);
  assert.deepEqual(C.destinations('edit',[{...p,id:'qwen-1ref',name:'Qwen'},{...p,id:'krea-refine',name:'Krea'},edit],source).map(x=>x.id),['flux-edit','qwen-1ref','krea-refine'],'the 20-second edit greets the user, not the 11-minute one');
  assert.deepEqual(U.recipesFor('combine',[combine,board,look,p]).map(x=>x.id),['combine-klein']);
  assert.deepEqual(U.recipesFor('restyle',[combine,board,look,klein]).map(x=>x.id),['restyle-klein','restyle-klein-picture','style-pose-nova']);
  assert.equal(U.INTENTS.find(i=>i.id==='combine').verb,'Combine');
  assert.deepEqual(C.unfilled(combine,combine.continuation_prompt),['[who]','[say the pose]']);assert.deepEqual(C.unfilled(combine,'Redraw the witch: leaning.'),[]);assert.deepEqual(C.unfilled(edit,null),[]);assert.deepEqual(C.unfilled(p,'[anything]'),[],'a recipe without fills has none');
  assert.deepEqual(U.recipesFor('edit',[{...p,id:'qwen-1ref',name:'Qwen',reference:['4','image']},{...edit,reference:['4','image']}]).map(x=>x.id),['flux-edit','qwen-1ref']);
});
test('bracketed fills become labelled fields and the answers write the prepared wording (#422 slice A)',()=>{
  const depth={id:'combine-klein-9b-depth',continuation_prompt:'Image 1 is a depth map: [image 1\'s pose in a few words, e.g. bent forward at the waist, hands on hips]. Draw [who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips] from image 2 wearing [image 2\'s clothes and colours, e.g. a black crop top, pink shorts]. One figure only.',
    continuation_placeholder:['[who is in image 2, e.g. Ellen Joe, a girl with short black hair with red tips]','[image 1\'s pose in a few words, e.g. bent forward at the waist, hands on hips]','[image 2\'s clothes and colours, e.g. a black crop top, pink shorts]']};
  const spec=C.fills(depth);
  assert.deepEqual(spec.map(f=>f.label),['Who is in image 2','Image 1\'s pose in a few words','Image 2\'s clothes and colours'],'the label is the text before the example; catalog order without a template');
  assert.deepEqual(spec.map(f=>f.example),['Ellen Joe, a girl with short black hair with red tips','bent forward at the waist, hands on hips','a black crop top, pink shorts']);
  assert.deepEqual(C.fills(depth,depth.continuation_prompt).map(f=>f.label),['Image 1\'s pose in a few words','Who is in image 2','Image 2\'s clothes and colours'],'with the wording, the fields follow the order it reads them');
  assert.equal(C.assemble(depth.continuation_prompt,{[spec[0].placeholder]:'quoting '+spec[0].placeholder+' itself'}),depth.continuation_prompt,'an answer that quotes its own bracket is left out');
  assert.deepEqual(C.fills({continuation_placeholder:'[who]'}),[{placeholder:'[who]',label:'Who',example:''}],'a fill without an example has an empty example');
  assert.deepEqual(C.fills({}),[]);
  const values={[spec[0].placeholder]:'Ellen Joe, red-tipped black hair',[spec[1].placeholder]:'  bent double, legs crossed ',[spec[2].placeholder]:''};
  const text=C.assemble(depth.continuation_prompt,values);
  assert.equal(text,'Image 1 is a depth map: bent double, legs crossed. Draw Ellen Joe, red-tipped black hair from image 2 wearing [image 2\'s clothes and colours, e.g. a black crop top, pink shorts]. One figure only.','answers are trimmed and an empty answer keeps its bracket');
  assert.deepEqual(C.unfilled(depth,text),[spec[2].placeholder],'the readiness list still names the one fill left');
  assert.equal(C.assemble(depth.continuation_prompt,{...values,[spec[2].placeholder]:'a black crop top, pink shorts, bare feet'}).includes('['),false);
  assert.equal(C.assemble(null,values),'');assert.equal(C.assemble('plain wording',null),'plain wording');
});
console.log(count+' continuation client policy checks passed.');
