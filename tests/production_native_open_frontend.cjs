// Real Production renderer in Node's VM: the "open this file" card names the recorded entry artifact and claims nothing more.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map();
const $=selector=>{if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,classList:{toggle(){}}});return elements.get(selector);};
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const context=vm.createContext({$,document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},api:async()=>[],post:async()=>({})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const id='c'.repeat(32),art=p=>({path:p,url:'/api/production/'+id+'/files/'+p,role:'native-source'});
const plan=(kind,export_kind,paths,state={})=>({id,name:'Export',kind,export_kind,budget:{reserved:0,allowance:0},stages:[],state:{status:'completed',message:'Native export complete',artifacts:paths.map(art),...state}});
const render=value=>{vm.runInContext(`productionPlans=[${JSON.stringify(value)}];productionId=${JSON.stringify(id)};renderProduction();`,context);return $('#productionDetail').innerHTML;};
const card=html=>(/<aside class="callout native-open"[\s\S]*?<\/aside>/.exec(html)||[''])[0];
const href=(file,query='?download')=>'href="/api/production/'+id+'/files/'+file+query+'"';
// Krita: the layered ORA, with the recorded roundtrip only when the plan has one.
let c=card(render(plan('native','ora',['export.zip','native/layers.ora','native/frames.json'])));
assert.match(c,/Open this in Krita:/);assert.ok(c.includes(href('native/layers.ora')+' download>layers.ora</a>'),c);assert.match(c,/Krita → File → Open/);assert.match(c,/No Krita roundtrip was recorded/);
c=card(render(plan('native','ora',['export.zip','native/layers.ora','native/krita/roundtrip.kra'],{krita:{kra:{layers:[1,2,3]}}})));
assert.match(c,/Recorded Krita roundtrip: saved and reopened roundtrip\.kra, 3 layer records retained\./);assert.doesNotMatch(c,/No Krita roundtrip/);
// Godot: project.godot, never the atlas or ORA.
c=card(render(plan('native','godot',['export.zip','native/atlas/atlas.png','native/godot/project.godot','native/godot/main.tscn'])));
assert.match(c,/Open this in Godot:/);assert.ok(c.includes('<code>godot/project.godot</code> inside <a '+href('export.zip')+' download>export.zip</a>'),c);assert.doesNotMatch(c,/native\/godot|files\/native/,'Godot links the whole pack, never the lone project file');assert.match(c,/Unzip the whole pack/);assert.match(c,/Project Manager/);assert.match(c,/No Godot check was recorded/);
c=card(render(plan('native','godot',['export.zip','native/godot/project.godot'],{engine:{ok:true}})));assert.match(c,/Recorded Godot check: import and timed playback verified/);
// Blender: chest.blend is only inside the recorded pack, so the link is the pack.
c=card(render(plan('articulated',undefined,['export.zip','articulated/chest.glb'])));
assert.match(c,/Open this in Blender:/);assert.ok(c.includes('<code>chest.blend</code> inside <a '+href('export.zip')+' download>export.zip</a>'),c);assert.match(c,/Blender → File → Open/);
// Nothing for a failed or interrupted plan, an atlas export, or a plan still running.
for(const status of ['failed','interrupted','uncertain','stopped','running','planned'])for(const [kind,ek,paths] of [['native','ora',['export.zip','native/layers.ora']],['native','godot',['native/godot/project.godot']],['articulated',undefined,['export.zip']]])
  assert.equal(card(render({...plan(kind,ek,paths),state:{status,message:'x',artifacts:paths.map(art)}})),'',kind+' '+ek+' '+status);
assert.equal(card(render(plan('native','atlas',['export.zip','native/atlas/atlas.png']))),'','Atlas export has no editor entry file');
// A missing entry is stated, never guessed from the other files.
for(const [kind,ek,tool,paths] of [['native','ora','Krita',['export.zip','native/frames.json']],['native','godot','Godot',['export.zip','native/atlas/atlas.png']],['native','godot','Godot',['native/godot/project.godot']],['articulated',undefined,'Blender',['articulated/chest.glb']]]){
  c=card(render(plan(kind,ek,paths)));assert.match(c,new RegExp('Open this in '+tool+':</b> entry file not recorded'));assert.doesNotMatch(c,/<a /);}
// No wording that claims the file was opened, inspected or accepted.
for(const html of [plan('native','ora',['native/layers.ora']),plan('native','godot',['native/godot/project.godot']),plan('articulated',undefined,['export.zip']),plan('native','ora',['native/layers.ora'],{krita:{kra:{layers:[1]}}})].map(p=>card(render(p)))){
  assert.doesNotMatch(html.replace('Studio records no art acceptance.',''),/accept|approved|inspected|looks good|ready/i);assert.doesNotMatch(html,/\b(was|has been|were) opened\b|opened in/i);}
for(const [search,expected] of [['?plan='+id,id],['?plan=other',null],['',null]]){
  const linked=vm.createContext({$,URLSearchParams,location:{search},document:{querySelector:$,querySelectorAll:()=>[]},esc,setInterval(){},showView(){},api:async()=>[],post:async()=>({})});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),linked);
  assert.equal(vm.runInContext('productionId',linked),expected,'Library links select only the exact well-formed plan');
}
console.log('Native open-this-file card names the recorded entry artifact and claims no opening or acceptance.');
