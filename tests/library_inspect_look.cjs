// Library look checks (#1703): Sizes / Mirror / Greyscale are display-only toggles on the open still image.
// Runs the actual workspace.js with an inert DOM; the stylesheet rules are read from asset-family.css.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const read = file => fs.readFileSync(path.join(__dirname, '../app/static', file), 'utf8');
const css = read('asset-family.css'), html = read('index.html');

function setup() {
  const elements = new Map(), handlers = [], calls = [];
  const el = id => {
    if (!elements.has(id)) elements.set(id, {value: '', open: false, disabled: false, hidden: false, innerHTML: '', textContent: '', dataset: {}, events: {}, classList: {toggle() {}},
      addEventListener(name, fn) {(this.events[name] ??= []).push(fn);},
      emit(name, event = {}) {for (const fn of this.events[name] || []) fn(event);},
      showModal() {this.open = true;}, close() {this.open = false; this.emit('close');}, focus() {}, scrollIntoView() {}});
    return elements.get(id);
  };
  const context = vm.createContext({console, AbortController, Set, JSON, Date, crypto: require('node:crypto').webcrypto,
    sessionStorage: {getItem: () => null, setItem() {}, removeItem() {}}, localStorage: undefined,
    StudioAssetGrid: {render() {}}, $: el, esc: value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])),
    window: {confirm: () => true}, document: {querySelectorAll: () => [], addEventListener(name, fn, capture) {handlers.push({name, fn, capture});}},
    setTimeout: () => 1, clearTimeout() {}, api: async (url, options = {}) => {calls.push([url, options.method || 'GET']); return new Promise(() => {});},
    fetch: () => {calls.push(['fetch']); throw Error('no fetch');}, message() {}, renderJobs() {}, jobsSignature: '', jobs: []});
  const run = code => vm.runInContext(code, context);
  run(read('asset-recovery.js')); run(read('workspace.js'));
  run(`refreshAssets=async()=>{};assetState.workspace_id='1'.repeat(32);assetState.assets=[
    {id:'a',title:'A',media_type:'image',url:'/files/a.png?x=1&privacy=private',review:'selected',tags:[],source:{},lineage:[],bytes:1,metadata_revision:0},
    {id:'b',title:'B',media_type:'image',url:'/files/b.png',review:'unreviewed',tags:[],source:{},lineage:[],bytes:1,metadata_revision:0},
    {id:'v',title:'V',media_type:'video',url:'/files/v.mp4',review:'unreviewed',tags:[],source:{},lineage:[],bytes:1,metadata_revision:0}
  ].map(a=>({...a,workspace_id:assetState.workspace_id}));`);
  const click = key => el('#assetDialog').emit('click', {target: {closest: sel => sel === '[data-asset-look]' ? {dataset: {assetLook: key}} : null}});
  return {el, run, calls, click, panel: () => el('#assetInspect').innerHTML, dialog: () => el('#assetDialog').dataset};
}
const pressed = (s, key) => new RegExp('data-asset-look="' + key + '" aria-pressed="true"').test(s.panel());
const cssRule = selector => css.split('}').find(rule => rule.includes(selector)) || '';

test('Mirror and Greyscale set and clear the display flags the stylesheet turns into scaleX(-1) and grayscale(1)', () => {
  const s = setup(); s.run("openAsset('a')");
  assert.equal(s.el('#assetInspect').hidden, false);
  assert.match(s.panel(), /data-asset-look="sizes" aria-pressed="false"/);
  s.click('mirror'); assert.equal(s.dialog().lookMirror, '1'); assert.ok(pressed(s, 'mirror'));
  s.click('grey'); assert.equal(s.dialog().lookGrey, '1'); assert.ok(pressed(s, 'grey'));
  s.click('mirror'); assert.equal('lookMirror' in s.dialog(), false); assert.equal(pressed(s, 'mirror'), false);
  s.click('grey'); assert.equal('lookGrey' in s.dialog(), false);
  assert.match(cssRule('[data-look-mirror] #assetDetailMedia>img'), /transform:scaleX\(-1\)/);
  assert.match(cssRule('[data-look-grey] #assetDetailMedia>img'), /filter:grayscale\(1\)/);
});

test('Sizes shows 64, 128 and 256 px boxes that keep aspect ratio, and Smooth/Pixel map to image-rendering', () => {
  const s = setup(); s.run("openAsset('a')");
  assert.doesNotMatch(s.panel(), /asset-inspect-sizes/);
  s.click('sizes');
  const imgs = [...s.panel().matchAll(/<img src="([^"]+)" alt="" data-px="(\d+)"/g)];
  assert.deepEqual(imgs.map(m => m[2]), ['64', '128', '256']);
  assert.ok(imgs.every(m => m[1] === '/files/a.png?x=1&amp;privacy=private'), 'same media URL the viewer shows, escaped');
  for (const n of [64, 128, 256]) assert.match(cssRule('img[data-px="' + n + '"]'), new RegExp('width:' + n + 'px;height:' + n + 'px'));
  assert.match(cssRule('.asset-inspect-row img{'), /object-fit:contain/, 'a square box with contain keeps the longest side at N px and the ratio');
  assert.match(s.panel(), /data-render="smooth"/); assert.ok(pressed(s, 'smooth'));
  s.click('pixel'); assert.match(s.panel(), /data-render="pixel"/); assert.ok(pressed(s, 'pixel')); assert.equal(pressed(s, 'smooth'), false);
  assert.match(css, /\[data-render="pixel"\] img\{image-rendering:pixelated\}/);
  assert.match(css, /\[data-render="smooth"\] img\{image-rendering:auto\}/);
  s.click('smooth'); assert.match(s.panel(), /data-render="smooth"/);
  s.click('sizes'); assert.doesNotMatch(s.panel(), /asset-inspect-sizes/);
});

test('Toggles reset when another asset opens, and the panel is empty for video and after close', () => {
  const s = setup(); s.run("openAsset('a')");
  s.click('sizes'); s.click('pixel'); s.click('mirror'); s.click('grey');
  s.el('#assetDialog').close(); s.run("openAsset('b')");
  assert.equal('lookMirror' in s.dialog() || 'lookGrey' in s.dialog(), false);
  assert.doesNotMatch(s.panel(), /aria-pressed="true"|asset-inspect-sizes/);
  s.click('mirror'); s.run("openAsset('v')");
  assert.equal(s.el('#assetInspect').hidden, true); assert.equal(s.panel(), ''); assert.equal('lookMirror' in s.dialog(), false);
  s.run("openAsset('a')"); assert.doesNotMatch(s.panel(), /aria-pressed="true"/);
  s.click('grey'); s.el('#assetDialog').close();
  assert.equal(s.panel(), ''); assert.equal('lookGrey' in s.dialog(), false);
});

test('Toggling never issues a request and leaves review, bytes and record untouched', () => {
  const s = setup(); s.run("openAsset('a')");
  const before = s.run('JSON.stringify(assetState.assets[0])'), requests = s.calls.length;
  for (const key of ['sizes', 'pixel', 'smooth', 'mirror', 'grey', 'mirror', 'grey', 'sizes']) s.click(key);
  assert.equal(s.calls.length, requests, 'no api/fetch/POST from the toggles');
  assert.equal(s.run('JSON.stringify(assetState.assets[0])'), before);
  assert.equal(s.run('assetDetailDirty()'), false);
  assert.equal(s.el('#assetReview').value, 'selected');
  s.click('bogus'); s.click('constructor'); assert.equal(s.calls.length, requests);
});

test('Toggle buttons are real buttons with aria-pressed, and the panel is in the dialog markup', () => {
  const s = setup(); s.run("openAsset('a')"); s.click('sizes');
  const buttons = [...s.panel().matchAll(/<button type="button" data-asset-look="(\w+)" aria-pressed="(true|false)">([^<]+)<\/button>/g)];
  assert.deepEqual(buttons.map(m => m[3]), ['Sizes', 'Mirror', 'Greyscale', 'Smooth', 'Pixel']);
  assert.match(html, /<div id="assetInspect" class="asset-inspect" hidden><\/div>/);
});
