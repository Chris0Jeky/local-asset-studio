"""Reject imperceptible/all-still delivered motion using decoded focal regions."""
from pathlib import Path
import argparse,json,hashlib,shutil,subprocess,tempfile
from PIL import Image,ImageChops,ImageStat
parser=argparse.ArgumentParser();parser.add_argument('asset',choices=['las','alibi']);parser.add_argument('video',type=Path);parser.add_argument('--output',type=Path)
args=parser.parse_args();out=args.output or Path(tempfile.mkdtemp(prefix='readable-motion-'));out.mkdir(parents=True,exist_ok=True)
frames=out/'decoded';frames.mkdir(exist_ok=True)
subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-n','-i',str(args.video),'-vf','fps=4,scale=320:-1',str(frames/'%03d.png')],check=True)
images=[Image.open(p).convert('RGB') for p in sorted(frames.glob('*.png'))]
assert len(images)>=24,'A complete clip must be decoded, not just its endpoints'
regions={'las':{'window':((.675,.03,.988,.67),.025),'falling_rain':((.675,.03,.988,.30),.0035),'train_band':((.675,.35,.988,.44),.06)},'alibi':{'steam':((.72,.40,.83,.64),.04),'flame':((.36,.58,.44,.68),.025),'glass':((.29,.4,.52,.72),.015)}}[args.asset]
results={}
for name,(bounds,minimum) in regions.items():
    box=tuple(round(v*(images[0].width if i%2==0 else images[0].height)) for i,v in enumerate(bounds))
    base=images[0].crop(box);fractions=[];means=[]
    for im in images[1:]:
        diff=ImageChops.difference(base,im.crop(box));pixels=diff.tobytes()
        fractions.append(sum(max(pixels[i:i+3])>=6 for i in range(0,len(pixels),3))/(diff.width*diff.height))
        means.append(sum(ImageStat.Stat(diff).mean)/3)
    results[name]={'max_changed_fraction_threshold6':max(fractions),'required_minimum':minimum,'max_mean_rgb':max(means),'passes':max(fractions)>=minimum}
report={'asset':args.asset,'decoded_frames':len(images),'display_width':320,'video_sha256':hashlib.sha256(args.video.read_bytes()).hexdigest(),'regions':results,'human_visual_acceptance':'separate gate; these thresholds reject still/near-still delivery only'}
(out/'readability.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report),flush=True)
assert all(r['passes'] for r in results.values()),'Decoded export is still or insufficiently readable at normal card size'
