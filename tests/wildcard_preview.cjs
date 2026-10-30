'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/static/app.js'),'utf8');
const Disclosure=require('../app/static/create-progressive-disclosure.js');
const shell=fs.readFileSync(path.join(__dirname,'../app/static/index.html'),'utf8');
function page(){
  const writes=[],listeners={},observers=[],mutations=[],state={scope:'private',privacy:'private',revision:1};let respond;
  const notify=(target,type,attributeName)=>{mutations.push({target,type,attributeName});for(const o of observers)if((target===o.target||o.options.subtree&&o.target.contains(target))&&(type==='childList'&&o.options.childList||type==='attributes'&&o.options.attributes&&o.options.attributeFilter.includes(attributeName)))o.fn();};
  class Element{
    constructor(tag){this.tagName=tag;this.id='';this.children=[];this.parentNode=null;this.dataset={};this.listeners={};this.value='';this.disabled=false;this.open=false;this._hidden=false;this._html='';this._text='';}
    append(...items){for(const item of items){if(item.parentNode)item.parentNode.children=item.parentNode.children.filter(c=>c!==item);item.parentNode=this;this.children.push(item);}notify(this,'childList');}
    after(item){const p=this.parentNode;if(item.parentNode)item.parentNode.children=item.parentNode.children.filter(c=>c!==item);item.parentNode=p;p.children.splice(p.children.indexOf(this)+1,0,item);notify(p,'childList');}
    contains(n){return n===this||this.children.some(c=>c.contains(n));}
    matches(s){return s[0]==='#'?this.id===s.slice(1):s==='[data-wildcard]'?this.dataset.wildcard!==undefined:s==='[data-wildcard-preview]'?this.preview:false;}
    querySelector(s){for(const c of this.children){if(c.matches(s))return c;const found=c.querySelector(s);if(found)return found;}return null;}
    closest(s){for(let n=this;n;n=n.parentNode)if(n.matches(s))return n;return null;}
    addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
    dispatchEvent(e){for(const fn of this.listeners[e.type]||[])fn({target:this});if(e.bubbles)for(const fn of listeners[e.type]||[])fn({target:this});}
    focus(){document.activeElement=this;}
    setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;}
    get hidden(){return this._hidden;}set hidden(v){this._hidden=v;notify(this,'attributes','hidden');}
    get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
    set textContent(v){this.children.forEach(c=>c.parentNode=null);this.children=[];this._text=v;this._html='';notify(this,'childList');}
    get innerHTML(){return this._html;}
    set innerHTML(html){this.children.forEach(c=>c.parentNode=null);this.children=[];this._html=html;this._text='';const stack=[this];
      for(const m of html.matchAll(/<(\/?)([a-z0-9]+)\b([^>]*)>/gi)){if(m[1]){stack.pop();continue;}const el=new Element(m[2]);el.id=/\bid="([^"]*)"/.exec(m[3])?.[1]||'';el.describedBy=/\baria-describedby="([^"]*)"/.exec(m[3])?.[1];el.disabled=/\bdisabled\b/.test(m[3]);el._hidden=/\bhidden\b/.test(m[3]);el.preview=/\bdata-wildcard-preview\b/.test(m[3]);const name=/\bdata-wildcard="([^"]*)"/.exec(m[3]);if(name)el.dataset.wildcard=name[1];el.parentNode=stack.at(-1);el.parentNode.children.push(el);stack.push(el);}notify(this,'childList');}
  }
  const body=new Element('body'),document={querySelector:s=>body.querySelector(s),createElement:tag=>new Element(tag),addEventListener:(event,fn)=>(listeners[event]||=[]).push(fn),defaultView:{MutationObserver:class{constructor(fn){this.fn=fn;}observe(target,options){observers.push({fn:this.fn,target,options});}}}};
  const view=new Element('section');view.id='createView';body.append(view);
  view.innerHTML=shell.slice(shell.indexOf('<div id="positiveWrap">'),shell.indexOf('<details id="nsfwIntel"'))+'</div><textarea id="negative"></textarea><select id="batch"></select>';
  const node=id=>document.querySelector(id);
  const context=vm.createContext({console,document,Event:class{constructor(type,options={}){this.type=type;this.bubbles=options.bubbles;}},
    StudioPrivacy:{capture:()=>({...state})},
    fetch:(url,options)=>{writes.push({url,options});return new Promise(resolve=>{respond=data=>resolve({ok:true,json:async()=>data});});},
    continuationPayload:()=>({}),tilePayload:()=>({}),parallaxPayload:()=>({}),attachedReferencePayload:()=>[],
    values:()=>({positive:node('#positive').value,negative:node('#negative').value,seed:'42'})});
  vm.runInContext(source.slice(0,source.indexOf('function i2vModeBlocker()')),context);
  vm.runInContext(source.slice(source.indexOf('function insertWildcard('),source.indexOf('function renderNsfwIntel(')),context);
  const start=source.indexOf("$('#wildcardChips')?.addEventListener");
  vm.runInContext(source.slice(start,source.indexOf("$('#variants').onclick",start)),context);
  vm.runInContext("selected={id:'demo',positive:['1','text'],negative:['2','text']};catalog={wildcards:[]}",context);
  node('#batch').value='2';
  const details=Disclosure.mount(document).wildcards;
  const reachable=el=>{for(let n=el;n;n=n.parentNode)if(n.hidden||n.tagName==='details'&&!n.open)return false;return true;};
  return {context,node,writes,state,listeners,document,details,mutations,reachable,reply:data=>respond(data),run:js=>vm.runInContext(js,context)};
}
test('plain prompts disable wording preview with a visible accessible reason and send nothing',async()=>{
  const h=page();h.node('#positive').value='plain';h.run('renderWildcardChips()');
  assert.equal(h.node('[data-wildcard-preview]').disabled,true);assert.equal(h.node('[data-wildcard-preview]').describedBy,'wildcardPreviewReason');
  assert.equal(h.node('#wildcardPreviewReason').textContent,'No wildcards in this prompt.');assert.equal(h.reachable(h.node('[data-wildcard-preview]')),true);
  await h.run('previewWildcardWording()');assert.equal(h.writes.length,0);
});
test('either prompt enables preview even with no named wildcard lists',()=>{
  for(const [key,text] of [['positive','{red|blue}'],['negative','__lighting__']]){
    const h=page();h.node('#'+key).value=text;h.run('renderWildcardChips()');
    assert.equal(h.run('wildcardPreviewReason()'),'');assert.equal(h.node('[data-wildcard-preview]').disabled,false);
    assert.equal(h.details.hidden,true);assert.equal(h.details.contains(h.node('[data-wildcard-preview]')),false);assert.equal(h.reachable(h.node('[data-wildcard-preview]')),true);
    assert.equal(h.writes.length,0);
  }
});
test('explicit preview uses creation payload and privacy headers, escapes both prompts and never submits',async()=>{
  const h=page();h.node('#positive').value='__lighting__';
  h.run('renderWildcardChips()');const pending=h.run('previewWildcardWording()');assert.equal(h.writes.length,1);assert.equal(h.writes[0].url,'/api/wildcards/preview');
  assert.equal(h.writes[0].options.headers['X-Studio-Creation-Privacy'],'private');assert.equal(h.writes[0].options.headers['X-Studio-Privacy'],'private');
  const payload=JSON.parse(h.writes[0].options.body);assert.equal(payload.preset_id,'demo');assert.equal(payload.batch_count,'2');assert.equal(payload.controls.seed,'42');
  h.reply({members:[{index:0,seed:9007199254740992,seed_text:'9007199254740993',positive:'<img onerror="bad">',negative:'<script>bad</script>',truncated:true},{index:1,seed:null,seed_unknown:true,positive:'unknown & safe',negative:''}]});await pending;
  const html=h.node('#wildcardPreview').innerHTML;assert.doesNotMatch(html,/<img|<script/);assert.match(html,/&lt;img/);assert.match(html,/&lt;script/);assert.match(html,/Seed 9007199254740993/);assert.match(html,/Seed unknown/);assert.match(html,/unknown &amp; safe/);assert.match(html,/\u2026/);
  assert.equal(h.writes.length,1);assert.equal(h.node('[data-wildcard-preview]').disabled,false);
});
test('late private results cannot enter a changed privacy view',async()=>{
  const h=page();h.node('#positive').value='__lighting__';h.run('renderWildcardChips()');const pending=h.run('previewWildcardWording()');h.state.revision++;
  h.reply({members:[{index:0,seed:42,positive:'PRIVATE-CANARY',negative:''}]});await pending;
  assert.doesNotMatch(h.node('#wildcardPreview').innerHTML,/PRIVATE-CANARY/);
});
test('typing and chip insertion preserve the real disclosure, host children and caret',()=>{
  const h=page();h.run("catalog.wildcards=[{name:'lighting',count:2}];renderWildcardChips()");
  const host=h.node('#wildcardChips'),chip=host.querySelector('[data-wildcard]'),html=host.innerHTML;
  const changes=()=>h.mutations.filter(m=>m.target===host).length,before=changes();
  h.details.open=true;chip.focus();h.node('#positive').value='plain';
  for(const type of ['input','change'])h.node('#positive').dispatchEvent({type,bubbles:true});
  assert.equal(h.details.open,true);assert.equal(h.document.activeElement,chip);assert.equal(changes(),before);
  assert.equal(h.node('[data-wildcard-preview]').disabled,true);assert.equal(h.node('#wildcardPreviewReason').textContent,'No wildcards in this prompt.');
  h.node('#wildcardPreview').innerHTML='OLD-PREVIEW';
  h.node('#positive').setSelectionRange(5,5);h.run("insertWildcard('lighting')");
  assert.equal(h.node('#positive').value,'plain __lighting__');assert.equal(h.node('#positive').selectionStart,18);
  assert.equal(h.document.activeElement,h.node('#positive'));assert.equal(h.details.open,true);assert.equal(changes(),before);
  assert.equal(host.innerHTML,html);assert.equal(host.querySelector('[data-wildcard]'),chip);
  assert.equal(h.node('[data-wildcard-preview]').disabled,false);assert.equal(h.node('#wildcardPreview').innerHTML,'');
  h.node('#wildcardPreview').innerHTML='PRIVATE-CANARY';h.listeners['studio:privacy-change'][0]();
  assert.equal(h.details.open,false);assert.doesNotMatch(h.node('#wildcardPreview').innerHTML,/PRIVATE-CANARY/);assert.equal(h.writes.length,0);
});
test('prompt edits invalidate an in-flight preview with a persistent output element',async()=>{
  const h=page();h.node('#positive').value='__lighting__';h.run('renderWildcardChips()');const pending=h.run('previewWildcardWording()');
  h.node('#positive').value='{new|wording}';h.node('#positive').dispatchEvent({type:'input',bubbles:true});
  h.reply({members:[{index:0,seed:42,positive:'STALE-CANARY',negative:''}]});await pending;
  assert.equal(h.node('#wildcardPreview').innerHTML,'');assert.equal(h.node('[data-wildcard-preview]').disabled,false);
});
test('a shown preview records its file digests for Generate and any re-render drops them',async()=>{
  const h=page();h.node('#positive').value='__lighting__';h.run('renderWildcardChips()');
  const pending=h.run('previewWildcardWording()');
  h.reply({members:[{index:0,seed:42,positive:'a',negative:''}],wildcard_files:{lighting:'a'.repeat(64)}});await pending;
  assert.deepEqual(h.run('wildcardPreviewDigests'),{lighting:'a'.repeat(64)});
  h.node('#positive').value='__lighting__ more';h.node('#positive').dispatchEvent({type:'input',bubbles:true});
  assert.equal(h.run('wildcardPreviewDigests'),null);
  const empty=page();empty.node('#positive').value='{a|b}';empty.run('renderWildcardChips()');const none=empty.run('previewWildcardWording()');
  empty.reply({members:[{index:0,seed:1,positive:'a',negative:''}],wildcard_files:{}});await none;
  assert.equal(empty.run('wildcardPreviewDigests'),null);
  assert.ok(source.includes('{wildcard_digests:{...wildcardPreviewDigests}}'));
});
