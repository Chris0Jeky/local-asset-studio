"""Inert CPU fixtures, not generation or model-quality evidence."""
import copy
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
import time
from types import SimpleNamespace
import uuid

sys.path.insert(0, str(Path(__file__).parents[1]/'app'))
from production import Production, fingerprint


class FixtureAssets:
    def __init__(self, root):
        self.root=root;self.root.mkdir(parents=True,exist_ok=True);self.records={};self.paths={}
    def get(self, identifier):return copy.deepcopy(self.records[identifier])
    def file(self, identifier):return self.paths[identifier]


class FixtureStudio:
    def __init__(self, root):
        self.root=Path(root);self.experiments=self.root/'experiments';self.experiments.mkdir(parents=True,exist_ok=True)
        self.assets=FixtureAssets(self.experiments/'workspace/media');self.jobs={};self.lock=threading.RLock()
        self.queue=queue.Queue();self.config={};self.comfy_url='http://127.0.0.1:1';self.network_calls=0
        self.production=Production(self)
    @staticmethod
    def public(job):return copy.deepcopy(job)
    @staticmethod
    def export_recipe(job):return copy.deepcopy(job['fixture_recipe'])
    def _request(self,*args,**kwargs):
        self.network_calls+=1;raise AssertionError('Review must never contact ComfyUI')
    def create_job(self,*args,**kwargs):raise AssertionError('Review must never generate')
    @staticmethod
    def _write_json_atomic(path,value):path.write_text(json.dumps(value))


def seed(studio, count=3, failed_stage=False):
    from PIL import Image, ImageDraw, PngImagePlugin
    identifier=uuid.uuid4().hex;stages=[];attempts={}
    for i in range(count):
        job_id='fixture-job-'+uuid.uuid4().hex;asset_id=uuid.uuid4().hex
        path=studio.assets.root/(asset_id+'.png')
        image=Image.new('RGBA',(192,256),(0,0,0,0));draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((35,35,156,218),radius=16,fill=('#48afb1','#9b7fce','#d49e58')[i%3])
        draw.rectangle((70+i*4,85,118,118),fill='#f0e7cc');draw.line((30,225,162,225),fill='#e7e4df',width=3)
        draw.text((83,156),str(i+1),fill='#10141b')
        meta=PngImagePlugin.PngInfo();meta.add_text('prompt','PRIVATE-SEED-'+str(i));image.save(path,pnginfo=meta);image.close()
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        studio.assets.paths[asset_id]=path
        studio.assets.records[asset_id]={'id':asset_id,'job_id':job_id,'output_index':0,'filename':'original-'+str(i)+'.png',
                                        'sha256':sha,'bytes':path.stat().st_size,'trashed_at':None,'lineage':[]}
        graph={'1':{'class_type':'FixtureOnly','inputs':{'seed':i}}}
        stages.append({'label':chr(65+i),'operation':'comfy.generate.v1','graph':graph,'graph_sha256':fingerprint(graph),
                       'request':{'preset_id':'inert-qa','controls':{'seed':i}}})
        status='failed' if failed_stage and i==count-1 else 'completed'
        job={'id':job_id,'status':status,'prompt_ids':['inert-prompt-'+str(i)],'elapsed_seconds':None if i else 0,
             'message':'Inert fixture, not a model execution','outputs':[{'asset_id':asset_id,'media_type':'image','filename':path.name}],
             'fixture_recipe':{'scope':'inert-fixture-only','graph':graph,'controls':{'seed':i}}}
        studio.jobs[job_id]=job;attempts[str(i)]={'job_id':job_id,'status':status,'prompt_ids':job['prompt_ids']}
    plan={'version':1,'kind':'comparison','name':'Procedural QA — not generated art','stages':stages,'axis':'seed',
          'values':list(range(count)),'recipe':{'preset_id':'inert-qa'},'bundle':{'comfy_url':studio.comfy_url},'max_seconds':60}
    plan['sha256']=fingerprint(plan)
    state={'status':'failed' if failed_stage else 'awaiting_review','attempts':attempts,'artifacts':[],
           'review':{'status':'unreviewed','notes':''}}
    with studio.production.connect() as db:
        db.execute('INSERT INTO budgets VALUES (?,?,?)',(identifier,count,count))
        db.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(identifier,identifier,json.dumps(plan),json.dumps(state),time.time()))
    directory=studio.production.root/identifier;directory.mkdir();(directory/'plan.json').write_text(json.dumps(plan))
    return identifier
