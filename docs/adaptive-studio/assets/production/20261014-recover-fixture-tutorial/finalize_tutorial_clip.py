"""Encode one completed actual UI recording; captions follow its observed shot timings."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,html
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--name',required=True);p.add_argument('--title',required=True);p.add_argument('--source',type=Path,required=True);a=p.parse_args();O=a.output.resolve();r=json.loads((O/'recording-receipt.json').read_text());clip=O/(a.name+'.mp4');assert not clip.exists()
assert not r['generation_submitted'] and not r['browser_errors'] and not r['forbidden_requests']
cmd=['ffmpeg','-hide_banner','-loglevel','error','-ss',str(r['trim_start_seconds']),'-i',str(O/r['raw_video']),'-t',str(r['duration_seconds']),'-an','-c:v','libx264','-preset','medium','-crf','22','-r','24','-pix_fmt','yuv420p','-movflags','+faststart',str(clip)]
subprocess.run(cmd,check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,avg_frame_rate,nb_frames','-of','json',str(clip)],text=True));stream=probe['streams'][0]
assert [stream['width'],stream['height']]==[1280,720] and stream['avg_frame_rate']=='24/1'
assert abs(float(probe['format']['duration'])-r['duration_seconds'])<.12
def stamp(t):
 ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
vtt='WEBVTT\n\n';transcript=[]
for i,e in enumerate(r['events']):
 end=r['events'][i+1]['seconds'] if i+1<len(r['events']) else min(r['duration_seconds'],float(probe['format']['duration']))
 vtt+=f'{i+1}\n{stamp(e["seconds"])} --> {stamp(end)}\n{e["caption"]}\n\n';transcript.append(stamp(e['seconds'])+' '+e['caption'])
(O/'captions.vtt').write_text(vtt,encoding='utf-8');(O/'transcript.txt').write_text('\n'.join(transcript)+'\n',encoding='utf-8');shutil.copy2(a.source,O/a.source.name)
poster=O/'poster.png';shutil.copy2(O/r['events'][min(3,len(r['events'])-1)]['screenshot'],poster)
decoded=[]
for i,e in enumerate(r['events']):
 t=e['seconds']+.7;f=O/f'decoded-{i+1:02}.png';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(t),'-i',str(clip),'-frames:v','1',str(f)],check=True);decoded.append(dict(seconds=t,file=f.name))
steps=''.join('<li>'+html.escape(e['caption'])+'</li>' for e in r['events'])
(O/'index.html').write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(a.title)}</title><style>body{{font:17px/1.6 system-ui;color:#243c3b;background:#f3eedf;max-width:1100px;margin:24px auto;padding:0 18px}}video{{display:block;width:100%;background:#111}}button{{font:inherit;min-height:44px;padding:10px 16px}}a{{color:#164d4d}}code{{overflow-wrap:anywhere}}li{{margin:10px 0}}::cue{{font:18px system-ui;background:#121416;color:white}}</style><h1>{html.escape(a.title)}</h1><p>Actual isolated Studio at <code>{r['application_revision']}</code>. No generation submitted. This records preparation and controls, not a model’s image quality or readiness. Backend health is unavailable in this isolated environment.</p><button id="load">Load recording</button><video id="clip" controls preload="none" poster="poster.png"><track kind="captions" src="captions.vtt" srclang="en" label="English" default></video><p>Silent 720p / 24 fps. Use Play after loading. Captions and the complete static steps are editable.</p><ol>{steps}</ol><p><a href="{clip.name}">Open MP4 directly</a> · <a href="captions.vtt">Captions</a> · <a href="transcript.txt">Transcript</a> · <a href="{a.source.name}">Recording source</a> · <a href="recording-receipt.json">State and HTTP receipt</a></p><script>const v=document.querySelector('#clip');document.querySelector('#load').onclick=()=>{{v.src='{clip.name}';v.load();document.querySelector('#load').hidden=true}};document.addEventListener('visibilitychange',()=>{{if(document.hidden)v.pause()}});addEventListener('pagehide',()=>v.pause());if(window.IntersectionObserver)new IntersectionObserver(es=>{{if(!es[0].isIntersecting)v.pause()}}).observe(v);matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>{{if(e.matches)v.pause()}});</script></html>''',encoding='utf-8')
(O/'media-receipt.json').write_text(json.dumps(dict(ffprobe=probe,sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),caption_cues=len(r['events']),decoded_frames=decoded,encode_command=cmd,encode_attempts=1),indent=2)+'\n');print(json.dumps(dict(clip=str(clip),probe=probe)))
