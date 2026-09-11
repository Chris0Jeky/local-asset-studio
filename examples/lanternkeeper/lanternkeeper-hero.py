"""Generate a hero through the resumable runner, preserving the supplied example."""
import argparse, subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,required=True,help='New local experiment folder; reuse to resume')
parser.add_argument('--seed',type=int,default=20260911)
args=parser.parse_args()
subprocess.run([sys.executable,str(root/'scripts/run-batch.py'),'--graph',str(Path(__file__).with_name('hero-workflow-api.json')),'--out',str(args.out),'--seed',str(args.seed)],check=True)
