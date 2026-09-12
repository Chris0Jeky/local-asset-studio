"""Synthetic two-actor edit fixture. No models, external artwork or approval claims."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.character_study import file_sha, sha, write_json, read_json
from scripts.character_edit import make_plan
from scripts.character_edit_pixels import prepare, apply


def create(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    im = Image.new('RGBA', (384, 256), (230, 237, 242, 255)); draw = ImageDraw.Draw(im)
    draw.line((0, 219, 384, 219), fill=(80, 90, 95), width=2)
    for x, colour in [(58, (43, 107, 161)), (237, (130, 81, 170))]:
        draw.rounded_rectangle((x, 100, x+72, 193), radius=10, fill=colour)
        draw.rounded_rectangle((x+6, 38, x+66, 97), radius=8, fill=(230, 184, 103))
        draw.ellipse((x+20, 59, x+25, 64), fill=(30, 32, 38)); draw.ellipse((x+48, 59, x+53, 64), fill=(30, 32, 38))
        draw.rectangle((x+10, 193, x+25, 218), fill=(35, 40, 49)); draw.rectangle((x+47, 193, x+62, 218), fill=(35, 40, 49))
    im.save(root/'source.png')
    mask = Image.new('L', im.size, 0); ImageDraw.Draw(mask).rectangle((66, 109, 121, 180), fill=255); mask.save(root/'edit-mask.png')
    protected = Image.new('L', im.size, 0); ImageDraw.Draw(protected).rectangle((220, 20, 335, 230), fill=255); protected.save(root/'protect-mask.png')
    ref = lambda name: {'path':name,'sha256':file_sha(root/name)}
    actors=[]
    for aid, bounds in [('amber',[45,25,145,220]),('violet',[220,20,335,230])]:
        # Deliberately labelled source metadata, not a human-approved canon.
        write_json(root/f'{aid}-design.json',{'kind':'synthetic_fixture_design','id':aid,'approval':'none'})
        im.crop(tuple(bounds)).save(root/f'{aid}-reference.png')
        actors.append({'id':aid,'canon':ref(f'{aid}-design.json'),'bounds':bounds,'references':[
            {'id':'neutral','role':'identity','image':ref(f'{aid}-reference.png'),
             'take':['Fixture face and silhouette'],'ignore':['Do not copy the other actor']} ]})
    doc={'schema_version':1,'kind':'character_edit_document','id':'two-actors','revision':1,'canvas':list(im.size),
         'source':ref('source.png'),'actors':actors,
         'scene':{'description':'Two synthetic block characters, CPU test only','camera':'Fixed frontal','lighting':'Flat diagram'},'relations':[]}
    request={'schema_version':1,'kind':'character_edit_intent','id':'amber-costume','document_sha256':sha(doc),
             'operation':'costume-change','changes':[{'actor':'amber','facet':'costume','instruction':'Change only the selected jacket area to orange.'}],
             'scene_change':None,'context_box':[50,96,137,189],'edit_mask':ref('edit-mask.png'),
             'protect_mask':ref('protect-mask.png'),'patch_alignment':8,'layout':None,
             'budget':{'owner':'editing-pilot','max_candidates':3,'max_repairs':1},
             'policy_preference':{'local_only':True,'exclude_known_filters':True,
                 'exclude_documented_weight_restrictions':True,'unknown_policy':'allow_with_warning'}}
    write_json(root/'document.json',doc); write_json(root/'intent.json',request)
    cat=read_json(ROOT/'research/character-consistency/edit-routes.json'); plan=make_plan(doc,request,cat); write_json(root/'plan.json',plan)
    bundle=prepare(root,plan,'prepared')
    # Intentionally changes the ENTIRE candidate, including noneditable context.
    # The published result must still change only the edit-mask support.
    candidate=Image.new('RGBA',tuple(bundle['transform']['model_size']),(236,123,58,255)); candidate.save(root/'candidate.png')
    receipt=apply(root,plan,'prepared',ref('candidate.png'),'revision-2')
    # Original + final are a mechanical proof, not generated character art.
    proof=Image.new('RGB',(768,256),'white'); proof.paste(im,(0,0))
    with Image.open(root/'revision-2/result.png') as result: proof.paste(result,(384,0))
    proof.save(root/'comparison.png')
    return receipt

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True); args=p.parse_args()
    try: print(json.dumps(create(args.out), indent=2))
    except (ValueError,KeyError,TypeError,OSError) as exc: p.exit(2,f'character-edit-demo: {exc}\n')
