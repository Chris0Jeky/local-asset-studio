'use strict';
// Explicit component-test owner. Synchronous compare/write is atomic within this
// one JS process; this adapter makes no native IndexedDB or cross-tab claim.
const Core=require('../app/static/asset-recovery-shelf.js');
module.exports=function create(options){
  const {storage,...rest}=options,target=()=>typeof storage==='function'?storage():storage;
  const backend={
    async read(){const raw=target().getItem(Core.KEY);return raw===null?[]:[{version:1,raw,legacy_digest:null}];},
    async compareAndSwap(before,next){
      const store=target();if(store.getItem(Core.KEY)!==(before[0]?.raw??null))throw Error('Recovery storage changed in another tab.');
      store.setItem(Core.KEY,next.raw);if(store.getItem(Core.KEY)!==next.raw)throw Error('Recovery readback did not verify.');
    }
  };
  return Core.create({...rest,storage:{getItem:()=>null},backend});
};
