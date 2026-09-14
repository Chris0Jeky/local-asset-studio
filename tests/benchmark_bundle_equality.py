"""Finite fresh-process benchmark for the two-stage bundle equality predicate.

Reuses #366's fixture, hashing and peak-RSS semantics. No models or network.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from PIL import Image
from benchmark_cpu_copies import fixture, load_module, peak_rss, pixel_hash


def trial(module_path, edge, changed):
    module=load_module(module_path)
    with closing(fixture(edge,'RGBA')) as a, closing(a.copy()) as b:
        if changed != 'none':
            location=(0,0) if changed=='first' else (edge-1,edge-1)
            pixel=b.getpixel(location); b.putpixel(location,((pixel[0]+1)%256,*pixel[1:]))
        identity=hashlib.sha256((pixel_hash(a)+pixel_hash(b)).encode()).hexdigest()
        start=time.perf_counter_ns(); equal=module.same_pixels(a,b)
        elapsed=time.perf_counter_ns()-start; peak=peak_rss()
        if equal is not (changed=='none'): raise ValueError('Equality result is incorrect')
    return {'elapsed_ms':elapsed/1e6,'process_peak_rss_bytes':peak,
            'input_sha256':identity,'equal':equal}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path);parser.add_argument('--candidate',type=Path)
    parser.add_argument('--edge',type=int,default=4096)
    parser.add_argument('--repeats',type=int,choices=range(1,8),default=5)
    parser.add_argument('--changed',choices=('none','first','last'),default='none')
    parser.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not 64<=args.edge<=4096:parser.error('edge must be between 64 and 4096')
    if args.worker:
        print(json.dumps(trial(args.worker,args.edge,args.changed)));return
    if args.baseline is None or args.candidate is None:parser.error('select baseline and candidate')
    sources={'baseline':args.baseline.resolve(strict=True),'candidate':args.candidate.resolve(strict=True)}
    samples=[]
    for repeat in range(args.repeats):
        order=('baseline','candidate') if repeat%2==0 else ('candidate','baseline')
        for label in order:
            command=[sys.executable,str(Path(__file__).resolve()),'--worker',str(sources[label]),
                     '--edge',str(args.edge),'--changed',args.changed]
            process=subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
            samples.append(dict(json.loads(process.stdout),implementation=label,repeat=repeat))
    if len({(row['input_sha256'],row['equal']) for row in samples})!=1:raise ValueError('Parity failed')
    summaries={}
    for label in sources:
        rows=[row for row in samples if row['implementation']==label]
        elapsed=[row['elapsed_ms'] for row in rows]
        peaks=[row['process_peak_rss_bytes'] for row in rows if row['process_peak_rss_bytes'] is not None]
        summaries[label]={'median_ms':statistics.median(elapsed),'range_ms':[min(elapsed),max(elapsed)],
                         'median_process_peak_rss_bytes':statistics.median(peaks) if peaks else None}
    print(json.dumps({'schema':'studio.bundle-equality-benchmark/v1','edge':args.edge,'changed':args.changed,
        'python':platform.python_version(),'pillow':Image.__version__,'platform':platform.platform(),
        'module_sha256':{label:hashlib.sha256(path.read_bytes()).hexdigest() for label,path in sources.items()},
        'samples':samples,'summary':summaries,'result_parity':True,'neural_executions':0,
        'limitations':['Standalone predicate, not the whole bundle verifier',
                       'Synthetic CPU process RSS includes setup; not Windows commit or GPU memory',
                       'Small samples do not establish tail latency or a guaranteed speed-up']},indent=2))


if __name__=='__main__':main()
