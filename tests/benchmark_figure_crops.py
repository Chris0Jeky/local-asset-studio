"""Finite fresh-process comparison of original and one-at-a-time crop preparation.

Select an exact baseline module with git show; no model, network or private media.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time

from PIL import Image
from test_figure_crop_memory import SnapshotWorkspace


def load(path):
    spec=importlib.util.spec_from_file_location('crop_subject',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def peak():
    try:import resource
    except ImportError:return None
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=='darwin' else value*1024)


def trial(path,kind,edge,count):
    module=load(path)
    # Four identical full-source selections exercise the permitted duplicate-heavy
    # path: every crop still encodes; the immutable snapshot is stored only once.
    raw=random.Random(399).randbytes(edge*edge*4)
    identity=hashlib.sha256(raw).hexdigest()
    canvas=Image.frombytes('RGBA',(edge,edge),raw);del raw
    boxes=[dict(x=0,y=0,width=10000,height=10000) for _ in range(count)]
    with tempfile.TemporaryDirectory() as folder:
        workspace=SnapshotWorkspace(folder)
        start=time.perf_counter_ns()
        size,rows=module._encode_crops(workspace,canvas,boxes)
        if kind=='baseline':
            snapshots=[module._snapshot_png(workspace,data) for _,_,data in rows]
        else:snapshots=[row[2] for row in rows]
        elapsed=(time.perf_counter_ns()-start)/1e6;rss=peak()
        records=[]
        for (rectangle,box,_),(name,digest,nbytes) in zip(rows,snapshots):
            payload=(workspace.root/name).read_bytes()
            if hashlib.sha256(payload).hexdigest()!=digest or len(payload)!=nbytes:
                raise ValueError('snapshot identity mismatch')
            records.append([rectangle,box,digest,nbytes])
    return dict(elapsed_ms=elapsed,process_peak_rss_bytes=rss,input_sha256=identity,
                result_sha256=hashlib.sha256(json.dumps([size,records],sort_keys=True).encode()).hexdigest(),
                encoded_bytes=sum(row[-1] for row in records))


def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    p.add_argument('--baseline',type=Path);p.add_argument('--candidate',type=Path)
    p.add_argument('--edge',type=int,choices=(512,1024,2048),default=2048)
    p.add_argument('--crops',type=int,choices=range(1,5),default=4)
    p.add_argument('--repeats',type=int,choices=range(1,6),default=3)
    p.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--kind',choices=('baseline','candidate'),help=argparse.SUPPRESS)
    a=p.parse_args()
    if a.worker:
        if a.kind is None:p.error('worker requires kind')
        print(json.dumps(trial(a.worker,a.kind,a.edge,a.crops)));return
    if a.baseline is None or a.candidate is None:p.error('baseline and candidate required')
    sources=dict(baseline=a.baseline.resolve(strict=True),candidate=a.candidate.resolve(strict=True))
    samples=[]
    for repeat in range(a.repeats):
        for kind in (('baseline','candidate') if repeat%2==0 else ('candidate','baseline')):
            command=[sys.executable,__file__,'--worker',str(sources[kind]),'--kind',kind,
                     '--edge',str(a.edge),'--crops',str(a.crops)]
            child=subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
            samples.append(dict(json.loads(child.stdout),implementation=kind,repeat=repeat))
    if len({(r['input_sha256'],r['result_sha256']) for r in samples})!=1:raise ValueError('parity failed')
    summaries={}
    for kind in sources:
        rows=[r for r in samples if r['implementation']==kind]
        times=[r['elapsed_ms'] for r in rows];memory=[r['process_peak_rss_bytes'] for r in rows]
        summaries[kind]=dict(median_ms=statistics.median(times),range_ms=[min(times),max(times)],
            median_process_peak_rss_bytes=statistics.median(memory) if all(v is not None for v in memory) else None)
    print(json.dumps(dict(schema='studio.figure-crop-benchmark/v1',edge=a.edge,crops=a.crops,
        python=platform.python_version(),pillow=Image.__version__,platform=platform.platform(),
        module_sha256={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sources.items()},
        samples=samples,summary=summaries,result_parity=True,neural_executions=0,
        limitations=['Synthetic duplicate-heavy crop preparation, not full split workflow',
            'Peak RSS includes setup and imports; not Windows commit or GPU memory',
            'Small sample does not establish tails or guaranteed speedup']),indent=2))


if __name__=='__main__':main()
