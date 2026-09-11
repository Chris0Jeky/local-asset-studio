"""Opt-in launch of the existing Studio plus Prompt Lab. Never stops/replaces a running server."""
from pathlib import Path
import argparse
import importlib.util
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_prompt.http_extension import extend_handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root',default=str(Path(__file__).resolve().parents[1]))
    args=parser.parse_args(); root=Path(args.repo_root).resolve()
    spec=importlib.util.spec_from_file_location('_prompt_studio_base',root/'app/server.py')
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    handler=extend_handler(base.Handler)
    # Acquire the same port before creating Studio workers. Port-in-use never triggers a kill/restart.
    with base.ThreadingHTTPServer((base.HOST,base.PORT),handler) as server:
        handler.studio=base.Studio(root)
        print(f'Existing Studio with Prompt Lab: http://{base.HOST}:{base.PORT}/prompt-lab.html',flush=True)
        server.serve_forever()
if __name__=='__main__':main()
