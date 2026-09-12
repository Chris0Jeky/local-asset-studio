"""Offline cover for the model acquisition scripts: header sniffing, stubs, receipts and the token path.

Nothing here touches the network, ComfyUI or the configured model folders. Green means the pure helpers
behave; it does not prove that a real download succeeds.
"""
import email.message
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from urllib.request import Request

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'


def load(stem):
    spec=importlib.util.spec_from_file_location(stem.replace('-','_'),SCRIPTS/(stem+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


hf=load('fetch-hf')
civitai=load('civitai-fetch')
intake=load('intake-downloads')


def safetensors(header,payload=b'\0'*8):
    body=json.dumps(header).encode('utf-8')
    return struct.pack('<Q',len(body))+body+payload


class TempMixin(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)


class HuggingFaceHelperTests(TempMixin):
    def test_urls_quote_spaces_and_walk_to_the_containing_folder(self):
        self.assertEqual(hf.resolve_url('ntc-ai/x','cinematic lighting.safetensors'),'https://huggingface.co/ntc-ai/x/resolve/main/cinematic%20lighting.safetensors')
        self.assertEqual(hf.tree_url('Comfy-Org/Krea-2','loras/krea2_darkbrush.safetensors'),'https://huggingface.co/api/models/Comfy-Org/Krea-2/tree/main/loras')
        self.assertEqual(hf.tree_url('a/b','top.safetensors','abc123'),'https://huggingface.co/api/models/a/b/tree/abc123')

    def test_lfs_oid_reads_the_tree_listing_and_refuses_a_non_hex_oid(self):
        digest='f47c4316dd93af66e0518c93b582f459571d4925b519133770c73a52cd5db7c6'
        tree=[{'path':'loras/other.safetensors','lfs':{'oid':digest,'size':1}},
              {'path':'loras/a.safetensors','lfs':{'oid':digest.upper(),'size':469291992}}]
        self.assertEqual(hf.lfs_oid(tree,'loras/a.safetensors'),(digest,469291992))
        self.assertEqual(hf.lfs_oid(tree,'loras/missing.safetensors'),(None,None))
        self.assertEqual(hf.lfs_oid([{'path':'p','lfs':{'oid':'sha256:zz'},'size':3}],'p'),(None,3))
        self.assertEqual(hf.lfs_oid(None,'p'),(None,None))

    def test_destination_stays_inside_the_model_library(self):
        target=hf.destination(self.root,'loras','demo.safetensors')
        self.assertEqual(target,(self.root/'models/loras/demo.safetensors').resolve())
        for name in ('../escape.safetensors','loras/nested.safetensors','.hidden.safetensors','demo.ckpt',''):
            with self.assertRaises(SystemExit):hf.destination(self.root,'loras',name)
        with self.assertRaises(SystemExit):hf.destination(self.root,'not-a-folder','demo.safetensors')

    def test_stub_matches_the_rules_validate_repo_enforces(self):
        digest='a'*64
        entry=hf.stub('loras','Krea2 Demo LoRA.safetensors','owner/repo','main','https://huggingface.co/owner/repo/resolve/main/x.safetensors',123,digest,family='Krea 2',trigger='@DEMO')
        self.assertEqual(entry['id'],'krea2-demo-lora')
        self.assertEqual(entry['file'],'loras/Krea2 Demo LoRA.safetensors')
        self.assertTrue(entry['url'].startswith('https://huggingface.co/'))
        self.assertEqual((entry['bytes'],entry['sha256'],entry['trigger']),(123,digest,'@DEMO'))
        self.assertIn('TODO',entry['terms'])
        self.assertEqual(entry['strength'],[1.0,1.0])

    def test_receipts_append_without_losing_earlier_entries(self):
        first=hf.append_receipt(self.root,{'file':'a.safetensors','sha256':'a'*64})
        hf.append_receipt(self.root,{'file':'b.safetensors','sha256':'b'*64})
        stored=json.loads((self.root/'.runtime/downloads/receipts.json').read_text(encoding='utf-8'))
        self.assertEqual([item['file'] for item in stored],['a.safetensors','b.safetensors'])
        self.assertEqual(stored[0],first)
        (self.root/'.runtime/downloads/receipts.json').write_text('{"not":"a list"}',encoding='utf-8')
        with self.assertRaises(SystemExit):hf.append_receipt(self.root,{'file':'c.safetensors'})

    def test_missing_local_config_is_an_explicit_message(self):
        with self.assertRaisesRegex(SystemExit,'config/local.json'):hf.load_config(self.root)
        (self.root/'config').mkdir();(self.root/'config/local.json').write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(SystemExit,'comfy_root'):hf.load_config(self.root)


class CivitaiHelperTests(TempMixin):
    version={'id':3302337,'modelId':2863875,'baseModel':'Krea 2','trainedWords':['@NIJISIS'],
             'model':{'name':'NIJISIS','allowCommercialUse':['Image','RentCivit','Rent'],'allowDerivatives':True,'allowDifferentLicense':True},
             'files':[{'id':1,'name':'preview.png','type':'Image','sizeKB':10},
                      {'id':3187293,'name':'NIJISIS_KREA_2 (1).safetensors','type':'Model','primary':True,'sizeKB':446399.5859375,
                       'hashes':{'SHA256':'7266BA9F6BE571054D61ED04BB9414A1396366A6AF19DF0C84E12B86EC266A7E'},
                       'downloadUrl':'https://civitai.com/api/download/models/3302337'}]}

    def test_token_comes_only_from_the_environment_and_is_never_echoed(self):
        with self.assertRaises(SystemExit) as caught:civitai.read_token({})
        message=str(caught.exception)
        self.assertIn('CIVITAI_API_TOKEN',message);self.assertIn('command line',message)
        self.assertEqual(civitai.read_token({'CIVITAI_API_TOKEN':'  secret-value  '}),'secret-value')
        source=(SCRIPTS/'civitai-fetch.py').read_text(encoding='utf-8')
        for forbidden in ("'--token'",'args.token','config.get("token")',"config.get('token')"):
            self.assertNotIn(forbidden,source,'the token must never arrive from argv or config')

    def test_pick_file_prefers_the_primary_safetensors_and_converts_sizekb(self):
        chosen=civitai.pick_file(self.version)
        self.assertEqual(chosen['id'],3187293)
        self.assertEqual(chosen['bytes'],457113176)
        self.assertEqual(chosen['sha256'],'7266ba9f6be571054d61ed04bb9414a1396366a6af19df0c84e12b86ec266a7e')
        self.assertEqual(civitai.pick_file(self.version,3187293)['id'],3187293)
        with self.assertRaises(SystemExit):civitai.pick_file(self.version,999)
        with self.assertRaises(SystemExit):civitai.pick_file({'files':[]})
        with self.assertRaises(SystemExit):civitai.pick_file({'files':[{'id':2,'name':'x.ckpt','type':'Model'}]})
        self.assertIsNone(civitai.pick_file({'files':[{'id':2,'name':'x.safetensors','type':'Model','hashes':{}}]})['sha256'])

    def test_safe_name_cleans_a_civitai_filename(self):
        self.assertEqual(civitai.safe_name('NIJISIS_KREA_2 (1).safetensors'),'NIJISIS_KREA_2_1_.safetensors')
        for name in ('model.ckpt','',None):
            with self.assertRaises(SystemExit):civitai.safe_name(name)

    def test_terms_note_does_not_invent_flags_the_version_payload_lacks(self):
        note=civitai.terms_note({'id':9,'modelId':8,'model':{'name':'x'},'baseModel':'Anima'})
        self.assertIn('carries no permission flags',note); self.assertNotIn('none listed',note); self.assertIn('/models/8',note)

    def test_terms_note_repeats_the_listing_flags_verbatim(self):
        note=civitai.terms_note(self.version)
        self.assertIn('Image, RentCivit, Rent',note);self.assertIn('derivatives allowed',note)
        strict=civitai.terms_note({'id':1,'modelId':2,'model':{'allowCommercialUse':[],'allowDerivatives':False,'allowDifferentLicense':False}})
        self.assertIn('none listed',strict);self.assertIn('derivatives NOT allowed',strict)

    def test_http_failures_explain_themselves(self):
        self.assertIn('401',civitai.explain_http(401))
        self.assertIn('CIVITAI_API_TOKEN',civitai.explain_http(401))
        self.assertIn('region',civitai.explain_http(403,'{"error":"REGION_BLOCKED"}'))
        self.assertIn('early access',civitai.explain_http(403,'{"error":"forbidden"}'))
        self.assertIn('404',civitai.explain_http(404));self.assertIn('429',civitai.explain_http(429))

    def test_authorization_is_dropped_when_a_download_redirects_to_another_host(self):
        request=Request('https://civitai.com/api/download/models/1',headers={'Authorization':'Bearer secret'})
        headers=email.message.Message()
        same=civitai.DropAuth().redirect_request(request,None,302,'Found',headers,'https://civitai.com/other')
        away=civitai.DropAuth().redirect_request(request,None,302,'Found',headers,'https://cdn.example.com/file.safetensors')
        self.assertEqual(same.get_header('Authorization'),'Bearer secret')
        self.assertIsNone(away.get_header('Authorization'))

    def test_stub_records_the_civitai_source_and_trigger(self):
        chosen=civitai.pick_file(self.version)
        entry=civitai.stub('loras','NIJISIS.safetensors',self.version,chosen)
        self.assertEqual(entry['id'],'nijisis')
        self.assertEqual(entry['url'],'https://civitai.com/api/download/models/3302337')
        self.assertEqual(entry['source'],'https://civitai.com/models/2863875?modelVersionId=3302337')
        self.assertEqual(entry['trigger'],'@NIJISIS');self.assertEqual(entry['family'],'Krea 2')
        self.assertIn('allowCommercialUse',entry['terms'])


class IntakeHeaderTests(TempMixin):
    def write(self,name,header,payload=b'\0'*8):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(safetensors(header,payload));return path

    def test_header_reading_rejects_files_that_are_not_safetensors(self):
        path=self.write('good.safetensors',{'a.weight':{'dtype':'F16'},'__metadata__':{'format':'pt'}})
        self.assertIn('a.weight',intake.read_header(path))
        short=self.root/'short.safetensors';short.write_bytes(b'123')
        with self.assertRaisesRegex(ValueError,'header length'):intake.read_header(short)
        huge=self.root/'huge.safetensors';huge.write_bytes(struct.pack('<Q',10**12)+b'{}')
        with self.assertRaisesRegex(ValueError,'unreasonable'):intake.read_header(huge)
        cut=self.root/'cut.safetensors';cut.write_bytes(struct.pack('<Q',64)+b'{"a":1}')
        with self.assertRaisesRegex(ValueError,'truncated'):intake.read_header(cut)
        junk=self.root/'junk.safetensors';junk.write_bytes(struct.pack('<Q',5)+b'notjs')
        with self.assertRaisesRegex(ValueError,'unreadable'):intake.read_header(junk)
        listed=self.root/'listed.safetensors';listed.write_bytes(safetensors([]))
        with self.assertRaisesRegex(ValueError,'not an object'):intake.read_header(listed)

    def test_classification_follows_the_shapes_of_the_installed_models(self):
        krea_lora={'diffusion_model.blocks.0.attn.gate.lora_A.weight':{},'diffusion_model.blocks.0.attn.gate.lora_B.weight':{},
                   '__metadata__':{'modelspec.architecture':'krea2/lora','ss_network_module':'networks.lora'}}
        sdxl_lora={'lora_unet_input_blocks_4_1_proj_in.alpha':{},'lora_unet_input_blocks_4_1_proj_in.lora_down.weight':{}}
        diffusers_lora={'unet.down_blocks.1.attentions.0.transformer_blocks.0.attn1.to_k.lora.down.weight':{},'__metadata__':{'format':'pt'}}
        comfy_lora={'transformer.final_layer.linear.lora_A.weight':{},'transformer.img_in.lora_B.weight':{}}
        checkpoint={'model.diffusion_model.input_blocks.0.0.weight':{},'conditioner.embedders.0.transformer.text_model.x':{},'first_stage_model.decoder.conv_in.weight':{}}
        vae={'decoder.conv_in.weight':{},'encoder.conv_in.weight':{},'conv1.bias':{},'conv2.weight':{}}
        encoder={'model.embed_tokens.weight':{},'model.layers.0.mlp.down_proj.weight':{}}
        backbone={'blocks.0.attn.wk.weight':{},'img_in.weight':{},'final_layer.linear.weight':{}}
        for header,folder in ((krea_lora,'loras'),(sdxl_lora,'loras'),(diffusers_lora,'loras'),(comfy_lora,'loras'),
                              (checkpoint,'checkpoints'),(vae,'vae'),(encoder,'text_encoders'),(backbone,'diffusion_models')):
            self.assertEqual(intake.classify(header),folder,header)

    def test_plan_carries_errors_and_honours_an_explicit_folder(self):
        good=self.write('a.safetensors',{'lora_unet_x.lora_down.weight':{}})
        bad=self.root/'b.safetensors';bad.write_bytes(b'nope')
        items=intake.plan([good,bad])
        self.assertEqual(items[0]['folder'],'loras');self.assertIsNone(items[0]['error'])
        self.assertIsNone(items[1]['folder']);self.assertIn('header length',items[1]['error'])
        forced=intake.plan([bad],'diffusion_models')
        self.assertEqual(forced[0]['folder'],'diffusion_models');self.assertIsNone(forced[0]['error'])

    def test_destination_and_stub_stay_inside_the_validator_rules(self):
        target=intake.destination(self.root,'loras','My LoRA (final).safetensors')
        self.assertEqual(target.name,'My_LoRA_final_.safetensors')
        escaped=intake.destination(self.root,'loras','../escape.safetensors')
        self.assertEqual(escaped,(self.root/'models/loras/escape.safetensors').resolve(),'a traversal must collapse to a basename inside the library')
        with self.assertRaises(SystemExit):intake.destination(self.root,'nowhere','a.safetensors')
        with self.assertRaises(SystemExit):intake.destination(self.root,'loras','notes.txt')
        entry=intake.stub('loras','demo.safetensors',42,'c'*64)
        self.assertEqual((entry['id'],entry['file'],entry['bytes']),('demo','loras/demo.safetensors',42))
        self.assertIn('TODO',entry['terms'])


if __name__=='__main__':unittest.main()
