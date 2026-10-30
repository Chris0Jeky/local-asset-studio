'use strict';
// #1837: the repaired-version request carries the picture's own privacy and parent, and refuses before any request for a picture it cannot repair.
const test=require('node:test'),assert=require('node:assert/strict'),R=require('../app/static/asset-repair.js');
const png=(over={})=>({name:'fixed.png',type:'image/png',size:1200,...over});
const asset=(over={})=>({id:'a'.repeat(32),media_type:'image',privacy:'regular',trashed_at:null,...over});
const idle=()=>({busy:false,pending:false,conflict:false,importing:false});

test('payload names the parent, the picture\'s privacy and a percent-encoded plain note',()=>{
  for(const privacy of ['regular','private']){
    const file=png(),{path,options}=R.request(asset({privacy}),file,'  Fixed the  eyes ✓ ');
    assert.equal(path,'/api/assets/import');assert.equal(options.method,'POST');assert.equal(options.body,file);
    assert.deepEqual(options.headers,{'Content-Type':'image/png','X-Filename':'fixed.png','X-Studio-Privacy':privacy,'X-Studio-Creation-Privacy':privacy,
      'X-Parent-Asset':'a'.repeat(32),'X-Editor-Note':encodeURIComponent('Fixed the eyes ✓')});
  }
  const bare=R.request(asset(),png({name:'réparé.png'}),'   ').options.headers;
  assert.equal('X-Editor-Note' in bare,false);assert.equal(bare['X-Filename'],'repaired.png');
});

test('refusals say why, before any request',async()=>{
  const cases=[[asset({media_type:'video'}),png(),'',idle(),/Only a picture/],[asset({trashed_at:3}),png(),'',idle(),/in the Bin/],
    [asset({privacy:'secret'}),png(),'',idle(),/privacy classification/],[asset(),png({type:'image/jpeg'}),'',idle(),/Choose a PNG/],
    [asset(),png({size:0}),'',idle(),/empty/],[asset(),png({size:21*1024*1024}),'',idle(),/20 MiB/],[asset(),null,'',idle(),/Choose the repaired PNG/],
    [asset(),png(),'x'.repeat(281),idle(),/280 characters/],[asset(),png(),'',{...idle(),busy:true},/save is still pending/],
    [asset(),png(),'',{...idle(),pending:true},/earlier save/],[asset(),png(),'',{...idle(),conflict:true},/earlier save/],[asset(),png(),'',{...idle(),importing:true},/already running/],
    [null,png(),'',idle(),/Open a picture/]];
  for(const [a,file,note,state,message] of cases){
    let calls=0;
    await assert.rejects(R.submit({asset:a,file,note,state:()=>state,api:async()=>{calls++;},current:()=>true}),message);
    assert.equal(calls,0);
  }
});

test('success needs the recorded link and reports whether the editor still shows the picture',async()=>{
  const parent=asset(),child='b'.repeat(32);let seen;
  const api=async(path,options)=>{seen={path,options};return {asset:{id:child,lineage:[parent.id]}};};
  assert.deepEqual(await R.submit({asset:parent,file:png(),note:'',state:idle,api,current:()=>true}),{id:child,parent:parent.id});
  assert.equal(seen.options.headers['X-Parent-Asset'],parent.id);
  await assert.rejects(R.submit({asset:parent,file:png(),note:'',state:idle,api:async()=>({asset:{id:child,lineage:[]}}),current:()=>true}),/link to this one was not confirmed/);
  await assert.rejects(R.submit({asset:parent,file:png(),note:'',state:idle,api:async()=>{throw Error('Asset not found');},current:()=>true}),/Asset not found/);
});

test('completion after the library refresh re-checks the picture and never speaks in an unrelated dialog',async()=>{
  const done={id:'b'.repeat(32),parent:'a'.repeat(32)};
  for(const [name,moves] of [['stays',false],['navigates during the refresh',true]]){
    let viewing=true;const shown=[],notices=[];
    await R.settle(done,{refresh:async()=>{if(moves)viewing=false;},current:()=>viewing,show:(id,text)=>shown.push([id,text]),notice:text=>notices.push(text)});
    if(moves){assert.deepEqual(shown,[],name);assert.equal(notices.length,1);assert.doesNotMatch(notices[0],/of this one/);}
    else{assert.equal(shown.length,1,name);assert.equal(shown[0][0],done.id);assert.deepEqual(notices,[]);}
  }
  let viewing=true;const shown=[];
  await R.settle(done,{refresh:async()=>{throw Error('offline');},current:()=>viewing,show:(...a)=>shown.push(a),notice:()=>assert.fail('a failed refresh is not a navigation')});
  assert.equal(shown.length,1);
});
