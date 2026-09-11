"""Create procedural QA fixtures, not generated artwork or a finished character pack."""
from pathlib import Path
import argparse
import json
from PIL import Image, ImageDraw
from game_asset_pipeline import file_sha, make_plan, catalog
from game_asset_media import atlas, ora


def create(output):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    frames=[]
    for i,dy in enumerate((0,-2,0,2)):
        im=Image.new('RGBA',(48,64));d=ImageDraw.Draw(im)
        d.rounded_rectangle((13,22+dy,34,50+dy),4,fill=(44,87,92,255),outline=(235,196,108,255),width=2)
        d.ellipse((16,6+dy,31,21+dy),fill=(235,196,108,255))
        d.rectangle((13,50,19,59),fill=(35,45,48,255));d.rectangle((28,50,34,59),fill=(35,45,48,255))
        path=f'frame-{i}.png';im.save(root/path)
        frames.append({'id':f'frame-{i}','path':path,'sha256':file_sha(root/path),'duration_ms':[120,80,120,160][i]})
    top=Image.new('RGBA',(48,64));ImageDraw.Draw(top).ellipse((16,6,31,21),fill=(235,196,108,255));top.save(root/'head.png')
    bottom=Image.open(root/'frame-0.png').convert('RGBA');ImageDraw.Draw(bottom).rectangle((0,0,47,21),fill=(0,0,0,0));bottom.save(root/'body.png')
    fm={'schema_version':1,'clip':'idle-qa','canvas':[48,64],'anchor':[24,60],'loop':True,'frames':frames}
    lm={'schema_version':1,'name':'QA puppet layers','canvas':[48,64],'layers':[{'id':'head','name':'Head QA','path':'head.png','sha256':file_sha(root/'head.png')},{'id':'body','name':'Body QA','path':'body.png','sha256':file_sha(root/'body.png')}]}
    brief={'schema_version':1,'asset_id':'lanternkeeper-qa','route':'character-2d-frames','description':'Create portraits and an idle animation for an original non-explicit fantasy lanternkeeper. Procedural fixture is only a placeholder for reference handling tests.','references':[{'id':'identity-guide','role':'identity','kind':'image','path':'frame-0.png','sha256':frames[0]['sha256'],'take':['palette and rough silhouette'],'ignore':['fixture drawing quality','frame timing']}],'target':{'engine':'godot','outputs':['portrait PNGs','RGBA atlas','clip durations and anchors','layered source','actual engine playback evidence']},'constraints':['48x64 logical sprite canvas','anchor at 24,60','preserve approved costume across expressions'],'budget':{'generation_attempts':12,'repair_attempts_per_stage':1,'allow_paid_services':False}}
    for name,value in [('frames.json',fm),('layers.json',lm),('brief.json',brief),('plan.json',make_plan(brief,catalog()))]:
        (root/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    atlas(fm,root,root/'atlas',columns=4)
    ora(lm,root,root/'editable.ora')
    (root/'README.txt').write_text('Procedural QA fixture. Not generative model output; not an accepted animation.\nUnequal frame durations and one duplicate pose intentionally exercise packaging.\nOpen editable.ora in Krita to perform the still-outstanding real import check.\n')
    return root


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True)
    print(create(p.parse_args().out))
