"""Constrained CPU FFmpeg preview renderer. No arbitrary filters, URLs or shell strings."""
from __future__ import annotations
from array import array
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave
from .project import validate, safe_path, file_hash, write_new, need


def tool(name):
    found=shutil.which(name); need(found is not None,f'{name} is not installed/on PATH');return found

def input_options(kind, fps=None):
    """Return the single-file demuxer contract for a declared asset kind."""
    formats={'image':'image2','video':'mov','audio':'wav'}
    if kind not in formats: raise ValueError('Unknown media kind')
    options=['-protocol_whitelist','file','-format_whitelist',formats[kind]]
    if kind=='image':
        # image2 otherwise expands '%' patterns into neighbouring files.
        options+=['-f','image2','-pattern_type','none']
        if fps is not None: options+=['-loop','1','-framerate',fps]
    elif kind=='video':
        # MOV/MP4 data references can name media outside the declared input.
        options+=['-f','mov','-enable_drefs','0','-use_absolute_path','0']
    elif kind=='audio':
        options+=['-f','wav']
    return options

def probe(path,kind):
    # The caller has validated path/hash.  The explicit demuxer prevents probe
    # auto-detection from treating a renamed asset as a playlist or script.
    try:
        result=subprocess.run([tool('ffprobe'),'-v','error',*input_options(kind),'-show_entries',
            'format=duration:stream=codec_type,codec_name,width,height,sample_rate,channels,r_frame_rate','-of','json',str(path)],
            capture_output=True,timeout=20,check=True)
    except subprocess.CalledProcessError as exc:
        raise ValueError(f'Invalid constrained {kind} input') from exc
    need(len(result.stdout)<1024*1024,'Probe result too large');return json.loads(result.stdout)

def validate_media(p,root):
    result=validate(p,root); metadata={}
    for key,a in p['assets'].items():
        path=safe_path(root,a['path']);info=probe(path,a['kind']);metadata[key]=info
        kinds=[s for s in info['streams'] if s['codec_type']==('audio' if a['kind']=='audio' else 'video')]
        need(len(kinds)==1,'Expected a single primary media stream')
        stream=kinds[0]
        if a['kind']=='audio':
            with wave.open(str(path),'rb') as w:
                need(w.getsampwidth()==2 and w.getframerate()==48000 and w.getnchannels() in (1,2), 'Audio interchange must be 48kHz 16-bit mono/stereo PCM WAV')
                info['sample_count']=w.getnframes()
        else:
            need(0<stream['width']*stream['height']<=16*1024*1024,'Source pixel cap exceeded')
            if a['kind']=='image':need(stream['codec_name']=='png','Image bytes must actually be PNG')
    fps=p['fps'][0]/p['fps'][1]
    for s in p['shots']:
        if p['assets'][s['asset']]['kind']=='video':
            duration=float(metadata[s['asset']].get('format',{}).get('duration',0))
            need(math.isfinite(duration) and (s['source_in']+s['frames'])/fps<=duration+1/fps,'Video source too short')
    for c in p['audio']:
        need(c['source_sample']+c['samples']<=metadata[c['asset']]['sample_count'],'Audio source too short')
    return result,metadata

def compile_project(p,root):
    info=validate(p,root);root=Path(root).resolve();w,h=p['size'];fps=f"{p['fps'][0]}/{p['fps'][1]}";rate=p['fps'][0]/p['fps'][1]
    args=[];filters=[];index=0
    def source(asset):
        nonlocal index
        a=p['assets'][asset];opts=input_options(a['kind'],fps)
        opts+=['-i',str(safe_path(root,a['path']))];args.extend(opts);index+=1;return index-1
    def sec(frames):return f'{frames/rate:.9f}'
    cumulative=0;last=''
    for i,s in enumerate(p['shots']):
        ix=source(s['asset']);label=f'v{i}'
        filters.append(f'[{ix}:v]fps={fps},trim=start_frame={s["source_in"]}:end_frame={s["source_in"]+s["frames"]},setpts=PTS-STARTPTS,'
            f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,settb=AVTB,fps={fps}[{label}]')
        if i==0:last=label;cumulative=s['frames'];continue
        next_label=f'join{i}';transition=s['transition_frames']
        if transition:filters.append(f'[{last}][{label}]xfade=transition=fade:duration={sec(transition)}:offset={sec(cumulative-transition)},settb=AVTB,fps={fps}[{next_label}]')
        else:filters.append(f'[{last}][{label}]concat=n=2:v=1:a=0,settb=AVTB,fps={fps}[{next_label}]')
        last=next_label;cumulative+=s['frames']-transition
    for i,o in enumerate(p['overlays']):
        ix=source(o['asset']);label=f'overlay{i}';next_label=f'comp{i}'
        filters.append(f'[{ix}:v]scale={o["width"]}:{o["height"]},format=rgba,colorchannelmixer=aa={o["opacity"]}[{label}]')
        filters.append(f"[{last}][{label}]overlay=x={o['x']}:y={o['y']}:enable='gte(t,{sec(o['start'])})*lt(t,{sec(o['start']+o['frames'])})':shortest=1[{next_label}]")
        last=next_label
    filters.append(f'[{last}]fps={fps},tpad=stop_mode=clone:stop_duration=1,trim=end_frame={info["frames"]},setpts=PTS-STARTPTS[vout]')
    audio_labels=[]
    for i,c in enumerate(p['audio']):
        if c['mute']:continue
        ix=source(c['asset']);label=f'a{i}'
        chain=f'[{ix}:a]atrim=start_sample={c["source_sample"]}:end_sample={c["source_sample"]+c["samples"]},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,volume={c["gain_db"]}dB'
        if c['fade_in']:chain+=f',afade=t=in:ss=0:ns={c["fade_in"]}'
        if c['fade_out']:chain+=f',afade=t=out:ss={c["samples"]-c["fade_out"]}:ns={c["fade_out"]}'
        chain+=f',adelay=delays={c["start_sample"]}S:all=1[{label}]';filters.append(chain);audio_labels.append(label)
    if audio_labels:
        filters.append(''.join(f'[{s}]' for s in audio_labels)+f'amix=inputs={len(audio_labels)}:duration=longest:normalize=0,apad,atrim=end_sample={info["samples"]},volume={p["master_gain_db"]}dB[aout]')
    else:filters.append(f'anullsrc=r=48000:cl=stereo,atrim=end_sample={info["samples"]}[aout]')
    # Keep audio in a lossless sidecar; explicit later mux retains encoded mix in preview.
    return {**info,'input_args':args,'filter_complex':';'.join(filters),'supported':['cut','dissolve','still-overlay','audio-trim','gain','fade','mix'],'not_supported':['HDR','speed-ramp','VST','OTIO-roundtrip','automatic-ducking']}

def inspect_wav(path):
    with wave.open(str(path),'rb') as w:
        need(w.getsampwidth()==2 and w.getnchannels() in (1,2),'QC expects 16bit mono/stereo WAV')
        channels=w.getnchannels();rate=w.getframerate();count=w.getnframes()
        need(0<count<=48000*120,'QC duration cap exceeded')
        sums=[0]*channels;squares=[0]*channels;peaks=[0]*channels;full=[0]*channels;actual=0
        while raw:=w.readframes(4096):
            data=array('h',raw)
            if sys.byteorder!='little':data.byteswap()
            for i,x in enumerate(data):
                c=i%channels;sums[c]+=x;squares[c]+=x*x;peaks[c]=max(peaks[c],abs(x));full[c]+=int(x>=32767 or x<=-32768)
            actual+=len(data)//channels
    need(actual==count,'Truncated WAV body')
    db=lambda amplitude:20*math.log10(amplitude) if amplitude else None
    return {'samples':count,'sample_rate':rate,'channels':channels,'duration_seconds':count/rate,
        'sample_peak_dbfs':[db(v/32768) for v in peaks],'rms_dbfs':[db(math.sqrt(v/count)/32768) for v in squares],
        'dc_offset':[v/count/32768 for v in sums],'full_scale_sample_count':full,
        'near_or_at_clipping':any(full),'method':'16-bit decoded sample statistics; not LUFS, true peak, intelligibility or perceptual review'}

def render(p,root,out,timeout=180):
    need(type(timeout) is int and 1<=timeout<=600,'Timeout outside1..600')
    info,_=validate_media(p,root);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'.incomplete').write_text('Incomplete render; do not treat as accepted\n')
    snapshot=out/'inputs';snapshot.mkdir()
    import copy
    q=copy.deepcopy(p)
    for i,(key,a) in enumerate(p['assets'].items()):
        original=safe_path(root,a['path']);dest=snapshot/f'source-{i}{original.suffix.lower()}'
        with original.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
        need(file_hash(dest)==a['sha256'],'Source changed during snapshot')
        q['assets'][key]['path']=dest.relative_to(out).as_posix()
    plan=compile_project(q,out);write_new(out/'project-source.json',p);write_new(out/'project-snapshot.json',q)
    common=[tool('ffmpeg'),'-hide_banner','-nostdin','-loglevel','error','-n','-filter_complex_threads','1']
    command=common+plan['input_args']+['-filter_complex',plan['filter_complex'],'-map','[vout]','-an','-frames:v',str(info['frames']),'-c:v','libx264','-threads','2','-pix_fmt','yuv420p',str(out/'picture.mp4'),'-map','[aout]','-vn','-ar','48000','-ac','2','-c:a','pcm_s16le',str(out/'mix.wav')]
    write_new(out/'render-plan.json',{'source_revision':info['project_sha256'],'snapshot_plan':plan,'argv':command})
    with (out/'ffmpeg.log').open('wb') as log:subprocess.run(command,stdout=log,stderr=log,check=True,timeout=timeout)
    with (out/'mux.log').open('wb') as log:
        subprocess.run(common+['-i',str(out/'picture.mp4'),'-i',str(out/'mix.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out/'preview.mp4')],stdout=log,stderr=log,check=True,timeout=timeout)
    qc=inspect_wav(out/'mix.wav');metadata=probe(out/'preview.mp4','video')
    need(qc['samples']==info['samples'],'Output audio duration mismatch')
    duration=float(metadata['format']['duration']);need(abs(duration-info['duration_seconds'])<=max(.05,p['fps'][1]/p['fps'][0]),'Output AV duration mismatch')
    receipt={'schema_version':1,'source_revision':info['project_sha256'],'frames_expected':info['frames'],'audio_qc':qc,'probe':metadata,
        'outputs':{n:file_hash(out/n) for n in ('picture.mp4','mix.wav','preview.mp4')},'generation_performed':False,'creative_acceptance':'not_reviewed',
        'audio_model_benchmark':False,'ffmpeg_version':subprocess.run([tool('ffmpeg'),'-version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]}
    write_new(out/'receipt.json',receipt);(out/'.incomplete').unlink();return receipt
