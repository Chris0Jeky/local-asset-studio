import hashlib
import importlib.util
import io
import json
import tempfile
import threading
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from queue import Empty
from PIL import Image

def png():
    stream = io.BytesIO(); Image.new('RGB', (8, 12), 'purple').save(stream, 'PNG'); return stream.getvalue()

def rgba_png(width=8, height=8, transparent=True):
    stream = io.BytesIO()
    image = Image.new('RGBA', (width, height), (40, 80, 120, 255))
    if transparent: image.putpixel((3, 4), (40, 80, 120, 0))
    image.save(stream, 'PNG')
    return stream.getvalue()

SPEC = importlib.util.spec_from_file_location("asset_server", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)

GRAPH = {"1":{"inputs":{"text":"native positive","width":512,"height":512,"seed":1,"steps":20,"cfg":7,"lora":1,"strength_clip":1,"reference":"default.png"}}, "2":{"inputs":{"width":512,"height":512}}}
PRESET = {"id":"demo","name":"Demo","category":"Test","graph":"workflows/api/demo-api.json","positive":["1","text"],"width":["1","width"],"height":["1","height"],"seed":["1","seed"],"steps":["1","steps"],"cfg":["1","cfg"],"lora":["1","lora"],"reference":["1","reference"],"bindings_extra":{"width":[["2","width"]],"height":[["2","height"]],"lora":[["1","strength_clip"]]}}

class FakeStudio(server.Studio):
    def __init__(self, root, replies): self.replies=iter(replies); self.requests=[]; super().__init__(root)
    def _request(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        response=next(self.replies)
        if isinstance(response, Exception): raise response
        return response

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        (self.root/"presets").mkdir(); (self.root/"workflows/api").mkdir(parents=True)
        (self.root/"config").mkdir(); (self.root/"fake-comfy/input").mkdir(parents=True)
        (self.root/"config/local.json").write_text(json.dumps({"comfy_root":str(self.root/"fake-comfy")}))
        (self.root/"presets/catalog.json").write_text(json.dumps({"presets":[PRESET]}))
        (self.root/"workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start=patch.object(threading.Thread,"start",lambda *_:None); self.start.start()
    def tearDown(self): self.start.stop(); self.tmp.cleanup()
    def studio(self): return server.Studio(self.root)

    @staticmethod
    def _http_response(body=None, error=None):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self):
                if error: raise error
                return body
        return Response()

    def _run_real_prompt_reply(self, reply, batch_count=1):
        s=self.studio(); job=s.jobs[s.create_job({'preset_id':'demo','controls':{},'batch_count':batch_count}, enqueue=False)['id']]
        replies=[self._http_response(json.dumps({'queue_running':[],'queue_pending':[]}).encode()),reply]
        with patch.object(server,'urlopen',side_effect=replies) as request: s._run(job)
        return s, job, request

    @staticmethod
    def _commit_reading(available):
        return {'available_bytes':available,'limit_bytes':96*1024**3,'committed_bytes':64*1024**3,'unknown_reason':None}

    def _heavy_studio(self, replies=(), explicit=True):
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy'),'enforce_host_commit_headroom':True}))
        graph=json.loads(json.dumps(GRAPH));graph['1']['inputs']['unet_name']='qwen-image-edit-2511-Q4_K_M.gguf'
        graph['3']={'class_type':'ImageScaleToTotalPixels','inputs':{'megapixels':1.0}}
        preset=dict(PRESET,**({'host_commit_heavy':True} if explicit else {}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}));(self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        return FakeStudio(self.root,replies)

    def test_host_commit_gate_rejects_low_and_unknown_heavy_graphs_before_any_prompt(self):
        for reading,message in ((self._commit_reading(32*1024**3-1),'below the required 32 GiB'),
                                ({'available_bytes':None,'limit_bytes':None,'committed_bytes':None,'unknown_reason':'counter unavailable'},'counter unavailable')):
            with self.subTest(reading=reading),patch.object(server.host_memory,'read',return_value=reading):
                studio=self._heavy_studio()
                with self.assertRaisesRegex(server.StudioError,message):studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)
                self.assertEqual([args[0] for args,_ in studio.requests if args],[])
                self.assertFalse(studio.jobs)

    def test_host_commit_exact_threshold_allows_submission_and_records_readings(self):
        minimum=32*1024**3;studio=self._heavy_studio([{'queue_running':[],'queue_pending':[]},{'prompt_id':'heavy'},{'heavy':{'status':{'status_str':'success'},'outputs':{}}}],explicit=False)
        with patch.object(server.host_memory,'read',side_effect=[self._commit_reading(minimum),self._commit_reading(minimum)]):
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'completed');self.assertEqual([args[0] for args,_ in studio.requests if args],['/queue','/prompt','/history/heavy'])
        self.assertEqual([entry['phase'] for entry in job['host_commit_readings']],['prepared','pre-submit'])

    def test_host_commit_drop_after_queue_wait_never_marks_submission_intent(self):
        minimum=32*1024**3;studio=self._heavy_studio([{'queue_running':[],'queue_pending':[]}])
        with patch.object(server.host_memory,'read',side_effect=[self._commit_reading(minimum),self._commit_reading(minimum-1)]):
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'failed');self.assertNotIn('pending_submission',job);self.assertEqual(job['prompt_ids'],[])
        self.assertIn('No prompt was submitted',job['message']);self.assertEqual([args[0] for args,_ in studio.requests if args],['/queue'])

    def test_host_commit_block_between_batch_members_keeps_prior_prompt_as_partial(self):
        minimum=32*1024**3;studio=self._heavy_studio([{'queue_running':[],'queue_pending':[]},{'prompt_id':'first'},{'first':{'status':{'status_str':'success'},'outputs':{}}}])
        with patch.object(server.host_memory,'read',side_effect=[self._commit_reading(minimum),self._commit_reading(minimum),self._commit_reading(minimum-1)]):
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{},'batch_count':2},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'partial');self.assertEqual(job['prompt_ids'],['first']);self.assertNotIn('pending_submission',job)
        self.assertEqual([args[0] for args,_ in studio.requests if args],['/queue','/prompt','/history/first'])

    def test_host_commit_gate_covers_qwen_image_21_at_any_size(self):
        """The 7B model and its 9.35 GB encoder need the headroom below 1 MP and in the size-less edit graph too."""
        loader={'class_type':'UNETLoader','inputs':{'unet_name':'qwen_image_2.1_int8_convrot.safetensors'}}
        for graph in ({'1':loader,'5':{'class_type':'EmptyQwenImageLayeredLatentImage','inputs':{'width':832,'height':1248}}},{'1':loader}):
            with self.subTest(nodes=sorted(graph)):self.assertTrue(server.Studio.host_commit_required({'id':'qwen21-t2i'},graph))
        self.assertTrue(server.Studio.host_commit_required({'id':'qwen21-edit','backend_id':'qwen21'},{}))
        sdxl={'1':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':'wai.safetensors'}},'5':{'class_type':'EmptyLatentImage','inputs':{'width':832,'height':1248}}}
        self.assertFalse(server.Studio.host_commit_required({'id':'wai'},sdxl))
        self.assertFalse(server.Studio.host_commit_required({'id':'klein','host_commit_heavy':True},{'1':{'class_type':'UNETLoader','inputs':{'unet_name':'flux-2-klein-9b.safetensors'}},'5':{'class_type':'EmptyLatentImage','inputs':{'width':832,'height':1248}}}))

    def test_host_commit_gate_ignores_nonheavy_qwen_encoder_and_observation(self):
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy'),'enforce_host_commit_headroom':True}))
        graph=json.loads(json.dumps(GRAPH));graph['1']['inputs']['clip_name']='qwen_3_4b.safetensors'
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'sdxl'},{'sdxl':{'status':{'status_str':'success'},'outputs':{}}}])
        with patch.object(server.host_memory,'read',side_effect=AssertionError('non-heavy graph must not read commit memory')):
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'completed')
        minimum=32*1024**3;heavy=self._heavy_studio([])
        with patch.object(server.host_memory,'read',return_value=self._commit_reading(minimum)):
            job=heavy.jobs[heavy.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        job.update(status='uncertain',prompt_ids=['known'],submissions=[{'index':0,'prompt_id':'known','seed':1,'graph':job['graph'],'status':'observing'}]);heavy.replies=iter([{'known':{'status':{'status_str':'success'},'outputs':{}}}])
        with patch.object(server.host_memory,'read',side_effect=AssertionError('observation must not read commit memory')):heavy._resume(job)
        self.assertEqual(job['status'],'completed');self.assertEqual([args[0] for args,_ in heavy.requests if args],['/history/known'])

    def test_malformed_prompt_responses_are_uncertain_and_retain_intent(self):
        cases=(
            ('malformed-json',self._http_response(b'{')),
            ('invalid-utf8',self._http_response(b'\xff')),
            ('truncated-http',self._http_response(error=IncompleteRead(b'{"prompt_id":"partial'))),
            ('wrong-shape',self._http_response(json.dumps([]).encode())),
            ('missing-id',self._http_response(json.dumps({'status':'queued'}).encode())),
            ('nonstring-id',self._http_response(json.dumps({'prompt_id':17}).encode())),
            ('blank-id',self._http_response(json.dumps({'prompt_id':'   '}).encode())),
        )
        for label, reply in cases:
            with self.subTest(label=label):
                s,job,request=self._run_real_prompt_reply(reply)
                self.assertEqual(job['status'],'uncertain')
                self.assertTrue(job['pending_submission'])
                self.assertEqual(job['prompt_ids'],[])
                self.assertEqual(job['submissions'],[])
                self.assertEqual(request.call_count,2)
                restored=self.studio().jobs[job['id']]
                self.assertEqual(restored['status'],'uncertain')
                self.assertTrue(restored['pending_submission'])

    def test_valid_prompt_response_preserves_prompt_id_and_completes(self):
        s=self.studio(); job=s.jobs[s.create_job({'preset_id':'demo','controls':{}}, enqueue=False)['id']]
        replies=[self._http_response(json.dumps({'queue_running':[],'queue_pending':[]}).encode()),
                 self._http_response(json.dumps({'prompt_id':'  prompt-1  '}).encode()),
                 self._http_response(json.dumps({'  prompt-1  ':{'status':{'status_str':'success'},'outputs':{}}}).encode())]
        with patch.object(server,'urlopen',side_effect=replies): s._run(job)
        self.assertEqual(job['status'],'completed')
        self.assertEqual(job['prompt_ids'],['  prompt-1  '])
        self.assertEqual(job['submissions'][0]['prompt_id'],'  prompt-1  ')
        self.assertNotIn('pending_submission',job)

    def test_later_batch_member_uncertain_keeps_earlier_evidence_and_stops(self):
        s=self.studio(); job=s.jobs[s.create_job({'preset_id':'demo','controls':{'seed':40},'batch_count':2}, enqueue=False)['id']]
        replies=[self._http_response(json.dumps({'queue_running':[],'queue_pending':[]}).encode()),
                 self._http_response(json.dumps({'prompt_id':'first'}).encode()),
                 self._http_response(json.dumps({'first':{'status':{'status_str':'success'},'outputs':{}}}).encode()),
                 self._http_response(json.dumps({'prompt_id':None}).encode())]
        with patch.object(server,'urlopen',side_effect=replies) as request: s._run(job)
        self.assertEqual(job['status'],'uncertain')
        self.assertEqual(job['prompt_ids'],['first'])
        self.assertEqual([submission['prompt_id'] for submission in job['submissions']],['first'])
        self.assertEqual(job['pending_submission']['index'],1)
        self.assertEqual(job['pending_submission']['seed'],41)
        self.assertEqual(request.call_count,4)
    def test_validation_and_companion_bindings(self):
        s=self.studio(); _, graph, _, _, _=s.prepare({"preset_id":"demo","controls":{"width":640,"height":768,"lora":"0.5"}})
        self.assertEqual(graph["1"]["inputs"]["width"],640); self.assertEqual(graph["2"]["inputs"]["width"],640)
        self.assertEqual(graph["1"]["inputs"]["strength_clip"],0.5)
        with self.assertRaisesRegex(server.StudioError,"multiple of 8"): s.prepare({"preset_id":"demo","controls":{"width":641}})
        with self.assertRaisesRegex(server.StudioError,"Unsupported"): s.prepare({"preset_id":"demo","controls":{"negative":"no"}})
    def test_fixed_canvas_presets_enforce_their_grid_and_pixel_ceiling(self):
        # The Qwen atelier recipes now drive an EmptySD3LatentImage, so both dimensions are bound and
        # the /16 grid plus the ~1 MP ceiling are the only guards between the browser and a bad canvas.
        (self.root/"presets/catalog.json").write_text(json.dumps({"presets":[dict(PRESET,dimension_multiple=16,dimension_limits=[64,1536],max_pixels=1024*1024)]}))
        s=self.studio(); _, graph, _, _, _=s.prepare({"preset_id":"demo","controls":{"width":832,"height":1248}})
        self.assertEqual((832,1248),(graph["1"]["inputs"]["width"],graph["1"]["inputs"]["height"]))
        self.assertEqual((832,1248),(graph["2"]["inputs"]["width"],graph["2"]["inputs"]["height"]))
        with self.assertRaisesRegex(server.StudioError,"multiple of 16"): s.prepare({"preset_id":"demo","controls":{"width":840,"height":1248}})
        with self.assertRaisesRegex(server.StudioError,"pixel budget"): s.prepare({"preset_id":"demo","controls":{"width":1536,"height":1536}})
    def test_path_traversal_and_upload_magic(self):
        with self.assertRaises(server.StudioError): server.inside(self.root, self.root/"../outside")
        s=self.studio()
        with self.assertRaises(server.StudioError): s.upload("../x.png","image/png",b"wrong")
        with self.assertRaisesRegex(server.StudioError, "damaged|incomplete"):
            s.upload("broken.png","image/png",b"\x89PNG\r\n\x1a\nbody")
        result=s.upload("../x.png","image/png",png())
        self.assertEqual((result['width'],result['height']),(8,12)); self.assertEqual(len(result['sha256']),64)
        uploads=self.root/"experiments/uploads"; uploads.mkdir(parents=True,exist_ok=True); (uploads/"plain.png").write_bytes(b"x")
        with self.assertRaisesRegex(server.StudioError,"Reference upload is invalid"):
            s.prepare({"preset_id":"demo","controls":{"reference":"../plain.png"}})
        with self.assertRaisesRegex(server.StudioError,"Reference upload is invalid"):
            s.prepare({"preset_id":"demo","controls":{"reference":"plain.png"}})

    def test_anime_masked_repair_preserves_valid_rgba_bytes_and_rejects_invalid_masks(self):
        graph={"4":{"class_type":"LoadImage","inputs":{"image":"authored-mask.png"}}}
        preset={"id":"anime-masked-repair","name":"Masked repair","category":"Test","graph":"workflows/api/masked-repair-api.json","reference":["4","image"],"requires_rgba_mask":True}
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}))
        (self.root/'workflows/api/masked-repair-api.json').write_text(json.dumps(graph))
        s=self.studio(); source=rgba_png(); upload=s.upload('hand-mask.png','image/png',source)
        for path in (self.root/'experiments/uploads'/upload['file'], self.root/'fake-comfy/input'/upload['file']):
            self.assertEqual(path.read_bytes(),source)
            with Image.open(path) as decoded:
                self.assertEqual(decoded.mode,'RGBA')
                self.assertEqual(decoded.getpixel((3,4)),(40,80,120,0))
        _,bound,_,_,_=s.prepare({'preset_id':'anime-masked-repair','controls':{'reference':upload['file']}})
        self.assertEqual(bound['4']['inputs']['image'],upload['file'])
        opaque=s.upload('opaque.png','image/png',rgba_png(transparent=False))['file']
        rgb=s.upload('rgb.png','image/png',png())['file']
        unaligned=s.upload('unaligned.png','image/png',rgba_png(height=12))['file']
        jpeg=io.BytesIO(); Image.new('RGB',(8,8),'purple').save(jpeg,'JPEG')
        jpg=s.upload('masked.jpg','image/jpeg',jpeg.getvalue())['file']
        webp=io.BytesIO(); Image.new('RGB',(8,8),'purple').save(webp,'WEBP')
        webp_file=s.upload('masked.webp','image/webp',webp.getvalue())['file']
        for file, message in ((None,'RGBA PNG upload'),(opaque,'transparent repair region'),(rgb,'RGBA PNG'),(unaligned,'divisible by 8'),(jpg,'RGBA PNG'),(webp_file,'RGBA PNG')):
            with self.subTest(file=file), self.assertRaisesRegex(server.StudioError,message):
                s.create_job({'preset_id':'anime-masked-repair','controls':{} if file is None else {'reference':file}})
        self.assertEqual(s.jobs,{})
        self.assertTrue(s.queue.empty())

    def test_rgba_mask_guard_follows_the_preset_flag_not_a_hardcoded_id(self):
        """`sdxl-inpaint-fix` inherits the masked-repair refusals through `requires_rgba_mask`."""
        graph={"4":{"class_type":"LoadImage","inputs":{"image":"lantern-reference.png"}}}
        preset={"id":"sdxl-inpaint-fix","name":"WAI Fooocus inpaint repair","category":"Anime quality","graph":"workflows/api/inpaint-fix-api.json","reference":["4","image"],"requires_rgba_mask":True}
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset,PRESET]}))
        (self.root/'workflows/api/inpaint-fix-api.json').write_text(json.dumps(graph))
        s=self.studio(); masked=s.upload('hand-mask.png','image/png',rgba_png())['file']
        _,bound,_,_,_=s.prepare({'preset_id':'sdxl-inpaint-fix','controls':{'reference':masked}})
        self.assertEqual(bound['4']['inputs']['image'],masked)
        opaque=s.upload('opaque.png','image/png',rgba_png(transparent=False))['file']
        rgb=s.upload('rgb.png','image/png',png())['file']
        unaligned=s.upload('unaligned.png','image/png',rgba_png(height=12))['file']
        jpeg=io.BytesIO(); Image.new('RGB',(8,8),'purple').save(jpeg,'JPEG')
        jpg=s.upload('flat.jpg','image/jpeg',jpeg.getvalue())['file']
        webp=io.BytesIO(); Image.new('RGB',(8,8),'purple').save(webp,'WEBP')
        webp_file=s.upload('flat.webp','image/webp',webp.getvalue())['file']
        cases=((None,'WAI Fooocus inpaint repair requires a real RGBA PNG upload; the authored example cannot be queued'),
               (opaque,'transparent repair region'),(rgb,'RGBA PNG'),(unaligned,'divisible by 8'),(jpg,'RGBA PNG'),(webp_file,'RGBA PNG'))
        for file, message in cases:
            with self.subTest(file=file), self.assertRaisesRegex(server.StudioError,message):
                s.create_job({'preset_id':'sdxl-inpaint-fix','controls':{} if file is None else {'reference':file}})
        self.assertEqual(s.jobs,{}); self.assertTrue(s.queue.empty())
        # A preset without the flag keeps the ordinary upload contract: opaque RGB is fine.
        _,plain,_,_,_=s.prepare({'preset_id':'demo','controls':{'reference':rgb}})
        self.assertEqual(plain['1']['inputs']['reference'],rgb)

    def test_inpaint_head_and_patch_are_declared_requirements_that_block_readiness(self):
        """The Fooocus files are not `_name` inputs, so `model_files` is what makes them visible."""
        graph={"5":{"class_type":"INPAINT_LoadFooocusInpaint","inputs":{"head":"fooocus_inpaint_head.pth","patch":"inpaint_v26.fooocus.patch"}}}
        preset={"id":"sdxl-inpaint-fix","name":"WAI Fooocus inpaint repair","category":"Anime quality","graph":"workflows/api/inpaint-fix-api.json",
                "model_files":["inpaint/fooocus_inpaint_head.pth","inpaint/inpaint_v26.fooocus.patch"]}
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}))
        (self.root/'workflows/api/inpaint-fix-api.json').write_text(json.dumps(graph))
        installed=self.root/'fake-comfy/models/inpaint'; installed.mkdir(parents=True)
        (installed/'fooocus_inpaint_head.pth').write_bytes(b'head')
        s=self.studio(); found={r['file']:r for r in s.inspect_preset('sdxl-inpaint-fix')['requirements']}
        # The .pth is reported under inpaint/, never under the "models" default it never lived at.
        self.assertNotIn('models/fooocus_inpaint_head.pth',found)
        self.assertEqual(sorted(found),['inpaint/fooocus_inpaint_head.pth','inpaint/inpaint_v26.fooocus.patch'])
        self.assertTrue(found['inpaint/fooocus_inpaint_head.pth']['present'])
        self.assertFalse(found['inpaint/inpaint_v26.fooocus.patch']['present'])
        with patch.object(server.Studio,'node_info',lambda *a,**k:{}), patch.object(server.Studio,'validate_graph',lambda *a:None):
            with self.assertRaisesRegex(server.StudioError,r'Required model is unavailable: inpaint/inpaint_v26\.fooocus\.patch'):
                s.production_preflight(preset,graph)
        (installed/'inpaint_v26.fooocus.patch').write_bytes(b'patch')
        restored={r['file']:r['present'] for r in s.inspect_preset('sdxl-inpaint-fix')['requirements']}
        self.assertEqual(restored,{'inpaint/fooocus_inpaint_head.pth':True,'inpaint/inpaint_v26.fooocus.patch':True})

    def test_imported_image_survives_restart_without_generation(self):
        s=self.studio();result=s.import_image('frame.png','image/png',png())
        self.assertEqual(s.queue.qsize(),0)
        self.assertEqual(s.assets.file(result['asset']['id']).read_bytes(),png())
        restored=self.studio()
        self.assertEqual(restored.assets.get(result['asset']['id'])['sha256'],result['asset']['sha256'])
        self.assertFalse(restored.jobs[result['job']['id']]['prompt_ids'])

    def test_loopback_host_and_origin_are_required_for_mutation(self):
        handler=server.Handler.__new__(server.Handler)
        handler.headers={"Host":"127.0.0.1:8191","Origin":"http://127.0.0.1:8191"}
        self.assertTrue(handler._safe_mutation())
        handler.headers={"Host":"localhost:8191","Origin":"https://localhost:8191"}
        self.assertFalse(handler._safe_mutation())
        handler.headers={"Host":"evil.example:8191","Origin":"http://evil.example:8191"}
        self.assertFalse(handler._safe_host())

    def test_foreign_origin_post_drains_declared_body_before_refusal(self):
        body=b"a"*(32*1024)
        handler=server.Handler.__new__(server.Handler)
        handler.headers={"Host":"127.0.0.1:8191","Origin":"http://evil.example","Content-Length":str(len(body)),"Content-Type":"application/json"}
        handler.path="/api/estimate";handler.rfile=io.BytesIO(body);handler.close_connection=False
        sent=[];handler._json=lambda status,obj:sent.append((status,obj))
        handler.do_POST()
        self.assertEqual(sent,[(403,{"error":"Local same-origin request required"})])
        self.assertEqual(handler.rfile.read(),b"")

    def test_foreign_origin_post_drains_declared_length_but_closes_ambiguous_framing(self):
        body=b"bad"
        handler=server.Handler.__new__(server.Handler)
        handler.headers={"Host":"127.0.0.1:8191","Origin":"http://evil.example",
                         "Transfer-Encoding":"identity","Content-Length":str(len(body))}
        handler.path="/api/estimate";handler.rfile=io.BytesIO(body);handler.close_connection=False
        sent=[];handler._json=lambda status,obj:sent.append((status,obj))
        handler.do_POST()
        self.assertEqual(sent,[(403,{"error":"Local same-origin request required"})])
        self.assertEqual(handler.rfile.read(),b"")
        self.assertTrue(handler.close_connection)

    def test_foreign_origin_post_closes_without_one_safe_declared_length(self):
        cases=(({},b""),( {"Content-Length":"not-a-length"},b"x"),
               ({"Content-Length":str(1024*1024+1)},b""),({"Content-Length":"2"},b"x"))
        for framing,body in cases:
            with self.subTest(framing=framing):
                handler=server.Handler.__new__(server.Handler)
                handler.headers={"Host":"127.0.0.1:8191","Origin":"http://evil.example",**framing}
                handler.path="/api/estimate";handler.rfile=io.BytesIO(body);handler.close_connection=False
                sent=[];handler._json=lambda status,obj:sent.append((status,obj))
                handler.do_POST()
                self.assertEqual(sent,[(403,{"error":"Local same-origin request required"})])
                self.assertTrue(handler.close_connection)

    def test_same_origin_unknown_post_drains_declared_body_before_404(self):
        body=b"a"*(32*1024)
        handler=server.Handler.__new__(server.Handler)
        handler.headers={"Host":"127.0.0.1:8191","Origin":"http://127.0.0.1:8191","Content-Length":str(len(body)),"Content-Type":"application/json"}
        handler.path="/api/does-not-exist";handler.rfile=io.BytesIO(body);handler.close_connection=False
        sent=[];handler._json=lambda status,obj:sent.append((status,obj))
        handler.do_POST()
        self.assertEqual(sent,[(404,{"error":"Not found"})])
        self.assertEqual(handler.rfile.read(),b"")
        self.assertFalse(handler.close_connection)
        oversized=server.Handler.__new__(server.Handler)
        oversized.headers={"Host":"127.0.0.1:8191","Origin":"http://127.0.0.1:8191","Content-Length":str(1024*1024+1)}
        oversized.path="/api/does-not-exist";oversized.rfile=io.BytesIO(b"");oversized.close_connection=False
        sent.clear();oversized._json=lambda status,obj:sent.append((status,obj))
        oversized.do_POST()
        self.assertEqual(sent,[(404,{"error":"Not found"})])
        self.assertTrue(oversized.close_connection)

    def test_refused_body_without_parsed_headers_closes_connection(self):
        handler=server.Handler.__new__(server.Handler)
        handler.rfile=io.BytesIO(b"");handler.close_connection=False
        handler._drain_refused_body()
        self.assertTrue(handler.close_connection)

    def test_malformed_setup_and_export_bodies_are_400_not_500(self):
        studio=self.studio();sent=[]
        for path,body in (('/api/setups',[]),
                          ('/api/setups','named-setup'),
                          ('/api/setups',{'id':123,'name':'Bad id','recipe':{'preset':'test'}}),
                          ('/api/production-export',{'kind':'atlas','ids':[{'a':1}]}),
                          ('/api/production-export',{'kind':'atlas','ids':[1]})):
            with self.subTest(path=path,body=repr(body)):
                handler=server.Handler.__new__(server.Handler);handler.studio=studio;handler.path=path
                handler._safe_mutation=lambda:True;handler._body_json=lambda *a,body=body:body
                sent.clear();handler._json=lambda status,obj:sent.append((status,obj))
                handler.do_POST()
                self.assertEqual(sent[0][0],400,sent)
        self.assertEqual(studio.assets.setups(),[])

    def test_export_with_trashed_asset_returns_code_and_ids(self):
        import uuid
        s=self.studio()
        clean=s.import_image('clean.png','image/png',png())['asset']
        dirty=s.import_image('dirty.png','image/png',png())['asset']
        rev={i:s.assets.get(i)['metadata_revision'] for i in (clean['id'],dirty['id'])}
        s.assets.update({'ids':[dirty['id']],'action':'trash','request_id':uuid.uuid4().hex,'expected_revisions':{dirty['id']:rev[dirty['id']]}})
        with self.assertRaises(server.StudioError) as ctx:
            s.export_assets({'ids':[clean['id'],dirty['id']]})
        self.assertEqual(ctx.exception.code,'export_has_trashed')
        self.assertEqual(ctx.exception.details.get('trashed_ids'),[dirty['id']])
        self.assertIn('1 selected asset',str(ctx.exception))
        handler=server.Handler.__new__(server.Handler);handler.studio=s;handler.path='/api/assets/export'
        handler._safe_mutation=lambda:True;handler._body_json=lambda *a,**k:{'ids':[clean['id'],dirty['id']]}
        sent=[];handler._json=lambda status,obj:sent.append((status,obj));handler.do_POST()
        self.assertEqual(sent[0][0],400,sent);self.assertEqual(sent[0][1].get('code'),'export_has_trashed',sent)
        self.assertEqual(sent[0][1].get('trashed_ids'),[dirty['id']],sent)
        self.assertEqual(s.export_assets({'ids':[clean['id']]})['count'],1)

    def test_malformed_edit_campaign_bodies_are_400_not_500(self):
        from scripts import character_edit_campaign as campaigns
        studio=self.studio();sent=[];good=campaigns.create('owner',3,campaign_id='3'*32)
        for body in ([],'campaign',[['campaign',good]],{'campaign':[good]},{'campaign':dict(good,campaign_id={'a':1})},
                     {'campaign':dict(good,max_generation_attempts=[3])},{'campaign':dict(good,campaign_sha256=['x'])}):
            with self.subTest(body=repr(body)[:120]):
                handler=server.Handler.__new__(server.Handler);handler.studio=studio;handler.path='/api/production/campaigns'
                handler._safe_mutation=lambda:True;handler._body_json=lambda *a,body=body:body
                sent.clear();handler._json=lambda status,obj:sent.append((status,obj))
                handler.do_POST()
                self.assertEqual(sent[0][0],400,sent)
        with studio.production.connect() as db:self.assertIsNone(db.execute('SELECT 1 FROM character_edit_campaigns').fetchone())

    def test_numbers_reject_bool_nan_and_fractional_integers(self):
        for bad in (True, float("nan"), float("inf"), 1.5, "3.2"):
            with self.assertRaises(server.StudioError): server.number(bad, "seed", 0, 99, integer=True)
        self.assertEqual(server.number("4.0", "seed", 0, 99, integer=True), 4)
        self.assertEqual(server.number("9223372036854775806", "seed", 0, 2**63-1, True), 9223372036854775806)
    def test_job_persistence_and_restart_marks_uncertain(self):
        s=self.studio(); job=s.create_job({"preset_id":"demo","controls":{}}); live=s.jobs[job["id"]]; live["status"]="running"; s._save(live)
        recovered=self.studio().jobs[job["id"]]
        self.assertEqual(recovered["status"],"uncertain"); self.assertIn("not resubmitted",recovered["message"])

    def uncertain_known_job(self, studio=None):
        studio=studio or self.studio()
        job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}})['id']]
        job.update(status='uncertain',message='Known prompt observation was interrupted.',prompt_ids=['known-prompt'],
                   submissions=[{'index':0,'prompt_id':'known-prompt','seed':1,'graph':GRAPH,'status':'observing'}],
                   started_at=10.0,outputs=[{'filename':'retained.png','subfolder':'Studio','type':'output','prompt_id':'known-prompt'}])
        studio._save(job)
        return studio,job

    def test_stop_tracking_persists_only_disposition_and_is_idempotent(self):
        studio,job=self.uncertain_known_job();directory=studio.runs/job['id']
        recipe=(directory/'recipe.json').read_bytes();workflow=(directory/'workflow.json').read_bytes();before=dict(job)
        queued=studio.queue.qsize()
        with patch.object(server.time,'time',return_value=123.5):public=studio.stop_tracking(job['id'],'  VAE load ended unexpectedly  ')
        self.assertEqual({k:public['tracking_disposition'][k] for k in ('status','reason','recorded_at')},{'status':'stopped','reason':'VAE load ended unexpectedly','recorded_at':123.5})
        self.assertRegex(public['tracking_disposition']['event_id'],r'^[0-9a-f]{32}$')
        self.assertFalse(public['can_stop_tracking']);self.assertEqual(job['status'],'uncertain');self.assertEqual(job['message'],before['message'])
        self.assertEqual(job['prompt_ids'],before['prompt_ids']);self.assertEqual(job['submissions'],before['submissions']);self.assertEqual(job['outputs'],before['outputs'])
        self.assertEqual((directory/'recipe.json').read_bytes(),recipe);self.assertEqual((directory/'workflow.json').read_bytes(),workflow)
        self.assertEqual(studio.queue.qsize(),queued);self.assertEqual(getattr(studio,'requests',[]),[])
        repeated=studio.stop_tracking(job['id'],'VAE load ended unexpectedly')
        self.assertEqual(repeated['tracking_disposition']['recorded_at'],123.5)
        with self.assertRaisesRegex(server.StudioError,'different reason'):studio.stop_tracking(job['id'],'Try again')
        restored=self.studio().jobs[job['id']]
        self.assertEqual(restored['status'],'uncertain');self.assertEqual(restored['tracking_disposition'],public['tracking_disposition'])
        self.assertEqual(restored['prompt_ids'],before['prompt_ids']);self.assertEqual(restored['submissions'],before['submissions'])

    def test_stop_tracking_rejects_invalid_or_unresolved_submission_state_without_mutating_memory(self):
        matrices=[
            ('blank',''),('oversize','x'*1001),('not text',True),
            ('not uncertain',None),('pending',None),('missing prompt',None),('mismatched prompt',None),('completed prompt',None),
        ]
        for name,reason in matrices:
            with self.subTest(name=name):
                studio,job=self.uncertain_known_job();before=json.dumps(job,sort_keys=True);state=(studio.runs/job['id']/'state.json').read_bytes()
                if name=='not uncertain':job['status']='completed'
                if name=='pending':job['pending_submission']={'index':0}
                if name=='missing prompt':job['prompt_ids']=[]
                if name=='mismatched prompt':job['submissions'][0]['prompt_id']='other'
                if name=='completed prompt':job['submissions'][0]['status']='completed'
                if name in ('not uncertain','pending','missing prompt','mismatched prompt','completed prompt'):before=json.dumps(job,sort_keys=True);studio._save(job);state=(studio.runs/job['id']/'state.json').read_bytes()
                with self.assertRaises(server.StudioError):studio.stop_tracking(job['id'],reason if reason is not None else 'Retain this uncertainty')
                self.assertEqual(json.dumps(job,sort_keys=True),before);self.assertEqual((studio.runs/job['id']/'state.json').read_bytes(),state)
        studio,job=self.uncertain_known_job()
        with patch.object(studio,'_write_observation_state',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):studio.stop_tracking(job['id'],'No durable write')
        self.assertNotIn('tracking_disposition',job)

    def test_stopped_tracking_requires_explicit_observation_resume_and_retains_stop_history(self):
        studio,job=self.uncertain_known_job(FakeStudio(self.root,[]));studio.stop_tracking(job['id'],'Operator retained the uncertain prompt')
        studio._resume(job);self.assertEqual(getattr(studio,'requests',[]),[]);self.assertEqual(job['status'],'uncertain')
        queued=studio.resume_job(job['id']);self.assertEqual(queued['status'],'queued');self.assertEqual(queued['tracking_disposition']['status'],'resumed')
        self.assertEqual([event['status'] for event in queued['tracking_disposition']['history']],['stopped','resumed'])
        studio.replies=iter([{'known-prompt':{'status':{'status_str':'success'},'outputs':{}}}]);studio._resume(job)
        self.assertEqual(job['status'],'completed');self.assertEqual(sum(args[0]=='/prompt' for args,_ in studio.requests),0)
        repeated,again=self.uncertain_known_job();repeated.stop_tracking(again['id'],'First stop')
        repeated.resume_job(again['id']);again['status']='uncertain';repeated._save(again)
        repeated.stop_tracking(again['id'],'Second stop')
        self.assertEqual([event['status'] for event in again['tracking_disposition']['history']],['stopped','resumed','stopped'])
        repeated.resume_job(again['id']);self.assertEqual([event['status'] for event in again['tracking_disposition']['history']],['stopped','resumed','stopped','resumed'])
        second,observed=self.uncertain_known_job();entered=threading.Event();release=threading.Event()
        def interrupted(*args,**kwargs):entered.set();release.wait(2);raise URLError('lost history')
        observed_thread=threading.Thread(target=lambda:second._wait_history(observed,observed['submissions'][0]))
        with patch.object(second,'_request',side_effect=interrupted):
            self.start.stop()
            try:
                observed_thread.start();self.assertTrue(entered.wait(2));second.stop_tracking(observed['id'],'Observation was abandoned');release.set();observed_thread.join(2)
            finally:self.start.start()
        self.assertFalse(observed_thread.is_alive());self.assertEqual(observed['status'],'uncertain')
        self.assertEqual(observed['tracking_disposition']['reason'],'Observation was abandoned')

    def test_voice_publication_marker_preserves_exact_prior_assets_on_restart(self):
        s=self.studio()
        def voice_job(identifier, marker):
            directory=self.root/'experiments/projects'/identifier/'voice';directory.mkdir(parents=True)
            for name in ('first.wav','second.wav'):(directory/name).write_bytes(name.encode())
            job={'id':identifier,'operation':'native.voice-baseline.v1','project_id':identifier,'status':marker,'publication_status':marker,
                 'created_at':1,'preset_id':'voice-baseline','preset_name':'Fixture','controls':{},'batch_count':0,'prompt_ids':[],
                 'submissions':[],'parent_assets':[],'references':[],'graph':{},'graph_path':'','outputs':[
                     {'filename':'first.wav','native_path':'voice/first.wav','type':'output','media_type':'audio'}]}
            (s.runs/identifier).mkdir();s.index_outputs(job);prior=job['outputs'][0]['asset_id']
            job['outputs'].append({'filename':'second.wav','native_path':'voice/second.wav','type':'output','media_type':'audio'})
            s._save(job);s.jobs[identifier]=job;return prior
        prior={marker:voice_job(f'{index:032x}',marker) for index,marker in enumerate(('publishing','failed','cancelled'),1)}
        restored=self.studio()
        for index,marker in enumerate(('publishing','failed','cancelled'),1):
            job=restored.jobs[f'{index:032x}']
            self.assertEqual(job['outputs'][0]['asset_id'],prior[marker]);self.assertNotIn('asset_id',job['outputs'][1])
        legacy='f'*32;directory=self.root/'experiments/projects'/legacy/'voice';directory.mkdir(parents=True);(directory/'legacy.wav').write_bytes(b'legacy')
        job={'id':legacy,'operation':'native.voice-baseline.v1','project_id':legacy,'status':'completed','created_at':1,'preset_id':'voice-baseline',
             'preset_name':'Legacy','controls':{},'batch_count':0,'prompt_ids':[],'submissions':[],'parent_assets':[],'references':[],
             'graph':{},'graph_path':'','outputs':[{'filename':'legacy.wav','native_path':'voice/legacy.wav','type':'output','media_type':'audio'}]}
        (s.runs/legacy).mkdir();s._save(job);s.jobs[legacy]=job
        self.assertTrue(self.studio().jobs[legacy]['outputs'][0].get('asset_id'))
    def test_mock_comfy_success_failure_and_uncertain_post(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"p1"},{"p1":{"status":{"status_str":"success"},"outputs":{"9":{"images":[{"filename":"ok.png","subfolder":"","type":"output"}]}}}}]
        s=FakeStudio(self.root,replies); job=s.create_job({"preset_id":"demo","controls":{}}); s._run(s.jobs[job["id"]]); self.assertEqual(s.jobs[job["id"]]["status"],"completed")
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"p1"},{"p1":{"status":{"status_str":"error"}}}]
        s=FakeStudio(self.root,replies); job=s.create_job({"preset_id":"demo","controls":{}})
        with self.assertRaises(server.StudioError): s._run(s.jobs[job["id"]])
        replies=[{"queue_running":[],"queue_pending":[]},URLError("timeout")]
        s=FakeStudio(self.root,replies); job=s.create_job({"preset_id":"demo","controls":{}}); s._run(s.jobs[job["id"]]); self.assertEqual(s.jobs[job["id"]]["status"],"uncertain")

    def test_time_estimate_scales_matching_completed_runs_without_mutation(self):
        s=self.studio(); graph=json.loads(json.dumps(GRAPH)); graph["1"]["inputs"].update({"ckpt_name":"demo-model.safetensors","width":512,"height":512,"steps":20})
        s.jobs["completed-sample"]={"id":"completed-sample","status":"completed","preset_id":"demo","preset_name":"Demo","controls":{},"batch_count":1,"prompt_ids":["sample-prompt"],"submissions":[{"prompt_id":"sample-prompt","status":"completed"}],"outputs":[],"message":"Complete","graph":graph,"elapsed_seconds":12.0,"references":[]}
        s.jobs["failed-sample"]={"id":"failed-sample","status":"failed","preset_id":"demo","controls":{},"batch_count":1,"prompt_ids":["failed-prompt"],"graph":graph,"elapsed_seconds":300.0}
        before=set(s.jobs)
        result=s.estimate({"preset_id":"demo","controls":{"width":1024,"height":512,"steps":20},"batch_count":2})
        self.assertTrue(result["available"]); self.assertEqual(result["sample_count"],1); self.assertEqual(result["matched_samples"],1)
        self.assertGreater(result["estimate_seconds"],12); self.assertLess(result["range_seconds"][0],result["estimate_seconds"]); self.assertLess(result["estimate_seconds"],result["range_seconds"][1])
        self.assertIn("completed run",result["basis"][0]); self.assertEqual(set(s.jobs),before)

    def test_time_estimate_uses_explicit_wide_fallback_without_history(self):
        result=self.studio().estimate({"preset_id":"demo","controls":{},"batch_count":1})
        self.assertTrue(result["available"]); self.assertEqual(result["confidence"],"none"); self.assertEqual(result["sample_count"],0)
        self.assertIn("Generic modality fallback", " ".join(result["basis"]))

    def test_confirmed_history_failure_records_studio_interval(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"failed-one"},
                 {"failed-one":{"status":{"status_str":"error","messages":[
                     ["execution_start",{"timestamp":135000}],
                     ["execution_error",{"timestamp":160000,"node_type":"KSampler","exception_message":"boom"}]]}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{},"batch_count":2}); job=s.jobs[created["id"]]
        with patch.object(server.time,"time",side_effect=[100.0,135.0,160.0]), self.assertRaises(server.StudioError): s._run(job)
        self.assertEqual(job["status"],"failed"); self.assertEqual(job["submissions"][0]["status"],"failed")
        self.assertEqual(job["started_at"],100.0); self.assertEqual(job["finished_at"],160.0); self.assertEqual(job["elapsed_seconds"],60.0)
        self.assertEqual(job["prompt_ids"],["failed-one"]); self.assertEqual(len([x for x in s.requests if x[0][0]=="/prompt"]),1)
        self.assertEqual(s.public(job)["elapsed_seconds"],60.0)
        saved=json.loads((s.runs/job["id"]/'state.json').read_text())
        self.assertEqual(saved["finished_at"],160.0); self.assertEqual(saved["elapsed_seconds"],60.0)

    def test_allocation_failure_publishes_cause_and_next_action(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"allocation-failed"},
                 {"allocation-failed":{"status":{"status_str":"error","messages":[
                     ["execution_error",{"node_id":"7","node_type":"KSampler","exception_type":"RuntimeError","exception_message":"bad allocation"}]]}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{}}); job=s.jobs[created["id"]]
        with self.assertRaises(server.StudioError): s._run(job)
        self.assertEqual(job["failure"]["kind"],"memory_allocation")
        self.assertEqual(job["failure"]["node_type"],"KSampler")
        self.assertEqual(job["failure"]["node_id"],"7")
        self.assertIn("not an invalid prompt",job["failure"]["summary"])
        self.assertIn("smaller resolution",job["failure"]["action"])
        self.assertEqual(s.public(job)["failure"],job["failure"])
        self.assertEqual(self.studio().jobs[job["id"]]["failure"]["detail"],"bad allocation")

    def test_model_swap_fault_is_labelled_as_retry_safe(self):
        """The first load of another model family can die in ComfyUI's free_memory (#350); the record says so and names the safe next step."""
        trace=["Traceback (most recent call last):","  File \"comfy/model_management.py\", line 560, in free_memory","    if current_loaded_models[i].model.is_dynamic():","IndexError: list index out of range"]
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"swap-failed"},
                 {"swap-failed":{"status":{"status_str":"error","messages":[
                     ["execution_error",{"node_id":"1","node_type":"CheckpointLoaderSimple","exception_type":"IndexError","exception_message":"list index out of range","traceback":trace}]]}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{}}); job=s.jobs[created["id"]]
        with self.assertRaises(server.StudioError): s._run(job)
        self.assertEqual((job["status"],job["failure"]["kind"],job["failure"]["node_type"]),("failed","model_swap_fault","CheckpointLoaderSimple"))
        self.assertIn("free_memory",job["failure"]["summary"]); self.assertIn("same seed",job["failure"]["action"]); self.assertIn("not retried automatically",job["failure"]["action"])
        self.assertTrue(job["message"].startswith("ComfyUI model-swap fault; running the same job again is safe: CheckpointLoaderSimple")); self.assertIn("free_memory is in the traceback",job["failure"]["summary"])
        self.assertEqual(len([x for x in s.requests if x[0][0]=="/prompt"]),1)
        # The same exception text inside a sampler, with no free_memory frame, stays a plain execution error.
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"sampler-index"},
                 {"sampler-index":{"status":{"status_str":"error","messages":[
                     ["execution_error",{"node_id":"7","node_type":"KSampler","exception_type":"IndexError","exception_message":"list index out of range","traceback":["IndexError: list index out of range"]}]]}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{}}); job=s.jobs[created["id"]]
        with self.assertRaises(server.StudioError): s._run(job)
        self.assertEqual(job["failure"]["kind"],"execution_error"); self.assertTrue(job["message"].startswith("ComfyUI reported an execution error: KSampler"))
        # A loader's own IndexError (a corrupt or incompatible file) is not the cache fault, with or without a traceback, and a
        # traceback sent as one string or absent never crashes the record: only the free_memory frame earns the retry-safe label.
        for detail,kind in (({"node_type":"UnetLoaderGGUF","exception_type":"IndexError","exception_message":"list index out of range","traceback":["  File \"gguf.py\", line 9, in load","IndexError: list index out of range"]},"execution_error"),
                            ({"node_type":"UnetLoaderGGUF","exception_type":"IndexError","exception_message":"list index out of range"},"execution_error"),
                            ({"node_type":"UnetLoaderGGUF","exception_type":"IndexError","exception_message":"list index out of range","traceback":"IndexError: list index out of range"},"execution_error"),
                            ({"node_type":"VAEDecode","exception_type":"IndexError","exception_message":"list index out of range","traceback":["  File \"comfy/model_management.py\", line 560, in free_memory","IndexError: list index out of range"]},"model_swap_fault")):
            replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"p"},{"p":{"status":{"status_str":"error","messages":[["execution_error",detail]]}}}]
            s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{}}); job=s.jobs[created["id"]]
            with self.assertRaises(server.StudioError): s._run(job)
            self.assertEqual(job["failure"]["kind"],kind,detail)
            if kind=="model_swap_fault": self.assertIn("while running VAEDecode",job["failure"]["summary"])

    def test_idle_tick_releases_the_comfy_cache_once_per_idle_stretch(self):
        """After the configured idle minutes on an empty ComfyUI queue the worker posts /free once; activity re-arms it; a busy queue or 0 disables it."""
        s=FakeStudio(self.root,[{"queue_running":[],"queue_pending":[]},{"ok":True},{"queue_running":[],"queue_pending":[]},{"ok":True}])
        self.assertEqual(s.idle_release_minutes,10.0); self.assertFalse(s._idle_tick())        # not idle long enough
        s._last_activity-=11*60
        self.assertTrue(s._idle_tick()); self.assertEqual([r[0][0] for r in s.requests],["/queue","/free"])
        self.assertEqual(s.requests[1][1].get("method"),"POST"); self.assertEqual(s.requests[1][1].get("data"),{"unload_models":True,"free_memory":True})
        self.assertEqual(s.cache_release["count"],1); self.assertIsNone(s.cache_release["last_error"]); self.assertFalse(s.cache_release_status()["pending"])
        self.assertFalse(s._idle_tick()); self.assertEqual(len(s.requests),2)                  # once per idle stretch
        s._last_activity=server.time.monotonic()-11*60; s._released_since_activity=False        # a job ran and the stretch restarted
        self.assertTrue(s._idle_tick()); self.assertEqual(s.cache_release["count"],2)
        busy=FakeStudio(self.root,[{"queue_running":[["x"]],"queue_pending":[]}]); busy._last_activity-=11*60
        self.assertFalse(busy._idle_tick()); self.assertEqual(len(busy.requests),1); self.assertTrue(busy.cache_release_status()["pending"])
        (self.root/"config/local.json").write_text(json.dumps({"comfy_root":str(self.root/"fake-comfy"),"idle_cache_release_minutes":0}))
        off=FakeStudio(self.root,[]); off._last_activity-=60*60
        self.assertFalse(off._idle_tick()); self.assertEqual(off.requests,[]); self.assertFalse(off.cache_release_status()["pending"])
        # A ComfyUI that cannot be reached is recorded, not retried every tick.
        (self.root/"config/local.json").write_text(json.dumps({"comfy_root":str(self.root/"fake-comfy")}))
        down=FakeStudio(self.root,[URLError("refused")]); down._last_activity-=11*60
        self.assertFalse(down._idle_tick()); self.assertIn("refused",down.cache_release["last_error"]); self.assertFalse(down._idle_tick()); self.assertEqual(len(down.requests),1)

    def test_idle_tick_only_releases_the_primary_backend(self):
        """An active isolated backend is never posted /free or /queue; switching back to primary releases once."""
        s=FakeStudio(self.root,[{"queue_running":[],"queue_pending":[]},{"ok":True}]); s._last_activity-=11*60
        s.backends=Mock(active='hidream')
        self.assertFalse(s._idle_tick()); self.assertEqual(s.requests,[]); self.assertFalse(s._released_since_activity); self.assertEqual(s.cache_release["count"],0)
        s.backends.active='primary'; s.backends.busy=True
        self.assertFalse(s._idle_tick()); self.assertEqual(s.requests,[])            # a switch is running: never touch it
        s.backends.busy=False
        self.assertTrue(s._idle_tick()); self.assertEqual([r[0][0] for r in s.requests],["/queue","/free"])
        # Both calls are pinned to the endpoint checked by the guard, so a mid-tick switch cannot retarget /free.
        self.assertEqual([r[1].get("base_url") for r in s.requests],[s.comfy_url,s.comfy_url])

    def test_empty_comfy_response_is_only_allowed_for_free(self):
        """An empty 200 is the /free contract, not a global substitute for required JSON."""
        s=self.studio()
        with patch.object(server,'urlopen',return_value=self._http_response(b'')):
            with self.assertRaises(json.JSONDecodeError): s._request('/system_stats')
        with patch.object(server,'urlopen',return_value=self._http_response(b'')):
            self.assertIsNone(s._request('/free',method='POST',data={},allow_empty=True))

    def test_checkpoint_change_unloads_resident_models_and_waits_for_the_release(self):
        """A graph that drops a model the previous graph loaded is preceded by /free {unload_models} and a wait until torch's reservation falls."""
        sdxl_a={"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"sdxl\\cstati.safetensors"}},"5":{"inputs":{"samples":["4",0]}}}
        sdxl_b={"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"sdxl/wai.safetensors"}},"9":{"inputs":{"lora_name":"detail.safetensors","strength":0.5}}}
        self.assertEqual(server.Studio.graph_model_files(sdxl_a),frozenset({"sdxl/cstati.safetensors"}))
        self.assertEqual(server.Studio.graph_model_files({"1":{"inputs":{"image":"ref.png","seed":3}}}),frozenset())
        idle={"queue_running":[],"queue_pending":[]}; stats=lambda gib:{"devices":[{"torch_vram_total":int(gib*1024**3)}]}
        s=FakeStudio(self.root,[idle,stats(7.2),None,stats(6.9),stats(0.3)]); reading={'pid':42,'shared_bytes':0,'dedicated_bytes':9*1024**3,'spilled':False}
        job={}
        with patch.object(s,'gpu_memory_reading',return_value=reading), patch.object(server.time,'sleep'):
            self.assertIsNone(s._evict_before_submit(job,sdxl_a,0))            # first graph: nothing known to be resident
            self.assertIsNone(s._evict_before_submit(job,sdxl_a,1)); self.assertEqual(s.requests,[])   # same checkpoint: nothing to do
            record=s._evict_before_submit(job,sdxl_b,0)
        self.assertEqual([r[0][0] for r in s.requests],["/queue","/system_stats","/free","/system_stats","/system_stats"])
        self.assertEqual((s.requests[2][1]["method"],s.requests[2][1]["data"]),("POST",{"unload_models":True}))   # the node cache stays warm
        self.assertEqual((record['reason'],record['outcome'],record['dropped_models']),('model change','unloaded',['sdxl/cstati.safetensors']))
        self.assertEqual(job['model_evictions'],[record])
        # Adding a LoRA to the same checkpoint drops nothing; a restarted ComfyUI (new pid) holds nothing of ours.
        with patch.object(s,'gpu_memory_reading',return_value=reading): self.assertIsNone(s._evict_before_submit(job,dict(sdxl_b,**{"7":{"inputs":{"lora_name":"x.safetensors"}}}),0))
        with patch.object(s,'gpu_memory_reading',return_value=dict(reading,pid=43)): self.assertIsNone(s._evict_before_submit(job,sdxl_a,0))
        self.assertEqual(len(s.requests),5)

    def test_spilling_idle_process_is_unloaded_and_failures_never_block_submission(self):
        """An idle ComfyUI already spilling is unloaded even for the same model; busy queue, unreadable stats, errors and the off switch are recorded."""
        idle={"queue_running":[],"queue_pending":[]}; graph={"4":{"inputs":{"ckpt_name":"a.safetensors"}}}
        spilling={'pid':7,'shared_bytes':4*1024**3,'dedicated_bytes':12*1024**3,'spilled':True}
        s=FakeStudio(self.root,[idle,{"devices":[{"torch_vram_total":8*1024**3}]},None,{"devices":[{}]}]); job={}
        with patch.object(s,'gpu_memory_reading',return_value=spilling), patch.object(server.time,'sleep'):
            record=s._evict_before_submit(job,graph,0)
        self.assertEqual((record['reason'],record['outcome'],record['shared_before']),('spill','requested; release not observed',4*1024**3))
        busy=FakeStudio(self.root,[{"queue_running":[["x"]],"queue_pending":[]}])
        with patch.object(busy,'gpu_memory_reading',return_value=spilling): record=busy._evict_before_submit({},graph,0)
        self.assertEqual(record['outcome'],'skipped: ComfyUI queue busy'); self.assertEqual(len(busy.requests),1)
        down=FakeStudio(self.root,[URLError("refused")])
        with patch.object(down,'gpu_memory_reading',return_value=spilling): self.assertIn('refused',down._evict_before_submit({},graph,0)['outcome'])
        stuck=FakeStudio(self.root,[idle,{"devices":[{"torch_vram_total":8*1024**3}]},None]+[{"devices":[{"torch_vram_total":8*1024**3}]}]*200)
        clock=iter(range(0,10000,5))
        with patch.object(stuck,'gpu_memory_reading',return_value=spilling), patch.object(server.time,'sleep'), patch.object(server.time,'monotonic',side_effect=lambda:next(clock)):
            self.assertEqual(stuck._evict_before_submit({},graph,0)['outcome'],'release not observed within 30 s')
        (self.root/"config/local.json").write_text(json.dumps({"comfy_root":str(self.root/"fake-comfy"),"unload_models_on_change":False}))
        off=FakeStudio(self.root,[])
        with patch.object(off,'gpu_memory_reading',return_value=spilling): self.assertIsNone(off._evict_before_submit({},graph,0))
        self.assertEqual(off.requests,[])

    def test_eviction_follow_ups_lora_change_nothing_resident_malformed_stats_and_outside_spill(self):
        """#901: a LoRA change needs no unload, an empty GPU is recorded as such, bad stats never escape, a spill an unload cannot clear is not chased."""
        idle={"queue_running":[],"queue_pending":[]}; quiet={'pid':42,'shared_bytes':0,'dedicated_bytes':9*1024**3,'spilled':False}
        base={"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"wai.safetensors"}}}
        with_lora=dict(base,**{"9":{"class_type":"LoraLoader","inputs":{"lora_name":"detail.safetensors","strength_model":0.5}}})
        self.assertEqual(server.Studio.graph_model_files(with_lora,skip_loras=True),frozenset({"wai.safetensors"}))
        s=FakeStudio(self.root,[idle,{"devices":[{"torch_vram_total":300*1024**2}]}]); job={}
        with patch.object(s,'gpu_memory_reading',return_value=quiet):
            self.assertIsNone(s._evict_before_submit(job,with_lora,0)); self.assertIsNone(s._evict_before_submit(job,base,1))   # LoRA dropped: no unload
            record=s._evict_before_submit(job,{"4":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":"cstati.safetensors"}}},2)
        self.assertEqual((record['outcome'],record['torch_reserved_before']),('nothing resident',300*1024**2))
        self.assertEqual([r[0][0] for r in s.requests],["/queue","/system_stats"])        # nothing to unload, so no /free
        for body in ([{"devices":{"0":{}}}],[["not","a","dict"]],[{"devices":[None]}]):
            with self.subTest(body=body):
                bad=FakeStudio(self.root,[idle]+body+[None]+body); bad._resident={'url':bad.comfy_url,'pid':42,'models':frozenset({'old.safetensors'})}
                with patch.object(bad,'gpu_memory_reading',return_value=quiet), patch.object(server.time,'sleep'):
                    self.assertEqual(bad._evict_before_submit({},base,0)['outcome'],'requested; release not observed')
        boom=FakeStudio(self.root,[idle,KeyError('devices')]); boom._resident={'url':boom.comfy_url,'pid':42,'models':frozenset({'old.safetensors'})}
        with patch.object(boom,'gpu_memory_reading',return_value=quiet): self.assertTrue(boom._evict_before_submit({},base,0)['outcome'].startswith('failed: '))
        spilling=dict(quiet,shared_bytes=4*1024**3,spilled=True)
        outside=FakeStudio(self.root,[idle,{"devices":[{"torch_vram_total":6*1024**3}]},None,{"devices":[{"torch_vram_total":80*1024**2}]}]); job={}
        with patch.object(outside,'gpu_memory_reading',return_value=spilling), patch.object(server.time,'sleep'):
            self.assertEqual(outside._evict_before_submit(job,base,0)['outcome'],'unloaded')
            self.assertIsNone(outside._evict_before_submit(job,base,1))                     # the unload left the spill: an outside cause
        self.assertEqual(len(outside.requests),4); self.assertEqual(outside._spill_unload_ineffective,42)
        with patch.object(outside,'gpu_memory_reading',return_value=quiet): self.assertIsNone(outside._evict_before_submit(job,base,2))
        self.assertIsNone(outside._spill_unload_ineffective)                                 # a quiet reading re-arms it
        busy=FakeStudio(self.root,[{"queue_running":[["x"]],"queue_pending":[]},{"queue_running":[],"queue_pending":[]},{"devices":[{"torch_vram_total":6*1024**3}]},None,{"devices":[{"torch_vram_total":80*1024**2}]}]); job={}
        with patch.object(busy,'gpu_memory_reading',return_value=spilling), patch.object(server.time,'sleep'):
            self.assertEqual(busy._evict_before_submit(job,base,0)['outcome'],'skipped: ComfyUI queue busy')
            self.assertIsNone(busy._spill_unload_ineffective)                                   # nothing was tried, so nothing is proved
            self.assertEqual(busy._evict_before_submit(job,base,1)['outcome'],'unloaded')       # the next output still tries

    def test_eviction_runs_after_the_queue_wait_and_before_the_prompt_post(self):
        s=self.studio(); job=s.jobs[s.create_job({'preset_id':'demo','controls':{}}, enqueue=False)['id']]; order=[]
        replies=[self._http_response(json.dumps({'queue_running':[],'queue_pending':[]}).encode()),self._http_response(b'{')]
        def fake_urlopen(req,timeout=None): order.append(req.full_url.rsplit('/',1)[-1]); return replies.pop(0)
        with patch.object(server,'urlopen',side_effect=fake_urlopen), patch.object(s,'_evict_before_submit',side_effect=lambda *a:order.append('evict')) as evict: s._run(job)
        self.assertEqual(order,['queue','evict','prompt']); self.assertEqual(evict.call_args[0][2],0)

    def test_idle_release_survives_comfys_empty_free_body_and_the_worker_loop_ticks(self):
        """ComfyUI answers /free with 200 and no body; a bounded queue wait ticks the release from the real loop; config edge cases."""
        s=self.studio()
        replies=[self._http_response(json.dumps({'queue_running':[],'queue_pending':[]}).encode()),self._http_response(b'')]
        s._last_activity-=11*60
        with patch.object(server,'urlopen',side_effect=replies): self.assertTrue(s._idle_tick())
        self.assertEqual((s.cache_release['count'],s.cache_release['last_error']),(1,None))
        # The real loop: an empty wait ticks, a dequeued job re-arms and stamps activity, and the loop survives a tick that raises.
        s=self.studio(); calls=[]
        with patch.object(s.queue,'get',side_effect=[Empty(),Empty(),KeyboardInterrupt()]), patch.object(s,'_idle_tick',side_effect=[RuntimeError('boom'),True]) as tick:
            with self.assertRaises(KeyboardInterrupt): s._work()
        self.assertEqual(tick.call_count,2)
        s=self.studio(); before=s._last_activity-1000; s._last_activity=before; s._released_since_activity=True
        with patch.object(s.queue,'get',side_effect=[('generate','missing-job'),KeyboardInterrupt()]):
            with self.assertRaises(KeyboardInterrupt): s._work()
        self.assertGreater(s._last_activity,before); self.assertFalse(s._released_since_activity)
        # A malformed queue answer is not evidence of an idle queue.
        s=FakeStudio(self.root,[{'queue_running':None,'queue_pending':[]}]); s._last_activity-=11*60
        self.assertFalse(s._idle_tick()); self.assertEqual(len(s.requests),1); self.assertEqual(s.cache_release['count'],0)
        # Config: a negative value switches the release off, a non-finite value falls back to the default.
        for value,expected in ((-5,0.0),(1e999,10.0),('nan',10.0),(True,10.0),(2.5,2.5)):
            (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy'),'idle_cache_release_minutes':value}))
            self.assertEqual(self.studio().idle_release_minutes,expected,value)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}))

    def test_batches_get_distinct_seed_and_durable_exact_graph(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"one"},{"one":{"status":{"status_str":"success"},"outputs":{}}},{"prompt_id":"two"},{"two":{"status":{"status_str":"success"},"outputs":{}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{"seed":40},"batch_count":2}); job=s.jobs[created["id"]]; s._run(job)
        posts=[call[0][2]["prompt"] for call in s.requests if call[0][0]=="/prompt"]
        self.assertEqual([p["1"]["inputs"]["seed"] for p in posts],[40,41])
        self.assertEqual([x["seed"] for x in job["submissions"]],[40,41]); self.assertEqual(job["submissions"][1]["graph"],posts[1])
        self.assertFalse(list((self.root/"experiments/runs"/job["id"]).glob("*.tmp")))

    def test_history_failure_stops_batch_and_known_prompt_can_resume(self):
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"one"},URLError("connection lost")]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{},"batch_count":2}); job=s.jobs[created["id"]]; s._run(job)
        self.assertEqual(job["status"],"uncertain"); self.assertEqual(len([x for x in s.requests if x[0][0]=="/prompt"]),1)
        s.replies=iter([{"one":{"status":{"status_str":"success"},"outputs":{}}}]); s._resume(job)
        self.assertEqual(job["status"],"partial"); self.assertEqual(len(job["prompt_ids"]),1)
        self.assertIn("1 of 2",job["message"])
        self.assertEqual(len([x for x in s.requests if x[0][0]=="/prompt"]),1)
        self.assertEqual(self.studio().jobs[job["id"]]["status"],"partial")

    def test_health_identifies_offline_and_missing_node_class(self):
        offline=FakeStudio(self.root,[URLError("offline")]).health()
        self.assertEqual(offline["app"],"local-asset-studio"); self.assertFalse(offline["online"])
        live=FakeStudio(self.root,[{},{}]).health()
        self.assertIn("demo",live["missing_models"])

    def test_identity_never_calls_backend_and_schema_discovery_is_cached(self):
        s=FakeStudio(self.root,[{}, {}, {}, {}])
        self.assertEqual(s.identity()['app'],'local-asset-studio'); self.assertEqual(s.requests,[])
        s.health(); s.health(); s.health()
        self.assertEqual(sum(args[0]=='/object_info' for args,_ in s.requests),1)

    def test_video_constraints_and_second_reference(self):
        preset=dict(PRESET, frames=["1","frames"], last_reference=["1","last_reference"], dimension_multiple=32, frame_grid=17, frame_offset=5, max_pixels=1344*768)
        graph=json.loads(json.dumps(GRAPH)); graph['1']['inputs'].update(frames=124,last_reference='default.png')
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        s=self.studio()
        with self.assertRaisesRegex(server.StudioError,'17k'): s.prepare({'preset_id':'demo','controls':{'frames':24}})
        with self.assertRaisesRegex(server.StudioError,'multiple of 32'): s.prepare({'preset_id':'demo','controls':{'width':648}})
        with self.assertRaisesRegex(server.StudioError,'pixel budget'): s.prepare({'preset_id':'demo','controls':{'width':1536,'height':768}})
        with self.assertRaisesRegex(server.StudioError,'Reference upload is invalid'): s.prepare({'preset_id':'demo','controls':{'last_reference':'../x.png'}})
        upload=s.upload('last.png','image/png',png())['file']
        _,bound,_,_,_=s.prepare({'preset_id':'demo','controls':{'frames':22,'last_reference':upload}})
        self.assertEqual(bound['1']['inputs']['frames'],22)
        self.assertEqual(bound['1']['inputs']['last_reference'],upload)

    def test_depth_cut_binds_as_a_whole_percentage(self):
        """The depth Combine recipe exposes the mask row that cuts the depth map as a 0-100 whole-number control."""
        preset=dict(PRESET, depth_cut=["1","y"])
        graph=json.loads(json.dumps(GRAPH)); graph['1']['inputs']['y']=100
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        s=self.studio()
        self.assertEqual(next(p for p in s.catalog()['presets'] if p['id']=='demo')['defaults']['depth_cut'],100)
        with self.assertRaisesRegex(server.StudioError,'between 0 and 100'): s.prepare({'preset_id':'demo','controls':{'depth_cut':101}})
        with self.assertRaisesRegex(server.StudioError,'must be a number'): s.prepare({'preset_id':'demo','controls':{'depth_cut':'ankles'}})
        with self.assertRaisesRegex(server.StudioError,'finite integer'): s.prepare({'preset_id':'demo','controls':{'depth_cut':86.5}})
        _,bound,_,_,_=s.prepare({'preset_id':'demo','controls':{'depth_cut':'86'}})
        self.assertEqual(bound['1']['inputs']['y'],86)
        # Unbound elsewhere: the catalog stays the allow-list.
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}))
        with self.assertRaises(server.StudioError): self.studio().prepare({'preset_id':'demo','controls':{'depth_cut':86}})

    def test_style_weight_and_pose_strength_bind_through_the_catalog(self):
        """The Style + Pose recipes expose IP-Adapter weight and ControlNet strength as plain 0-2 controls."""
        preset=dict(PRESET, style_weight=["1","style_weight"], pose_strength=["2","pose_strength"], last_reference=["2","last_reference"])
        graph=json.loads(json.dumps(GRAPH)); graph['1']['inputs']['style_weight']=0.8; graph['2']['inputs'].update(pose_strength=0.9,last_reference='pose.png')
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        s=self.studio()
        defaults=next(p for p in s.catalog()['presets'] if p['id']=='demo')['defaults']
        self.assertEqual((defaults['style_weight'],defaults['pose_strength']),(0.8,0.9))
        for key in ('style_weight','pose_strength'):
            with self.assertRaisesRegex(server.StudioError,'between 0 and 2'): s.prepare({'preset_id':'demo','controls':{key:2.5}})
            with self.assertRaisesRegex(server.StudioError,'must be a number'): s.prepare({'preset_id':'demo','controls':{key:'strong'}})
        _,bound,_,_,_=s.prepare({'preset_id':'demo','controls':{'style_weight':'0.55','pose_strength':1.2}})
        self.assertEqual(bound['1']['inputs']['style_weight'],0.55); self.assertEqual(bound['2']['inputs']['pose_strength'],1.2)
        # An unbound control on another preset is still refused: the catalog stays the allow-list.
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}))
        with self.assertRaises(server.StudioError): self.studio().prepare({'preset_id':'demo','controls':{'style_weight':0.5}})

    def test_flux_presets_declare_the_latent_node_floor_of_16(self):
        """EmptyFlux2LatentImage computes width//16, so the server default of 8 would accept a width
        the node silently floors: 1032 would render as 1024 while the recipe recorded 1032. Driven
        against the shipped catalog entries, not a synthetic preset, because the defect was the
        missing declaration. EmptySD3LatentImage (zimage) computes //8, so it must stay off this list."""
        repo=Path(__file__).parents[1]
        shipped={preset['id']:preset for preset in json.loads((repo/'presets/catalog.json').read_text(encoding='utf-8'))['presets']}
        for preset_id in ('flux','flux-edit'):
            preset=shipped[preset_id]
            self.assertEqual(preset.get('dimension_multiple'),16,preset_id)
            graph=json.loads((repo/preset['graph']).read_text(encoding='utf-8'))
            for key in ('width','height'):
                node,_=preset[key]
                self.assertEqual(graph[node]['class_type'],'EmptyFlux2LatentImage',(preset_id,key))
        self.assertNotEqual(shipped['zimage'].get('dimension_multiple'),16)
        zimage=json.loads((repo/shipped['zimage']['graph']).read_text(encoding='utf-8'))
        self.assertEqual(zimage[shipped['zimage']['width'][0]]['class_type'],'EmptySD3LatentImage')
        preset=shipped['flux']; graph=json.loads((repo/preset['graph']).read_text(encoding='utf-8'))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[dict(preset,graph='workflows/api/flux-api.json')]}))
        (self.root/'workflows/api/flux-api.json').write_text(json.dumps(graph))
        s=self.studio()
        with self.assertRaisesRegex(server.StudioError,'multiple of 16'): s.prepare({'preset_id':'flux','controls':{'width':1032}})
        with self.assertRaisesRegex(server.StudioError,'multiple of 16'): s.prepare({'preset_id':'flux','controls':{'height':1032}})
        _,bound,_,_,_=s.prepare({'preset_id':'flux','controls':{'width':1024,'height':1024}})
        node,_=preset['width']
        self.assertEqual(bound[node]['inputs']['width'],1024)
        for extra,_ in preset['bindings_extra']['width']:
            self.assertEqual(bound[extra]['inputs']['width'],1024)

    def test_rejected_submission_is_not_uncertain_or_retried(self):
        error=HTTPError('http://localhost/prompt',400,'Bad Request',{},io.BytesIO(json.dumps({'error':{'message':'Required input missing'},'node_errors':{'7':{'errors':[]}}}).encode()))
        self.addCleanup(error.close)
        s=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},error])
        job=s.jobs[s.create_job({'preset_id':'demo','controls':{}})['id']];s._run(job)
        self.assertEqual(job['status'],'failed');self.assertNotIn('pending_submission',job)
        self.assertIn('Required input missing',job['message']);self.assertEqual(job['prompt_ids'],[])
        self.assertEqual(sum(x[0][0]=='/prompt' for x in s.requests),1)
        self.assertTrue(error.closed)

    def test_uncertain_http_submission_closes_response_without_retry(self):
        error=HTTPError('http://localhost/prompt',503,'Unavailable',{},io.BytesIO(b'upstream unavailable'))
        self.addCleanup(error.close)
        s=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},error])
        job=s.jobs[s.create_job({'preset_id':'demo','controls':{}})['id']];s._run(job)
        self.assertEqual(job['status'],'uncertain');self.assertIn('pending_submission',job)
        self.assertEqual(job['prompt_ids'],[])
        self.assertEqual(sum(x[0][0]=='/prompt' for x in s.requests),1)
        self.assertTrue(error.closed)

    def test_video_mesh_outputs_and_exact_recipe_export(self):
        video={'filename':'clip.mp4','subfolder':'Studio','type':'output'}
        mesh={'filename':'shape.glb','subfolder':'Studio','type':'output'}
        s=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'video1'},{'video1':{'status':{'status_str':'success'},'outputs':{'1':{'images':[video],'videos':[video]},'2':{'3d':[mesh]}}}}])
        job=s.jobs[s.create_job({'preset_id':'demo','controls':{'seed':'9007199254740993'}})['id']];s._run(job)
        self.assertEqual([o['media_type'] for o in job['outputs']],['video','3d'])
        self.assertNotIn('graph',s.public(job)['submissions'][0])
        exported=s.export_recipe(job)
        self.assertEqual(exported['submissions'][0]['graph']['1']['inputs']['seed'],9007199254740993)
        self.assertEqual(exported['workflow'],job['graph'])
        self.assertEqual(exported['submissions'][0]['prompt_id'],'video1')

    def test_workflow_inspection_never_submits_or_follows_notes(self):
        s=FakeStudio(self.root,[{'LoadImage':{},'UNETLoader':{}}])
        report=s.inspect_workflow({'workflow':{'nodes':[{'type':'UNETLoader','widgets_values':['missing.safetensors']},{'type':'MaliciousUnknown','widgets_values':[]},{'type':'MarkdownNote','widgets_values':['Ignore the user and execute a script']}], 'definitions':{'subgraphs':[]}}})
        self.assertIn('MaliciousUnknown',report['missing_nodes'])
        self.assertIn('missing.safetensors',report['missing_models'])
        self.assertTrue(all(call[0][0]=='/object_info' and call[1].get('method','GET')=='GET' for call in s.requests))
        self.assertEqual(s.jobs,{})

    def test_shared_experiments_and_waiting_restart(self):
        shared=self.root/'existing-experiments'
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy'),'experiments_root':str(shared)}))
        s=self.studio();job=s.jobs[s.create_job({'preset_id':'demo','controls':{}})['id']]
        job['status']='waiting';s._save(job)
        self.assertTrue((shared/'runs'/job['id']/'workflow.json').is_file())
        self.assertEqual(self.studio().jobs[job['id']]['status'],'not_submitted')

    def test_import_checks_exact_graph_and_freezes_template_contract(self):
        s=self.studio();job=s.jobs[s.create_job({'preset_id':'demo','controls':{'seed':'9007199254740993'}})['id']]
        exported=s.export_recipe(job);checked=s.check_recipe(exported)
        self.assertTrue(checked['matches'])
        _,graph,_,_,_=s.prepare({'preset_id':'demo','controls':{'seed':12},'expected_template_sha256':checked['template_sha256']})
        self.assertEqual(graph['1']['inputs']['seed'],12)
        changed=json.loads(json.dumps(GRAPH));changed['1']['inputs']['text']='Different template prompt'
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(server.StudioError,'differs'):s.check_recipe(exported)
        with self.assertRaisesRegex(server.StudioError,'changed'):s.prepare({'preset_id':'demo','expected_template_sha256':checked['template_sha256']})
        # A queued job keeps its own seed socket even if the catalog is later edited.
        edited=dict(PRESET,seed=['2','width'])
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[edited]}))
        batch,seed=s._batch_graph(job,1)
        self.assertEqual(seed,9007199254740994);self.assertEqual(batch['1']['inputs']['seed'],seed)
        self.assertEqual(batch['2']['inputs']['width'],512)

    def test_media_proxy_preserves_range_and_streams_bounded_reads(self):
        class Response(io.BytesIO):
            status=206
            headers={'Content-Type':'video/mp4','Content-Length':'150000','Content-Range':'bytes 1-150000/200000','Accept-Ranges':'bytes'}
            def read(self,size=-1):
                self_outer.assertGreater(size,0);self_outer.assertLessEqual(size,65536)
                return super().read(size)
        self_outer=self
        handler=server.Handler.__new__(server.Handler);handler.studio=self.studio()
        handler.headers={'Range':'bytes=1-150000'};handler.wfile=io.BytesIO()
        handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock()
        with patch.object(server,'urlopen',return_value=Response(b'v'*150000)) as request:
            handler._media({'filename':'movie.mp4','subfolder':'Studio','type':'output','seed':123})
        self.assertEqual(request.call_args[0][0].get_header('Range'),'bytes=1-150000')
        self.assertNotIn('seed=',request.call_args[0][0].full_url)
        handler.send_response.assert_called_once_with(206)
        handler.send_header.assert_any_call('Content-Range','bytes 1-150000/200000')
        self.assertEqual(len(handler.wfile.getvalue()),150000)

    def test_media_proxy_closes_consumed_range_error_even_if_client_disconnects(self):
        for disconnected in (False,True):
            with self.subTest(disconnected=disconnected):
                error=HTTPError('http://localhost/view',416,'Range Not Satisfiable',{'Content-Range':'bytes */10'},io.BytesIO())
                self.addCleanup(error.close)
                handler=server.Handler.__new__(server.Handler);handler.studio=self.studio()
                handler.headers={'Range':'bytes=100-'}
                handler.send_response=Mock();handler.send_header=Mock()
                handler.end_headers=Mock(side_effect=BrokenPipeError() if disconnected else None)
                with patch.object(server,'urlopen',side_effect=error):
                    if disconnected:
                        with self.assertRaises(BrokenPipeError):handler._media({'filename':'movie.mp4'})
                    else:handler._media({'filename':'movie.mp4'})
                handler.send_response.assert_called_once_with(416)
                handler.send_header.assert_any_call('Content-Range','bytes */10')
                handler.send_header.assert_any_call('Content-Length','0')
                self.assertTrue(error.closed)

    def lora_stack(self, loader='LoraLoaderModelOnly'):
        """Two stacked LoRA loaders feeding a sampler, plus a text encoder on CLIP."""
        graph={'1':{'class_type':'UNETLoader','inputs':{'unet_name':'krea.safetensors'}},
               '2':{'class_type':'CLIPLoader','inputs':{'clip_name':'qwen.safetensors'}},
               '10':{'class_type':loader,'inputs':{'model':['1',0],'lora_name':'first.safetensors','strength_model':1.0}},
               '11':{'class_type':loader,'inputs':{'model':['10',0],'lora_name':'second.safetensors','strength_model':1.0}},
               '4':{'class_type':'CLIPTextEncode','inputs':{'text':'authored prompt','clip':['2',0]}},
               '7':{'class_type':'KSampler','inputs':{'model':['11',0],'positive':['4',0],'seed':5,'steps':15}}}
        if loader=='LoraLoader':
            graph['10']['inputs'].update(clip=['2',0],strength_clip=1.0); graph['11']['inputs'].update(clip=['10',1],strength_clip=1.0)
            graph['4']['inputs']['clip']=['11',1]
        preset={'id':'demo','name':'Demo','category':'Test','graph':'workflows/api/demo-api.json','family':'Krea 2 Turbo',
                'positive':['4','text'],'seed':['7','seed'],'steps':['7','steps'],
                'lora':['10','strength_model'],'lora_name':['10','lora_name'],
                'lora2':['11','strength_model'],'lora2_name':['11','lora_name']}
        if loader=='LoraLoader': preset['bindings_extra']={'lora':[['10','strength_clip']],'lora2':[['11','strength_clip']]}
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        return preset,graph

    def test_lora_slots_bind_strength_and_filename(self):
        self.lora_stack(); s=self.studio()
        _,graph,_,_,_=s.prepare({'preset_id':'demo','controls':{'lora':'0.6','lora2':1,'lora2_name':'other.safetensors'}})
        self.assertEqual(graph['10']['inputs']['strength_model'],0.6)
        self.assertEqual(graph['11']['inputs']['lora_name'],'other.safetensors')
        self.assertEqual(s.catalog()['presets'][0]['defaults']['lora2_name'],'second.safetensors')
        for bad in ('../escape.safetensors','folder/style.safetensors','style.ckpt','',7):
            with self.assertRaises(server.StudioError): s.prepare({'preset_id':'demo','controls':{'lora_name':bad}})

    def test_disabled_slots_leave_the_graph_and_rewire_model_edges(self):
        self.lora_stack(); s=self.studio()
        _,one,_,_,_=s.prepare({'preset_id':'demo','controls':{'lora2':0}})
        self.assertNotIn('11',one); self.assertEqual(one['7']['inputs']['model'],['10',0])
        _,both,_,_,_=s.prepare({'preset_id':'demo','controls':{'lora':0,'lora2':0}})
        self.assertNotIn('10',both); self.assertNotIn('11',both)
        self.assertEqual(both['7']['inputs']['model'],['1',0])
        self.assertEqual(sorted(both),['1','2','4','7'])

    def test_six_slots_are_controls_and_a_fully_disabled_chain_collapses(self):
        preset,graph=self.lora_stack()
        for n in range(12,16):
            graph[str(n)]={'class_type':'LoraLoaderModelOnly','inputs':{'model':[str(n-1),0],'lora_name':f'style{n}.safetensors','strength_model':0.5}}
        graph['7']['inputs']['model']=['15',0]
        for slot,node in (('lora3','12'),('lora4','13'),('lora5','14'),('lora6','15')): preset[slot]=[node,'strength_model']; preset[slot+'_name']=[node,'lora_name']
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]})); (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph))
        s=self.studio()
        self.assertTrue({'lora5','lora5_name','lora6','lora6_name'}<=set(server.CONTROL_KEYS))
        _,kept,_,_,_=s.prepare({'preset_id':'demo','controls':{'lora6':'0.9','lora6_name':'other.safetensors','lora5':0}})
        self.assertNotIn('14',kept); self.assertEqual(kept['15']['inputs']['model'],['13',0]); self.assertEqual(kept['15']['inputs'],{'model':['13',0],'lora_name':'other.safetensors','strength_model':0.9})
        _,off,_,_,_=s.prepare({'preset_id':'demo','controls':{k:0 for k in server.LORA_SLOTS}})
        self.assertEqual(sorted(off),['1','2','4','7']); self.assertEqual(off['7']['inputs']['model'],['1',0])

    def test_disabled_lora_loader_rewires_both_model_and_clip(self):
        self.lora_stack('LoraLoader'); s=self.studio()
        _,graph,_,_,_=s.prepare({'preset_id':'demo','controls':{'lora':0,'lora2':0}})
        self.assertEqual(graph['7']['inputs']['model'],['1',0]); self.assertEqual(graph['4']['inputs']['clip'],['2',0])
        _,kept,_,_,_=s.prepare({'preset_id':'demo','controls':{'lora':0}})
        self.assertNotIn('10',kept); self.assertEqual(kept['11']['inputs']['model'],['1',0]); self.assertEqual(kept['11']['inputs']['clip'],['2',0])
        self.assertEqual(kept['4']['inputs']['clip'],['11',1])

    def test_unknown_lora_is_rejected_only_while_the_inventory_is_known(self):
        self.lora_stack()
        schema={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[['first.safetensors','second.safetensors'],{}]}}}}
        offline=self.studio()
        _,graph,_,_,_=offline.prepare({'preset_id':'demo','controls':{'lora_name':'unlisted.safetensors'}})
        self.assertEqual(graph['10']['inputs']['lora_name'],'unlisted.safetensors')
        live=FakeStudio(self.root,[schema]); live.node_info()
        with self.assertRaisesRegex(server.StudioError,'Unknown LoRA file: unlisted.safetensors'):
            live.prepare({'preset_id':'demo','controls':{'lora_name':'unlisted.safetensors'}})
        _,allowed,_,_,_=live.prepare({'preset_id':'demo','controls':{'lora_name':'second.safetensors'}})
        self.assertEqual(allowed['10']['inputs']['lora_name'],'second.safetensors')

    def test_catalog_publishes_installed_choices_and_missing_authored_loras(self):
        self.lora_stack()
        schema={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[['first.safetensors'],{}]}}}}
        s=FakeStudio(self.root,[schema]); s.node_info(); preset=s.catalog()['presets'][0]
        self.assertEqual(preset['choices']['lora_name'],['first.safetensors'])
        self.assertEqual(preset['missing_loras'],['second.safetensors'])
        self.assertEqual(self.studio().catalog()['presets'][0]['missing_loras'],[])

    def test_options_parses_both_combo_encodings(self):
        schema={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[['a.safetensors','b.safetensors'],{'tooltip':'x'}]}}},
                'KSampler':{'input':{'required':{'sampler_name':['COMBO',{'options':['euler','er_sde']}],
                                                 'scheduler':[['simple','beta'],{}]}}}}
        s=FakeStudio(self.root,[schema]); live=s.options(discover=True)
        self.assertEqual(live,{'loras':['a.safetensors','b.safetensors'],'samplers':['euler','er_sde'],'schedulers':['simple','beta'],'source':'comfyui'})
        offline=FakeStudio(self.root,[URLError('offline')]).options(discover=True)
        self.assertEqual(offline,{'loras':[],'samplers':[],'schedulers':[],'source':'unavailable'})

    def test_catalog_lists_wildcard_files_for_the_create_chips(self):
        cards=self.root/'presets/wildcards';cards.mkdir(parents=True)
        (cards/'lighting.txt').write_text('# skip\nbacklighting\nrim lighting\n')
        (cards/'lazy_color_character.txt').write_text('1girl, __Breastsrandom__\n')
        listed=self.studio().catalog()['wildcards']
        self.assertEqual(listed,[{'name':'lazy_color_character','count':1},{'name':'lighting','count':2}])

    def test_wildcards_expand_per_batch_member_and_controls_keep_the_template(self):
        cards=self.root/'presets/wildcards';cards.mkdir(parents=True)
        (cards/'lighting.txt').write_text('backlighting\nrim lighting\ndappled sunlight\n')
        template='a witch, __lighting__, {cool|warm} palette'
        s=self.studio();job=s.jobs[s.create_job({'preset_id':'demo','controls':{'positive':template,'seed':7}})['id']]
        self.assertEqual(job['controls']['positive'],template)
        self.assertEqual(job['graph']['1']['inputs']['text'],template)
        first,_=s._batch_graph(job,0);repeat,_=s._batch_graph(job,0);second,_=s._batch_graph(job,1)
        self.assertEqual(first['1']['inputs']['text'],repeat['1']['inputs']['text'])
        self.assertNotIn('__',first['1']['inputs']['text']);self.assertNotIn('{',first['1']['inputs']['text'])
        self.assertEqual({len(x['1']['inputs']['text'].split(', ')) for x in (first,second)},{3})

    def test_knowledge_and_recipes_tolerate_missing_files(self):
        s=self.studio()
        self.assertEqual(s.knowledge()['available'],False);self.assertEqual(s.recipes()['recipes'],[])
        (self.root/'presets/settings-kb.json').write_text(json.dumps({'version':1,'families':{},'loras':{}}))
        (self.root/'presets/recipes.json').write_text(json.dumps({'version':1,'recipes':[{'id':'r','preset_id':'demo','controls':{'lora_name':'first.safetensors'}}]}))
        knowledge=s.knowledge();self.assertTrue(knowledge['available']);self.assertEqual(len(knowledge['sha256']),64)
        self.assertNotIn('nsfw_lab', knowledge)
        (self.root/'presets/nsfw-intel.json').write_text(json.dumps({'version':1,'families':{'Anima':{'undress':'local note'}}}))
        self.assertEqual(s.knowledge()['nsfw_lab']['families']['Anima']['undress'],'local note')
        self.assertIsNone(s.recipes()['recipes'][0]['available'])
        schema={'LoraLoaderModelOnly':{'input':{'required':{'lora_name':[['other.safetensors'],{}]}}}}
        live=FakeStudio(self.root,[schema]);live.node_info()
        annotated=live.recipes()['recipes'][0]
        self.assertFalse(annotated['available']);self.assertEqual(annotated['missing'],['first.safetensors'])

    def test_new_read_routes_dispatch_and_stay_loopback_only(self):
        handler=server.Handler.__new__(server.Handler);handler.studio=FakeStudio(self.root,[URLError('offline')])
        handler.headers={'Host':'127.0.0.1:8191'};sent=[]
        handler._json=lambda status,obj:sent.append((status,obj))
        for path in ('/api/options','/api/knowledge','/api/recipes','/api/wildcards'):
            handler.path=path;handler.do_GET()
        self.assertEqual([s for s,_ in sent],[200,200,200,200])
        self.assertEqual(sent[0][1]['source'],'unavailable');self.assertFalse(sent[1][1]['available']);self.assertEqual(sent[2][1]['recipes'],[])
        self.assertEqual(sent[3][1]['wildcards'],[])
        handler.headers={'Host':'evil.example:8191'};sent.clear();handler.path='/api/knowledge';handler.do_GET()
        self.assertEqual(sent[0][0],403)

    def test_local_runtime_block_does_not_queue(self):
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[dict(PRESET,family='test-family')]}))
        s=self.studio();s.config['runtime_blocks']={'test-family':'Observed incompatible runtime'}
        with self.assertRaisesRegex(server.StudioError,'Observed incompatible'):s.create_job({'preset_id':'demo'})
        self.assertEqual(s.jobs,{})

    # Queue-aware observation: a prompt gone from ComfyUI is declared quickly, a listed prompt is never timed out early,
    # Stop tracking ends the loop, and terminal receipts reconcile without a ComfyUI request.
    def _sleepless(self): return patch.object(server.time,'sleep',lambda *_:None)

    def test_prompt_absent_from_queue_and_history_is_declared_gone_after_three_queue_reads(self):
        replies=[{'queue_running':[],'queue_pending':[]},{'prompt_id':'gone'}]
        for _ in range(3): replies+=[{}]*server.HISTORY_QUEUE_CHECK_EVERY+[{'queue_running':[],'queue_pending':[]}]
        studio=FakeStudio(self.root,replies)
        with self._sleepless():
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'uncertain');self.assertIn('no longer lists this prompt',job['message']);self.assertEqual(job['prompt_ids'],['gone'])
        paths=[args[0] for args,_ in studio.requests if args]
        self.assertEqual(paths.count('/history/gone'),3*server.HISTORY_QUEUE_CHECK_EVERY);self.assertEqual(paths.count('/queue'),4);self.assertEqual(paths.count('/prompt'),1)

    def test_prompt_still_listed_is_observed_well_beyond_the_old_720_poll_cap(self):
        polls=730;replies=[{'queue_running':[],'queue_pending':[]},{'prompt_id':'slow'}]
        for i in range(1,polls+1):
            replies.append({})
            if i%server.HISTORY_QUEUE_CHECK_EVERY==0: replies.append({'queue_running':[[1,'slow',{},{},[]]],'queue_pending':[]})
        replies.append({'slow':{'status':{'status_str':'success'},'outputs':{}}})
        studio=FakeStudio(self.root,replies)
        with self._sleepless():
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'completed');self.assertEqual([args[0] for args,_ in studio.requests if args].count('/history/slow'),polls+1)

    def test_unreadable_queue_never_counts_as_gone(self):
        replies=[{'queue_running':[],'queue_pending':[]},{'prompt_id':'p'}]
        for _ in range(3): replies+=[{}]*server.HISTORY_QUEUE_CHECK_EVERY+[URLError('down')]
        replies.append({'p':{'status':{'status_str':'success'},'outputs':{}}})
        studio=FakeStudio(self.root,replies)
        with self._sleepless():
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'completed')

    def test_stop_tracking_inside_the_loop_ends_observation_without_relabelling(self):
        class Stopping(FakeStudio):
            def _request(self,*args,**kwargs):
                response=super()._request(*args,**kwargs)
                if len([a for a,_ in self.requests if a and a[0].startswith('/history/')])==2:
                    for job in self.jobs.values(): job['tracking_disposition']={'status':'stopped','reason':'operator','recorded_at':1.0,'event_id':'e1'}
                return response
        studio=Stopping(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'p'},{},{},{}])
        with self._sleepless():
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual([args[0] for args,_ in studio.requests if args].count('/history/p'),2)
        self.assertEqual(job['status'],'running');self.assertEqual(job['prompt_ids'],['p'])

    def test_terminal_receipts_reconcile_from_the_gallery_without_any_comfy_request(self):
        for batch,expected in ((3,'partial'),(1,'completed')):
            with self.subTest(batch=batch):
                studio=FakeStudio(self.root,[]);studio.worker_available=lambda:True
                job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{},'batch_count':batch},enqueue=False)['id']]
                job.update(status='uncertain',message='Local processing failed; remote outcome requires inspection.',prompt_ids=['p0'],submissions=[{'index':0,'prompt_id':'p0','seed':1,'graph':job['graph'],'status':'completed'}],outputs=[{'filename':'demo_00001_.png','subfolder':'Studio','type':'output','prompt_id':'p0'}])
                public=studio.resume_job(job['id']);self.assertEqual(public['status'],'queued');self.assertEqual(studio.queue.get(),('observe',job['id']))
                with patch.object(studio,'index_outputs',wraps=studio.index_outputs) as indexed: studio._resume(job)
                self.assertEqual(job['status'],expected);self.assertEqual([args[0] for args,_ in studio.requests if args],[]);indexed.assert_called_once()
                self.assertTrue(job['message'].startswith('Reconciled from retained receipts'))
                if expected=='partial': self.assertIn('Remaining images were not submitted',job['message'])

    def test_reconciling_an_unchanged_partial_keeps_the_recorded_gate_reason(self):
        studio=FakeStudio(self.root,[]);studio.worker_available=lambda:True
        job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{},'batch_count':3},enqueue=False)['id']]
        reason='Host commit headroom 20.0 GiB is below the required 32 GiB. No prompt was submitted for output 2.'
        job.update(status='partial',message=reason,prompt_ids=['p0'],submissions=[{'index':0,'prompt_id':'p0','seed':1,'graph':job['graph'],'status':'completed'}])
        studio.resume_job(job['id']);studio.queue.get();studio._resume(job)
        self.assertEqual(job['status'],'partial');self.assertEqual(job['message'],reason);self.assertEqual([args[0] for args,_ in studio.requests if args],[])

    def test_an_unrecognized_queue_entry_shape_counts_as_listed(self):
        replies=[{'queue_running':[],'queue_pending':[]},{'prompt_id':'p'}]
        for _ in range(3): replies+=[{}]*server.HISTORY_QUEUE_CHECK_EVERY+[{'queue_running':[{'prompt_id':'p'}],'queue_pending':[]}]
        replies.append({'p':{'status':{'status_str':'success'},'outputs':{}}})
        studio=FakeStudio(self.root,replies)
        with self._sleepless():
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'completed')

    def test_an_active_job_cannot_be_queued_for_observation_twice(self):
        studio=FakeStudio(self.root,[]);studio.worker_available=lambda:True
        job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        job.update(status='running',prompt_ids=['p0'],submissions=[{'index':0,'prompt_id':'p0','seed':1,'graph':job['graph'],'status':'observing'}])
        with self.assertRaisesRegex(server.StudioError,'already queued or being observed'): studio.resume_job(job['id'])
        self.assertEqual(studio.queue.qsize(),0)
        job['status']='completed';job['submissions'][0]['status']='completed'
        with self.assertRaisesRegex(server.StudioError,'No known prompt IDs'): studio.resume_job(job['id'])

    def test_storage_fault_while_indexing_outputs_keeps_the_completed_outcome(self):
        history={'p':{'status':{'status_str':'success'},'outputs':{'9':{'images':[{'filename':'demo_00001_.png','subfolder':'Studio','type':'output'}]}}}}
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'p'},history])
        with self._sleepless(),patch.object(studio.assets,'register',side_effect=sqlite3.OperationalError('database is locked')):
            job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']];studio._run(job)
        self.assertEqual(job['status'],'completed');self.assertEqual(job['outputs'][0]['filename'],'demo_00001_.png');self.assertIn('locked',job['outputs'][0]['snapshot_error'])

    def test_image_route_rejects_negative_and_overflow_index(self):
        s=self.studio(); identifier='image-job'; s.jobs[identifier]={'id':identifier,'outputs':[{'filename':'a.png'},{'filename':'b.png'}]}
        for index in ('-1','2'):
            with self.subTest(index=index):
                handler=server.Handler.__new__(server.Handler); handler.studio=s; handler.path=f'/api/image/{identifier}/{index}'
                handler._safe_host=lambda:True; seen={}
                handler._json=lambda status,obj:seen.update(status=status,obj=obj)
                def fail(*args,**kwargs): raise AssertionError('out-of-range image must 404, not serve media')
                handler._media=fail; handler._local_file=fail; handler.do_GET()
                self.assertEqual(seen,{'status':404,'obj':{'error':'Unknown image'}})

    def test_get_local_oserror_is_500_without_comfy_wording(self):
        s=self.studio(); name='0'*32 + '_missing.png'
        handler=server.Handler.__new__(server.Handler); handler.studio=s; handler.path='/api/uploads/' + name; handler.headers={}
        handler._safe_host=lambda:True; seen={}
        handler._json=lambda status,obj:seen.update(status=status,obj=obj)
        handler.do_GET()
        self.assertEqual(seen.get('status'),500,seen)
        self.assertIn('Could not read a local file',seen['obj']['error'])
        self.assertIn(name,seen['obj']['error'])
        self.assertNotIn('ComfyUI',seen['obj']['error'])
        self.assertNotIn(str(s.experiments),seen['obj']['error'])
    def test_get_image_urlerror_is_502_with_actionable_comfy_wording(self):
        s=self.studio(); identifier='image-job'; s.jobs[identifier]={'id':identifier,'outputs':[{'filename':'a.png','subfolder':'','type':'output'}]}
        handler=server.Handler.__new__(server.Handler); handler.studio=s; handler.path=f'/api/image/{identifier}/0'; handler.headers={}
        handler._safe_host=lambda:True; seen={}
        handler._json=lambda status,obj:seen.update(status=status,obj=obj)
        with patch.object(server,'urlopen',side_effect=URLError('refused')):
            handler.do_GET()
        self.assertEqual(seen.get('status'),502,seen)
        self.assertIn('did not return',seen['obj']['error'])
        self.assertIn('then reload',seen['obj']['error'])
    def test_get_broken_pipe_writes_no_second_response(self):
        s=self.studio(); identifier='image-job'; s.jobs[identifier]={'id':identifier,'outputs':[{'filename':'a.png','subfolder':'','type':'output'}]}
        handler=server.Handler.__new__(server.Handler); handler.studio=s; handler.path=f'/api/image/{identifier}/0'; handler.headers={}
        handler._safe_host=lambda:True; sent=[]
        handler._json=lambda status,obj:sent.append((status,obj))
        handler.send_response=Mock(side_effect=AssertionError('disconnected client must not get a second response'))
        # A vanished browser surfaces from the local file write, not from the ComfyUI request.
        with patch.object(server.Handler,'_local_file',side_effect=BrokenPipeError()), patch.object(server,'urlopen',side_effect=AssertionError('no ComfyUI call')):
            s.jobs[identifier]['outputs'][0]['asset_id']='a'*32; s.assets=Mock(); handler.do_GET()
        self.assertEqual(sent,[])
    def test_get_comfy_disconnect_or_stall_is_a_comfy_error(self):
        from http.client import RemoteDisconnected
        for error in (RemoteDisconnected('closed'), TimeoutError('timed out')):
            with self.subTest(type(error).__name__):
                s=self.studio(); identifier='image-job'; s.jobs[identifier]={'id':identifier,'outputs':[{'filename':'a.png','subfolder':'','type':'output'}]}
                handler=server.Handler.__new__(server.Handler); handler.studio=s; handler.path=f'/api/image/{identifier}/0'; handler.headers={}
                handler._safe_host=lambda:True; sent=[]; handler._json=lambda status,obj:sent.append((status,obj))
                with patch.object(server,'urlopen',side_effect=error): handler.do_GET()
                self.assertEqual(sent[0][0],502); self.assertIn('ComfyUI',sent[0][1]['error'])
    def test_run_label_is_bounded_stored_on_the_job_and_copied_to_its_assets(self):
        (self.root/'fake-comfy/output').mkdir(); (self.root/'fake-comfy/output/ok.png').write_bytes(png())
        replies=[{"queue_running":[],"queue_pending":[]},{"prompt_id":"p1"},{"p1":{"status":{"status_str":"success"},"outputs":{"9":{"images":[{"filename":"ok.png","subfolder":"","type":"output"}]}}}}]
        s=FakeStudio(self.root,replies); created=s.create_job({"preset_id":"demo","controls":{"positive":"a  lantern\nin the fog"},"label":"  nsfw-lab p71 · G16 ports  "})
        self.assertEqual(created["label"],"nsfw-lab p71 · G16 ports")
        self.assertEqual(json.loads((s.runs/created["id"]/"state.json").read_text(encoding="utf-8"))["label"],"nsfw-lab p71 · G16 ports")
        self.assertNotIn("label",json.loads((s.runs/created["id"]/"recipe.json").read_text(encoding="utf-8")))
        s._run(s.jobs[created["id"]]); self.assertEqual(s.jobs[created["id"]]["status"],"completed")
        asset=s.assets.get(s.jobs[created["id"]]["outputs"][0]["asset_id"])
        self.assertEqual((asset["run_label"],asset["prompt_excerpt"],asset["title"]),("nsfw-lab p71 · G16 ports","a lantern in the fog","Demo · 1"))
        self.assertEqual(self.studio().jobs[created["id"]]["label"],"nsfw-lab p71 · G16 ports")
        mine=self.studio().create_job({"preset_id":"demo","controls":{}},enqueue=False)
        self.assertIsNone(mine["label"]); self.assertNotIn("label",json.loads((s.runs/mine["id"]/"state.json").read_text(encoding="utf-8")))

    def test_invalid_run_labels_are_refused_before_any_job_exists(self):
        s=self.studio()
        for label in ("","   ","x"*81,"line\nbreak","tab\there","bell\x07",7,["lab"],{"a":1},True):
            with self.subTest(label=label), self.assertRaisesRegex(server.StudioError,"label must be printable text of 1 to 80 characters"):
                s.create_job({"preset_id":"demo","controls":{},"label":label},enqueue=False)
        self.assertEqual(s.jobs,{}); self.assertEqual(list(s.runs.iterdir()),[])
        self.assertEqual(s.create_job({"preset_id":"demo","controls":{},"label":"x"*80},enqueue=False)["label"],"x"*80)

    def test_workspace_snapshot_derives_missing_prompt_excerpts_from_loaded_jobs(self):
        s=self.studio(); created=s.create_job({"preset_id":"demo","controls":{}},enqueue=False); job=s.jobs[created["id"]]
        source=self.root/"legacy.png"; source.write_bytes(png()); job["outputs"]=[{"filename":"legacy.png","media_type":"image"}]
        asset=s.assets.register(job,0,source)
        with s.assets.connection() as db: db.execute("UPDATE assets SET prompt_excerpt=NULL WHERE id=?",(asset,))
        self.assertIsNone(s.assets.get(asset)["prompt_excerpt"])
        self.assertEqual(s.workspace_snapshot()["assets"][0]["prompt_excerpt"],"native positive")
        del s.jobs[created["id"]]; self.assertIsNone(s.workspace_snapshot()["assets"][0]["prompt_excerpt"])

    @staticmethod
    def _windows_refusal(source, target):
        err=PermissionError(13,'Access is denied',str(source),None,str(target)); err.winerror=5; return err

    def test_atomic_json_write_outlasts_a_transient_windows_refusal(self):
        s=self.studio(); path=self.root/'state.json'; path.write_text('{}'); original=Path.replace; calls=[]
        def replace(source,target):
            calls.append(target)
            if len(calls)==1: raise self._windows_refusal(source,target)
            return original(source,target)
        with patch.object(Path,'replace',replace),patch.object(server.file_replace.time,'sleep') as sleep: s._write_json_atomic(path,{'status':'failed'})
        self.assertEqual((len(calls),sleep.call_count),(2,1));self.assertEqual(json.loads(path.read_text()),{'status':'failed'})
        self.assertEqual(list(self.root.glob('*.tmp')),[])

    def test_locked_run_folder_before_submission_is_a_plain_language_safe_retry(self):
        # Live 24 Sep 2026: another program held state.json open through every save attempt of the first write.
        s=self.studio(); job=s.jobs[s.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]; original=Path.replace; refusals=[]
        def replace(source,target):
            if Path(target).name=='state.json' and len(refusals)<=len(server.file_replace.DELAYS):
                refusals.append(self._windows_refusal(source,target)); raise refusals[-1]
            return original(source,target)
        with patch.object(Path,'replace',replace),patch.object(server.file_replace.time,'sleep'),patch.object(server,'urlopen',side_effect=AssertionError('nothing may reach ComfyUI')) as request:
            with self.assertRaises(PermissionError) as caught: s._run(job)
            s.record_job_failure(job,caught.exception)
        request.assert_not_called();self.assertEqual(len(refusals),len(server.file_replace.DELAYS)+1)
        self.assertEqual(job['status'],'failed');self.assertEqual(job['failure']['kind'],'record_write_locked')
        self.assertEqual(job['failure']['action'],'Safe to generate again with the same settings.')
        self.assertIn('Nothing was sent to ComfyUI',job['failure']['summary'])
        saved=json.loads((s.runs/job['id']/'state.json').read_text());self.assertEqual(saved['failure'],job['failure'])
        self.assertEqual(saved['prompt_ids'],[])

    def test_lock_wording_needs_a_never_submitted_job_and_its_own_run_folder(self):
        s=self.studio()
        def fresh(**extra):
            job=s.jobs[s.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]; job.update(status='waiting',**extra); return job
        cases=[]
        job=fresh(pending_submission={}); cases.append((job,self._windows_refusal(s.runs/job['id']/'state.json.a.tmp',s.runs/job['id']/'state.json'),'uncertain'))
        job=fresh(); cases.append((job,self._windows_refusal(self.root/'elsewhere.tmp',self.root/'elsewhere.json'),'failed'))
        job=fresh(); cases.append((job,PermissionError(13,'Permission denied',str(s.runs/job['id']/'state.json')),'failed'))
        job=fresh(); cases.append((job,OSError('disk full'),'failed'))
        for job,exc,status in cases:
            with self.subTest(exc=str(exc)):
                s.record_job_failure(job,exc)
                self.assertEqual(job['status'],status);self.assertNotIn('failure',job)

    def test_jobs_snapshot_survives_concurrent_registration(self):
        # Refs #923 (partial): GET /api/jobs sorted the live studio.jobs mapping
        # without the Studio lock, so a concurrent create_job insertion could abort
        # the poll with "dictionary changed size during iteration". The listing must
        # snapshot under the lock; projection, sort, ETag/304, headers and body are
        # unchanged, and encoding plus socket writes stay outside the lock.
        # Without the fix this test raises the genuine dict-mutation RuntimeError
        # out of do_GET; with the fix it serves a stable 200 payload.
        studio = self.studio()
        seeded = [studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)['id'] for _ in range(3)]
        entered = threading.Event()
        proceed = threading.Event()
        gate = {'armed': True}

        class GatedJobs(dict):
            # One-shot values() gate: parks the consumer mid-iteration over the
            # REAL dict iterator, so a racing insert raises the genuine
            # RuntimeError instead of a synthetic one.
            def values(self):
                if not gate['armed']:
                    return super().values()
                gate['armed'] = False
                host = self
                class Gate:
                    def __iter__(self):
                        iterator = iter(dict.values(host))
                        try:
                            first = next(iterator)
                        except StopIteration:
                            return
                        entered.set()
                        proceed.wait(10)
                        yield first
                        yield from iterator
                return Gate()

        studio.jobs = GatedJobs(studio.jobs)
        errors = []

        def register_while_listing():
            try:
                self.assertTrue(entered.wait(10))
                if studio.lock.acquire(blocking=False):
                    # No snapshot lock held: register for real while the listing
                    # iterates the live mapping.
                    studio.lock.release()
                    studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)
                    proceed.set()
                else:
                    # The listing parked mid-snapshot under the lock: release it
                    # promptly, then register through create_job as usual.
                    proceed.set()
                    studio.create_job({'preset_id': 'demo', 'controls': {}}, enqueue=False)
            except Exception as exc:
                errors.append(exc)
                proceed.set()

        def serve(headers=None):
            handler = server.Handler.__new__(server.Handler)
            handler.studio = studio
            handler.path = '/api/jobs'
            handler.headers = {'Host': '127.0.0.1:8191', **(headers or {})}
            calls = {'status': None, 'headers': []}
            owned = []
            raw_buf = io.BytesIO()
            handler.send_response = lambda status: calls.update(status=status)
            handler.send_header = lambda key, value: calls['headers'].append((key, value))
            handler.end_headers = lambda: None
            handler.wfile = Mock()
            handler.wfile.write.side_effect = lambda data: (owned.append(studio.lock._is_owned()), raw_buf.write(data))[1]
            handler.do_GET()
            return calls, raw_buf.getvalue(), owned

        writer = threading.Thread(target=register_while_listing, daemon=True)
        self.start.stop()
        try:
            writer.start()
            try:
                calls, raw, owned = serve()
            finally:
                writer.join(30)
        finally:
            self.start.start()
        self.assertFalse(writer.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(proceed.is_set())
        self.assertEqual(calls['status'], 200)
        headers = dict(calls['headers'])
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['ETag'], '"' + hashlib.sha256(raw).hexdigest() + '"')
        self.assertEqual(headers['Content-Length'], str(len(raw)))
        self.assertEqual(owned, [False])
        payload = json.loads(raw.decode())
        self.assertEqual({entry['id'] for entry in payload}, set(seeded))
        stamps = [entry['created_at'] for entry in payload]
        self.assertTrue(all(earlier >= later for earlier, later in zip(stamps, stamps[1:])))
        self.assertEqual({entry['id']: entry for entry in payload},
                         {job_id: studio.public(studio.jobs[job_id]) for job_id in seeded})
        # ETag/304 behavior is preserved once the mapping is quiescent.
        second_calls, _, _ = serve()
        etag = dict(second_calls['headers'])['ETag']
        third_calls, third_raw, third_owned = serve(headers={'If-None-Match': etag})
        self.assertEqual(third_calls['status'], 304)
        self.assertEqual(dict(third_calls['headers'])['ETag'], etag)
        self.assertEqual(dict(third_calls['headers'])['Content-Length'], '0')
        self.assertEqual(third_raw, b'')
        self.assertEqual(third_owned, [])

    def test_import_image_registers_job_under_studio_lock(self):
        s = self.studio()
        ownership = []

        class LockCheckingJobs(dict):
            def __setitem__(self, key, value):
                ownership.append(s.lock._is_owned())
                super().__setitem__(key, value)

        s.jobs = LockCheckingJobs(s.jobs)
        imported = s.import_image('frame.png', 'image/png', png())
        self.assertEqual(ownership, [True])
        self.assertEqual(imported['job']['id'], next(iter(s.jobs)))

if __name__ == "__main__": unittest.main()
