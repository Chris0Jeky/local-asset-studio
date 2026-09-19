"""Finite large-trace parser comparison, not inference or an old-CLI capability.

The frozen eager algorithm's bounds are raised ONLY inside this benchmark so both
implementations inspect identical data. Ordinary small-reader limits stay intact.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import inference_trace_stream as streaming


def load(path):
    spec=importlib.util.spec_from_file_location('eager_trace_baseline',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def make_trace(path, count, argument_bytes):
    # Persist a deterministic source in bounded writes; no whole-input parent list.
    with path.open('xb') as stream:
        stream.write(b'{"schemaVersion":1,"traceEvents":[')
        for i in range(count):
            row=dict(ph='X',cat='cpu_op',name=('aten::mm','aten::copy_')[i%2],
                     pid=1,tid=i%4,ts=(count-i)*10,dur=12,
                     args={'synthetic_padding':'x'*argument_bytes})
            if i:stream.write(b',')
            stream.write(json.dumps(row,separators=(',',':')).encode())
        stream.write(b'],"displayTimeUnit":"ms"}\n')


def peak():
    try:import resource
    except ImportError:return None
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=='darwin' else value*1024)


def trial(path, kind, baseline):
    if kind=='eager':
        module=load(baseline)
        module.MAX_BYTES=streaming.MAX_STREAM_BYTES
        module.MAX_EVENTS=streaming.MAX_STREAM_EVENTS
        module.MAX_OPERATORS=streaming.MAX_STREAM_OPERATORS
    start=time.perf_counter_ns()
    if kind=='eager':result=module.summarize_trace(path.read_bytes())
    else:
        with path.open('rb') as stream:result=streaming.summarize_trace_stream(stream)
    elapsed=(time.perf_counter_ns()-start)/1e6;rss=peak()
    return dict(elapsed_ms=elapsed,process_peak_rss_bytes=rss,input_bytes=result['input_bytes'],
        input_sha256=result['input_sha256'],recognized_events=result['recognized_events'],
        result_sha256=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--events',type=int,choices=(5000,12000,30000),default=12000)
    p.add_argument('--argument-bytes',type=int,choices=(0,256,2048),default=2048)
    p.add_argument('--repeats',type=int,choices=range(1,6),default=3)
    p.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--kind',choices=('eager','stream'),help=argparse.SUPPRESS)
    args=p.parse_args();baseline=args.baseline.resolve(strict=True)
    if args.worker:
        if args.kind is None:p.error('worker requires kind')
        print(json.dumps(trial(args.worker,args.kind,baseline)));return
    samples=[]
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'synthetic-trace.json';make_trace(path,args.events,args.argument_bytes)
        for repeat in range(args.repeats):
            for kind in (('eager','stream') if repeat%2==0 else ('stream','eager')):
                command=[sys.executable,__file__,'--worker',str(path),'--kind',kind,'--baseline',str(baseline)]
                child=subprocess.run(command,check=True,capture_output=True,text=True,timeout=120)
                samples.append(dict(json.loads(child.stdout),implementation=kind,repeat=repeat))
    if len({(r['input_sha256'],r['result_sha256']) for r in samples})!=1:raise ValueError('Exact report parity failed')
    summaries={}
    for kind in ('eager','stream'):
        rows=[r for r in samples if r['implementation']==kind]
        times=[r['elapsed_ms'] for r in rows];memory=[r['process_peak_rss_bytes'] for r in rows]
        summaries[kind]=dict(median_ms=statistics.median(times),range_ms=[min(times),max(times)],
            median_process_peak_rss_bytes=statistics.median(memory) if all(v is not None for v in memory) else None)
    files=dict(eager_algorithm=baseline,stream_parser=ROOT/'app/inference_trace_stream.py',
               shared_aggregation=ROOT/'app/inference_trace.py')
    if hasattr(streaming, '_JSONValues'):
        files['value_framing'] = ROOT/'app/inference_trace_values.py'
    print(json.dumps(dict(schema='studio.trace-stream-benchmark/v1',events=args.events,
        argument_bytes_per_event=args.argument_bytes,python=platform.python_version(),platform=platform.platform(),
        module_sha256={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in files.items()},
        eager_limits_raised_for_experiment_only=True,samples=samples,summary=summaries,
        result_parity=True,neural_executions=0,
        limitations=['Synthetic argument-heavy saved trace, not a real diffusion workload',
            'Eager bounds raised only for algorithm comparison; not an old CLI-supported size',
            'Process RSS includes imports; not Windows commit, VRAM or live profiler allocations',
            'Small samples do not establish tail latency']),indent=2))


if __name__=='__main__':main()
