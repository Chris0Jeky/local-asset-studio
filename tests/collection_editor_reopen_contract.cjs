'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {setup}=require('./asset_detail_contracts.cjs');
const source=path.join(__dirname,'../app/static/collection-editor.js');
const A='a'.repeat(32),B='b'.repeat(32),W='1'.repeat(32);

function page(){
  const s=setup({autoOpen:false});
  s.run(`assetState.collections=[
    {id:'${A}',name:'Remove me',description:'',count:0},
    {id:'${B}',name:'Open next',description:'Retained',count:0}
  ];assetScope='all';assetSelection=new Set();`);
  s.run(fs.readFileSync(source,'utf8'));
  return {...s,open:id=>s.run(`openCollection(${JSON.stringify(id)})`)};
}

(async()=>{
  const s=page();s.approve(true);s.open(A);
  const dialog=s.el('#collectionDialog');
  const delayedCloseHandlers=[...(dialog.events.close||[])];
  let closeRequested=false;
  dialog.close=()=>{dialog.open=false;closeRequested=true;};

  const pending=s.el('#removeCollection').onclick();
  const payload=s.payload(0);
  assert.equal(payload.action,'delete');
  s.writes[0].resolve({id:A,deleted:true,workspace_id:W});
  await pending;

  assert.equal(closeRequested,true,'delete must request dialog close');
  assert.equal(dialog.open,false,'the close request clears the open state before the close event');
  assert.equal(s.el('#collectionName').disabled,true,'the destructive request disabled the inputs');

  s.open(B);
  assert.equal(dialog.open,true,'a replacement editor opens immediately');
  assert.equal(s.el('#collectionName').disabled,false,'a new session must initialize the name input');
  assert.equal(s.el('#collectionDescription').disabled,false,'a new session must initialize the description input');
  assert.equal(s.el('#collectionName').value,'Open next');

  for(const handler of delayedCloseHandlers)handler();
  assert.equal(dialog.open,true,'the delayed old close event must not close the replacement editor');
  assert.equal(s.run('collectionSession.id'),B,'the delayed old close event must not clear the replacement session');
  console.log('Collection editor immediate-reopen contract passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
