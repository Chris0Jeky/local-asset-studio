"""Reject imperceptible/all-still delivered motion using decoded focal regions."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess,tempfile
from PIL import Image,ImageChops,ImageStat
SAMPLE_FPS=4 # decode rate; the declared sample count is TIMELINE.json duration_seconds x this
SUSTAINED_FRACTION=.25 # share of consecutive sample pairs that must each show the region's minimum change
WINDOWS=4 # the clip is split into this many equal stretches; each must contain at least one moving pair (no frozen tail)
TIMELINE=Path(__file__).with_name('TIMELINE.json')
REGIONS={'las':{'window':((.675,.03,.988,.67),.025),'falling_rain':((.675,.03,.988,.30),.0035),'train_band':((.675,.35,.988,.44),.06)},'alibi':{'steam':((.72,.40,.83,.64),.04),'flame':((.36,.58,.44,.68),.025),'glass':((.29,.4,.52,.72),.015)}}
def expected_samples(timeline=TIMELINE): return round(json.loads(Path(timeline).read_text(encoding='utf-8'))['duration_seconds']*SAMPLE_FPS)
def sample_count_ok(count,expected): return abs(count-expected)<=1 # one sample of slack for ffmpeg rounding at the clip end
def changed(a,b):
    diff=ImageChops.difference(a,b);pixels=diff.tobytes()
    return sum(max(pixels[i:i+3])>=6 for i in range(0,len(pixels),3))/(diff.width*diff.height),sum(ImageStat.Stat(diff).mean)/3
def region_results(images,regions):
    results={}
    for name,(bounds,minimum) in regions.items():
        box=tuple(round(v*(images[0].width if i%2==0 else images[0].height)) for i,v in enumerate(bounds))
        crops=[im.crop(box) for im in images];pairs=[changed(a,b) for a,b in zip(crops,crops[1:])]
        moving=sum(fraction>=minimum for fraction,_ in pairs);share=moving/len(pairs)
        flags=[fraction>=minimum for fraction,_ in pairs];size=len(flags)/WINDOWS;windows=[any(flags[round(i*size):round((i+1)*size)]) for i in range(WINDOWS)]
        results[name]={'max_changed_fraction_threshold6':max(f for f,_ in pairs),'required_minimum':minimum,'moving_pairs':moving,'pairs':len(pairs),'moving_pair_fraction':share,'required_moving_pair_fraction':SUSTAINED_FRACTION,'max_mean_rgb':max(m for _,m in pairs),'moving_windows':sum(windows),'windows':WINDOWS,'passes':share>=SUSTAINED_FRACTION and all(windows)}
    return results
def clip_passes(images,expected,regions): return sample_count_ok(len(images),expected) and all(r['passes'] for r in region_results(images,regions).values())
def main():
    parser=argparse.ArgumentParser();parser.add_argument('asset',choices=['las','alibi']);parser.add_argument('video',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();out=args.output or Path(tempfile.mkdtemp(prefix='readable-motion-'));out.mkdir(parents=True,exist_ok=True)
    frames=out/'decoded';frames.mkdir(exist_ok=True)
    subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-n','-i',str(args.video),'-vf',f'fps={SAMPLE_FPS},scale=320:-1',str(frames/'%03d.png')],check=True)
    images=[Image.open(p).convert('RGB') for p in sorted(frames.glob('*.png'))]
    expected=expected_samples()
    assert sample_count_ok(len(images),expected),f'Decoded {len(images)} samples but the timeline declares {expected} (duration x {SAMPLE_FPS} fps, allow 1 for rounding); a complete clip must be decoded, not just its endpoints'
    results=region_results(images,REGIONS[args.asset])
    report={'asset':args.asset,'decoded_frames':len(images),'expected_samples':expected,'display_width':320,'video_sha256':hashlib.sha256(args.video.read_bytes()).hexdigest(),'regions':results,'human_visual_acceptance':'separate gate; these thresholds reject still/near-still and frozen-tail delivery only'}
    (out/'readability.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report),flush=True)
    assert all(r['passes'] for r in results.values()),'Decoded export is still, frozen after a change, or insufficiently readable at normal card size'
if __name__=='__main__': main()
