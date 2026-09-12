import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location('reference_compiler',ROOT/'app/references.py')
ref=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ref)


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        Image.new('RGB',(400,600),'teal').save(self.root/'identity.png')
        Image.new('RGB',(600,400),'gold').save(self.root/'pose.png')
        self.preset={'positive':['6','prompt'],'reference_slots':[{'binding':['4','image']},{'binding':['16','image']}]}
        self.graph={'4':{'inputs':{'image':'default'}},'16':{'inputs':{'image':'default'}},'5':{'inputs':{'width':512,'height':0}},'6':{'inputs':{'prompt':'Hold a compass'}}}
        self.references=[{'role':'identity','file':'identity.png','contribution':'Face and costume','avoid':'Pose'},{'role':'pose','file':'pose.png','contribution':'Hand placement','avoid':'Clothes'}]
    def tearDown(self):self.temp.cleanup()

    def test_portrait_aspect_and_roles_are_retained(self):
        result=ref.compile_references(self.preset,self.graph,self.references,self.root)
        self.assertEqual(result[0]['transform']['resized_size'],[512,768])
        self.assertEqual(result[0]['transform']['vae_size'],[512,768])
        self.assertEqual(self.graph['4']['inputs']['image'],'identity.png')
        self.assertIn('Image 2 — pose',self.graph['6']['inputs']['prompt'])
        self.assertTrue(self.graph['6']['inputs']['prompt'].endswith('Hold a compass'))
        self.assertEqual(len(result[0]['sha256']),64)

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

    def test_live_recipe_defaults_compile_without_exposing_auto_height(self):
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
            self.assertNotIn('height',preset['defaults'])
            controls={k:v for k,v in preset['defaults'].items() if k!='reference'}
            _,graph,_,_,_=studio.prepare({'preset_id':preset['id'],'controls':controls,
                'references':[{'role':'identity','file':'identity.png'} for _ in range(count)]})
            self.assertEqual(graph['5']['inputs']['height'],0)
            self.assertEqual(graph['5']['inputs']['width'],512)
