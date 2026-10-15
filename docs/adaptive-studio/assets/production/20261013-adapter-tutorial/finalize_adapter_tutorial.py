"""Encode a real screen capture and author editable captions/static delivery."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--recording-source',type=Path,default=Path(__file__).with_name('record_adapter_strength.py'))
args=parser.parse_args();out=args.output.resolve()
r=json.loads((out/'recording-receipt.json').read_text(encoding='utf-8'))
assert r['changed_control_keys']==['lora'] and r['jobs_after']==[] and not r['browser_errors']
assert float(r['before']['controls']['lora'])==1 and float(r['after']['controls']['lora'])==.8
assert r['before']['controls']['lora2']==r['after']['controls']['lora2']=='0'
clip=out/'tutorial-adapters.mp4'
command=['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',str(r['trim_start_seconds']),'-i',str(out/r['raw_video']),'-t',str(r['duration_seconds']),'-an','-c:v','libx264','-preset','medium','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(clip)]
subprocess.run(command,check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,codec_type','-of','json',str(clip)],text=True))
assert 20<=float(probe['format']['duration'])<=35 and int(probe['format']['size'])<8*1024*1024
assert len(probe['streams'])==1 and probe['streams'][0]['codec_name']=='h264'
assert [probe['streams'][0]['width'],probe['streams'][0]['height']]==[1280,720]
captions=[
 'Actual isolated Studio. Readiness is unavailable; no image will be generated.',
 'Inspect the authored checkpoint and adapter files. Installed bytes are not verified.',
 'Read stored adapter notes: slot 1 is at 1.0; slot 2 is off.',
 'Return to the editable workbench. Slot 1 is 1.0 and slot 2 is 0.',
 'Change only slot 1 to 0.8. All other controls and adapter files stay unchanged.',
 'Slot 2 remains 0. This records an edit, not the visual effect of an adapter.',
 'Readiness remains unavailable. No generation, model launch or download occurred.']
def stamp(t):
    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'
vtt='WEBVTT\n\n';transcript=[]
for i,(event,caption) in enumerate(zip(r['events'],captions)):
    end=r['events'][i+1]['seconds'] if i+1<len(captions) else min(r['duration_seconds'],float(probe['format']['duration']))
    vtt+=f'{i+1}\n{stamp(event["seconds"])} --> {stamp(end)}\n{caption}\n\n'
    transcript.append(f'{stamp(event["seconds"])} {caption}')
(out/'captions.vtt').write_text(vtt.rstrip()+'\n',encoding='utf-8');(out/'transcript.txt').write_text('\n'.join(transcript)+'\n',encoding='utf-8')
if args.recording_source.resolve() != (out/'record_adapter_strength.py').resolve():
    shutil.copyfile(args.recording_source,out/'record_adapter_strength.py')
shutil.copyfile(out/'05-edited.png',out/'poster.png')
decoded=[]
for seconds in [1,6,10,14,18,22,26]:
    file=out/f'decoded-{seconds:02}.png'
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',str(seconds),'-i',str(clip),'-frames:v','1',str(file)],check=True)
    decoded.append(file.name)
steps=''.join('<li>'+caption+'</li>' for caption in captions)
(out/'index.html').write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Inspect and edit one adapter strength</title><style>body{{font:17px/1.6 system-ui;max-width:1000px;margin:2rem auto;padding:0 1rem;background:#f4f2e9;color:#17372e}}video{{display:block;width:100%;height:auto;background:#121416}}button,a{{font:inherit}}button{{padding:.65rem 1rem;margin:.5rem 0}}li{{margin:.65rem 0}}code{{overflow-wrap:anywhere}}::cue{{font:18px system-ui;background:#121416;color:#fff}}</style></head><body><h1>Inspect the stack. Edit one strength.</h1><p>Actual isolated Local Asset Studio UI at <code>{r['application_revision']}</code>. Readiness unavailable. No generation or model effect is claimed. Historical examples shown by the app are not new outputs.</p><p>Slot 1: <b>1.0 → 0.8</b>. Slot 2: <b>0 → 0</b>. Every other workbench value stays unchanged.</p><button id="load" type="button">Load recording</button><video id="clip" controls preload="none" poster="poster.png" aria-label="Actual adapter strength edit, with editable English captions"><track kind="captions" src="captions.vtt" srclang="en" label="English" default></video><p>Use the video controls to play or pause. The clip pauses when hidden or scrolled away.</p><h2>Complete static steps</h2><ol>{steps}</ol><p><a href="transcript.txt">Plain transcript</a> · <a href="captions.vtt">Editable captions</a> · <a href="recording-receipt.json">Before/after receipt</a> · <a href="record_adapter_strength.py">Recording source</a></p><script>const v=document.querySelector('#clip');document.querySelector('#load').onclick=()=>{{v.src='tutorial-adapters.mp4';v.load();document.querySelector('#load').hidden=true}};document.addEventListener('visibilitychange',()=>{{if(document.hidden)v.pause()}});if(window.IntersectionObserver)new IntersectionObserver(es=>{{if(!es[0].isIntersecting)v.pause()}}).observe(v);const motion=matchMedia('(prefers-reduced-motion: reduce)');motion.addEventListener('change',()=>{{if(motion.matches)v.pause()}});</script></body></html>''',encoding='utf-8')
receipt={'ffprobe':probe,'clip_sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),'decoded_frames':decoded,'caption_cues':len(captions),'encode_command':command,'encode_attempts':1,'assertions':['one changed control only','slot2 unchanged','zero jobs','zero browser page errors','silent1280x720H264','20-35 seconds','under8MiB']}
(out/'media-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'duration':probe['format']['duration'],'bytes':int(probe['format']['size']),'sha256':receipt['clip_sha256'],'captions':len(captions)}))
