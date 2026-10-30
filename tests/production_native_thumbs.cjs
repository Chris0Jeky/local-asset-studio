// Native export (#1812): every source row shows its own thumbnail and 1-based position, and ordering keeps each row's id,
// duration, layer name and picture together. Runs production.js and the Library's own thumbnail helpers in a VM; no browser.
'use strict';
const assert=require('node:assert/strict'),test=require('node:test'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const read=name=>fs.readFileSync(path.join(__dirname,'../app/static',name),'utf8');
const SHA={a1:'1111111111111111aaaa',a2:'2222222222222222bbbb',a3:'3333333333333333cccc'};
function world(){
  const elements=new Map(),posts=[],selection=new Set(['a1','a2','a3']);let dom=new Map();
  const assets=new Map(['a1','a2','a3'].map(id=>[id,{id,title:'Walk',media_type:'image',sha256:SHA[id],url:'/files/'+id+'.png',...(id==='a2'?{privacy:'private'}:{})}]));
  const $=selector=>{if(!elements.has(selector)){const el={value:'',textContent:'',open:true,disabled:false,hidden:false,classList:{toggle(){}},showModal(){},close(){}};
    if(selector==='#nativeAssetList'){let html='';Object.defineProperty(el,'innerHTML',{get:()=>html,set:v=>{html=v;dom=new Map();}});
      el.querySelectorAll=()=>[...html.matchAll(/<input[^>]*data-native-(duration|layer)="([^"]+)"[^>]*value="([^"]*)"/g)].map(m=>{const key=m[1]+':'+m[2];
        return {dataset:{[m[1]==='duration'?'nativeDuration':'nativeLayer']:m[2]},get value(){return dom.has(key)?dom.get(key):m[3];}};});}
    else el.innerHTML='';elements.set(selector,el);}return elements.get(selector);};
  const context=vm.createContext({$,esc:String,document:{querySelector:$,querySelectorAll:()=>[],addEventListener(){}},CSS:{escape:String},window:{},setInterval(){},showView(){},
    assetState:{assets:[...assets.values()]},assetSelection:selection,catalog:{presets:[]},api:async()=>[],post:async(url,body)=>{posts.push({url,body});return {id:'plan'};},
    assetRecord:id=>assets.get(id),resolveAssetIDs:async()=>true,refreshAssets:async()=>true,assetMessage(){},message(){},mutateAssets:async()=>{}});
  vm.runInContext(read('review-checks.js'),context);
  const workspace=read('workspace.js');
  for(const re of [/^const ASSET_THUMB_VERSION[^\n]*$/m,/^function assetThumbUrl[^\n]*$/m,/^function assetPreview[\s\S]*?^}/m])vm.runInContext(workspace.match(re)[0],context);
  vm.runInContext(read('production.js'),context);
  const rows=()=>$('#nativeAssetList').innerHTML.split('<div class="native-source">').slice(1).map(h=>({
    position:Number(h.match(/<b>(\d+)<\/b>/)[1]),src:h.match(/<img[^>]*?\ssrc="([^"]+)"/)?.[1],alt:h.match(/<img[^>]*alt="([^"]*)"/)?.[1],
    id:h.match(/data-native-duration="([^"]+)"/)[1],duration:h.match(/data-native-duration="[^"]+"[^>]*value="([^"]*)"/)[1],layer:h.match(/data-native-layer="[^"]+"[^>]*value="([^"]*)"/)[1]}));
  const type=(kind,id,value)=>{dom.set(kind+':'+id,value);$('#nativeAssetList').oninput();};
  const move=(dir,i)=>$('#nativeAssetList').onclick({target:{closest:sel=>sel==='[data-native-'+dir+']'?{dataset:{[dir==='up'?'nativeUp':'nativeDown']:String(i)}}:null}});
  const thumb=id=>context.assetThumbUrl(assets.get(id));
  return {$,context,posts,rows,type,move,thumb,open:()=>$('#nativeExport').onclick(),submit:()=>$('#nativeForm').onsubmit({preventDefault(){},submitter:{id:'prepareNativeOnly'}})};
}
test('each row shows its own Library thumbnail, alt text and 1-based position, private pictures with the privacy parameter',()=>{
  const w=world();w.open();const rows=w.rows();
  assert.deepEqual(rows.map(r=>r.id),['a1','a2','a3']);assert.deepEqual(rows.map(r=>r.position),[1,2,3]);
  for(const r of rows){assert.equal(r.src,w.thumb(r.id),r.id);assert.equal(r.alt,'Walk');assert.ok(r.src.startsWith('/api/assets/'+r.id+'/thumb?v=')&&r.src.includes('-'+SHA[r.id].slice(0,16)),r.src);}
  assert.match(rows[1].src,/&privacy=private$/);assert.doesNotMatch(rows[0].src+rows[2].src,/privacy/);
});
test('reordering keeps picture, duration and layer name with their id, and the submitted plan follows the shown order',async()=>{
  const w=world();w.open();
  w.type('duration','a1','120');w.type('layer','a1','first');w.type('duration','a3','250');w.type('layer','a3','third');
  w.move('down',0);w.move('up',2);
  const rows=w.rows(),want={a1:['120','first'],a2:['100','Walk'],a3:['250','third']};
  assert.deepEqual(rows.map(r=>r.id),['a2','a3','a1']);assert.deepEqual(rows.map(r=>r.position),[1,2,3]);
  for(const r of rows){assert.equal(r.src,w.thumb(r.id),'thumbnail follows '+r.id);assert.deepEqual([r.duration,r.layer],want[r.id],r.id);}
  w.type('layer','a1','last');await w.submit();
  const {url,body}=w.posts.at(-1);assert.equal(url,'/api/production-export');assert.deepEqual([...body.ids],['a2','a3','a1']);
  assert.deepEqual([...body.options.duration_ms],[100,250,120]);assert.deepEqual([...body.options.layer_names],['Walk','third','last']);
});
