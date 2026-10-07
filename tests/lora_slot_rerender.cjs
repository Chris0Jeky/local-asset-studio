'use strict';
// A recorded LoRA file added to the select must survive renderLoraSlots rebuilding the options.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const elements = new Map();
const loraBox = {
  hidden: false, innerHTML: '',
  _selects: [{dataset: {key: 'lora_name'}, value: 'recorded-only.safetensors'}],
  querySelectorAll() { return this._selects; },
};
function element(selector) {
  if (selector === '#loraSlots') return loraBox;
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
  navigator: {clipboard: {writeText: async () => {}}},
});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
vm.runInContext("selected={id:'wai',lora_name:['8','lora_name'],defaults:{lora_name:'authored.safetensors'},choices:{}};installedLoras=['authored.safetensors','other.safetensors'];renderLoraSlots();", context);
assert.match(loraBox.innerHTML, /recorded-only\.safetensors/);
console.log('lora slot rerender passed');
