/* Standalone demo data only. There is deliberately no transport or executor here. */
'use strict';
const byId=id=>document.getElementById(id);
const demoPrompt=byId('positive').value;
let selected={id:'ink',name:'Ink illustration',defaults:{positive:demoPrompt,negative:''}};
let uploaded=null;
let sourceURL=null;
const examples={anime:'../../examples/workflow-lab/anima.png',pixel:'../../examples/gallery/pixel-lora-128.png'};
function demoStatus(message){byId('status').textContent=message;}
function demoClearSource(){if(sourceURL)URL.revokeObjectURL(sourceURL);sourceURL=null;uploaded=null;byId('reference').value='';byId('demoSource').hidden=true;byId('demoRemove').hidden=true;}
function selectPreset(id){
  demoClearSource();
  selected=id==='ink'?{id,name:'Ink illustration',defaults:{positive:demoPrompt,negative:''}}:{id,name:'Refine a picture',reference:true,defaults:{positive:'Change the lighting; keep the composition and character.',negative:''}};
  byId('positive').value=selected.defaults.positive;byId('negative').value='';
  byId('referenceWrap').hidden=!selected.reference;
  byId('selectedPreset').textContent=selected.name;byId('uxRecipeLabel').textContent=selected.name;
  for(const b of document.querySelectorAll('#presetList button'))b.classList.toggle('chosen',b.dataset.id===id);
  demoStatus('Demo recipe selected. Review your brief; no generation will run.');
  document.dispatchEvent(new Event('studio:recipe'));
}
byId('presetList').onclick=e=>{const b=e.target.closest('[data-id]');if(b)selectPreset(b.dataset.id);};
byId('presetSearch').oninput=e=>{let count=0;for(const b of document.querySelectorAll('#presetList button')){b.hidden=!b.textContent.toLowerCase().includes(e.target.value.toLowerCase());if(!b.hidden)count++;}byId('filteredCount').textContent=count;};
byId('generate').onclick=()=>demoStatus('Setup previewed: '+selected.name+' · '+byId('batch').selectedOptions[0].textContent+'. Your brief is unchanged. No job was submitted.');
byId('randomSeed').onclick=()=>{document.querySelector('[data-key=seed]').value=Math.floor(Math.random()*100000);document.dispatchEvent(new Event('studio:recipe'));};
byId('demoReset').onclick=()=>{for(const input of document.querySelectorAll('#controls input'))input.value=input.defaultValue;document.dispatchEvent(new Event('studio:recipe'));};
byId('reference').onchange=()=>{
  const file=byId('reference').files[0];if(!file)return;
  if(!file.type.startsWith('image/')||file.size>20*1024*1024){demoClearSource();demoStatus('Choose an image below 20 MB for this preview.');return;}
  if(sourceURL)URL.revokeObjectURL(sourceURL);sourceURL=URL.createObjectURL(file);uploaded=file.name;
  byId('demoSource').src=sourceURL;byId('demoSource').hidden=false;byId('demoRemove').hidden=false;demoStatus('Reference stays in this browser tab. Nothing was uploaded.');
};
byId('demoRemove').onclick=demoClearSource;
byId('uxPullAsset').onclick=()=>{if(selected.id!=='refine'){demoStatus('Open Change and choose Refine a picture to try a reference without losing your brief silently.');byId('workshopRecipeChange').click();}else byId('reference').click();};
byId('demoContinue').onclick=()=>{
  if(!confirm('Use this repository example in the Refine demo? This replaces the current demo prompt and source.'))return;
  selectPreset('refine');uploaded='repository-example';byId('demoSource').src=byId('demoArtwork').src;byId('demoSource').hidden=false;byId('demoRemove').hidden=false;
  demoStatus('Example attached in this preview only. Review the brief before trying anything else.');
};
for(const b of document.querySelectorAll('[data-demo-art]'))b.onclick=()=>{byId('demoArtwork').src=examples[b.dataset.demoArt];byId('demoArtwork').alt=b.dataset.demoArt==='anime'?'Existing repository illustration: explorer with an umbrella':'Existing repository pixel-art study';for(const other of document.querySelectorAll('[data-demo-art]'))other.setAttribute('aria-pressed',String(other===b));};
document.querySelector('[data-key=lora]').addEventListener('input',e=>{byId('demoStrength').value=e.target.value;});
const setups=[];
byId('save').onclick=()=>{
  const name=byId('saveName').value.trim();if(!name){byId('setupStatus').textContent='Name this demo setup first.';return;}
  setups.push({name,recipe:selected.id,positive:byId('positive').value});
  const item=document.createElement('button');item.type='button';item.textContent=name;const saved=setups.at(-1);
  item.onclick=()=>{if(confirm('Replace the current demo brief with “'+saved.name+'”?')){selectPreset(saved.recipe);byId('positive').value=saved.positive;}};
  byId('savedList').append(item);byId('setupStatus').textContent='Saved in this tab only.';byId('saveName').value='';
};
byId('uxExportDraft').onclick=()=>{
  const data={format:'studio.workshop-demo/v1',recipe:selected.id,positive:byId('positive').value,negative:byId('negative').value};
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='workshop-demo-brief.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
byId('planComparison').onclick=()=>{const select=byId('workshopLayout');select.value=select.value==='focus'?'studio':'focus';select.dispatchEvent(new Event('change',{bubbles:true}));};
byId('uxRecheckReadiness').onclick=()=>demoStatus('Standalone interface preview. Connect your real Local Asset Studio to ComfyUI to generate.');
let noticeTimer;
document.addEventListener('click',e=>{
  if(!e.target.closest('[data-demo-nav]'))return;e.preventDefault();
  let notice=byId('demoNotice');if(!notice){notice=document.createElement('div');notice.id='demoNotice';notice.setAttribute('role','status');document.body.append(notice);}
  notice.textContent='This prototype covers Create. Other tools remain in the real Local Asset Studio.';notice.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>notice.hidden=true,4500);
});
window.addEventListener('DOMContentLoaded',()=>setTimeout(()=>{
  // Start this demonstration in the visual variation; production still defaults to Focus.
  const layout=byId('workshopLayout');if(layout){layout.value='studio';layout.dispatchEvent(new Event('change',{bubbles:true}));}
},0));
