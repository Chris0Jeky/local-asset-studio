import copy,json,unittest
from pathlib import Path

from app.server import Studio

ROOT=Path(__file__).resolve().parents[1]
PRESETS={p['id']:p for p in json.loads((ROOT/'presets/catalog.json').read_text(encoding='utf-8'))['presets']}
RECIPES={r['id']:r for r in json.loads((ROOT/'presets/recipes.json').read_text(encoding='utf-8'))['recipes']}
BASELINES={
    'cstati-v3-baseline':('CheckpointLoaderSimple','cstatiANIMEV30XL_v30.safetensors',4.0,'euler_ancestral','karras',2),
    'yumeflux-ilv1-baseline':('CheckpointLoaderSimple','yumefluxXLIllustrious_ilV10.safetensors',4.0,'euler_ancestral','karras',2),
    'anifox-v2-baseline':('CheckpointLoaderSimple','anifoxXLV20_anifoxV2.safetensors',5.0,'euler_ancestral','karras',2),
    'anima-v1-baseline':('UNETLoader','anima-base-v1.0.safetensors',4.5,'euler','simple',6),
    'janima-v1-baseline':('UNETLoader','JANIMAAnima_v10_2847103.safetensors',4.5,'euler','simple',5),
}

class ModularIllustrationBaselineTests(unittest.TestCase):
    def graph(self,preset_id):
        return json.loads((ROOT/PRESETS[preset_id]['graph']).read_text(encoding='utf-8'))

    def test_fixed_checkpoint_family_and_control_values(self):
        for preset_id,(loader,filename,cfg,sampler,scheduler,slots) in BASELINES.items():
            with self.subTest(preset_id=preset_id):
                graph=self.graph(preset_id); sample=graph['5'] if loader=='CheckpointLoaderSimple' else graph['7']
                self.assertEqual(graph['1']['class_type'],loader)
                self.assertEqual(graph['1']['inputs']['ckpt_name' if loader=='CheckpointLoaderSimple' else 'unet_name'],filename)
                self.assertEqual((graph['4'] if loader=='CheckpointLoaderSimple' else graph['6'])['inputs'],{'width':832,'height':1216,'batch_size':1})
                self.assertEqual(sample['inputs']['seed'],2026091301)
                self.assertEqual(sample['inputs']['steps'],30)
                self.assertEqual(sample['inputs']['cfg'],cfg)
                self.assertEqual(sample['inputs']['sampler_name'],sampler)
                self.assertEqual(sample['inputs']['scheduler'],scheduler)
                loras=[node for node in graph.values() if node['class_type'].startswith('LoraLoader')]
                self.assertEqual(len(loras),slots)
                self.assertTrue(all(node['inputs']['strength_model']==0 for node in loras))
                if loader=='UNETLoader':
                    self.assertEqual(graph['2']['inputs']['clip_name'],'qwen_3_06b_base.safetensors')
                    self.assertEqual(graph['3']['inputs']['vae_name'],'qwen_image_vae.safetensors')

    def test_zero_strength_base_recipes_prune_every_lora(self):
        for preset_id,(loader,_,_,_,_,slots) in BASELINES.items():
            with self.subTest(preset_id=preset_id):
                graph=self.graph(preset_id); before=len(graph)
                Studio.prune_disabled_loras(None,graph)
                self.assertEqual(len(graph),before-slots)
                self.assertFalse(any(node['class_type'].startswith('LoraLoader') for node in graph.values()))
                sampler=graph['5'] if loader=='CheckpointLoaderSimple' else graph['7']
                self.assertEqual(sampler['inputs']['model'],['1',0])

    def test_base_and_deliberate_adapter_recipe_controls(self):
        for recipe_id in ('cstati-v3-base','yumeflux-ilv1-base','anifox-v2-base','anima-v1-base','janima-v1-base'):
            with self.subTest(recipe_id=recipe_id):
                controls=RECIPES[recipe_id]['controls']
                self.assertTrue(RECIPES[recipe_id]['status']=='unverified')
                self.assertTrue(all(value==0 for key,value in controls.items() if key.startswith('lora')))
        stack=RECIPES['janima-v1-authored-five-adapter-stack']
        self.assertEqual([stack['controls'][f'lora{n or ""}'] for n in ('',2,3,4,5)],[0.3,0.6,0.35,0.25,0.5])
        self.assertIn('not screenshot/source transcription',stack['notes'])
        comparison=RECIPES['anima-v1-first-adapter-comparison']['controls']
        base=RECIPES['anima-v1-base']['controls']
        self.assertEqual((comparison['steps'],comparison['cfg'],comparison['sampler'],comparison['scheduler']),(base['steps'],base['cfg'],base['sampler'],base['scheduler']))
        self.assertEqual(comparison['lora'],1.0)
        self.assertTrue(all(comparison[f'lora{n}']==0 for n in range(2,7)))
        screenshot=RECIPES['anima-v1-screenshot-sampling-comparison']['controls']
        self.assertEqual((screenshot['positive'],screenshot['negative'],screenshot['seed'],screenshot['lora']),(base['positive'],base['negative'],base['seed'],1.0))
        self.assertEqual((screenshot['steps'],screenshot['cfg'],screenshot['sampler'],screenshot['scheduler']),(30,5.5,'euler_ancestral','simple'))
        self.assertTrue(all(screenshot[f'lora{n}']==0 for n in range(2,7)))

    def test_new_adapter_metadata_matches_model_library(self):
        settings=json.loads((ROOT/'presets/settings-kb.json').read_text(encoding='utf-8'))['loras']
        library={asset['file']:asset for asset in json.loads((ROOT/'models/library.json').read_text(encoding='utf-8'))['assets']}
        names=('nsfw_girls.safetensors','noirpopwave.safetensors','nsfw_girls_anima.safetensors','anima-highres-aesthetic-boost.safetensors','rapscallion_cherrypick_min1024_prodigy_lr1_4000_stylepush.safetensors','BunnySlop_Ani_v5.56.safetensors','BunnyMid_Ani_v1.safetensors')
        for name in names:
            with self.subTest(name=name):
                setting=settings[name]; asset=library[f'loras/{name}']
                self.assertEqual({key:setting[key] for key in ('source','sha256','bytes','trigger')},{key:asset[key] for key in ('source','sha256','bytes','trigger')})
                self.assertEqual(setting['licence'],'Source pinned; installation separately verified; licence terms unverified.')

    def test_new_family_licence_notes_preserve_unverified_terms(self):
        families=json.loads((ROOT/'presets/settings-kb.json').read_text(encoding='utf-8'))['families']
        for family in ('CSTati v3 (SDXL)','YumeFlux ILv1 (SDXL)','AniFox v2 (SDXL)','JANIMA v1 (Anima)'):
            with self.subTest(family=family):
                self.assertEqual(families[family]['licence_note'],'Source pinned; installation separately verified; licence terms unverified.')
