// Prove recovery controls use backend eligibility and explicit resume routes only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
  return {textContent: '', innerHTML: '', disabled: false, value: '', classList: {toggle() {}},
    closest() { return null; }, onclick: null, onchange: null};
}

async function voicePage() {
  const elements = new Map(), requests = [];
  const $ = selector => { if (!elements.has(selector)) elements.set(selector, element()); return elements.get(selector); };
  const project = {id: 'a'.repeat(32), name: 'Interrupted fixture', state: {status: 'interrupted', message: 'Restarted', artifacts: []}, voice_resume: {eligible: true}};
  const context = vm.createContext({document: {querySelector: $}, fetch: async (url, options = {}) => {
    if (options.method === 'POST') requests.push(url);
    return {ok: true, json: async () => url === '/api/voice-baseline' ? {capabilities: {configured: true}, projects: [project]} : {}};
  }, setTimeout() { return 1; }, clearTimeout() {}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/voice.js'), 'utf8'), context);
  await vm.runInContext('refresh()', context);
  assert.match($('#voiceTakes').innerHTML, /data-resume="a{32}"/, 'Voice page exposes only backend-approved resume');
  assert.deepEqual(requests, [], 'Page load never submits or resumes a take');
  const button = {dataset: {resume: project.id}, disabled: false};
  await $('#voiceTakes').onclick({target: {closest: selector => selector === '[data-start],[data-stop],[data-resume]' ? button : null}});
  assert.ok(requests.includes('/api/production/'+project.id+'/resume'), 'Voice resume uses the explicit coordinator route');
}

function productionPage() {
  const elements = new Map(), routes = [];
  const $ = selector => { if (!elements.has(selector)) elements.set(selector, element()); return elements.get(selector); };
  const project = {id: 'b'.repeat(32), name: 'Interrupted fixture', kind: 'voice', stages: [], state: {status: 'interrupted', message: 'Restarted'}, voice_resume: {eligible: true}};
  const context = vm.createContext({$: $, document: {querySelector: $, querySelectorAll: () => []}, esc: value => String(value),
    api: async () => [], post: async url => { routes.push(url); return {}; }, showView() {}, setInterval() {}, blindComparison: false});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/production.js'), 'utf8'), context);
  vm.runInContext(`productionPlans=[${JSON.stringify(project)}];productionId=${JSON.stringify(project.id)};renderProduction();`, context);
  assert.match($('#productionDetail').innerHTML, /Resume unstarted take/, 'Production page exposes backend-approved voice recovery');
  vm.runInContext(`productionPlans=[${JSON.stringify({...project, voice_resume: {eligible: false}})}];renderProduction();`, context);
  assert.doesNotMatch($('#productionDetail').innerHTML, /Resume unstarted take/, 'Production page does not optimistically expose unsafe voice recovery');
}

(async () => { await voicePage(); productionPage(); console.log('Voice recovery controls require backend eligibility and an explicit route.'); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
