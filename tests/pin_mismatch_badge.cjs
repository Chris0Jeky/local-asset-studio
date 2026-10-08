'use strict';
// A health pin_mismatch names files whose cached digest or size differs from the library pin.
// The recipe list has to show that, and Generate stays available: the mismatch is a warning, not a missing file.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    value: '', files: [], textContent: '', className: '', disabled: false, hidden: false, innerHTML: '',
    classList: {toggle() {}}, addEventListener() {}, querySelectorAll() { return []; },
  });
  return elements.get(selector);
}
const context = vm.createContext({
  document: {querySelector: element, querySelectorAll: () => [], addEventListener() {}},
  URL, Blob, location: {hash: ''}, setInterval() {},
  fetch: () => new Promise(() => {}),
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
vm.runInContext(`
catalog={presets:[
  {id:'wai',name:'WAI',description:'portrait',family:'Illustrious',category:'Anime',verified:true},
  {id:'plain',name:'Plain',description:'words',family:'SDXL',category:'General',verified:false}
]};
selected=catalog.presets[0];
mode='all';
$('#presetSearch').value='';
$('#categorySelect').value='All';
api=async()=>({online:true,worker_alive:true,schema_available:true,missing_models:{},pin_mismatch:{wai:['loras/pinned.safetensors']}});
`, context);
vm.runInContext('refreshHealth()', context).then(() => {
  const html = element('#presetList').innerHTML;
  assert.match(html, /data-id="wai"[\s\S]*Checksum differs/);
  assert.match(html, /loras\/pinned\.safetensors/);
  assert.doesNotMatch(html, /data-id="plain"[\s\S]*Checksum differs/);
  assert.equal(element('#generate').disabled, false, 'a pin mismatch warns and does not block Generate');
  console.log('pin mismatch badge passed');
}).catch(error => { console.error(error); process.exitCode = 1; });
