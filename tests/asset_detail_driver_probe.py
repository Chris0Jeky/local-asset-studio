"""Prove the actual driver's baseline exit policy with explicitly injected faults.

python tests/asset_detail_driver_probe.py --out .runtime/asset-detail-driver-probes
Runs only the inert synthetic fixture. No native-origin or model-quality claim.
"""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def child(case, out):
    import asset_detail_browser as driver
    original=driver.inert_page
    async def injected(page, port):
        await original(page,port)
        if case=='page-error':
            await page.evaluate("setTimeout(()=>{throw new Error('intentional QA probe exception')},0)")
        else:
            # Deliberately violates the two preview-height expectations only.
            await page.add_style_tag(content='#assetDetailMedia{min-height:500px!important}')
    driver.inert_page=injected
    asyncio.run(driver.run(SimpleNamespace(out=out,inert=True,baseline=True,chromium=None,response_delay_ms=0)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--case',choices=['page-error','expectation'],help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.case:return child(args.case,args.out)
    args.out.mkdir(parents=True,exist_ok=True)
    for case,expected_exit,expected_fails in [('page-error',1,1),('expectation',0,2)]:
        directory=args.out/case
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--out',str(directory),'--case',case],
                              capture_output=True,text=True,encoding='utf-8',timeout=120)
        (args.out/(case+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode!=expected_exit:
            raise RuntimeError(f'{case}: expected exit {expected_exit}, got {result.returncode}; inspect {args.out}')
        receipt=json.loads((directory/'receipt.json').read_text(encoding='utf-8'))
        if receipt['fail']!=expected_fails or receipt['pass']+receipt['fail']!=30:
            raise RuntimeError(f'{case}: incomplete or unexpected scenario failures')
        if bool(receipt['errors'])!=(case=='page-error'):
            raise RuntimeError(f'{case}: JavaScript error evidence does not match the injected fault')
        print(f'{case}: exit {result.returncode}, {receipt["fail"]} intended failed checks, {len(receipt["errors"])} JavaScript exceptions')
    return 0


if __name__=='__main__':raise SystemExit(main())
