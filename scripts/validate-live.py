"""Read-only native-node validation of Workflow Lab graphs; never queues work."""
import json
from pathlib import Path
from urllib.request import urlopen

root=Path(__file__).resolve().parents[1]
info=json.load(urlopen('http://127.0.0.1:8188/object_info',timeout=30))
presets=json.loads((root/'presets/catalog.json').read_text(encoding='utf-8'))['presets']
errors=[];missing=[];count=0
for preset in presets:
    if preset.get('collection')!='workflow-lab':continue
    count+=1
    graph=json.loads((root/preset['graph']).read_text(encoding='utf-8'))
    for key,node in graph.items():
        prefix=f'{preset["id"]}/{key}/{node["class_type"]}'
        schema=info.get(node['class_type'])
        if not schema:errors.append(prefix+': missing node');continue
        inputs=node['inputs'];required=schema.get('input',{}).get('required',{});optional=schema.get('input',{}).get('optional',{})
        for field in required:
            if field not in inputs:errors.append(prefix+': missing '+field)
        for field,value in inputs.items():
            spec=(required|optional).get(field)
            if spec is None:errors.append(prefix+': unknown input '+field);continue
            kind=spec[0];options=spec[1] if len(spec)>1 and isinstance(spec[1],dict) else {}
            if isinstance(value,list):
                source,slot=value
                try:out=info[graph[source]['class_type']]['output'][slot]
                except (KeyError,IndexError):errors.append(prefix+': invalid link '+field);continue
                if isinstance(kind,str) and kind!='*' and out!='*' and not set(out.split(',')) & set(kind.split(',')):errors.append(prefix+': socket mismatch '+field+' '+str(out)+' -> '+kind)
            else:
                enum=kind if isinstance(kind,list) else options.get('options') if kind=='COMBO' else None
                if enum is not None and value not in enum:
                    (missing if isinstance(value,str) and value.endswith(('.safetensors','.png')) else errors).append(prefix+': unavailable '+str(value))
                if kind in ('INT','FLOAT'):
                    if 'min' in options and value<options['min']:errors.append(prefix+': below min '+field)
                    if 'max' in options and value>options['max']:errors.append(prefix+': above max '+field)
for error in errors:print('ERROR',error)
for item in missing:print('MISSING FILE',item)
print(f'{count} native graphs: {len(errors)} schema errors, {len(missing)} missing file selections; no submissions')
raise SystemExit(1 if errors or missing else 0)
