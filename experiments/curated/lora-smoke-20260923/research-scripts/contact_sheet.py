"""Small labelled JPEG contact sheet per checkpoint from results.json (control first, then each LoRA at its two strengths).

  python contact_sheet.py wai|noob|pony <out.jpg>
"""
import json,os,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
REPO=Path(__file__).resolve().parents[4];OUT=Path(os.environ.get('OUT',REPO/'.runtime/lora-smoke'))
COMFY_OUT=Path('C:/AI/ComfyUI_windows_portable/ComfyUI/output/Research')
TW,TH,LH,COLS=240,351,34,4
def main(ck,dest):
 data=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
 data=data['runs'] if isinstance(data,dict) else data   # curated results.json wraps the runtime list under 'runs'
 res=[r for r in data if r['name'].startswith(ck+'-') and r['status']=='success']
 seen={};[seen.__setitem__(r['name'],r) for r in res];res=list(seen.values())
 rows=(len(res)+COLS-1)//COLS;sheet=Image.new('RGB',(COLS*TW,rows*(TH+LH)),'white');d=ImageDraw.Draw(sheet)
 try:font=ImageFont.truetype('arial.ttf',13)
 except OSError:font=ImageFont.load_default()
 for i,r in enumerate(res):
  im=Image.open(COMFY_OUT/r['files'][-1]).convert('RGB');im.thumbnail((TW,TH),Image.LANCZOS)
  x,y=(i%COLS)*TW,(i//COLS)*(TH+LH);sheet.paste(im,(x+(TW-im.width)//2,y))
  label=r['name'][len(ck)+1:];d.text((x+4,y+TH+2),label,fill='black',font=font)
  d.text((x+4,y+TH+17),f"{(r['lora'] or 'no LoRA')[:30]}",fill=(90,90,90),font=font)
 Path(dest).parent.mkdir(parents=True,exist_ok=True);sheet.save(dest,'JPEG',quality=82,optimize=True)
 print(dest,sheet.size,os.path.getsize(dest))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
