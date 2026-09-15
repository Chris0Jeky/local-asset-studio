'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const figures=require('../app/static/addressable-figures.js');
let passed=0;
function test(name,fn){fn();passed++;console.log('PASS',name);}


test('the Asset workspace entrypoint loads the separate editor module in browsers',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../app/static/asset-grid.js'),'utf8');
  assert.match(source,/\/static\/addressable-figures\.js/);
  assert.match(source,/typeof document!==['"]undefined['"]/);
});

test('pointer geometry becomes stable basis points independent of drag direction',()=>{
  const image={left:10,top:20,width:200,height:100};
  assert.deepEqual(figures.fromPixels({x:160,y:95},{x:60,y:45},image),{x:2500,y:2500,width:5000,height:5000});
});

test('rectangle validation preserves authored order and returns detached values',()=>{
  const source=[{x:5000,y:0,width:5000,height:10000},{x:0,y:0,width:5000,height:10000}];
  const result=figures.validateRectangles(source,true);
  assert.deepEqual(result,source);assert.notEqual(result,source);assert.notEqual(result[0],source[0]);
});

test('bounds and optional non-overlap fail closed',()=>{
  assert.throws(()=>figures.validateRectangles([{x:9000,y:0,width:1001,height:10}],false),/inside/i);
  const overlap=[{x:0,y:0,width:6000,height:10000},{x:5000,y:0,width:5000,height:10000}];
  assert.throws(()=>figures.validateRectangles(overlap,true),/overlap/i);
  assert.deepEqual(figures.validateRectangles(overlap,false),overlap);
});

test('history supports add, reorder, remove, clear and explicit undo',()=>{
  const first={x:0,y:0,width:5000,height:10000},second={x:5000,y:0,width:5000,height:10000};
  const history=figures.createHistory();
  history.commit([first]);history.commit([first,second]);
  history.move(1,-1);assert.deepEqual(history.value(),[second,first]);
  history.remove(0);assert.deepEqual(history.value(),[first]);
  assert.equal(history.undo(),true);assert.deepEqual(history.value(),[second,first]);
  history.clear();assert.deepEqual(history.value(),[]);
  assert.equal(history.undo(),true);assert.deepEqual(history.value(),[second,first]);
});

test('request binds exact workspace, parent bytes, order and idempotency key',()=>{
  const rectangles=[{x:0,y:0,width:5000,height:10000}];
  const request=figures.createRequest({workspaceId:'a'.repeat(32),asset:{id:'asset-1',sha256:'b'.repeat(64)},rectangles,requestId:'request-1',requireNonOverlapping:true});
  assert.deepEqual(request,{workspace_id:'a'.repeat(32),request_id:'request-1',asset_id:'asset-1',parent_sha256:'b'.repeat(64),rectangles,require_non_overlapping:true});
  rectangles[0].width=1;assert.equal(request.rectangles[0].width,5000);
});

test('matching receipt confirms local children without inferring generation or review',()=>{
  const request=figures.createRequest({workspaceId:'a'.repeat(32),asset:{id:'asset-1',sha256:'b'.repeat(64)},rectangles:[{x:0,y:0,width:5000,height:10000}],requestId:'request-1',requireNonOverlapping:true});
  const child='c'.repeat(32);
  const receipt={status:'created',action:'split_figures',workspace_id:request.workspace_id,parent_asset_id:request.asset_id,request_id:request.request_id,generation_submitted:false,created:[child],figures:[{index:1,asset_id:child}]};
  assert.equal(figures.validateReceipt(receipt,request),receipt);
  assert.throws(()=>figures.validateReceipt({...receipt,generation_submitted:true},request),/receipt/i);
  const withoutRequest={...receipt};delete withoutRequest.request_id;
  assert.throws(()=>figures.validateReceipt(withoutRequest,request),/receipt/i);
  assert.throws(()=>figures.validateReceipt({...receipt,created:['unsafe child'],figures:[{index:1,asset_id:'unsafe child'}]},request),/receipt/i);
});

test('retained commands are canonical UI requests rather than trusted storage objects',()=>{
  const request=figures.createRequest({workspaceId:'a'.repeat(32),asset:{id:'asset-1',sha256:'b'.repeat(64)},rectangles:[{x:0,y:0,width:5000,height:10000}],requestId:'1'.repeat(32),requireNonOverlapping:true});
  assert.deepEqual(figures.restoreRequest(request),request);
  assert.throws(()=>figures.restoreRequest({...request,request_id:'request-1'}),/retained/i);
  assert.throws(()=>figures.restoreRequest({...request,extra:true}),/retained/i);
  assert.throws(()=>figures.restoreRequest({...request,rectangles:[{x:0,y:0,width:0,height:10}]}),/retained/i);
});

test('a retained command can only reopen against its exact immutable source',()=>{
  const request={workspace_id:'a'.repeat(32),asset_id:'asset-1',parent_sha256:'b'.repeat(64)};
  const asset={workspace_id:request.workspace_id,id:request.asset_id,sha256:request.parent_sha256};
  assert.equal(figures.requestMatchesAsset(request,asset),true);
  assert.equal(figures.requestMatchesAsset({...request,asset_id:'other'},asset),false);
  assert.equal(figures.requestMatchesAsset({...request,workspace_id:'c'.repeat(32)},asset),false);
  assert.equal(figures.requestMatchesAsset({...request,parent_sha256:'d'.repeat(64)},asset),false);
  assert.equal(figures.requestMatchesAsset({invalid:true},asset),false);
});

test('transport failures distinguish refused edits from unconfirmed exact commands',()=>{
  assert.equal(figures.failureKind({status:422}),'refused');
  assert.equal(figures.failureKind({status:503}),'unconfirmed');
  assert.equal(figures.failureKind(new Error('network')),'unconfirmed');
});

console.log('Addressable figure frontend contracts: '+passed+' passed');
