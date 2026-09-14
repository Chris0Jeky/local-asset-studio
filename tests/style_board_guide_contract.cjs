'use strict';
const assert=require('node:assert/strict');
const C=require('../app/static/studio-guide-state.js');

assert.equal(typeof C.referenceSlots,'function','the guide needs one pure reference-slot policy');
const board={reference_slots:[{role:'style'},{role:'style'},{role:'style'}],reference_board:{min:1}};
assert.deepEqual(C.referenceSlots(board,[{file:'one.png'},{file:null},{file:null}]),{attached:true,missing:false});
assert.deepEqual(C.referenceSlots({...board,reference_board:{min:2}},[{file:'one.png'},{file:null},{file:null}]),{attached:false,missing:false});
assert.deepEqual(C.referenceSlots(board,[{file:'one.png'},{file:null,missing:true},{file:null}]),{attached:false,missing:true});
const named={reference_slots:[{role:'identity'},{role:'pose'}]};
assert.deepEqual(C.referenceSlots(named,[{file:'one.png'},{file:null}]),{attached:false,missing:false});
assert.deepEqual(C.referenceSlots(named,[{file:'one.png'},{file:'two.png'}]),{attached:true,missing:false});
console.log('Style-board guide readiness contract passed');
