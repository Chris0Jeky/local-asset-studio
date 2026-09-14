'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const C=require('../app/static/studio-guide-state.js');

assert.equal(typeof C.referenceSlots,'function','the guide needs one pure reference-slot policy');
const board={reference_slots:[{role:'style'},{role:'style'},{role:'style'}],reference_board:{min:1}};
assert.deepEqual(C.referenceSlots(board,[{file:'one.png'},{file:null},{file:null}]),{attached:true,missing:false});
assert.deepEqual(C.referenceSlots({...board,reference_board:{min:2}},[{file:'one.png'},{file:null},{file:null}]),{attached:false,missing:false});
assert.deepEqual(C.referenceSlots(board,[{file:'one.png'},{file:null,missing:true},{file:null}]),{attached:false,missing:true});
const named={reference_slots:[{role:'identity'},{role:'pose'}]};
assert.deepEqual(C.referenceSlots(named,[{file:'one.png'},{file:null}]),{attached:false,missing:false});
assert.deepEqual(C.referenceSlots(named,[{file:'one.png'},{file:'two.png'}]),{attached:true,missing:false});

const guide=fs.readFileSync(path.join(__dirname,'../app/static/studio-guide.js'),'utf8');
assert.match(guide,/C\.referenceSlots\(p,\s*roles\)/,'the mounted guide must use the shared board-aware policy');
assert.doesNotMatch(guide,/roles\.length\s*===\s*roleCount\s*&&\s*roles\.every/,'the old all-slots-only guide check must be removed');
console.log('Style-board guide readiness contract passed');
