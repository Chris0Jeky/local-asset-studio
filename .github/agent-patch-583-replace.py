from __future__ import annotations

import argparse
from pathlib import Path

TEST = Path('tests/workbench_handoff_guards.cjs')
SOURCE = Path('app/static/studio-workbench.js')
MARKER = "test('a delayed replacement copy cannot overwrite a newer workbench state'"

TEST_APPEND = r'''

const replaceSecondPictureSource = between("  q('#uxSecondReplace').onclick=async()=>{", '\n  // A modal handoff carries IDs');

function replaceHarness() {
  const context = {};
  vm.runInNewContext([
    "let secondPicture={asset:{id:'replacement',title:'Replacement'}},continuationState={source_asset_id:'source'};",
    "const selected={id:'recipe'};let stamp='before',finish,uploaded='old-upload',draftDirty=false;",
    "const notices=[];const nodes=new Map();const q=selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',files:[]});return nodes.get(selector);};",
    "const window={confirm:()=>true};const dismissSecondPicture=()=>{secondPicture=null};",
    "const selectPreset=()=>{stamp='reset'};const workbenchStamp=()=>stamp;",
    "const post=()=>new Promise(resolve=>{finish=resolve});",
    "let replaceCount=0,saveCount=0,syncCount=0;",
    "const replaceParentAsset=()=>{replaceCount++};const saveDraft=()=>{saveCount++};const syncCreate=()=>{syncCount++};",
    "const announce=(message,error=false)=>notices.push({message,error});const secondName=item=>item.asset.title;",
    "const legacyReferenceChange=null;const DataTransfer=function(){};const Event=function(){};",
    replaceSecondPictureSource,
    "this.start=()=>q('#uxSecondReplace').onclick();this.setStamp=value=>{stamp=value};this.finish=value=>finish(value);",
    "this.state=()=>({uploaded,draftDirty,replaceCount,saveCount,syncCount});this.notices=notices;",
  ].join('\n'), context);
  return context;
}

test('a delayed replacement copy cannot overwrite a newer workbench state', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.setStamp('changed');
  harness.finish({file:'replacement.png'});
  await pending;
  assert.deepEqual(harness.state(), {
    uploaded:'old-upload',draftDirty:false,replaceCount:0,saveCount:0,syncCount:0,
  });
  assert.equal(harness.notices.at(-1).error, true);
  assert.match(harness.notices.at(-1).message, /workbench changed/);
});

test('a current replacement copy commits once', async () => {
  const harness = replaceHarness();
  const pending = harness.start();
  harness.finish({file:'replacement.png'});
  await pending;
  assert.deepEqual(harness.state(), {
    uploaded:'replacement.png',draftDirty:true,replaceCount:1,saveCount:1,syncCount:1,
  });
  assert.equal(harness.notices.length, 1);
  assert.equal(harness.notices[0].error, false);
  assert.match(harness.notices[0].message, /now the reference/);
});
'''


def add_test() -> None:
    source = TEST.read_text(encoding='utf-8')
    if MARKER not in source:
        TEST.write_text(source.rstrip() + TEST_APPEND + '\n', encoding='utf-8')


def add_implementation() -> None:
    source = SOURCE.read_text(encoding='utf-8')
    old = "      else{const result=await post('/api/assets/reference',{id:item.asset.id});uploaded=result.file;q('#reference').value='';replaceParentAsset('reference',null,item.asset.id);}"
    new = "      else{const stamp=workbenchStamp(),result=await post('/api/assets/reference',{id:item.asset.id});if(stamp!==workbenchStamp())throw Error('The workbench changed while the picture was being copied. It was not applied.');uploaded=result.file;q('#reference').value='';replaceParentAsset('reference',null,item.asset.id);}"
    if new in source:
        return
    if source.count(old) != 1:
        raise SystemExit('replacement source marker changed')
    SOURCE.write_text(source.replace(old, new), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-only', action='store_true')
    parser.add_argument('--implementation', action='store_true')
    args = parser.parse_args()
    if args.test_only == args.implementation:
        raise SystemExit('choose exactly one mode')
    add_test()
    if args.implementation:
        add_implementation()


if __name__ == '__main__':
    main()
