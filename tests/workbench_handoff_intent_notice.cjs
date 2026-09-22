const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/studio-workbench.js'), 'utf8');

function between(start, end) {
  const first = source.indexOf(start);
  assert.notEqual(first, -1, `missing source marker: ${start}`);
  const last = source.indexOf(end, first);
  assert.notEqual(last, -1, `missing source marker: ${end}`);
  return source.slice(first, last);
}

// Match the event boundary, not whichever action happens to be dispatched first.
const clickMarker = "  document.addEventListener('click',async e=>{try{";
assert.equal(source.split(clickMarker).length, 2, 'expected one delegated click owner');
const clickSource = between(
  clickMarker,
  "\n  // Native file input remains the accessible fallback",
);

function harness({intent = 'restyle', next = 'edit', pending = true} = {}) {
  const context = {};
  vm.runInNewContext([
    "let listener=null;",
    "const document={addEventListener:(name,handler)=>{if(name==='click')listener=handler;}};",
    `let handoffIntent=${JSON.stringify(intent)},handoffBusy=false,pendingStyle=${pending ? "{file:{name:'look.png'}}" : 'null'};`,
    "let recipeRenders=0;const notices=[];",
    "const handoffRecipes=()=>{recipeRenders++};",
    "const announce=(message,error=false)=>notices.push({message,error});",
    "const q=()=>({close(){},value:'',files:[]});",
    "const chooseIntent=()=>{};const openHandoff=()=>{};const refreshAssets=async()=>{};const openAsset=()=>{};const showView=()=>{};const renderAssets=()=>{};const renderProduction=()=>{};",
    "let assetScope='',productionId=null;const assetSelection={clear(){}};",
    clickSource,
    `const destination={dataset:{uxDestination:${JSON.stringify(next)}}};`,
    "const event={target:{closest:selector=>selector==='[data-ux-destination]'?destination:null}};",
    "this.run=()=>listener(event);",
    "this.state=()=>JSON.stringify({handoffIntent,pending:!!pendingStyle,recipeRenders,notices});",
  ].join('\n'), context);
  return context;
}

test('changing handoff task clears the uncommitted extra picture and explains it', async () => {
  const page = harness();
  await page.run();
  const state = JSON.parse(page.state());
  assert.equal(state.handoffIntent, 'edit');
  assert.equal(state.pending, false);
  assert.equal(state.recipeRenders, 1);
  assert.equal(state.notices.length, 1);
  assert.equal(state.notices[0].error, false);
  assert.match(state.notices[0].message, /not attached/i);
  assert.match(state.notices[0].message, /changed the handoff task/i);
});

test('reselecting the same task retains its extra picture without a warning', async () => {
  const page = harness({next:'restyle'});
  await page.run();
  const state = JSON.parse(page.state());
  assert.equal(state.handoffIntent, 'restyle');
  assert.equal(state.pending, true);
  assert.equal(state.recipeRenders, 1);
  assert.deepEqual(state.notices, []);
});

test('ordinary handoff task changes do not invent a discarded picture', async () => {
  const page = harness({pending:false,next:'repair'});
  await page.run();
  const state = JSON.parse(page.state());
  assert.equal(state.handoffIntent, 'repair');
  assert.equal(state.pending, false);
  assert.equal(state.recipeRenders, 1);
  assert.deepEqual(state.notices, []);
});

test('preset selection calls the hoisted reset directly rather than pretending it is optional', () => {
  assert.doesNotMatch(source, /typeof dismissSecondPicture===['"]function['"]/);
  assert.match(source, /pendingInputs\.clear\(\);dismissSecondPicture\(\);syncCreate\(\);/);
});
