/* API-graph authoring, never a hidden Comfy executor. All schema text is inert. */
(function () {
  'use strict';
  const $ = s => document.querySelector(s), API = '/api/workflow-studio';
  const KEY = 'studio.workflow.draft.v1', MAX = Number.MAX_SAFE_INTEGER;
  let schema = null, doc = null, selected = null, checked = null, undo = [], redo = [], epoch = 0, schemaEpoch = 0;
  const clone = value => JSON.parse(JSON.stringify(value));
  const isLink = value => Array.isArray(value) && value.length === 2 && typeof value[0] === 'string' && Number.isInteger(value[1]);
  const match = (a, b) => a.split(',').map(x => x.trim()).some(x => x === '*' || b.split(',').map(y => y.trim()).includes(x)) || b === '*';
  function el(tag, text, attrs = {}) { const item = document.createElement(tag); if (text !== null) item.textContent = text; for (const [k, v] of Object.entries(attrs)) item.setAttribute(k, v); return item; }
  function button(text, action) { const b = el('button', text, {type: 'button'}); b.onclick = action; return b; }
  function status(message) { $('#workflowStatus').textContent = message; }
  function safeNumbers(value) {
    if (typeof value === 'number' && (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value)))) throw Error('This document contains an integer outside the browser’s exact range. Use the Python CLI to preserve it, or deliberately choose a smaller seed in the source. Nothing was imported.');
    if (value && typeof value === 'object') for (const [key, child] of Object.entries(value)) {
      if (['__proto__', 'constructor', 'prototype'].includes(key)) throw Error('Reserved object key refused');
      safeNumbers(child);
    }
  }
  async function api(path, data) {
    const response = await fetch(API + path, data === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Studio request failed');
    return result;
  }
  function guard(fn) { return async () => { try { await fn(); } catch (error) { status(error.message); } }; }
  function persist() { try { localStorage.setItem(KEY, JSON.stringify(doc)); } catch (_) { status('Draft changed, but browser storage is unavailable or full. Save a document file before leaving.'); } }
  function changed(next, record = true) {
    safeNumbers(next);
    if (record && doc) { undo.push(clone(doc)); while (undo.length > 30 || JSON.stringify(undo).length > 4 * 1024 * 1024) undo.shift(); redo = []; }
    next.revision = (doc?.revision ?? next.revision ?? 0) + 1;
    if (checked) status('Draft changed. Check connections again before exporting.');
    doc = next; epoch++; checked = null;
    if (!doc.nodes[selected]) selected = Object.keys(doc.nodes)[0] || null;
    persist(); render();
  }
  function edit(action) { const next = clone(doc); action(next); changed(next); }
  function replace(next) { safeNumbers(next); document.dispatchEvent(new Event('workflow:replace')); undo = []; redo = []; doc = null; selected = null; camera = null; changed(next, false); status('Draft loaded. Check connections before exporting. Nothing was queued.'); }
  function discard() { return !doc || window.confirm('Replace the current draft? Save a document file first to keep it.'); }
  function download(name, value) { const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + '\n'], {type: 'application/json'})); const a = el('a', '', {href: url, download: name}); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  function defaultValue(spec) {
    if ('default' in spec.options) return clone(spec.options.default);
    if (spec.widget === 'combo') return spec.options.options[0];
    if (spec.type === 'BOOLEAN') return false;
    if (spec.type === 'STRING') return '';
    if (['INT', 'FLOAT'].includes(spec.type)) return spec.options.min || 0;
    return undefined;
  }
  function addNode(kind) {
    if (!doc) replace({format: 'studio.workflow/v1', name: 'Untitled workflow', revision: 0, backend_id: schema.backend_id, schema_sha256: schema.schema_sha256, nodes: {}, outputs: [], disabled: [], bypass: {}, positions: {}});
    if (Object.keys(doc.nodes).length >= 256) return status('This authoring slice supports at most 256 nodes.');
    let id = 1; while (doc.nodes[String(id)]) id++;
    selected = String(id);
    const inputs = {};
    for (const spec of kind.inputs) if (spec.required && !spec.hidden && spec.widget !== 'unsupported' && spec.widget !== 'socket') {
      const value = defaultValue(spec); if (value !== undefined) inputs[spec.name] = value;
    }
    edit(next => { next.nodes[selected] = {class_type: kind.class_type, inputs}; if (kind.output_node) next.outputs.push(selected); });
  }
  function nodeCatalog() {
    const host = $('#nodeCatalog'); host.replaceChildren();
    if (!schema) return;
    const q = $('#nodeSearch').value.toLowerCase(), all = Object.values(schema.nodes);
    const list = all.filter(n => [n.class_type, n.name, n.category].join(' ').toLowerCase().includes(q));
    $('#nodeCount').textContent = `${list.length} matching / ${all.length} installed classes · showing at most 100`;
    for (const kind of list.slice(0, 100)) {
      const b = button('+ ' + kind.name, guard(() => addNode(kind)));
      b.append(el('small', kind.category + (kind.unsupported ? ' · native adapter needed' : ''))); host.append(b);
    }
  }
  async function loadSchema(refresh = false) {
    const request = ++schemaEpoch; checked = null; render();
    const result = await api(refresh ? '/nodes/refresh' : '/nodes', refresh ? {} : undefined);
    if (request !== schemaEpoch) return;
    schema = result;
    $('#schemaState').textContent = `${schema.backend_id} · ${Object.keys(schema.nodes).length} node classes`;
    nodeCatalog(); render();
    status(doc && doc.schema_sha256 !== schema.schema_sha256 ? 'Node definitions changed. Review the draft and explicitly accept the refreshed schema; compilation remains blocked until then.' : 'Installed nodes loaded. No model job was submitted.');
  }
  function position(id, index) { return doc.positions[id] || [30 + (index % 3) * 285, 28 + Math.floor(index / 3) * 130]; }
  const NODE_W = 245, NODE_H = 82, ZOOM_MIN = 0.4, ZOOM_MAX = 2.5, PAD = 44;
  let camera = null, bounds = null;
  const zoomClamp = (value, floor = ZOOM_MIN) => Math.min(ZOOM_MAX, Math.max(floor, value)), tidy = n => Math.round(n * 100) / 100;
  function canvasBox() { const rect = $('#workflowCanvas').getBoundingClientRect(); return [Math.max(1, rect.width), Math.max(1, rect.height)]; }
  function applyCamera() {
    if (!camera) return;
    const [w, h] = canvasBox();
    $('#workflowCanvas').setAttribute('viewBox', `${tidy(camera.x)} ${tidy(camera.y)} ${tidy(w / camera.scale)} ${tidy(h / camera.scale)}`);
    $('#canvasZoom').textContent = Math.round(camera.scale * 100) + '%';
  }
  function fitCanvas() {
    if (!bounds) return;
    const [w, h] = canvasBox(), bw = bounds[2] - bounds[0] + PAD * 2, bh = bounds[3] - bounds[1] + PAD * 2;
    const scale = zoomClamp(Math.min(w / bw, h / bh), 0.01); // Fit must frame every node, so it may go below the interactive floor.
    camera = {scale, x: (bounds[0] + bounds[2]) / 2 - w / scale / 2, y: (bounds[1] + bounds[3]) / 2 - h / scale / 2}; applyCamera();
  }
  function resetCanvas() { if (!bounds) return; camera = {scale: 1, x: bounds[0] - PAD, y: bounds[1] - PAD}; applyCamera(); }
  function perPixel() { return camera ? 1 / camera.scale : 1; }
  function diagram() {
    const svg = $('#workflowCanvas'); svg.replaceChildren();
    const ns = 'http://www.w3.org/2000/svg';
    const se = (tag, attrs, text) => { const n = document.createElementNS(ns, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); if (text !== undefined) n.textContent = text; return n; };
    if (!doc) { bounds = null; return; }
    const ids = Object.keys(doc.nodes), positions = Object.fromEntries(ids.map((id, i) => [id, position(id, i)]));
    const spots = Object.values(positions);
    bounds = spots.length ? [Math.min(...spots.map(p => p[0])), Math.min(...spots.map(p => p[1])), Math.max(...spots.map(p => p[0])) + NODE_W, Math.max(...spots.map(p => p[1])) + NODE_H] : [0, 0, 900, 560];
    const curve = (a, b) => `M${a[0] + NODE_W},${a[1] + 40} C${a[0] + NODE_W + 40},${a[1] + 40} ${b[0] - 35},${b[1] + 40} ${b[0]},${b[1] + 40}`;
    const edges = [];
    for (const [id, node] of Object.entries(doc.nodes)) for (const [field, value] of Object.entries(node.inputs)) if (isLink(value) && positions[value[0]]) {
      const line = se('path', {d: curve(positions[value[0]], positions[id]), class: 'wf-edge'});
      line.append(se('title', {}, `${value[0]}:${value[1]} → ${id}.${field}`)); edges.push([line, value[0], id]); svg.append(line);
    }
    for (const id of ids) {
      const node = doc.nodes[id], [x, y] = positions[id];
      const group = se('g', {transform: `translate(${x},${y})`, tabindex: '0', role: 'button', 'aria-label': `Edit node ${id}: ${node.class_type}`});
      group.append(se('rect', {width: String(NODE_W), height: String(NODE_H), rx: '10', fill: doc.disabled.includes(id) ? '#252831' : '#1b3030', stroke: selected === id ? 'var(--wf-accent)' : '#4a6572', 'stroke-width': selected === id ? '3' : '1'}));
      group.append(se('text', {x: '13', y: '29'}, `${id} · ${node.class_type.slice(0, 26)}`));
      group.append(se('text', {x: '13', y: '56', opacity: '.7'}, doc.disabled.includes(id) ? 'Disabled · explicit bypass only' : doc.outputs.includes(id) ? 'Selected output' : 'Configure inputs →'));
      const choose = () => { selected = id; render(); if (matchMedia('(max-width:1350px)').matches) $('#nodeInspector').scrollIntoView({block: 'nearest'}); };
      group.onclick = choose; group.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } };
      const redraw = (nx, ny) => { for (const [line, from, to] of edges) if (from === id || to === id) line.setAttribute('d', curve(from === id ? [nx, ny] : positions[from], to === id ? [nx, ny] : positions[to])); };
      let drag = null;
      group.onpointerdown = e => { if (e.button !== 0) return; drag = [e.clientX, e.clientY]; group.setPointerCapture(e.pointerId); e.stopPropagation(); };
      group.onpointermove = e => { if (!drag) return; const per = perPixel(), nx = Math.max(0, x + (e.clientX - drag[0]) * per), ny = Math.max(0, y + (e.clientY - drag[1]) * per); group.setAttribute('transform', `translate(${nx},${ny})`); redraw(nx, ny); };
      group.onpointerup = e => { if (!drag) return; const start = drag; drag = null; if (Math.abs(e.clientX - start[0]) + Math.abs(e.clientY - start[1]) < 5) return choose(); const per = perPixel(); selected = id; edit(next => { next.positions[id] = [Math.min(100000, Math.max(0, Math.round(x + (e.clientX - start[0]) * per))), Math.min(100000, Math.max(0, Math.round(y + (e.clientY - start[1]) * per)))]; }); };
      group.onpointercancel = () => { drag = null; group.setAttribute('transform', `translate(${x},${y})`); redraw(x, y); };
      svg.append(group);
    }
    if (camera) applyCamera(); else fitCanvas();
  }
  function canvasNavigation() {
    const svg = $('#workflowCanvas'); let pan = null;
    svg.addEventListener('pointerdown', e => { if (e.button !== 0 || !camera || e.target.closest('g')) return; pan = [e.clientX, e.clientY, camera.x, camera.y]; svg.setPointerCapture(e.pointerId); svg.classList.add('wf-panning'); });
    svg.addEventListener('pointermove', e => { if (!pan || !camera) return; const per = perPixel(); camera = {scale: camera.scale, x: pan[2] - (e.clientX - pan[0]) * per, y: pan[3] - (e.clientY - pan[1]) * per}; applyCamera(); });
    const stop = () => { pan = null; svg.classList.remove('wf-panning'); };
    svg.addEventListener('pointerup', stop); svg.addEventListener('pointercancel', stop);
    svg.addEventListener('wheel', e => {
      if (!e.ctrlKey || !camera) return; // A plain wheel keeps scrolling the page, exactly as before.
      e.preventDefault();
      const rect = svg.getBoundingClientRect(), fx = e.clientX - rect.left, fy = e.clientY - rect.top;
      const wx = camera.x + fx * perPixel(), wy = camera.y + fy * perPixel(), scale = zoomClamp(camera.scale * Math.exp(-e.deltaY * 0.0018), Math.min(ZOOM_MIN, camera.scale));
      camera = {scale, x: wx - fx / scale, y: wy - fy / scale}; applyCamera();
    }, {passive: false});
    if (window.ResizeObserver) new ResizeObserver(() => applyCamera()).observe(svg);
    $('#canvasFit').onclick = fitCanvas; $('#canvasReset').onclick = resetCanvas;
  }
  function renderNodeList() {
    // One compact selector, not a second copy of the diagram: the canvas is the node list on wide screens.
    const host = $('#workflowNodes'); host.replaceChildren();
    if (!doc || !Object.keys(doc.nodes).length) return;
    const label = el('label', 'Jump to node'), select = el('select', null, {id: 'workflowNodeSelect'});
    for (const [id, node] of Object.entries(doc.nodes)) select.append(el('option', `${id} · ${node.class_type}`, {value: id}));
    select.value = selected && doc.nodes[selected] ? selected : '';
    select.onchange = () => { if (!doc.nodes[select.value]) return; selected = select.value; render(); $('#nodeInspector').scrollIntoView({block: 'nearest'}); };
    label.append(select); host.append(label);
  }
  function checkbox(text, checkedValue, fn) { const label = el('label', null, {class: 'wf-check'}); const input = el('input', null, {type: 'checkbox'}); input.checked = checkedValue; input.onchange = () => fn(input.checked); label.append(input, document.createTextNode(text)); return label; }
  function renderInspector() {
    const host = $('#nodeInspector'); host.replaceChildren(el('h3', 'Node settings'));
    if (!doc || !selected || !doc.nodes[selected]) { host.append(el('p', 'Select a node in the diagram or list.')); return; }
    const id = selected, node = doc.nodes[id], kind = schema?.nodes[node.class_type];
    host.append(el('strong', `${id} · ${kind?.name || node.class_type}`));
    host.append(checkbox('Enabled', !doc.disabled.includes(id), checkedValue => edit(next => { next.disabled = next.disabled.filter(x => x !== id); if (!checkedValue) next.disabled.push(id); })));
    if (kind?.output_node) host.append(checkbox('Include this output', doc.outputs.includes(id), checkedValue => edit(next => { next.outputs = next.outputs.filter(x => x !== id); if (checkedValue) next.outputs.push(id); })));
    const coordinates = el('div', null, {class: 'wf-position'}), current = position(id, Object.keys(doc.nodes).indexOf(id));
    ['X', 'Y'].forEach((axis, i) => { const label = el('label', axis), input = el('input', null, {type: 'number', min: '0', max: '100000'}); input.value = current[i]; input.onchange = () => { if (!input.checkValidity() || !Number.isFinite(input.valueAsNumber)) return status('Use a finite position from 0 to 100000.'); edit(next => { next.positions[id] = [...current]; next.positions[id][i] = input.valueAsNumber; }); }; label.append(input); coordinates.append(label); }); host.append(coordinates);
    if (!kind) host.append(el('p', 'Node class unavailable. Original input data is retained; load its installed environment or keep it for native editing.'));
    else {
      if (kind.description) host.append(el('p', kind.description));
      for (const spec of kind.inputs.filter(x => !x.hidden)) fieldEditor(host, id, node, spec);
      const bypass = el('details'), summary = el('summary', 'Explicit passthrough when disabled'); bypass.append(summary, el('p', 'Only connected inputs of a matching type may be forwarded. There is no guessed bypass.'));
      for (const output of kind.outputs) {
        const label = el('label', `${output.index} · ${output.name} (${output.type})`), select = el('select', null, {'aria-label': 'Bypass output ' + output.index}); select.append(el('option', 'No bypass', {value: ''}));
        for (const spec of kind.inputs) if (match(spec.type, output.type) && isLink(node.inputs[spec.name])) select.append(el('option', spec.name, {value: spec.name}));
        select.value = doc.bypass[id]?.[String(output.index)] || '';
        select.onchange = () => edit(next => { next.bypass[id] ||= {}; if (select.value) next.bypass[id][String(output.index)] = select.value; else delete next.bypass[id][String(output.index)]; }); label.append(select); bypass.append(label);
      } host.append(bypass);
    }
    host.append(button('Remove node', () => { if (!confirm('Remove this node? Connections to it will remain visible as errors until repaired.')) return; edit(next => { for (const step of next.steps || []) { step.nodes = step.nodes.filter(x => x !== id); step.controls = step.controls.filter(c => c.node !== id); } delete next.nodes[id]; delete next.positions[id]; delete next.bypass[id]; next.disabled = next.disabled.filter(x => x !== id); next.outputs = next.outputs.filter(x => x !== id); }); }));
  }
  const WIDE_NAMES = ['text', 'prompt', 'positive', 'negative'];
  function wideText(spec, value) {
    if (spec.options?.multiline === true) return true;
    if (WIDE_NAMES.some(name => spec.name.toLowerCase().includes(name))) return true;
    return typeof value === 'string' && (value.includes('\n') || value.length > 60);
  }
  function grow(area) { area.style.height = 'auto'; area.style.height = Math.min(area.scrollHeight + 2, Math.round(window.innerHeight * 0.4)) + 'px'; }
  let expander = null;
  function expand(name, value, accept) {
    if (!expander) {
      const dialog = el('dialog', null, {class: 'wf-expand', 'aria-labelledby': 'wfExpandTitle'}), title = el('h3', 'Edit text', {id: 'wfExpandTitle'});
      const area = el('textarea', null, {'aria-label': 'Expanded text', wrap: 'soft', spellcheck: 'false'});
      const actions = el('div', null, {class: 'wf-expand-actions'});
      actions.append(button('Cancel', () => dialog.close('cancel')), button('Apply', () => dialog.close('apply')));
      dialog.append(title, area, actions); document.body.append(dialog); expander = {dialog, title, area};
    }
    expander.title.textContent = 'Edit ' + name; expander.area.value = typeof value === 'string' ? value : '';
    expander.dialog.onclose = () => { if (expander.dialog.returnValue === 'apply') accept(expander.area.value); };
    expander.dialog.returnValue = ''; // Only newer engines clear this on an Escape cancel; never inherit the previous Apply.
    expander.dialog.showModal(); expander.area.focus();
  }
  function fieldEditor(host, id, node, spec) {
    const field = el('div', null, {class: 'wf-field'}), present = Object.hasOwn(node.inputs, spec.name), value = node.inputs[spec.name];
    field.append(el('strong', spec.name + (spec.required ? ' *' : '')), el('code', spec.type));
    if (!spec.required) field.append(checkbox('Use optional input', present, checkedValue => edit(next => { if (checkedValue) { const d = defaultValue(spec); next.nodes[id].inputs[spec.name] = d === undefined ? null : d; } else { delete next.nodes[id].inputs[spec.name]; for (const [port, input] of Object.entries(next.bypass[id] || {})) if (input === spec.name) delete next.bypass[id][port]; } })));
    if (!present && !spec.required) { host.append(field); return; }
    if (spec.widget === 'unsupported') { field.append(el('small', spec.reason + '. Data retained, not simplified.'), el('pre', present ? JSON.stringify(value, null, 2) : 'Not set')); host.append(field); return; }
    const mode = el('select', null, {'aria-label': spec.name + ' input mode'});
    if (spec.widget !== 'socket') mode.append(el('option', 'Set a value', {value: 'value'}));
    mode.append(el('option', 'Connect an output', {value: 'link'})); mode.value = isLink(value) || spec.widget === 'socket' ? 'link' : 'value'; field.append(mode);
    const setValue = newValue => edit(next => { next.nodes[id].inputs[spec.name] = newValue; });
    const control = el('div'); field.append(control);
    function show(modeValue) {
      control.replaceChildren();
      if (modeValue === 'link') {
        const select = el('select', null, {'aria-label': spec.name + ' source'}); select.append(el('option', 'Choose a compatible output', {value: ''}));
        for (const [otherId, other] of Object.entries(doc.nodes)) if (otherId !== id) for (const output of schema.nodes[other.class_type]?.outputs || []) if (match(output.type, spec.type)) select.append(el('option', `${otherId} · ${other.class_type} → ${output.name} (${output.type})`, {value: JSON.stringify([otherId, output.index])}));
        select.value = isLink(value) ? JSON.stringify(value) : '';
        select.onchange = () => { if (select.value) setValue(JSON.parse(select.value)); else edit(next => { delete next.nodes[id].inputs[spec.name]; for (const [port, input] of Object.entries(next.bypass[id] || {})) if (input === spec.name) delete next.bypass[id][port]; }); }; control.append(select);
        if (isLink(value) && !select.value) control.append(el('small', 'Current connection is unavailable or incompatible; it remains in the draft until you replace it.'));
      } else {
        let input;
        if (spec.widget === 'combo') {
          input = el('select', null, {'aria-label': spec.name}); input.append(el('option', 'Choose a value', {value: ''}));
          spec.options.options.forEach((item, index) => input.append(el('option', String(item), {value: String(index)})));
          const index = spec.options.options.findIndex(item => typeof item === typeof value && item === value); input.value = index < 0 ? '' : String(index);
          input.onchange = () => { if (input.value !== '') setValue(spec.options.options[Number(input.value)]); };
        } else if (spec.type === 'BOOLEAN') {
          input = checkbox('On / off', value === true, setValue); input.querySelector('input').setAttribute('aria-label', spec.name);
        } else {
          const wide = spec.type === 'STRING' && wideText(spec, value);
          input = el(wide ? 'textarea' : 'input', null, {'aria-label': spec.name});
          if (wide) { input.rows = 4; input.className = 'wf-text'; input.oninput = () => grow(input); }
          else if (spec.type === 'STRING') input.type = 'text';
          else {
            input.type = 'number'; input.step = spec.type === 'INT' ? '1' : 'any';
            input.min = Math.max(-MAX, spec.options.min ?? -MAX); input.max = Math.min(MAX, spec.options.max ?? MAX);
          }
          input.value = present && !isLink(value) ? value : '';
          input.onchange = () => { try { const v = spec.type === 'STRING' ? input.value : input.valueAsNumber; safeNumbers(v); if (!input.checkValidity() || (spec.type === 'INT' && !Number.isInteger(v))) throw Error('Use a value inside the declared range. Integer fields require whole numbers.'); setValue(v); } catch (error) { status(error.message); renderInspector(); } };
          if (wide) { control.append(input); const wider = button('Expand', () => expand(spec.name, input.value, next => { input.value = next; grow(input); setValue(next); })); wider.className = 'wf-expand-open'; control.append(wider); requestAnimationFrame(() => grow(input)); return; }
        }
        control.append(input);
        if (['INT', 'FLOAT'].includes(spec.type) && Number.isFinite(spec.options.min) && Number.isFinite(spec.options.max) && spec.options.max <= 10000 && spec.options.min >= -10000) {
          const range = el('input', null, {type: 'range', min: spec.options.min, max: spec.options.max, step: spec.type === 'INT' ? '1' : String(spec.options.step || 'any'), 'aria-label': spec.name + ' slider'}); range.value = typeof value === 'number' ? value : spec.options.min;
          range.onchange = () => setValue(Number(range.value)); control.append(range);
        }
      }
    }
    mode.onchange = () => { if (mode.value === 'value') { const d = defaultValue(spec); if (d !== undefined) setValue(d); } else show('link'); };
    show(mode.value); host.append(field);
  }
  function render() {
    $('#workflowName').value = doc?.name || 'Untitled workflow';
    $('#undoWorkflow').disabled = !undo.length; $('#redoWorkflow').disabled = !redo.length;
    for (const id of ['saveWorkflow', 'compileWorkflow']) $('#' + id).disabled = !doc || (id === 'compileWorkflow' && !schema);
    $('#rebaseWorkflow').disabled = !doc || !schema || (doc.schema_sha256 === schema.schema_sha256 && doc.backend_id === schema.backend_id);
    $('#exportGraph').disabled = !checked?.valid;
    for (const id of ['canvasFit', 'canvasReset']) $('#' + id).disabled = !doc || !Object.keys(doc.nodes).length;
    $('#documentStats').textContent = doc ? `${Object.keys(doc.nodes).length} nodes · revision ${doc.revision}` : 'No draft';
    if (!checked) $('#workflowDiagnostics').replaceChildren();
    diagram(); renderNodeList(); renderInspector();
    document.dispatchEvent(new Event('workflow:render'));
  }
  async function goals() {
    const data = await api('/guides'), host = $('#goalCards'); host.replaceChildren();
    data.guides.forEach((guide, index) => {
      const card = el('article', null, {class: 'wf-goal'}); card.append(el('small', `PATH ${String(index + 1).padStart(2, '0')} · ${guide.steps.length} STEPS`), el('h3', guide.title), el('p', guide.summary));
      function href(step) { const url = new URL(guide.steps[step].route, document.baseURI); url.searchParams.set('guide', guide.id); url.searchParams.set('step', String(step)); if (guide.steps[step].id) url.searchParams.set('stage', guide.steps[step].id); return url.pathname + url.search + url.hash; }
      card.append(el('a', 'Start guided path →', {href: href(0)}));
      try { const saved = JSON.parse(localStorage.getItem('studio.guide.' + guide.id)); const resume = saved?.stage ? guide.steps.findIndex(s => s.id === saved.stage) : saved?.step; if (Number.isInteger(resume) && resume > 0 && resume < guide.steps.length) card.append(el('a', `Resume at step ${resume + 1} →`, {href: href(resume)})); } catch (_) {}
      host.append(card);
    });
  }
  canvasNavigation();
  $('#loadNodes').onclick = guard(() => loadSchema(true));
  $('#nodeSearch').oninput = nodeCatalog;
  $('#loadPreset').onclick = guard(async () => { const id = $('#presetChoice').value; if (!id) throw Error('Choose a registered recipe first.'); if (!discard()) return; const token = ++epoch; if (!schema) await loadSchema(); const result = await api('/presets/' + encodeURIComponent(id)); if (token !== epoch) return status('Import ignored because the draft changed while loading.'); replace(result.document); });
  $('#newWorkflow').onclick = guard(async () => { if (!discard()) return; if (!schema) await loadSchema(); replace({format: 'studio.workflow/v1', name: 'Untitled workflow', revision: 0, backend_id: schema.backend_id, schema_sha256: schema.schema_sha256, nodes: {}, outputs: [], disabled: [], bypass: {}, positions: {}}); });
  $('#openWorkflow').onchange = guard(async () => { const file = $('#openWorkflow').files[0]; if (!file || !discard()) return; if (file.size > 1024 * 1024) throw Error('Use a JSON file no larger than 1 MiB.'); const token = ++epoch; const result = await api('/open', {content: await file.text()}); if (token !== epoch) return status('Import ignored because the draft changed while loading.'); replace(result.document); $('#openWorkflow').value = ''; });
  $('#restoreWorkflow').onclick = guard(async () => { const source = localStorage.getItem(KEY); if (!source) throw Error('No browser draft is saved.'); if (!discard()) return; const token = ++epoch; const result = await api('/open', {content: source}); if (token === epoch) replace(result.document); });
  $('#workflowName').onchange = () => { if (doc) edit(next => { next.name = $('#workflowName').value; }); };
  $('#rebaseWorkflow').onclick = () => { if (doc && schema && confirm('Adopt the active schema for this draft? This does not certify compatibility. Check the graph again before exporting.')) edit(next => { next.backend_id = schema.backend_id; next.schema_sha256 = schema.schema_sha256; }); };
  $('#saveWorkflow').onclick = () => { if (doc) download('studio-workflow.json', doc); };
  $('#undoWorkflow').onclick = () => { if (!undo.length) return; const next = undo.pop(); redo.push(clone(doc)); changed(next, false); };
  $('#redoWorkflow').onclick = () => { if (!redo.length) return; const next = redo.pop(); undo.push(clone(doc)); changed(next, false); };
  $('#compileWorkflow').onclick = guard(async () => {
    if (!doc) return; const token = epoch, catalogToken = schemaEpoch; status('Checking selected output connections…');
    const result = await api('/compile', {document: clone(doc)});
    if (token !== epoch || catalogToken !== schemaEpoch) return status('Check result ignored: the draft or schema changed while checking. Check again.');
    checked = result; $('#exportGraph').disabled = !result.valid;
    const host = $('#workflowDiagnostics'); host.replaceChildren();
    for (const item of [...result.errors, ...result.warnings]) { const row = el('div', null, {class: 'wf-diagnostic'}); if (item.node) row.append(button(`Node ${item.node}${item.field ? '.' + item.field : ''}`, () => { document.dispatchEvent(new Event('workflow:inspect')); selected = item.node; renderInspector(); renderNodeList(); $('#nodeInspector').scrollIntoView({block: 'start'}); })); row.append(document.createTextNode(item.message)); host.append(row); }
    status(result.valid ? 'Connections checked. Export is available. This is not a runtime or resource check, and nothing was queued.' : `${result.errors.length} issue(s) to resolve before API export. Your draft is preserved.`);
  });
  $('#exportGraph').onclick = () => { if (checked?.valid) download('workflow-api.json', checked.graph); };
  window.WorkflowStudio = Object.freeze({
    snapshot: () => doc && clone(doc), schema: () => schema && clone(schema), epoch: () => epoch,
    authoringStatus: () => Object.freeze({document_present: !!doc, schema_loaded: !!schema,
      schema_matches: !!doc && !!schema && doc.backend_id === schema.backend_id && doc.schema_sha256 === schema.schema_sha256,
      checked_valid: checked?.valid ?? null, epoch, schema_epoch: schemaEpoch}),
    load: replace, change: changed, validate: safeNumbers, status,
    inspect: id => { selected = id; render(); $('#nodeInspector').scrollIntoView({block: 'start'}); },
    field: (host, id, input) => {
      const node = doc?.nodes[id], spec = node && schema?.nodes[node.class_type]?.inputs.find(x => x.name === input && !x.hidden);
      if (!spec) return host.append(el('p', 'This input is unavailable in the loaded schema; its data is retained.'));
      fieldEditor(host, id, node, spec);
    }
  });
  goals().catch(error => { $('#goalCards').textContent = 'Guides unavailable: ' + error.message; });
  fetch('/api/catalog').then(r => { if (!r.ok) throw Error('Recipe catalog unavailable'); return r.json(); }).then(data => { for (const preset of data.presets || []) $('#presetChoice').append(el('option', preset.name || preset.id, {value: preset.id})); }).catch(error => status(error.message));
})();
