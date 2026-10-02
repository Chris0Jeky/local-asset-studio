// #1250: exercise the real poll and settled-run adapter with synthetic jobs, no browser or backend.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const {test} = require('node:test');

function sandbox() {
  class Element {
    constructor(tagName='DIV') {this.tagName=tagName;this.children=[];this.dataset={};this.hidden=false;this.className='';this.value='';this.attributes={};this.classList={toggle(){}};}
    set textContent(value) {this.text=String(value);this.children=[];}
    get textContent() {return (this.text||'')+this.children.map(e=>e.textContent).join('');}
    set innerHTML(value) {this.html=value;this.text='';this.children=[];}
    get innerHTML() {return this.html||'';}
    append(...nodes) {for(const node of nodes){node.parentElement=this;this.children.push(node);}}
    after(node) {nodes.set('#'+node.id,node);}
    setAttribute(name,value) {this.attributes[name]=String(value);}
    hasAttribute(name) {return name in this.attributes;}
    querySelector(selector) {return selector==='button,a,summary'?this.children.find(n=>n.tagName==='BUTTON')||null:null;}
    querySelectorAll() {return [];}
    addEventListener() {}
    scrollIntoView() {this.scrolled=true;}
    focus() {if(!this.disabled&&!this.hidden)document.activeElement=this;}
    closest(selector) {return selector==='[data-run-outcome]'&&this.dataset.runOutcome?this:selector==='#generate'&&this.id==='generate'?this:selector==='.wk-run-dock'&&this.parentElement?.className==='wk-run-dock'?this.parentElement:null;}
  }
  const nodes=new Map(),listeners=new Map(),requests=[];
  const element=selector=>{if(!nodes.has(selector))nodes.set(selector,new Element());return nodes.get(selector);};
  const descendants=node=>[node,...node.children.flatMap(descendants)];
  const document={querySelector:selector=>selector.startsWith('#runOutcome [data-run-outcome=')?element('#runOutcome').children.find(n=>n.dataset.runOutcome==='dismiss'):element(selector),
    querySelectorAll:()=>[],getElementById:id=>nodes.get('#'+id)||[...nodes.values()].flatMap(descendants).find(n=>n.id===id)||null,createElement:tag=>new Element(tag.toUpperCase()),
    addEventListener(name,handler) {if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(handler);},
    dispatchEvent(event) {for(const handler of listeners.get(event.type)||[])handler(event);}};
  let response={status:304,ok:false};
  element('#status');
  const context=vm.createContext({document,window:{},location:{hash:''},URL,Blob,setInterval(){},CSS:{escape:s=>s},
    CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}},sessionStorage:{getItem(){return null;}},
    fetch:async(url,options={})=>{if(url==='/api/catalog')return new Promise(()=>{});requests.push({url,options});return response;}});
  for(const file of ['app.js','run-outcome.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static',file),'utf8'),context);
  const run=source=>vm.runInContext(source,context);
  // Avoid unrelated gallery/time-estimate DOM work; retain real refreshJobs, settleActiveJob and message.
  run('renderJobs=()=>{};scheduleTimeEstimate=()=>{};jobs=[];activeJobId=null;');
  element('#generate').id='generate';
  const poll=async list=>{response={status:200,ok:true,headers:{get:()=>null},json:async()=>list};await run('refreshJobs()');};
  const click=node=>document.dispatchEvent({type:'click',target:node});
  const outcome=()=>element('#runOutcome'),summary=()=>outcome().children.find(n=>n.className.startsWith('run-outcome-summary'));
  const button=action=>outcome().children.find(n=>n.dataset.runOutcome===action);
  const target=(id,completed=true)=>{const record=new Element('ARTICLE'),details=new Element('DETAILS');details.append(record);
    if(completed)record.append(new Element('BUTTON'));
    nodes.set(completed?'#gallery [data-output^="'+id+':"]':'[data-problem="'+id+'"]',record);return {record,details};};
  return {run,element,requests,document,poll,click,outcome,summary,button,target,
    start(...ids){run(ids.map(id=>'startedJobIds.add('+JSON.stringify(id)+');').join('')+'activeJobId='+JSON.stringify(ids.at(-1))+';');},
    settle(job){document.dispatchEvent({type:'studio:job-settled',detail:job});},
    async error(){response={status:503,ok:false,json:async()=>({error:'Jobs temporarily unavailable'})};await run('refreshJobs()');},
    async unchanged(){response={status:304,ok:false,headers:{get:()=>null}};await run('refreshJobs()');}};
}
const job=(id,status='completed')=>({id,status,preset_name:'Synthetic '+id,message:status==='failed'?'Synthetic failure':status==='not_submitted'?'Queue unavailable. Nothing submitted.':'Done',outputs:status==='completed'?[{}]:[],elapsed_seconds:2});

test('two jobs settled by one poll remain reachable in start order',async()=>{
  const s=sandbox(),first=s.target('first'),second=s.target('second',false);
  s.start('first','second');await s.poll([job('second','failed'),job('first')]);
  assert.equal(s.button('show').textContent,'Show result →','the first run is not replaced by the second');
  assert.match(s.outcome().textContent,/1 more run settled/);
  s.click(s.button('show'));assert.equal(s.document.activeElement,first.record.children[0]);
  s.click(s.button('dismiss'));assert.match(s.summary().textContent,/Failed: Synthetic failure/);
  s.click(s.button('show'));assert.equal(s.document.activeElement,second.record);
  s.click(s.button('dismiss'));assert.equal(s.outcome().hidden,true);
  assert.equal(s.requests.filter(r=>r.options.method==='POST').length,0);
});

test('settled summary and action survive a poll error and recovery',async()=>{
  const s=sandbox();s.start('saved');await s.poll([job('saved')]);
  assert.ok(s.summary(),'the summary belongs to the outcome panel');
  const text=s.summary().textContent,action=s.button('show');
  await s.error();assert.equal(s.element('#status').textContent,'Jobs temporarily unavailable');
  assert.equal(s.summary().textContent,text);assert.equal(s.button('show'),action);
  await s.unchanged();await s.poll([job('saved')]);
  assert.equal(s.summary().textContent,text);s.click(s.button('dismiss'));assert.equal(s.outcome().hidden,true,'recovery never queues another copy');
  assert.equal(s.element('#status').textContent,'Jobs temporarily unavailable','dismiss preserves an unrelated status');
});

test('incoming completions preserve the focused action and advertise every pending run',()=>{
  const s=sandbox();s.settle(job('first'));const action=s.button('show');action.focus();
  s.settle(job('second'));s.settle(job('third','not_submitted'));
  assert.equal(s.button('show'),action);assert.equal(s.document.activeElement,action);assert.match(s.outcome().textContent,/2 more runs settled/);
  s.button('dismiss').focus();s.click(s.button('dismiss'));assert.match(s.outcome().textContent,/1 more run settled/);
  assert.equal(s.document.activeElement,s.button('dismiss'),'keyboard dismissal can continue through the queue');
  s.click(s.button('dismiss'));assert.match(s.summary().textContent,/Not started: Queue unavailable/);
  assert.doesNotMatch(s.outcome().textContent,/more runs settled/);
});

test('a new Generate leaves settled notices reachable',()=>{
  const s=sandbox();s.settle(job('first'));s.settle(job('second','failed'));
  s.click(s.element('#generate'));assert.equal(s.outcome().hidden,false);
  s.click(s.button('dismiss'));assert.match(s.summary().textContent,/Failed:/);
});

test('final keyboard dismissal returns to Generate or the status when Generate is disabled',()=>{
  for(const disabled of [false,true]) {
    const s=sandbox(),generate=s.element('#generate'),status=s.element('#status');
    generate.disabled=disabled;status.textContent='Generation is unavailable';s.settle(job('done'));
    s.button('dismiss').focus();s.click(s.button('dismiss'));
    assert.equal(s.outcome().hidden,true);
    assert.equal(s.document.activeElement,disabled?status:generate);
    if(disabled)assert.equal(status.tabIndex,-1,'the fallback does not enter the tab order');
    assert.equal(status.textContent,'Generation is unavailable');
    assert.equal(s.requests.filter(r=>r.options.method==='POST').length,0);
  }
});

test('dismissal does not move focus from another control',()=>{
  const s=sandbox(),elsewhere=s.element('#elsewhere');s.settle(job('done'));elsewhere.focus();
  s.click(s.button('dismiss'));assert.equal(s.document.activeElement,elsewhere);
});

test('final dismissal uses the generation dock when the short typing layout hides status',()=>{
  const s=sandbox(),status=s.element('#status'),dock=s.element('#dock');dock.className='wk-run-dock';dock.append(status);
  status.hidden=true;s.element('#generate').disabled=true;s.settle(job('done'));
  s.button('dismiss').focus();s.click(s.button('dismiss'));
  assert.equal(s.document.activeElement,dock);assert.equal(dock.tabIndex,-1);
});

test('a 304 announces a run whose POST returned after its completed record was polled once',async()=>{
  const s=sandbox();await s.poll([job('quick')]);s.start('quick');await s.unchanged();await s.unchanged();
  assert.match(s.summary().textContent,/Done/);s.click(s.button('dismiss'));assert.equal(s.outcome().hidden,true);
});

test('clear discards the displayed and queued notices without touching a newer status',()=>{
  const s=sandbox();s.settle(job('first'));s.settle(job('second'));s.run("message('Newer status');window.StudioRunOutcome.clear();");
  assert.equal(s.outcome().hidden,true);s.settle(job('fresh','failed'));assert.doesNotMatch(s.outcome().textContent,/more runs settled/);
  assert.equal(s.element('#status').textContent,'Newer status');
});
