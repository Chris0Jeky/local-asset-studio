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
            # The builder carries `verified` and `execution_note` forward when the graph bytes are unchanged, so a
            # recorded run must not turn this guard red: assert the field exists, not its value.
            self.assertIn('verified',preset)
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


def board_graph():
    """Three style loaders, one encoder each, combined into one embed for IPAdapterEmbeds."""
    g={'12':{'class_type':'IPAdapterModelLoader','inputs':{'ipadapter_file':'x'}},'13':{'class_type':'CLIPVisionLoader','inputs':{'clip_name':'y'}},
       '22':{'class_type':'IPAdapterCombineEmbeds','inputs':{'embed1':['19',0],'embed2':['20',0],'embed3':['21',0],'method':'concat'}},
       '14':{'class_type':'IPAdapterEmbeds','inputs':{'model':['9',0],'ipadapter':['12',0],'pos_embed':['22',0],'weight':0.8}},
       '2':{'class_type':'CLIPTextEncode','inputs':{'text':'a witch'}}}
    for loader,encoder in (('10','19'),('30','20'),('31','21')):
        g[loader]={'class_type':'LoadImage','inputs':{'image':'example.png'}}
        g[encoder]={'class_type':'IPAdapterEncoder','inputs':{'ipadapter':['12',0],'image':[loader,0],'weight':1.0,'clip_vision':['13',0]}}
    return g


class StyleBoardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for name in ('a.png','b.png','c.png'): Image.new('RGB',(300,400),'teal').save(self.root/name)
        self.preset={'positive':['2','text'],'reference_board':{'min':1},
                     'reference_slots':[{'role':'style','binding':['10','image']},{'role':'style','binding':['30','image']},{'role':'style','binding':['31','image']}]}
    def tearDown(self):self.temp.cleanup()

    def test_full_board_binds_every_loader_and_writes_no_prompt_guidance(self):
        g=board_graph()
        records=ref.compile_references(self.preset,g,[{'role':'style','file':'a.png'},{'role':'style','file':'b.png'},{'role':'style','file':'c.png'}],self.root)
        self.assertEqual([g['10']['inputs']['image'],g['30']['inputs']['image'],g['31']['inputs']['image']],['a.png','b.png','c.png'])
        self.assertEqual(g['2']['inputs']['text'],'a witch'); self.assertEqual([r['slot'] for r in records],[1,2,3])
        self.assertEqual(records[0]['transform']['policy'],'native IP-Adapter CLIP-vision preprocessing (224 px centre crop)')

    def test_empty_middle_slot_prunes_its_loader_and_encoder_and_drops_the_combiner_input(self):
        g=board_graph()
        records=ref.compile_references(self.preset,g,[{'role':'style','file':'a.png'},{},{'role':'style','file':'c.png'}],self.root)
        self.assertNotIn('30',g); self.assertNotIn('20',g)
        self.assertEqual(g['22']['inputs'],{'embed1':['19',0],'embed3':['21',0],'method':'concat'})
        self.assertEqual([r['file'] for r in records],['a.png',None,'c.png']); self.assertEqual([r['slot'] for r in records],[1,2,3])
        self.assertEqual(records[1],{'slot':2,'role':'style','file':None,'pruned':True,'contribution':'','avoid':''})

    def test_only_the_last_slot_filled_slides_into_the_combiner_first_input(self):
        g=board_graph()
        records=ref.compile_references(self.preset,g,[{},{},{'role':'style','file':'c.png'}],self.root)
        self.assertEqual(g['22']['inputs'],{'embed1':['21',0],'method':'concat'}); self.assertEqual(g['31']['inputs']['image'],'c.png')
        # Three records come back so a saved recipe restores the picture into slot 3, not slot 1.
        self.assertEqual([(r['slot'],r['file']) for r in records],[(1,None),(2,None),(3,'c.png')])
        for gone in ('10','19','30','20'): self.assertNotIn(gone,g)
        # Nothing else was touched: the embed consumer and the loaders it needs are intact.
        self.assertEqual(g['14']['inputs']['pos_embed'],['22',0]); self.assertIn('12',g); self.assertIn('13',g)

    def test_short_or_empty_payloads_are_padded_and_the_minimum_is_enforced(self):
        g=board_graph()
        ref.compile_references(self.preset,g,[{'role':'style','file':'b.png'}],self.root)
        self.assertEqual(g['22']['inputs'],{'embed1':['19',0],'method':'concat'}); self.assertEqual(g['10']['inputs']['image'],'b.png')
        with self.assertRaisesRegex(ValueError,'at least 1 picture'): ref.compile_references(self.preset,board_graph(),[],self.root)
        with self.assertRaisesRegex(ValueError,'at least 1 picture'): ref.compile_references(self.preset,board_graph(),None,self.root)
        with self.assertRaisesRegex(ValueError,'3 board slots'): ref.compile_references(self.preset,board_graph(),[{}]*4,self.root)
        with self.assertRaisesRegex(ValueError,'supported role'): ref.compile_references(self.preset,board_graph(),[{'role':'vibe','file':'a.png'}],self.root)

    def test_persisted_records_round_trip_into_the_same_bindings(self):
        """The placeholders exist so a saved recipe restores by position: feeding the records back must
        reproduce the same loaders and the same combiner inputs, including an empty first slot."""
        for supplied in ([{},{'role':'style','file':'b.png'},{'role':'style','file':'c.png'}],[{'role':'style','file':'a.png'},{},{'role':'style','file':'c.png'}]):
            first=board_graph(); records=ref.compile_references(self.preset,first,supplied,self.root)
            second=board_graph(); ref.compile_references(self.preset,second,records,self.root)
            self.assertEqual(second,first); self.assertEqual(len(records),3)


def klein_board_graph():
    """A FLUX.2 Klein board: the source's reference latent, then one per board slot, chained into the guider."""
    g={'4':{'class_type':'CLIPTextEncode','inputs':{'text':'Redraw image 1 in the pose of image 2.'}},
       '6':{'class_type':'CFGGuider','inputs':{'positive':['27',0],'cfg':1.0}},'13':{'class_type':'SaveImage','inputs':{'images':['6',0]}}}
    cond=['4',0]
    for loader,latent in (('14','17'),('20','23'),('24','27')):
        scale=str(int(loader)+1); encode=str(int(loader)+2)
        g[loader]={'class_type':'LoadImage','inputs':{'image':'example.png'}}
        g[scale]={'class_type':'ImageScaleToTotalPixels','inputs':{'image':[loader,0],'megapixels':1.0,'resolution_steps':1}}
        g[encode]={'class_type':'VAEEncode','inputs':{'pixels':[scale,0]}}
        g[latent]={'class_type':'ReferenceLatent','inputs':{'conditioning':cond,'latent':[encode,0]}}; cond=[latent,0]
    return g


class KleinBoardTests(unittest.TestCase):
    """An empty slot's ReferenceLatent is bypassed so the chain closes up; the guider never loses its conditioning."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        for name in ('a.png','c.png'): Image.new('RGB',(300,400),'teal').save(self.root/name)
        self.preset={'positive':['4','text'],'last_reference':['14','image'],'reference_board':{'min':1,'policy':'FLUX.2 Klein reference latents'},
                     'reference_slots':[{'role':'pose','binding':['20','image']},{'role':'pose','binding':['24','image']}]}
    def tearDown(self):self.temp.cleanup()

    def test_empty_last_slot_is_bypassed_and_the_guider_reads_the_surviving_latent(self):
        g=klein_board_graph(); records=ref.compile_references(self.preset,g,[{'role':'pose','file':'a.png'},{}],self.root)
        for node in ('24','25','26','27'): self.assertNotIn(node,g)
        self.assertEqual(g['6']['inputs']['positive'],['23',0]); self.assertEqual(g['20']['inputs']['image'],'a.png'); self.assertEqual(g['23']['inputs']['conditioning'],['17',0])
        self.assertEqual([(r['slot'],r['file']) for r in records],[(1,'a.png'),(2,None)]); self.assertIn('13',g)

    def test_empty_first_slot_is_bypassed_and_the_next_latent_reads_the_source_latent(self):
        g=klein_board_graph(); ref.compile_references(self.preset,g,[{},{'role':'pose','file':'c.png'}],self.root)
        for node in ('20','21','22','23'): self.assertNotIn(node,g)
        self.assertEqual(g['27']['inputs']['conditioning'],['17',0]); self.assertEqual(g['6']['inputs']['positive'],['27',0]); self.assertEqual(g['24']['inputs']['image'],'c.png')

    def test_a_full_board_keeps_the_whole_chain(self):
        g=klein_board_graph(); ref.compile_references(self.preset,g,[{'role':'pose','file':'a.png'},{'role':'pose','file':'c.png'}],self.root)
        self.assertEqual((g['6']['inputs']['positive'],g['27']['inputs']['conditioning'],g['23']['inputs']['conditioning']),(['27',0],['23',0],['17',0]))
        self.assertEqual((g['20']['inputs']['image'],g['24']['inputs']['image']),('a.png','c.png'))
