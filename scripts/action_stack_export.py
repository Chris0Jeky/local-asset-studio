"""Verified local bridge: a prepared Action Stack brief -> existing LAS narration.

No model loader, network server, source watcher, or browser-triggered generation.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import wave

MAX_AUDIO = 12_000_000
HASH = re.compile(r'[a-f0-9]{64}')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def bounded(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Expected a bounded regular file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('File exceeded its bound')
    return raw

def validate_request(value):
    required = {'schema','jobId','briefId','actionId','narration','narrationSha256','profileId','deliveryId'}
    if not isinstance(value, dict) or set(value) != required or any(not isinstance(v, str) for v in value.values()):
        raise ValueError('Invalid narration request shape')
    if value['schema'] != 'action-stack.request/v1':
        raise ValueError('Unsupported narration request')
    if not all(HASH.fullmatch(value[k]) for k in ('jobId','briefId','narrationSha256')):
        raise ValueError('Invalid request identity')
    text = value['narration']
    if not text.strip() or len(text) > 1600 or any(ord(c) < 32 for c in text):
        raise ValueError('Narration must be one bounded plain-text paragraph')
    if sha(text.encode('utf-8')) != value['narrationSha256']:
        raise ValueError('Narration content changed')
    for key in ('profileId', 'deliveryId'):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}', value[key]):
            raise ValueError('Invalid voice selector')
    if not 1 <= len(value['actionId']) <= 200:
        raise ValueError('Invalid source identity')
    expected = sha('\n'.join(value[k] for k in ('briefId','narrationSha256','profileId','deliveryId')).encode('utf-8'))
    if expected != value['jobId']:
        raise ValueError('Job does not bind this content and voice')
    return value

def check_wav(raw):
    if len(raw) > MAX_AUDIO or len(raw) < 44 or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE' or int.from_bytes(raw[4:8], 'little') + 8 != len(raw):
        raise ValueError('Invalid bounded WAV')
    with wave.open(io.BytesIO(raw), 'rb') as audio:
        if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getcomptype()) != (1,2,48000,'NONE'):
            raise ValueError('Expected LAS 48 kHz mono PCM16')
        frames = audio.getnframes()
        if not 0 < frames <= 48000 * 120 or len(audio.readframes(frames)) != frames * 2:
            raise ValueError('Invalid WAV duration or truncated samples')

def atomic(path, raw):
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix='.publish-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def generate(source, request, base_url):
    # Existing coordinator owns recipe, model, identity and uncertain-child recovery.
    from spoken_brief_runtime import plan, run
    arguments = {'profile_id':request['profileId'], 'delivery_id':request['deliveryId']}
    preview = plan(source, **arguments)
    manifest = json.loads(bounded(preview['manifest'], 1_000_000))
    spoken = ' '.join(segment['text'] for segment in manifest['segments'])
    if ' '.join(spoken.split()) != ' '.join(request['narration'].split()):
        raise ValueError('Spoken projection differs from the supplied transcript; prepare plain text upstream')
    return run(source, base_url=base_url, deadline_seconds=540, **arguments)

def export_brief(value, job_dir, *, base_url='http://127.0.0.1:8191', producer=generate):
    request = validate_request(value)
    root = Path(job_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.action-stack-export.lock'
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        source_bytes = (request['narration'] + '\n').encode('utf-8')
        source = root / 'COMPRESSED.md'
        if source.exists() and bounded(source, 10000) != source_bytes:
            raise ValueError('Retained source changed; do not overwrite a narration run')
        if not source.exists(): atomic(source, source_bytes)
        destination = root / 'bundle.json'
        if destination.exists():
            bundle = json.loads(bounded(destination, 10000))
            for key in ('jobId','briefId','narrationSha256','profileId','deliveryId'):
                if bundle.get(key) != request[key]: raise ValueError('Retained bundle binding changed')
            if not all(HASH.fullmatch(str(bundle.get(k,''))) for k in ('audioSha256','receiptSha256','producerSha256')):
                raise ValueError('Retained provenance is malformed')
            raw = bounded(root / 'audio.wav', MAX_AUDIO)
            if bundle.get('schema') != 'action-stack.audio/v1' or sha(raw) != bundle.get('audioSha256'):
                raise ValueError('Retained audio changed')
            check_wav(raw)
            return {'status':'ready','jobId':request['jobId'],'reused':True}
        result = producer(source, request, base_url)
        def owned(name):
            p = Path(result[name]).resolve()
            if not p.is_relative_to(root / '_spoken'):
                raise ValueError('Producer returned a foreign artifact')
            return p
        receipt_bytes = bounded(owned('receipt'), 1_000_000)
        receipt = json.loads(receipt_bytes)
        raw = bounded(owned('output'), MAX_AUDIO)
        if receipt.get('source',{}).get('sha256') != sha(source_bytes) or bounded(source,10000) != source_bytes:
            raise ValueError('Producer receipt does not bind the exact source')
        if receipt.get('output',{}).get('sha256') != sha(raw) or not HASH.fullmatch(str(receipt.get('producer_sha256',''))):
            raise ValueError('Producer audio hash or provenance is invalid')
        check_wav(raw)
        bundle = {key:request[key] for key in ('jobId','briefId','narrationSha256','profileId','deliveryId')}
        bundle.update(schema='action-stack.audio/v1',audioSha256=sha(raw),receiptSha256=sha(receipt_bytes),producerSha256=receipt['producer_sha256'])
        atomic(root / 'audio.wav', raw)
        atomic(destination, (json.dumps(bundle,sort_keys=True) + '\n').encode('utf-8'))
        return {'status':'ready','jobId':request['jobId'],'reused':False}
    finally:
        lock.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--job-dir', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8191')
    args = parser.parse_args()
    try:
        result = export_brief(json.loads(bounded(args.request,20000)),args.job_dir,base_url=args.base_url)
        print(json.dumps(result)); return 0
    except Exception:  # CLI boundary also redacts coordinator/transport exceptions.
        # Do not echo private brief text, paths, credentials or upstream response bodies.
        print('Narration export blocked; inspect the retained local LAS run.',file=__import__('sys').stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
