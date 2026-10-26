"""Explicit shelf-owner setup for disposable browser fixtures, never production."""


async def inert_shelf_owner(page):
    """Single-document memory substitute; it is not native persistence proof."""
    await page.evaluate('''() => {
      const S=StudioAssetRecoveryShelf,current=()=>localStorage.getItem(S.KEY);
      const backend={read:async()=>{const raw=current();return raw===null?[]:[{version:1,raw,legacy_digest:null}];},
        compareAndSwap:async(before,next)=>{if(current()!==(before[0]?.raw??null))throw Error('Recovery storage changed in another tab.');
          localStorage.setItem(S.KEY,next.raw);if(current()!==next.raw)throw Error('Recovery readback did not verify.');}};
      assetShelfStore=S.create({storage:{getItem:()=>null},locks:()=>navigator.locks,crypto,backend});
      assetShelfSession=StudioAssetRecoveryShelfSession.create({journal:assetRecovery,store:assetShelfStore,crypto,onStatus:assetShelfStatus});
    }''')


async def replace_shelf_raw(page, raw, inert=False):
    """Restore synthetic setup between independent cases; no application migration."""
    if inert:
        await page.evaluate('raw=>localStorage.setItem(StudioAssetRecoveryShelf.KEY,raw)', raw)
    else:
        await page.evaluate('''raw=>new Promise((resolve,reject)=>{
          const S=StudioAssetRecoveryShelf,open=indexedDB.open(S.DATABASE,1);
          open.onupgradeneeded=()=>open.result.createObjectStore(S.STORE);
          open.onerror=()=>reject(open.error);open.onblocked=()=>reject(Error('Synthetic owner replacement blocked'));
          open.onsuccess=()=>{const db=open.result,tx=db.transaction(S.STORE,'readwrite');
            const store=tx.objectStore(S.STORE),read=store.get(S.ENTRY);
            read.onsuccess=()=>store.put({version:1,raw,legacy_digest:read.result?.legacy_digest??null},S.ENTRY);
            tx.oncomplete=()=>{db.close();resolve();};tx.onabort=()=>{db.close();reject(tx.error||Error('Synthetic owner replacement aborted'));};};
        })''', raw)


async def read_shelf_entry(page):
    return await page.evaluate('''()=>new Promise((resolve,reject)=>{
      const S=StudioAssetRecoveryShelf,open=indexedDB.open(S.DATABASE,1);
      open.onerror=()=>reject(open.error);open.onblocked=()=>reject(Error('Synthetic owner read blocked'));
      open.onsuccess=()=>{const db=open.result,tx=db.transaction(S.STORE,'readonly'),read=tx.objectStore(S.STORE).getAll(S.ENTRY,1);
        tx.oncomplete=()=>{db.close();resolve(read.result);};tx.onabort=()=>{db.close();reject(tx.error||Error('Synthetic owner read aborted'));};};
    })''')


async def clear_shelf_storage(page, inert=False):
    await page.evaluate('localStorage.clear();sessionStorage.clear()')
    if not inert:
        await page.evaluate('''()=>new Promise((resolve,reject)=>{
          const request=indexedDB.deleteDatabase(StudioAssetRecoveryShelf.DATABASE);
          request.onsuccess=()=>resolve();request.onerror=()=>reject(request.error);
          request.onblocked=()=>reject(Error('Synthetic recovery clear blocked'));
        })''')


async def refuse_shelf_writes(page, inert=False):
    if inert:
        await page.evaluate('''()=>{const proto=Object.getPrototypeOf(localStorage),set=proto.setItem;
          window.__restoreShelfStorage=()=>{proto.setItem=set;};proto.setItem=function(k,v){
            if(k===StudioAssetRecoveryShelf.KEY)throw new DOMException('Synthetic quota','QuotaExceededError');return set.call(this,k,v);};}''')
    else:
        await page.evaluate('''()=>{const proto=IDBObjectStore.prototype,put=proto.put;
          window.__restoreShelfStorage=()=>{proto.put=put;};proto.put=function(value,key){
            if(this.name===StudioAssetRecoveryShelf.STORE&&key===StudioAssetRecoveryShelf.ENTRY)throw new DOMException('Synthetic quota','QuotaExceededError');
            return put.call(this,value,key);};}''')
