"""Fix file:// caption loading without re-encoding or changing an accepted clip."""
from pathlib import Path
import argparse,json
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();O=a.output.resolve();file=O/'index.html';s=file.read_text(encoding='utf-8');vtt=(O/'captions.vtt').read_text(encoding='utf-8')
literal='const captionSource='+json.dumps(vtt,ensure_ascii=True)+';'
if 'captionSource' in s:
 start=s.index('const captionSource=');end=s.index("document.querySelector('#load')",start);s=s[:start]+literal+s[end:]
else:
 assert 'src="captions.vtt"' in s
 s=s.replace('src="captions.vtt" ','')
 s=s.replace("const v=document.querySelector('#clip');", "const v=document.querySelector('#clip');"+literal)
 s=s.replace("document.querySelector('#load').onclick=()=>{", "document.querySelector('#load').onclick=()=>{const t=v.querySelector('track');t.src=URL.createObjectURL(new Blob([captionSource],{type:'text/vtt'}));v.textTracks[0].mode='showing';")
file.write_text(s,encoding='utf-8');print('Caption player updated; MP4 bytes unchanged.')
