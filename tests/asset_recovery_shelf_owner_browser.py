"""Native cross-renderer shelf transactions and faults; synthetic browser data only."""
import argparse
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'app/static/asset-recovery-shelf.js'
JOURNAL = ROOT / 'app/static/asset-recovery.js'

SETUP = r'''async label=>{
 const S=StudioAssetRecoveryShelf;window.__label=label;window.__store=S.create();window.__events=[];
 window.__db=(action,value)=>new Promise((resolve,reject)=>{
   const open=indexedDB.open(S.DATABASE,1);open.onupgradeneeded=()=>open.result.createObjectStore(S.STORE);
   open.onerror=()=>reject(open.error);open.onblocked=()=>reject(Error('Fixture database blocked'));
   open.onsuccess=()=>{const db=open.result,tx=db.transaction(S.STORE,action==='read'?'readonly':'readwrite'),store=tx.objectStore(S.STORE);
     const request=action==='read'?store.getAll(S.ENTRY,1):action==='delete'?store.delete(S.ENTRY):store.put(value,S.ENTRY);
     tx.oncomplete=()=>{db.close();resolve(request.result);};tx.onabort=()=>{db.close();reject(tx.error||Error('Fixture transaction aborted'));};};
 });
 window.__record=async(i,note,generation=1)=>{
   const w='1'.repeat(32),form={title:'Synthetic owner',tags:'tag',review:'unreviewed',notes:note};
   const metadata={id:'asset-a',workspace_id:w,metadata_revision:0,title:form.title,notes:'baseline',tags:['tag'],review:'unreviewed',favorite:false,trashed_at:null};
   const command={ids:['asset-a'],action:'edit',notes:'submitted',workspace_id:w,expected_revisions:{'asset-a':0},request_id:'request_1234567890_'+i};
   const payload={version:2,workspace_id:w,id:'asset-a',metadata,baseline:{...form,notes:'baseline'},draft:form,
     operation:{command,body:JSON.stringify(command,null,2),kind:'details',snapshot:{...form,notes:'submitted'}},conflict:null};
   return S.seal('detail',payload,{id:i.toString(16).padStart(32,'0'),generation,created_at:1,updated_at:generation},crypto);
 };
 window.__seed=async records=>{if(records===null){await __db('delete');return;}await __db('put',{version:1,raw:await S.encode(records),legacy_digest:null});};
 window.__prepare=({barrier=null,target=null})=>{
   __events=[];window.__ready=false;let hits=0;
   const log=kind=>__events.push({tab:label,kind,at:performance.timeOrigin+performance.now()});
   const nativeLocks={request:(name,options,action)=>{log('requested');return navigator.locks.request(name,options,async lock=>{
     log('entered');try{return await action(lock);}finally{log('exited');}});}};
   const cryptoProxy={subtle:{digest:async(name,bytes)=>{
     let value;try{value=JSON.parse(new TextDecoder().decode(bytes));}catch(_){}
     const selected=barrier==='candidate'?value?.payload?.draft?.notes.startsWith('Candidate '):barrier==='decode'&&value?.id===target;
     if(selected&&++hits===(barrier==='candidate'?2:1)){log('candidate-ready');await new Promise(resolve=>{window.__release=resolve;window.__ready=true;});}
     return crypto.subtle.digest(name,bytes);
   }}};
   // This explicit fault-isolation lane omits cooperative lock scheduling so
   // both prepared candidates reach the actual IDB CAS from the same snapshot.
   // The ordinary queued case above still uses the native origin Web Lock.
   __store=S.create({locks:barrier?{request:async(_n,_o,action)=>action()}:nativeLocks,crypto:cryptoProxy});
 };
 window.__perform=async command=>{try{
   if(command.remove)await __store.remove(command.remove,command.expected);
   else await __store.put(command.record,command.expected);
   return {written:true,tab:label,digest:command.record?.sha256||null};
 }catch(error){return {written:false,tab:label,error:error.message,digest:command.record?.sha256||null};}};
 window.__dispatch=async(record,expected,store=__store)=>{
   const values=new Map(),memory={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
   // Match the real shelf restore bridge: canonical bundle key order must not
   // change the journal's command/body ordering, and wire bytes stay untouched.
   const payload=structuredClone(record.payload);payload.operation.command=JSON.parse(payload.operation.body);
   const journal=StudioAssetRecovery.create(memory);journal.write('detail',payload);const before=memory.getItem(StudioAssetRecovery.PREFIX+'detail');
   journal.connect({changed(){},prepare:()=>store.put(record,expected)});let posts=0,error=null;
   try{await journal.dispatch('detail',payload.operation,()=>{posts++;});}catch(problem){error=problem.message;}
   return {posts,error,journal_unchanged:memory.getItem(StudioAssetRecovery.PREFIX+'detail')===before};
 };
 performance.mark('shelf-owner-process-'+label);
 return {origin:location.origin,isolated:crossOriginIsolated};
}'''


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, trace = [], [], []
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (CORE, JOURNAL, Path(__file__))}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            source = CORE if self.path == '/core.js' else JOURNAL if self.path == '/journal.js' else None
            body = source.read_bytes() if source else b'<!doctype html><title>Synthetic transactional shelf</title><script src="/journal.js"></script><script src="/core.js"></script>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/javascript' if source else 'text/html')
            if self.path == '/isolated':
                self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
                self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
            self.end_headers(); self.wfile.write(body)

        def log_message(self, *_):
            pass

    def check(name, passed, detail=None):
        checks.append({'id': name, 'passed': bool(passed), 'detail': detail})
        print(name, bool(passed), flush=True)
        if not passed:
            raise AssertionError(name)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    failure = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(channel='chromium', headless=True, args=['--no-sandbox'])
            context = await browser.new_context()
            cdp = await browser.new_browser_cdp_session()
            cdp.on('Tracing.dataCollected', lambda event: trace.extend(event['value']))
            complete = asyncio.Event(); cdp.on('Tracing.tracingComplete', lambda _: complete.set())
            await cdp.send('Tracing.start', {'categories': 'blink.user_timing', 'transferMode': 'ReportEvents'})
            try:
                pages, identity = [], []
                for label, path in [('A', '/'), ('B', '/isolated')]:
                    page = await context.new_page(); page.set_default_timeout(6000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    await page.goto(f'http://127.0.0.1:{server.server_port}{path}')
                    identity.append(await page.evaluate(SETUP, label)); pages.append(page)
                a, b = pages

                async def records(count):
                    return await a.evaluate('async count=>Promise.all(Array.from({length:count},(_,i)=>__record(i+1,"Base "+i)))', count)

                async def race(name, existing, commands, barrier, target=None):
                    await a.evaluate('__seed', existing)
                    await asyncio.gather(*[page.evaluate('__prepare', {'barrier': barrier, 'target': target}) for page in pages])
                    queued = None
                    if barrier is None:
                        await a.evaluate('''()=>{window.__held=false;navigator.locks.request(StudioAssetRecoveryShelf.LOCK,()=>new Promise(resolve=>{window.__releaseLock=resolve;window.__held=true;}));}''')
                        await a.wait_for_function('__held')
                    tasks = [asyncio.create_task(page.evaluate('__perform', command)) for page, command in zip(pages, commands)]
                    for page in pages:
                        await page.wait_for_function('__ready' if barrier else '__events.some(event=>event.kind==="requested")')
                    if barrier:
                        await asyncio.gather(*[page.evaluate('__release()') for page in pages])
                    else:
                        queued = await a.evaluate('navigator.locks.query()'); await a.evaluate('__releaseLock()')
                    outcomes = await asyncio.gather(*tasks)
                    entry = (await a.evaluate('__db("read")'))[0]
                    persisted = json.loads(entry['raw'])['records']
                    winners = [index for index, result in enumerate(outcomes) if result['written']]
                    expected = list(existing or [])
                    if len(winners) == 1:
                        command = commands[winners[0]]
                        if command.get('remove'):
                            expected = [r for r in expected if r['id'] != command['remove']]
                        else:
                            record = command['record']; expected = [record if r['id'] == record['id'] else r for r in expected]
                            if not any(r['id'] == record['id'] for r in expected): expected.append(record)
                    detail = {'mode': 'native origin lock' if barrier is None else 'actual IDB CAS with prepared same-snapshot candidates',
                              'writers': outcomes, 'queued': queued, 'stored': persisted,
                              'events': sum(await asyncio.gather(*[page.evaluate('__events') for page in pages]), [])}
                    check(name, len(winners) == 1 and persisted == expected, detail)

                base = (await records(1))[0]
                next_a = await a.evaluate('r=>__record(1,"Candidate A",r.generation+1)', base)
                next_b = await a.evaluate('r=>__record(1,"Candidate B",r.generation+1)', base)
                await race('OWNER-NATIVE-01 queued native locks preserve exactly the reported winner', [base],
                           [{'record': next_a, 'expected': base['sha256']}, {'record': next_b, 'expected': base['sha256']}], None)
                first_a, first_b = await a.evaluate('Promise.all([__record(2,"Candidate A"),__record(3,"Candidate B")])')
                commands = [{'record': first_a, 'expected': None}, {'record': first_b, 'expected': None}]
                await race('OWNER-NATIVE-02 concurrent initialization compares absence atomically', None, commands, 'candidate')
                await race('OWNER-NATIVE-03 concurrent append retains the existing record and one winner', [base], commands, 'candidate')
                pair = await records(2)
                await race('OWNER-NATIVE-04 concurrent discard removes only its inspected record once', pair,
                           [{'remove': pair[0]['id'], 'expected': pair[0]['sha256']}] * 2, 'decode', pair[0]['id'])
                capacity = await records(19)
                last_a, last_b = await a.evaluate('Promise.all([__record(20,"Candidate A"),__record(21,"Candidate B")])')
                await race('OWNER-NATIVE-05 concurrent capacity checks retain all nineteen prior records', capacity,
                           [{'record': last_a, 'expected': None}, {'record': last_b, 'expected': None}], 'candidate')

                for initialized in [False, True]:
                    for kind in ['quota', 'abort']:
                        await a.evaluate('__seed', [base] if initialized else None)
                        candidate = next_a if initialized else first_a
                        result = await a.evaluate(r'''async data=>{
                          const before=await __db('read'),proto=IDBObjectStore.prototype,put=proto.put;
                          proto.put=function(value,key){if(this.name!==StudioAssetRecoveryShelf.STORE)return put.call(this,value,key);
                            if(data.kind==='quota')throw new DOMException('Synthetic owner quota','QuotaExceededError');
                            const request=put.call(this,value,key);request.addEventListener('success',()=>this.transaction.abort(),{once:true});return request;};
                          let outcome;try{outcome=await __dispatch(data.record,data.expected,StudioAssetRecoveryShelf.create());}finally{proto.put=put;}
                          return {...outcome,before,after:await __db('read')};
                        }''', {'kind': kind, 'record': candidate, 'expected': base['sha256'] if initialized else None})
                        check('OWNER-FAULT '+('replacement ' if initialized else 'initialization ')+kind+' preserves evidence and sends zero POST',
                              bool(result['error']) and result['posts'] == 0 and result['journal_unchanged'] and result['before'] == result['after'], result)

                await a.evaluate('__seed', [base])
                unavailable = await a.evaluate(r'''async record=>{
                  const before=await __db('read'),descriptor=Object.getOwnPropertyDescriptor(window,'indexedDB');
                  Object.defineProperty(window,'indexedDB',{value:undefined,configurable:true});let outcome;
                  try{outcome=await __dispatch(record,null,StudioAssetRecoveryShelf.create());}
                  finally{if(descriptor)Object.defineProperty(window,'indexedDB',descriptor);else delete window.indexedDB;}
                  return {...outcome,before,after:await __db('read')};
                }''', first_a)
                check('OWNER-FAULT unavailable IndexedDB never falls back or dispatches', unavailable['posts'] == 0 and unavailable['journal_unchanged'] and
                      'unavailable' in unavailable['error'] and unavailable['before'] == unavailable['after'], unavailable)
                blocked = await a.evaluate(r'''async record=>{
                  const S=StudioAssetRecoveryShelf,before=await __db('read');
                  const held=await new Promise((resolve,reject)=>{const r=indexedDB.open(S.DATABASE,1);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
                  held.onversionchange=()=>{};let upgradeDone;
                  const blocked=new Promise(resolve=>{const upgrade=indexedDB.open(S.DATABASE,2);
                    upgradeDone=new Promise(done=>{upgrade.onerror=()=>done();upgrade.onsuccess=()=>{upgrade.result.close();done();};});
                    upgrade.onblocked=()=>resolve();upgrade.onupgradeneeded=()=>upgrade.transaction.abort();});
                  await blocked;let outcome;
                  try{outcome=await __dispatch(record,null,S.create({lockTimeoutMs:30}));}finally{held.close();await upgradeDone;}
                  const after=await __db('read');
                  const late_handles_closed=await new Promise((resolve,reject)=>{
                    const probe=indexedDB.open(S.DATABASE,2);probe.onblocked=()=>reject(Error('A timed-out owner left a live database handle'));
                    probe.onupgradeneeded=()=>probe.transaction.abort();probe.onerror=()=>resolve(probe.error?.name==='AbortError');
                    probe.onsuccess=()=>{probe.result.close();reject(Error('Synthetic close probe unexpectedly upgraded the database'));};
                  });
                  return {...outcome,before,after,late_handles_closed};
                }''', first_a)
                check('OWNER-FAULT blocked open times out and closes late handles without dispatch', blocked['posts'] == 0 and blocked['journal_unchanged'] and
                      'timed out' in blocked['error'] and blocked['before'] == blocked['after'] and blocked['late_handles_closed'], blocked)

                migration = await a.evaluate(r'''async record=>{
                  const S=StudioAssetRecoveryShelf,legacy=await S.encode([record]);localStorage.setItem(S.KEY,legacy);await __db('delete');
                  const store=S.create(),inspected=await store.list(),before=await __db('read');
                  await store.remove(record.id,record.sha256);const entry=await __db('read'),after=await S.create().list();
                  return {legacy,retained:await store.legacyRaw(),inspected,before,entry,after};
                }''', base)
                check('OWNER-MIGRATION inspection is read-only and empty initialized shelf cannot resurrect legacy evidence',
                      migration['before'] == [] and migration['inspected'] == [base] and migration['legacy'] == migration['retained'] and
                      len(migration['entry']) == 1 and json.loads(migration['entry'][0]['raw'])['records'] == [] and migration['after'] == [], migration)
                check('OWNER-NATIVE no JavaScript exceptions', not errors, errors)
            except Exception as error:
                failure = error
            finally:
                await cdp.send('Tracing.end'); await asyncio.wait_for(complete.wait(), 10)
                marks = [{'name': item['name'], 'pid': item['pid']} for item in trace if item.get('name', '').startswith('shelf-owner-process-')]
                try:
                    check('OWNER-NATIVE distinct renderer processes share the same storage origin', len({m['pid'] for m in marks}) == 2 and
                          len({i['origin'] for i in identity}) == 1 and [i['isolated'] for i in identity] == [False, True], {'marks': marks, 'identity': identity})
                except Exception as error:
                    failure = failure or error
                (args.out / 'receipt.json').write_text(json.dumps({'mode': 'native Chromium IndexedDB/Web Locks/WebCrypto', 'browser': browser.version,
                    'source_sha256': source_hashes, 'checks': checks, 'errors': errors, 'failure': str(failure) if failure else None}, indent=2), encoding='utf-8')
                (args.out / 'trace.json').write_text(json.dumps(trace), encoding='utf-8')
                await browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
    if failure:
        raise failure
    if len(checks) != 14:
        raise AssertionError('Incomplete owner qualification')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-recovery-shelf-owner'))
    asyncio.run(exercise(parser.parse_args()))
