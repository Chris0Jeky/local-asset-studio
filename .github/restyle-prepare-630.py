from pathlib import Path
import hashlib

def blob(path):
    data=Path(path).read_bytes()
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

before={'app/static/app.js':'86e898d559e8170c3b2dd143416a0d458509c46e','tests/frontend_handoffs.cjs':'859d1bd2564d799f6e5e1dc87eda9d8fd8d58aae','tests/setup_lineage_browser.py':'07d9210f080cbb67fbd103dd172ffd8b64dfeef3'}
after={'app/static/app.js':'c167a9417e1bdeee1c2c155775b53b408c69eb94','tests/frontend_handoffs.cjs':'b7d629ecf9f42617acc0d39d704963da0587f606','tests/setup_lineage_browser.py':'8afe6d51fde070b4aac98178b3e761ccb994af66'}
for path,expected in before.items():
    assert blob(path)==expected, ('base mismatch',path)
p=Path('app/static/app.js');s=p.read_text();old="const saved=s.parent_by_input,mapped=saved&&typeof saved==='object'&&!Array.isArray(saved)&&Object.keys(saved).length?saved:null;";new="const savedMapping=s.parent_by_input,mapped=savedMapping&&typeof savedMapping==='object'&&!Array.isArray(savedMapping)&&Object.keys(savedMapping).length?savedMapping:null;";assert s.count(old)==1;p.write_text(s.replace(old,new))
p=Path('tests/frontend_handoffs.cjs');s=p.read_text();a=s.index('async function boardContinuationSourceHasItsOwnLineageClaim()');at=s.index('  assert.deepEqual(JSON.parse(s.run(\'JSON.stringify(parentByInput)\')),',s.index("s.run(`selectPreset('plain');applySaved",a));s=s[:at]+"  await flush(); // Settle the saved role availability check before the replacement upload.\n"+s[at:];p.write_text(s)
p=Path('tests/setup_lineage_browser.py');s=p.read_text();needle="                    await page.add_script_tag(content=(ROOT/'app/static/workshop.js').read_text())";assert s.count(needle)==1;s=s.replace(needle,"                    await page.add_script_tag(content=(ROOT/'app/static/presentation-context.js').read_text())\n"+needle);p.write_text(s)
for path,expected in after.items():
    assert blob(path)==expected, ('result mismatch',path)
print('Prepared exact locally tested source blobs:',after)
