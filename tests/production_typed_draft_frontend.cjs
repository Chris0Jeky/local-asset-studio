// Real Experiments detail rendering in Node's VM (#772): a poll, the Refresh button or a filter change
// re-renders the plan detail, and must not replace text the user has typed but not sent. No browser,
// no ComfyUI, no generation.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const unescape=text=>String(text).replace(/&(amp|lt|gt|quot|#39);/g,(_,e)=>({amp:'&',lt:'<',gt:'>',quot:'"','#39':"'"}[e]));
const document={activeElement:null};
// A form field as innerHTML would build it: the rendered value, a caret and focus.
function field(tagName,id,type,value){
  const node={tagName,id,type,value,selectionStart:value.length,selectionEnd:value.length,selectionDirection:'none',scrollTop:0,
    focus(){document.activeElement=node;},blur(){if(document.activeElement===node)document.activeElement=null;},
    setSelectionRange(start,end,direction='none'){if(type==='number')throw Error('InvalidStateError');node.selectionStart=start;node.selectionEnd=end;node.selectionDirection=direction;}};
  return node;
}
// Only the detail panel parses its markup; every other selector is a plain record, as in the sibling harnesses.
const detail={_html:'',fields:[],classList:{toggle(){}},
  get innerHTML(){return this._html;},
  set innerHTML(html){this._html=html;if(this.fields.includes(document.activeElement))document.activeElement=null;this.fields=[];
    for(const m of html.matchAll(/<textarea id="([^"]+)"[^>]*>([\s\S]*?)<\/textarea>/g))this.fields.push(field('TEXTAREA',m[1],'textarea',unescape(m[2])));
    for(const m of html.matchAll(/<input id="([^"]+)"([^>]*)>/g)){const type=/type="([^"]+)"/.exec(m[2])?.[1]||'text',value=/value="([^"]*)"/.exec(m[2])?.[1]||'';this.fields.push(field('INPUT',m[1],type,unescape(value)));}},
  querySelector(selector){return this.fields.find(f=>'#'+f.id===selector)||null;},
  contains(node){return this.fields.includes(node);}};
const elements=new Map([['#productionDetail',detail]]);
const $=selector=>{const live=detail.querySelector(selector);if(live)return live;
  if(!elements.has(selector))elements.set(selector,{innerHTML:'',value:'',textContent:'',disabled:false,hidden:false,classList:{toggle(){}},focus(){document.activeElement=this;}});return elements.get(selector);};
document.querySelector=$;document.querySelectorAll=()=>[];document.createElement=()=>({style:{},classList:{toggle(){}},querySelectorAll:()=>[]});
const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const stored=new Map(),localStorage={getItem:key=>stored.has(key)?stored.get(key):null,setItem:(key,value)=>stored.set(key,String(value))};
let served=[];const requests=[];
const context=vm.createContext({$,document,localStorage,esc,safeUrl:url=>url,setInterval(){},showView(){},
  api:async()=>JSON.parse(JSON.stringify(served)),post:async(url,data)=>{requests.push({url,data});return {};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/production.js'),'utf8'),context);
const run=source=>vm.runInContext(source,context);

const at=Date.now()/1000;
const review={id:'a'.repeat(32),name:'Lantern study',kind:'comparison',axis:'seed',values:[1,2],created_at:at,budget:{reserved:2,allowance:4},stages:[],
  state:{status:'awaiting_review',message:'Two candidates are ready.',review:{notes:'Saved earlier'},artifacts:[]}};
const clock={id:'c'.repeat(32),name:'Stopped study',kind:'comparison',axis:'seed',values:[1,2],created_at:at,budget:{reserved:2,allowance:4},stages:[],
  state:{status:'stopped',message:'Time allowance exhausted',time_budget:{revision:3,measured_seconds:60,unmeasured_seconds:0,remaining_seconds:0,limit_seconds:600,active:false},artifacts:[]}};
const type=(id,text,start,end)=>{const node=$('#'+id);node.focus();node.value=text;node.selectionStart=start??text.length;node.selectionEnd=end??text.length;detail.oninput?.({target:node});return node;};
const click=attrs=>({target:{closest:selector=>{const key=Object.keys(attrs).find(k=>selector==='['+k+']');return key?{dataset:attrs[key],disabled:false}:null;}}});
const poll=async plans=>{served=plans;await run('refreshProduction()');};

(async()=>{
  served=[review,clock];await run('refreshProduction(true)');
  assert.equal($('#productionNotes').value,'Saved earlier','The saved review note renders as before');

  // 1 · A poll that brings a changed plan re-renders the detail; the unsent note, its focus and caret survive.
  const typed=type('productionNotes','Candidate B keeps the lantern glow',10,15);
  await poll([{...review,state:{...review.state,message:'Still two candidates.'}},clock]);
  assert.match(detail.innerHTML,/Still two candidates/,'The poll really re-rendered the detail');
  const notes=$('#productionNotes');
  assert.notEqual(notes,typed,'The field is a new element after the re-render');
  assert.equal(notes.value,'Candidate B keeps the lantern glow','A poll must not replace the note being typed');
  assert.equal(document.activeElement,notes,'Focus returns to the field being typed in');
  assert.deepEqual([notes.selectionStart,notes.selectionEnd],[10,15],'The caret and selection return too');

  // 2 · The Refresh button forces the same re-render.
  await $('#refreshProduction').onclick();
  assert.equal($('#productionNotes').value,'Candidate B keeps the lantern glow','Refresh must not replace the note being typed');
  assert.equal(document.activeElement,$('#productionNotes'));

  // 3 · Filters (#965) re-render the list and the detail; the note stays and Show all still hands focus to Status.
  run("setPlanFilter({type:'comparison'})");
  assert.equal($('#productionNotes').value,'Candidate B keeps the lantern glow','A filter change must not replace the note');
  run("setPlanFilter({type:'voice',status:'active'})");$('#productionList').onclick(click({'data-plan-show-all':{}}));
  assert.equal(document.activeElement,$('#planStatus'),'Show all keeps handing focus to the Status select');
  assert.equal($('#productionNotes').value,'Candidate B keeps the lantern glow');

  // 4 · A field the user never typed in still follows the server.
  document.activeElement=null;run('productionId='+JSON.stringify(clock.id)+';renderProduction();');
  const reason=type('extendTimeReason','Finish candidate B');
  await poll([review,{...clock,state:{...clock.state,message:'Still stopped.'}}]);
  assert.equal($('#extendTimeReason').value,'Finish candidate B','The typed reason survives a poll');
  assert.notEqual($('#extendTimeReason'),reason);
  assert.equal($('#extendTimeMinutes').value,'15','An untouched field keeps its rendered value');
  $('#extendTimeMinutes').focus();$('#extendTimeMinutes').value='12';detail.oninput?.({target:$('#extendTimeMinutes')});
  await poll([review,{...clock,state:{...clock.state,message:'Stopped, still.'}}]);
  assert.equal($('#extendTimeMinutes').value,'12','A typed number survives a poll');
  assert.equal(document.activeElement,$('#extendTimeMinutes'),'Focus returns to a number field without a caret API');

  // 5 · Sending the values drops them: the next render shows what the server holds.
  await $('#productionDetail').onclick(click({'data-project-action':{projectAction:'extend-time'}}));
  assert.deepEqual(JSON.parse(JSON.stringify(requests.at(-1))),{url:'/api/production/'+clock.id+'/extend-time',data:{seconds:720,reason:'Finish candidate B',expected_revision:3}});
  await poll([review,{...clock,state:{...clock.state,time_budget:{...clock.state.time_budget,limit_seconds:1320,revision:4}}}]);
  assert.equal($('#extendTimeReason').value,'','A sent reason is not restored after the save succeeds');
  assert.equal($('#extendTimeMinutes').value,'15','A sent number is not restored after the save succeeds');

  // 6 · Switching plan drops the unsent values of the plan left behind.
  run('productionId='+JSON.stringify(review.id)+';renderProduction();');
  assert.equal($('#productionNotes').value,'Saved earlier','The note typed before another plan was opened is not carried back');
  type('productionNotes','Draft for the other plan');
  $('#productionList').onclick(click({'data-project':{project:clock.id}}));
  $('#productionList').onclick(click({'data-project':{project:review.id}}));
  assert.equal($('#productionNotes').value,'Saved earlier','Opening another plan drops the unsent note');

  // 7 · A failed save keeps the note; a successful one drops it.
  type('productionNotes','Needs a cleaner silhouette');
  const failing=context.post;context.post=async()=>{throw Error('Review revision changed');};
  await $('#productionDetail').onclick(click({'data-project-action':{projectAction:'needs_work'}}));
  await poll([{...review,state:{...review.state,message:'Changed elsewhere.'}},clock]);
  assert.equal($('#productionNotes').value,'Needs a cleaner silhouette','A failed save keeps the unsent note');
  context.post=failing;
  await $('#productionDetail').onclick(click({'data-project-action':{projectAction:'needs_work'}}));
  assert.deepEqual(JSON.parse(JSON.stringify(requests.at(-1))),{url:'/api/production/'+review.id+'/review',data:{asset_id:null,notes:'Needs a cleaner silhouette',reviewer:'local-user'}});
  await poll([{...review,state:{...review.state,review:{notes:'Stored by the server'}}},clock]);
  assert.equal($('#productionNotes').value,'Stored by the server','After a successful save the server copy renders');
  console.log('Typed review notes and time-extension fields survive polls, Refresh and filters until sent or another plan is opened.');
})().catch(error=>{console.error(error);process.exitCode=1;});
