/* An ephemeral, read-only setting proposal. Graph values remain owned by the editor. */
(function () {
  'use strict';
  const W = window.WorkflowStudio, builder = document.getElementById('builder');
  if (!W || !builder) return;
  const LIMIT = 1048576, MAX_TARGETS = 32, enc = new TextEncoder();
  const clone = value => JSON.parse(JSON.stringify(value));
  const el = (tag, text, attrs = {}) => {
    const node = document.createElement(tag); if (text !== null) node.textContent = text;
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const button = (text, id, fn) => { const node = el('button', text, {type:'button', id}); node.onclick = fn; return node; };
  const label = (text, control) => { const node = el('label', text); node.append(control); return node; };
  function safe(value) {
    if (typeof value === 'number' && (!Number.isFinite(value) || Number.isInteger(value) && !Number.isSafeInteger(value)))
      throw Error('This value exceeds the browser safe integer or finite-number range. Use the Python SDK for wide integers.');
    if (value && typeof value === 'object') Object.values(value).forEach(safe);
  }
  /* Only literals this browser could carry back into the graph are held to the safe-integer rule.
     Installed schemas routinely declare bounds beyond 2^53 (a seed's max is 0xffffffffffffffff),
     and the reply echoes them as targets[].minimum/maximum/step_hint and interface.minimum/maximum.
     Guarding the whole reply refused valid proposals and blamed the user's value for a schema bound. */
  function safeValues(result) {
    safe(result.value); safe(result.commands);
    if (Array.isArray(result.targets)) for (const target of result.targets) safe(target.current);
    if (result.interface) safe(result.interface.choices);
  }
  const panel = el('details', null, {id:'controlPreviewPanel', class:'wf-panel wf-control-preview'});
  panel.append(el('summary', 'Preview a shared setting across nodes'));
  const body = el('div', null, {class:'wf-control-body'});
  body.append(el('h3', 'One setting, explicit targets'), el('p', 'Choose the inputs to change together and inspect the proposal. This panel never applies, saves or runs it.'));
  const name = el('input', null, {id:'controlName', maxlength:'120', value:'Shared setting'});
  body.append(label('Setting name', name));
  const picks = el('div', null, {class:'wf-control-picks'});
  const nodeChoice = el('select', null, {id:'controlTargetNode'}), inputChoice = el('select', null, {id:'controlTargetInput'});
  const targets = [], list = el('ol', null, {id:'controlTargets', 'aria-label':'Ordered setting targets'});
  const valueHost = el('div'), output = el('section', null, {id:'controlPreviewResult', 'data-state':'empty', 'aria-label':'Setting proposal'});
  const status = el('p', 'Open a workflow and load its installed nodes, then choose targets.', {id:'controlPreviewStatus', role:'status'});
  const submit = button('Preview shared setting', 'controlPreviewButton', preview); submit.disabled = true;
  const add = button('Add target', 'controlAddTarget', addTarget);
  picks.append(label('Node', nodeChoice), label('Input', inputChoice), add);
  body.append(picks, list, valueHost, submit, status, output); panel.append(body); builder.append(panel);
  let stamp = 0, flight = null, valueInput = null, valueType = null, valueChoices = [], valueSpec = '';
  function say(text) { status.textContent = text; }
  function invalidate(message = 'Proposal changed. Preview again to inspect the current values.') {
    stamp++; flight?.abort(); flight = null;
    output.replaceChildren(); output.dataset.state = 'stale'; submit.disabled = !targets.length || !valueInput;
    say(message);
  }
  function specs(nodeId) {
    const node = W.snapshot()?.nodes?.[nodeId];
    return node ? W.schema()?.nodes?.[node.class_type]?.inputs || [] : [];
  }
  function fillInputs() {
    const before = inputChoice.value, fields = specs(nodeChoice.value);
    inputChoice.replaceChildren();
    for (const field of fields.slice(0,256)) {
      if (typeof field.name !== 'string' || field.hidden) continue;
      inputChoice.append(el('option', field.name + ' · ' + field.type, {value:field.name}));
    }
    if ([...inputChoice.options].some(o => o.value === before)) inputChoice.value = before;
    if (!inputChoice.options.length) inputChoice.append(el('option', 'No visible installed inputs', {value:''}));
    add.disabled = !nodeChoice.value || !inputChoice.value || targets.length >= MAX_TARGETS;
    if (fields.length > 256) say('Only the first 256 input definitions are shown. Use the SDK for other explicitly supported inputs.');
  }
  function fillNodes() {
    const before = nodeChoice.value, doc = W.snapshot(), schema = W.schema();
    nodeChoice.replaceChildren();
    if (doc && schema) for (const [id, node] of Object.entries(doc.nodes).slice(0,256)) {
      nodeChoice.append(el('option', id + ' · ' + (schema.nodes?.[node.class_type]?.name || node.class_type), {value:id}));
    }
    if ([...nodeChoice.options].some(o => o.value === before)) nodeChoice.value = before;
    if (!nodeChoice.options.length) nodeChoice.append(el('option', 'Open a workflow and load nodes first', {value:''}));
    fillInputs();
  }
  function renderValue() {
    valueHost.replaceChildren(); valueType = null; valueChoices = []; valueInput = null;
    const first = targets[0], spec = first && specs(first.node).find(s => s.name === first.input);
    valueSpec = JSON.stringify(spec || null);
    if (!first) return;
    valueType = spec?.type;
    if (valueType === 'BOOLEAN') valueInput = el('input', null, {id:'controlProposedValue', type:'checkbox'});
    else if (valueType === 'COMBO' && Array.isArray(spec.options?.options) && spec.options.options.length <= 256) {
      try { safe(spec.options.options); }
      catch (error) { valueHost.append(el('p',error.message)); submit.disabled = true; return; }
      valueInput = el('select', null, {id:'controlProposedValue'}); valueChoices = clone(spec.options.options);
      for (const [i, value] of valueChoices.entries()) valueInput.append(el('option',
        typeof value === 'number' && Number.isInteger(value) ? 'Numeric choice (use SDK to preserve its type)' : JSON.stringify(value), {value:String(i)}));
    } else if (valueType === 'STRING') valueInput = el('textarea', null, {id:'controlProposedValue', rows:'4', maxlength:'65536'});
    else if (['INT','FLOAT'].includes(valueType)) valueInput = el('input', null, {id:'controlProposedValue', type:'text', inputmode:'decimal'});
    else { valueHost.append(el('p', 'This input needs a native or custom adapter. Choose a supported scalar input for a shared value.')); submit.disabled = true; return; }
    valueInput.oninput = () => invalidate(); valueInput.onchange = () => invalidate();
    valueHost.append(label(valueType === 'BOOLEAN' ? 'Proposed value (checked means true)' : 'Proposed value', valueInput));
    valueHost.append(el('small', 'The server checks every target. Different current values remain visible as mixed; no value is copied automatically.'));
  }
  function renderTargets() {
    list.replaceChildren();
    targets.forEach((target, index) => {
      const row = el('li'), title = target.node + '.' + target.input;
      const remove = button('Remove', 'controlRemove-' + index, () => {
        targets.splice(index,1); invalidate('Target removed. Nothing was applied.'); if (index === 0) renderValue(); renderTargets(); fillInputs();
        add.focus();
      });
      remove.setAttribute('aria-label','Remove target ' + title);
      row.append(el('span',title),remove); list.append(row);
    });
    submit.disabled = !targets.length || !!flight || !valueInput;
  }
  function addTarget() {
    const target = {node:nodeChoice.value,input:inputChoice.value};
    if (!target.node || !target.input) return say('Choose an installed node input first.');
    if (targets.some(t => t.node === target.node && t.input === target.input)) return say('This target is already selected.');
    if (targets.length >= MAX_TARGETS) return say('Use at most 32 targets.');
    targets.push(target); invalidate('Target added. Preview to inspect the complete proposal.');
    if (targets.length === 1) renderValue(); renderTargets(); fillInputs();
  }
  function proposedValue() {
    if (!valueInput) throw Error('Choose a supported scalar input first.');
    if (valueType === 'BOOLEAN') return valueInput.checked;
    if (valueType === 'STRING') return valueInput.value;
    if (valueType === 'COMBO') {
      if (valueInput.value === '') throw Error('Choose a proposed value.');
      const value = valueChoices[Number(valueInput.value)]; safe(value);
      if (typeof value === 'number' && Number.isInteger(value))
        throw Error('Integral numeric choices cannot preserve int versus float in this browser. Use the Python SDK for that choice.');
      if (!['string','boolean','number'].includes(typeof value)) throw Error('Custom choices need a native adapter.');
      return value;
    }
    const text = valueInput.value.trim();
    if (!(valueType === 'INT' ? /^[+-]?\d+$/ : /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i).test(text))
      throw Error('Enter a ' + (valueType === 'INT' ? 'whole number' : 'finite number') + ' without units.');
    const value = Number(text); safe(value); return value;
  }
  async function readJSON(response) {
    const reader = response.body?.getReader();
    if (!reader) throw Error('A bounded response stream is required.');
    const chunks = []; let length = 0;
    try {
      while (true) {
        const part = await reader.read(); if (part.done) break;
        length += part.value.byteLength;
        if (length > LIMIT) { await reader.cancel(); throw Error('The preview response exceeds 1 MiB. Use fewer targets or shorter text.'); }
        chunks.push(part.value);
      }
    } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk,offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
  }
  function show(value) {
    output.replaceChildren(); output.dataset.state = value.state;
    output.append(el('h4', value.state === 'ready' ? 'Proposal ready to inspect' : 'Proposal needs changes'),
      el('p',value.mixed ? 'Mixed current values — each target is shown below.' : 'Current values match across these targets.'));
    const text = value => { const full = JSON.stringify(value); return full.length > 1200 ? full.slice(0,1200) + '… (display shortened)' : full; };
    for (const target of value.targets) {
      const row = el('article', null, {'data-target':target.node + '.' + target.input});
      row.append(el('strong',target.node + '.' + target.input),el('p','Current: ' + (target.present ? text(target.current) : '(not set)')),
        el('p','Proposed: ' + text(value.value))); output.append(row);
    }
    for (const diagnostic of value.diagnostics) output.append(el('p',(diagnostic.node ? diagnostic.node + '.' + diagnostic.input + ': ' : '') + diagnostic.message));
    if (value.interface.minimum !== null || value.interface.maximum !== null)
      output.append(el('p','Shared range: ' + (value.interface.minimum ?? 'unbounded') + ' to ' + (value.interface.maximum ?? 'unbounded')));
    if (value.interface.choices !== null) output.append(el('p','Shared choices: ' + text(value.interface.choices)));
    output.append(el('p',value.commands.length ? value.commands.length + ' proposed input changes. Nothing applied or queued.' : 'No commands proposed. Nothing applied or queued.'));
    const exact = el('details'); exact.append(el('summary','Inspect exact proposed commands'));
    exact.addEventListener('toggle', () => {
      if (exact.open && !exact.querySelector('pre')) exact.append(el('pre',JSON.stringify(value.commands,null,2)));
    });
    output.append(exact,el('small',value.notice));
  }
  async function preview() {
    if (flight) return;
    let controller = null, token, timer;
    try {
      const doc = W.snapshot(); if (!doc || !W.schema()) throw Error('Open a workflow and load its installed nodes first.');
      safe(doc); if (!targets.length) throw Error('Choose at least one target.');
      if (!name.value.trim()) throw Error('Give the setting a name.');
      const value = proposedValue(), control = {format:'studio.control/v1',name:name.value,targets:clone(targets)};
      const payload = {document:doc,expected_revision:doc.revision,control,value};
      const source = JSON.stringify(doc), epoch = W.epoch(), body = JSON.stringify(payload);
      if (enc.encode(body).length > LIMIT) throw Error('The preview request exceeds 1 MiB. Use fewer targets or shorter text.');
      invalidate('Checking the proposal without applying it…'); token = stamp;
      controller = flight = new AbortController(); submit.disabled = true;
      timer = setTimeout(() => controller.abort(),15000);
      const response = await fetch('/api/workflow-studio/control-preview',{method:'POST',headers:{'Content-Type':'application/json'},body,signal:controller.signal});
      const result = await readJSON(response);
      if (token !== stamp) return;
      if (epoch !== W.epoch() || source !== JSON.stringify(W.snapshot())) return invalidate('The draft changed. Preview the current values again.');
      if (!response.ok) throw Error(result.error || 'Preview request failed (HTTP ' + response.status + ').');
      safeValues(result);
      if (result.format !== 'studio.control-preview/v1' || !['ready','blocked'].includes(result.state) ||
          result.committed !== false || result.generation_submitted !== false || result.document_revision !== doc.revision ||
          result.backend_id !== doc.backend_id || result.schema_sha256 !== doc.schema_sha256 ||
          result.control?.format !== control.format || result.control?.name !== control.name ||
          !Array.isArray(result.control?.targets) || result.control.targets.length !== control.targets.length ||
          result.control.targets.some((item,i) => item.node !== control.targets[i].node || item.input !== control.targets[i].input) || JSON.stringify(result.value) !== JSON.stringify(value) ||
          !Array.isArray(result.targets) || result.targets.length !== targets.length || !Array.isArray(result.diagnostics) ||
          !Array.isArray(result.commands) || !result.interface ||
          result.targets.some((item,i) => item.node !== control.targets[i].node || item.input !== control.targets[i].input || typeof item.present !== 'boolean') ||
          (result.state === 'blocked' ? result.commands.length !== 0 :
            result.diagnostics.length !== 0 || result.commands.length !== control.targets.length || result.commands.some((cmd,i) =>
              cmd.op !== 'set_input' || cmd.id !== control.targets[i].node || cmd.input !== control.targets[i].input || JSON.stringify(cmd.value) !== JSON.stringify(value)))) throw Error('The server returned an incompatible or stale preview. Nothing was applied.');
      show(result); say('Preview only. Review every target; apply and execution are not available here.');
    } catch (error) {
      if (token !== undefined && token !== stamp) return;
      output.replaceChildren(); output.dataset.state = 'error';
      say(error.name === 'AbortError' ? 'Preview timed out. Nothing was applied; no request was retried.' : error.message);
    } finally {
      clearTimeout(timer);
      if (flight === controller) { flight = null; submit.disabled = !targets.length || !valueInput; }
    }
  }
  nodeChoice.onchange = fillInputs;
  name.oninput = () => invalidate();
  document.addEventListener('workflow:render', () => {
    invalidate('The workflow changed. Preview again before using any proposal.'); fillNodes();
    const first = targets[0], spec = first && specs(first.node).find(s => s.name === first.input);
    if (JSON.stringify(spec || null) !== valueSpec) { renderValue(); renderTargets(); }
  });
  document.addEventListener('workflow:replace', () => { targets.length = 0; invalidate('Another workflow was opened. Choose its targets explicitly.'); renderValue(); renderTargets(); fillNodes(); });
  window.addEventListener('pagehide', () => { stamp++; flight?.abort(); });
  panel.addEventListener('toggle', () => { if (panel.open) fillNodes(); });
  fillNodes(); // Editor/schema reads only; no HTTP, saving or model work on load.
})();
