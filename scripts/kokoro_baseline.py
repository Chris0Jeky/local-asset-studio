"""Offline CPU inference for a pinned Kokoro baseline bundle; invoked by Studio."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def execute(request_path, output):
    request=json.loads(Path(request_path).read_text(encoding='utf-8'));bundle=request['bundle']
    output=Path(output);output.mkdir(exist_ok=False)
    (output/'.incomplete').write_text('Incomplete voice take; inspect before requesting another.\n',encoding='utf-8')
    for item in bundle['files'].values():
        path=Path(item['path'])
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('Voice bundle changed')
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PIP_NO_INDEX='1',TOKENIZERS_PARALLELISM='false')
    # This isolated inference process has no network role. Missing G2P/model files fail here.
    def offline(*args,**kwargs):raise RuntimeError('Offline voice inference cannot open network connections')
    socket.socket.connect=offline;socket.socket.connect_ex=offline;socket.create_connection=offline
    import numpy as np
    import soundfile as sf
    import torch
    from kokoro import KPipeline
    from kokoro.model import KModel
    torch.set_num_threads(6);torch.set_num_interop_threads(1)
    start=time.monotonic();files=bundle['files']
    model=KModel(repo_id=bundle['model_id'],config=files['config']['path'],model=files['model']['path']).to('cpu').eval()
    pipeline=KPipeline(lang_code=bundle['lang_code'],repo_id=bundle['model_id'],model=model,device='cpu')
    load_seconds=time.monotonic()-start;records=[];total=0
    for line in request['lines']:
        began=time.monotonic();chunks=[];graphemes=[];phonemes=[]
        for result in pipeline(line['text'],voice=files['voice']['path'],speed=1):
            audio=np.asarray(result.audio,dtype=np.float32)
            if audio.ndim!=1 or not np.isfinite(audio).all():raise ValueError('Invalid voice waveform')
            total+=len(audio)
            if total>24000*120:raise ValueError('Voice take exceeds the 120-second sample budget')
            chunks.append(audio);graphemes.append(result.graphemes);phonemes.append(result.phonemes)
        if not chunks:raise ValueError('No voice audio returned')
        samples=np.concatenate(chunks);name=line['id']+'.wav';path=output/name
        sf.write(path,samples,24000,subtype='PCM_16')
        records.append({'id':line['id'],'speaker_id':request['speaker_id'],'text':line['text'],'graphemes':graphemes,'phonemes':phonemes,
                        'file':name,'sha256':sha(path),'bytes':path.stat().st_size,'sample_rate':24000,'samples':len(samples),
                        'seconds':len(samples)/24000,'elapsed_seconds':time.monotonic()-began})
        (output/'partial-receipt.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    receipt={'version':1,'model_id':bundle['model_id'],'model_revision':bundle['revision'],'voice':bundle['voice'],'speaker_id':request['speaker_id'],
             'load_seconds':load_seconds,'elapsed_seconds':time.monotonic()-start,'lines':records,'cpu_threads':6,'network_enabled':False,
             'voice_identity':'built-in baseline voice, not a designed or cloned character identity','creative_acceptance':'not_reviewed',
             'transcription':'not_performed','alignment':'not_performed','performance_instructions_supported':False}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');(output/'.incomplete').unlink();return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    execute(args.request,args.output)
