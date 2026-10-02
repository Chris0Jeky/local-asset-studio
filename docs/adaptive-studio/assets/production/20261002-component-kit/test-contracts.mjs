import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {motionDecision} from './motion-policy.mjs';
const tokens=JSON.parse(fs.readFileSync(new URL('./tokens.json',import.meta.url)));
const css=fs.readFileSync(new URL('./foundations.css',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('./components.html',import.meta.url),'utf8');
const ready={hidden:false,inViewport:true,reducedMotion:false,forcedColors:false,choice:'subtle',jobState:'idle',saveData:false,userPaused:false,approvedLocalLoop:true,mediaReady:true};
for(const [name,patch,mode] of [
 ['hidden tab wins',{hidden:true},'paused'],['out of viewport',{inViewport:false},'paused'],
 ['reduced motion',{reducedMotion:true},'static'],['forced colours',{forcedColors:true},'static'],
 ['explicit still',{choice:'still'},'static'],['missing explicit opt-in',{choice:undefined},'static'],
 ['active job',{jobState:'running'},'static'],['unknown job outcome',{jobState:'uncertain'},'static'],
 ['missing job observation',{jobState:undefined},'static'],['economy mode',{saveData:true},'static'],
 ['persistent user pause',{userPaused:true},'paused'],['unapproved local loop',{approvedLocalLoop:false},'static'],
 ['missing/decode-failed media',{mediaReady:false},'static'],['approved idle visible local loop',{},'local-loop']]) {
 test(name,()=>assert.equal(motionDecision({...ready,...patch})?.mode,mode));
}
test('missing input is safe static',()=>assert.equal(motionDecision()?.mode,'static'));
test('missing visibility observation is static',()=>assert.equal(motionDecision({...ready,hidden:undefined})?.mode,'static'));
test('missing viewport observation is static',()=>assert.equal(motionDecision({...ready,inViewport:undefined})?.mode,'static'));
test('invalid visibility observation is static',()=>assert.equal(motionDecision({...ready,hidden:'false'})?.mode,'static'));
test('unobserved reduced-motion preference is static',()=>assert.equal(motionDecision({...ready,reducedMotion:undefined})?.mode,'static'));
test('unobserved forced-colours preference is static',()=>assert.equal(motionDecision({...ready,forcedColors:undefined})?.mode,'static'));
test('invalid economy preference is static',()=>assert.equal(motionDecision({...ready,saveData:'false'})?.mode,'static'));
test('uninitialised user pause is static',()=>assert.equal(motionDecision({...ready,userPaused:undefined})?.mode,'static'));
test('does not mutate input or clear user pause',()=>{const state=Object.freeze({...ready,userPaused:true});assert.equal(motionDecision(state)?.mode,'paused');assert.equal(state.userPaused,true)});
test('hidden dominates user pause and resource conditions',()=>assert.equal(motionDecision({...ready,hidden:true,userPaused:true,reducedMotion:true})?.reason,'hidden'));
test('motion duration is bounded',()=>assert.ok(motionDecision(ready)?.crossfadeMs<=300));
test('six token skins with at most twelve overrides',()=>{assert.equal(Object.keys(tokens.skins||{}).length,6);for(const overrides of Object.values(tokens.skins))assert.ok(Object.keys(overrides).length<=12)});
test('semantic and review colours are fixed across skins',()=>{assert.ok(tokens.base?.['status-unknown']);assert.ok(tokens.base?.['review-keeper']);for(const skin of Object.values(tokens.skins||{}))assert.ok(!Object.keys(skin).some(x=>x.startsWith('status-')||x.startsWith('review-')))});
function lum(h){const c=[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722}
function contrast(a,b){const [lo,hi]=[lum(a),lum(b)].sort((x,y)=>x-y);return(hi+.05)/(lo+.05)}
test('all text/status/review colours meet 4.5 on each solid surface',()=>{assert.ok(tokens.base);for(const [name,skin] of Object.entries(tokens.skins)){const t={...tokens.base,...skin};for(const s of ['bg','surface-1','surface-2','surface-3'])for(const fg of ['text','text-muted','text-faint',...Object.keys(t).filter(x=>x.startsWith('status-')||x.startsWith('review-'))])assert.ok(contrast(t[fg],t[s])>=4.5,`${name} ${fg} on ${s}`)}});
test('accent buttons and control boundaries have contrast',()=>{assert.ok(tokens.base);for(const skin of Object.values(tokens.skins)){const t={...tokens.base,...skin};assert.ok(contrast(t['text-on-accent'],t.accent)>=4.5);assert.ok(contrast(t['line-strong'],t['surface-2'])>=3);assert.ok(contrast(t['focus-ring'],t['surface-2'])>=3);assert.ok(contrast(t['focus-underlay'],t.accent)>=3)}});
test('generated CSS retains token values and skin overrides',()=>{for(const[k,v]of Object.entries(tokens.base))assert.ok(css.includes(`--${k}:${v};`),k);for(const[name,skin]of Object.entries(tokens.skins)){const selector=`.las-kit[data-skin="${name}"]{`;const body=css.slice(css.indexOf(selector)+selector.length).split('}')[0];for(const[k,v]of Object.entries(skin))assert.ok(body.includes(`--${k}:${v};`),`${name} ${k}`)}});
test('source HTML IDs and labels resolve uniquely',()=>{const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);assert.equal(new Set(ids).size,ids.length);for(const m of html.matchAll(/\b(?:for|aria-describedby)="([^"]+)"/g))for(const id of m[1].split(' '))assert.ok(ids.includes(id),id);assert.ok(!/<script|\son\w+=|<form/i.test(html));assert.ok([...html.matchAll(/<button\b([^>]*)>/g)].every(x=>x[1].includes('type="button"')))});
test('static and forced-colour modes disable all optional transitions',()=>{assert.ok(css.includes('.las-kit[data-motion="static"] :is(.decorative,.ui-feedback,.panel-enter,.scene-layer){animation:none!important;transition:none!important}'));assert.ok(css.includes('@media(forced-colors:active){.las-kit *{animation:none!important;transition:none!important}'))});
