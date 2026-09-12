import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location('reference_compiler',ROOT/'app/references.py')
ref=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ref)


def scaler(source):
    return {'class_type':'ImageScaleToTotalPixels','inputs':{'image':[source,0],'upscale_method':'lanczos','megapixels':1.0,'resolution_steps':1}}


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        Image.new('RGB',(400,600),'teal').save(self.root/'identity.png')
        Image.new('RGB',(600,400),'gold').save(self.root/'pose.png')
        self.preset={'positive':['6','prompt'],'max_reference_pixels':1024*1024,
                     'reference_slots':[{'binding':['4','image']},{'binding':['16','image']}]}
        self.graph={'4':{'class_type':'LoadImage','inputs':{'image':'default'}},'16':{'class_type':'LoadImage','inputs':{'image':'default'}},
                    '5':scaler('4'),'18':scaler('16'),'6':{'class_type':'TextEncodeQwenImageEditPlus','inputs':{'prompt':'Hold a compass'}}}
        self.references=[{'role':'identity','file':'identity.png','contribution':'Face and costume','avoid':'Pose'},{'role':'pose','file':'pose.png','contribution':'Hand placement','avoid':'Clothes'}]
    def tearDown(self):self.temp.cleanup()

    def test_every_slot_is_scaled_to_one_megapixel_and_roles_are_retained(self):
        result=ref.compile_references(self.preset,self.graph,self.references,self.root)
        # ComfyUI's own arithmetic in ImageScaleToTotalPixels, then the encoder's eight-pixel reference latent.
        self.assertEqual(result[0]['transform'],{'policy':'scale-to-total-pixels','megapixels':1.0,'upscale_method':'lanczos',
            'source_size':[400,600],'resized_size':[836,1254],'vae_size':[840,1256]})
        self.assertEqual(result[1]['transform']['resized_size'],[1254,836])
        self.assertEqual(result[1]['transform']['vae_size'],[1256,840])
        self.assertEqual(self.graph['4']['inputs']['image'],'identity.png')
        self.assertEqual(self.graph['16']['inputs']['image'],'pose.png')
        # TextEncodeQwenImageEditPlus injects "Picture {i+1}:" tokens, so the brief must say Picture.
        self.assertIn('Picture 2 — pose',self.graph['6']['inputs']['prompt'])
        self.assertNotIn('Image 2',self.graph['6']['inputs']['prompt'])
        self.assertTrue(self.graph['6']['inputs']['prompt'].endswith('Hold a compass'))
        self.assertEqual(len(result[0]['sha256']),64)

    def test_pixel_budget_and_aspect_checks_still_bite(self):
        graph=copy.deepcopy(self.graph);graph['5']['inputs']['megapixels']=2.0
        with self.assertRaisesRegex(ValueError,'pixel budget'):
            ref.compile_references(self.preset,graph,self.references,self.root)
        Image.new('RGB',(9000,2),'teal').save(self.root/'identity.png')
        with self.assertRaisesRegex(ValueError,'aspect ratio'):
            ref.compile_references(self.preset,copy.deepcopy(self.graph),self.references,self.root)

    def test_slot_without_a_scaler_keeps_the_native_encoder_record(self):
        graph=copy.deepcopy(self.graph);graph.pop('18')
        result=ref.compile_references(self.preset,graph,self.references,self.root)
        self.assertEqual(result[1]['transform'],{'policy':'native Qwen encoder preprocessing'})

    def test_reordering_changes_binding_and_clearing_never_drops_a_slot(self):
        result=ref.compile_references(self.preset,self.graph,list(reversed(self.references)),self.root)
        self.assertEqual(self.graph['4']['inputs']['image'],'pose.png')
        self.assertEqual(result[0]['role'],'pose')
        with self.assertRaisesRegex(ValueError,'2 reference images'):
            ref.compile_references(self.preset,self.graph,self.references[:1],self.root)
        missing=copy.deepcopy(self.references);missing[0]['file']=None
        with self.assertRaises(ValueError):ref.compile_references(self.preset,self.graph,missing,self.root)

    def test_saved_reference_change_or_escape_is_rejected(self):
        self.references[0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'bytes changed'):
            ref.compile_references(self.preset,self.graph,self.references,self.root)
        self.references[0]['file']='../outside.png'
        with self.assertRaises(ValueError):ref.compile_references(self.preset,self.graph,self.references,self.root)

    def test_reference_roles_do_not_mutate_user_records(self):
        before=copy.deepcopy(self.references)
        ref.compile_references(self.preset,self.graph,self.references,self.root)
        self.assertEqual(self.references,before)

    def test_live_recipes_bind_a_fixed_canvas_and_scale_every_reference(self):
        sys.path.insert(0,str(ROOT/'app'))
        from server import Studio
        studio=Studio.__new__(Studio)
        studio.root=ROOT;studio.catalog_path=ROOT/'presets/catalog.json';studio.config={}
        studio.experiments=self.root
        studio.comfy_root=self.root/'comfy'
        uploads=self.root/'uploads';uploads.mkdir()
        Image.new('RGB',(400,600),'teal').save(uploads/'identity.png')
        for count in (1,2,3):
            preset=studio.preset(f'qwen-{count}ref')
            self.assertEqual((832,1248),(preset['defaults']['width'],preset['defaults']['height']))
            self.assertEqual(16,preset['dimension_multiple'])
            controls={k:v for k,v in preset['defaults'].items() if k!='reference'}
            references=[{'role':'identity','file':'identity.png'} for _ in range(count)]
            _,graph,_,_,_=studio.prepare({'preset_id':preset['id'],'controls':controls,'references':references})
            self.assertEqual({'width':832,'height':1248,'batch_size':1},graph['20']['inputs'])
            self.assertEqual(['20',0],graph['11']['inputs']['latent_image'])
            self.assertNotIn('10',graph)
            for node in list('5'*(count>0))+(['18'] if count>1 else [])+(['19'] if count>2 else []):
                self.assertEqual('ImageScaleToTotalPixels',graph[node]['class_type'])
                self.assertEqual(1.0,graph[node]['inputs']['megapixels'])
            for index in range(count):
                self.assertEqual([('5','18','19')[index],0],graph['6']['inputs'][f'image{index+1}'])
                self.assertEqual([('5','18','19')[index],0],graph['7']['inputs'][f'image{index+1}'])
            self.assertIn(f'Picture {count} —',graph['6']['inputs']['prompt'])
            with self.assertRaisesRegex(Exception,'multiple of 16'):
                studio.prepare({'preset_id':preset['id'],'controls':dict(controls,width=840),'references':references})

    def recipe_builder(self):
        spec=importlib.util.spec_from_file_location('reference_recipes',ROOT/'scripts/build-reference-recipes.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder);return builder

    def test_shipped_graphs_match_the_recipe_builder(self):
        builder=self.recipe_builder()
        for count in (1,2,3):
            source=json.loads((ROOT/f'research/game-assets/workflows/qwen-{count}ref-api.json').read_text(encoding='utf-8'))
            shipped=json.loads((ROOT/f'workflows/api/qwen-{count}ref-api.json').read_text(encoding='utf-8'))
            self.assertEqual(shipped,builder.geometry(source,count))

    def test_shipped_catalog_block_matches_the_recipe_builder(self):
        builder=self.recipe_builder()
        presets={p['id']:p for p in json.loads((ROOT/'presets/catalog.json').read_text(encoding='utf-8'))['presets']}
        for count in (1,2,3):
            preset=presets[f'qwen-{count}ref']
            source=(ROOT/f'research/game-assets/workflows/qwen-{count}ref-api.json').read_bytes()
            # The digest names the exact bytes the shipped graph derives from; a stale one is a lie.
            self.assertEqual(hashlib.sha256(source).hexdigest(),preset['source_graph_sha256'])
            self.assertEqual([[builder.LATENT_NODE,'width'],[builder.LATENT_NODE,'height']],[preset['width'],preset['height']])
            self.assertEqual(16,preset['dimension_multiple']);self.assertEqual([64,1536],preset['dimension_limits'])
            self.assertEqual(1024*1024,preset['max_pixels']);self.assertEqual(1024*1024,preset['max_reference_pixels'])
            self.assertEqual(builder.REFERENCE_MEGAPIXELS,preset['reference_policy']['megapixels'])
            self.assertEqual([{'width':640,'height':960},{'width':builder.CANVAS[0],'height':builder.CANVAS[1]}],
                             [v['controls'] for v in preset['variants']])
            self.assertFalse(preset['verified']);self.assertNotIn('execution_note',preset)
            graph=json.loads((ROOT/preset['graph']).read_text(encoding='utf-8'))
            self.assertEqual(builder.PROMPTS[count],graph['6']['inputs']['prompt'])
            self.assertEqual(list(builder.DEFAULT_IMAGES[:count]),
                             [graph[slot['binding'][0]]['inputs']['image'] for slot in preset['reference_slots']])

    def test_shipped_visual_graphs_match_the_recipe_builder(self):
        from urllib.error import URLError
        from urllib.request import urlopen
        try:
            with urlopen('http://127.0.0.1:8188/object_info',timeout=20) as stream: info=json.load(stream)
        except (URLError,OSError):self.skipTest('Visual export needs a live ComfyUI node schema on 127.0.0.1:8188')
        for path in (ROOT/'app',ROOT/'scripts'):
            if str(path) not in sys.path: sys.path.insert(0,str(path))
        spec=importlib.util.spec_from_file_location('expansion_builder',ROOT/'scripts/build-expansion.py')
        expansion=importlib.util.module_from_spec(spec);spec.loader.exec_module(expansion)
        for count in (1,2,3):
            title=f'Qwen Atelier - {count} Reference'+('s' if count>1 else '')
            graph=json.loads((ROOT/f'workflows/api/qwen-{count}ref-api.json').read_text(encoding='utf-8'))
            shipped=json.loads((ROOT/f'workflows/comfyui/{49+count} - {title}.json').read_text(encoding='utf-8'))
            self.assertEqual(shipped,expansion.visual(graph,title,info))
