'use strict';
const assert=require('node:assert/strict');
const grid=require('../app/static/asset-grid.js');
let passed=0;
function test(name,fn){fn();passed++;console.log('PASS',name);}
const asset={id:'a',media_type:'image',url:'/api/assets/a/file',sha256:'a'.repeat(64),title:'A',preset_name:'Fixture',review:'unreviewed',favorite:false,tags:['one','two','three','four','not displayed']};
test('A remaining focused asset retains its identity across reorder',()=>assert.equal(grid.nextFocus(['a','b','c'],['c','a','b'],'b'),'b'));
test('Removal prefers the next survivor in prior reading order',()=>assert.equal(grid.nextFocus(['a','b','c','d'],['d','a','c'],'b'),'c'));
test('Last removal falls back to the previous survivor',()=>assert.equal(grid.nextFocus(['a','b','c'],['a','b'],'c'),'b'));
test('No surviving previous item chooses the first new item',()=>assert.equal(grid.nextFocus(['a','b'],['x','y'],'a'),'x'));
test('Empty results have no card focus target',()=>assert.equal(grid.nextFocus(['a'],[],'a'),null));
test('Metadata and selection do not alter media identity',()=>assert.equal(grid.mediaKey(asset),grid.mediaKey({...asset,title:'New',review:'selected',favorite:true,tags:[]})));
test('Source URL, hash and media type each invalidate media identity',()=>{for(const change of [{url:'/new'},{sha256:'b'.repeat(64)},{media_type:'video'}])assert.notEqual(grid.mediaKey(asset),grid.mediaKey({...asset,...change}));});
test('Only displayed metadata belongs to the render signature',()=>{assert.equal(grid.displayKey(asset,false),grid.displayKey({...asset,notes:'New notes',metadata_revision:10,tags:[...asset.tags.slice(0,4),'changed invisible tag']},false));assert.notEqual(grid.displayKey(asset,false),grid.displayKey({...asset,title:'Renamed'},false));assert.notEqual(grid.displayKey(asset,false),grid.displayKey(asset,true));});
test('Arbitrary string identifiers are compared without interpreting selectors',()=>assert.equal(grid.nextFocus(['[a]','"b"','c'],['c','"b"'],'[a]'),'"b"'));
console.log(`Asset grid contracts: ${passed} passed`);
