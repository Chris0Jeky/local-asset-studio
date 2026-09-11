"""Build one self-contained local audition/edit page from a validated project."""
from pathlib import Path
import argparse
import base64
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_av.project import read_json,validate,safe_path,need

def build(project,root,preview,out):
    validate(project,root);path=Path(preview);need(path.is_file() and path.stat().st_size<16*1024*1024,'Preview capped at16MiB')
    audio={}
    for k,a in project['assets'].items():
        if a['kind']=='audio':
            file=safe_path(root,a['path']);need(file.stat().st_size<4*1024*1024,'Embedded audio capped at4MiB per file')
            audio[k]=base64.b64encode(file.read_bytes()).decode()
    data=json.dumps({'project':project,'audio':audio,'preview':'data:video/mp4;base64,'+base64.b64encode(path.read_bytes()).decode()},ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(Path(__file__).resolve().parents[1]/'research/av-studio/workbench.template.html').read_text()
    need(template.count('__AV_DATA__')==1 and template.count('__AV_SCRIPT__')==1,'Bad template')
    script=(Path(__file__).resolve().parents[1]/'research/av-studio/workbench.js').read_text()
    template=template.replace('__AV_SCRIPT__',script)
    with Path(out).open('x',encoding='utf-8') as f:f.write(template.replace('__AV_DATA__',data))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('project');p.add_argument('--workspace',required=True);p.add_argument('--preview',required=True);p.add_argument('--out',required=True);a=p.parse_args();build(read_json(a.project),a.workspace,a.preview,a.out)
