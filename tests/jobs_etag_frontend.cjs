// Conditional GET /api/jobs in the browser: 304 keeps jobs/state without a
// re-render, 200 applies the new list, errors never clear the list (#971).
// Real refreshJobs/renderJobs from app/static/app.js; HTTP is stubbed.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const elements = new Map();
const element = s => { if (!elements.has(s)) elements.set(s, { value: '', textContent: '', innerHTML: '', className: '', hidden: false, disabled: false, classList: { toggle() {} }, addEventListener() {} }); return elements.get(s); };
const calls = [];
let handler = async () => { throw Error('no stubbed jobs response'); };
const context = vm.createContext({ document: { querySelector: element, querySelectorAll: () => [], addEventListener() {} },
  window: {}, location: { hash: '' }, URL, Blob, setInterval() {}, sessionStorage: { getItem() { return null; } },
  crypto: { randomUUID: () => 'request-stub' },
  fetch: async (url, options = {}) => { if (url === '/api/catalog') return new Promise(() => {}); calls.push({ url, options }); return handler(url, options); } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8'), context);
const run = s => vm.runInContext(s, context);
const header = value => ({ get: name => String(name).toLowerCase() === 'etag' ? value : null });
const jobs200 = (list, etag) => ({ status: 200, ok: true, headers: header(etag), json: async () => JSON.parse(JSON.stringify(list)) });
const notModified = etag => ({ status: 304, ok: false, headers: header(etag), json: async () => { throw Error('304 carries no body and must never be parsed as JSON'); } });
const failed = () => ({ status: 500, ok: false, headers: header(null), json: async () => ({ error: 'ComfyUI did not return' }) });
const jobA = { id: 'job-a', status: 'running', preset_name: 'Demo', message: 'Generating output 1 of 1', prompt_ids: [], outputs: [], submissions: [] };
const jobADone = { ...jobA, status: 'completed', message: 'Complete' };
(async () => {
  run('jobs=[];jobsDataSignature="";jobsSignature="";activeJobId=null;jobsEtag=null;');
  run('let renderCalls=0;const origRenderJobs=renderJobs;renderJobs=(signature)=>{renderCalls++;return origRenderJobs(signature);}');
  // First load sends no validator and applies the list.
  handler = async () => jobs200([jobA], '"etag-a"');
  await run('refreshJobs()');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/jobs');
  assert.ok(!calls[0].options.headers, 'first load sends no If-None-Match');
  assert.deepEqual(run('jobs'), [jobA]);
  assert.equal(run('jobsEtag'), '"etag-a"');
  assert.equal(run('jobsDataSignature'), JSON.stringify([jobA]));
  assert.equal(run('renderCalls'), 1);
  // An unchanged poll answers 304: jobs, signatures, rendered output and
  // active state stay put, with no duplicate render and no JSON parse.
  run('activeJobId="job-a";');
  const before = run('JSON.stringify(jobs)'), signature = run('jobsSignature'), gallery = element('#gallery').innerHTML;
  handler = async () => notModified('"etag-a"');
  await run('refreshJobs()');
  assert.equal(calls.length, 2);
  assert.equal(calls[1].options.headers['If-None-Match'], '"etag-a"');
  assert.equal(run('JSON.stringify(jobs)'), before, '304 must not touch the job list');
  assert.equal(run('jobsSignature'), signature, '304 must not re-render');
  assert.equal(run('renderCalls'), 1, '304 must not duplicate a render');
  assert.equal(element('#gallery').innerHTML, gallery);
  assert.equal(run('activeJobId'), 'job-a', '304 keeps the active job');
  assert.equal(run('jobsEtag'), '"etag-a"');
  assert.equal(element('#status').textContent, '', '304 must never surface as a parse error');
  // A changed list still updates jobs, signatures, message and active state.
  handler = async () => jobs200([jobADone], '"etag-b"');
  await run('refreshJobs()');
  assert.equal(calls[2].options.headers['If-None-Match'], '"etag-a"');
  assert.deepEqual(run('jobs'), [jobADone]);
  assert.equal(run('jobsEtag'), '"etag-b"');
  assert.equal(run('renderCalls'), 2);
  assert.equal(element('#status').textContent, 'Demo: Complete');
  assert.equal(run('activeJobId'), null, 'a terminal job clears the active job');
  // An HTTP error keeps the last good list and its validator.
  handler = async () => failed();
  await run('refreshJobs()');
  assert.deepEqual(run('jobs'), [jobADone], 'an error must not clear the job list');
  assert.equal(run('jobsEtag'), '"etag-b"', 'an error keeps the last validator');
  assert.match(element('#status').textContent, /ComfyUI did not return/);
  assert.equal(run('renderCalls'), 2, 'an error must not render');
  // Without a usable ETag the browser falls back to ordinary 200 handling.
  handler = async () => jobs200([jobADone], null);
  await run('refreshJobs()');
  assert.deepEqual(run('jobs'), [jobADone]);
  assert.equal(run('jobsEtag'), null);
  handler = async (url, options = {}) => { assert.ok(!options.headers, 'no validator means no If-None-Match'); return jobs200([jobADone], '"etag-c"'); };
  await run('refreshJobs()');
  assert.equal(run('jobsEtag'), '"etag-c"');
  console.log('Conditional job polling preserves state on 304 and still applies 200 changes.');
})().catch(error => { console.error(error); process.exitCode = 1; });
