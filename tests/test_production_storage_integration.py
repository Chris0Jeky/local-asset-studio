"""Full Studio persistence/queue integration; Comfy transport remains inert."""
import copy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT/'app/server.py').is_file(), 'requires complete Studio checkout')
class ProductionStorageIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_production import ProductionTests
        from test_server import FakeStudio
        self.fixtures=ProductionTests();self.fixtures.setUp();self.addCleanup(self.fixtures.tearDown)
        self.root=self.fixtures.root;self.Studio=FakeStudio
    def count_posts(self, studio):return sum(args[0]=='/prompt' for args,_ in studio.requests)

    def test_actual_studio_failed_creation_never_leaves_startable_orphan(self):
        studio=self.Studio(self.root,[]);mkdir=Path.mkdir
        def fail(path,*args,**kwargs):
            if path.parent==studio.production.root:raise OSError('project mkdir refused')
            return mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',fail):
            with self.assertRaisesRegex(OSError,'project mkdir'):studio.production.create(self.fixtures.intent())
        self.assertEqual(studio.production.list(),[]);self.assertEqual(studio.jobs,{})
        self.assertEqual(studio.queue.qsize(),0);self.assertEqual(self.count_posts(studio),0)
        with studio.production.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM budgets').fetchone()[0],0)

    def test_actual_studio_restart_preserves_legacy_plan_and_refuses_start(self):
        studio=self.Studio(self.root,[]);p=studio.production.create(self.fixtures.intent())
        before=studio.production.get(p['id'],full=True);shutil.rmtree(studio.production.root/p['id'])
        restarted=self.Studio(self.root,[]);after=restarted.production.get(p['id'],full=True)
        self.assertEqual(before['plan'],after['plan']);self.assertEqual(before['budget'],after['budget'])
        self.assertIn('storage_issue',after['state'])
        with self.assertRaisesRegex(ValueError,'directory'):restarted.production.start(p['id'])
        self.assertEqual(restarted.jobs,{});self.assertEqual(restarted.queue.qsize(),0);self.assertEqual(self.count_posts(restarted),0)

    def test_uncertain_prompt_survives_storage_failure_and_explicit_restore(self):
        studio=self.Studio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'retained'},URLError('history lost')])
        p=studio.production.create(self.fixtures.intent());studio.production.start(p['id']);studio.production.run(p['id'])
        before=studio.production.get(p['id']);path=studio.production.root/p['id']/'plan.json';saved=path.read_bytes();path.unlink()
        original=next(iter(studio.jobs.values()));prompt_ids=copy.deepcopy(original['prompt_ids']);submissions=copy.deepcopy(original['submissions'])
        restarted=self.Studio(self.root,[])
        with self.assertRaisesRegex(ValueError,'plan.json'):restarted.production.resume(p['id'])
        retained=restarted.jobs[original['id']]
        self.assertEqual(retained['prompt_ids'],prompt_ids);self.assertEqual(retained['submissions'],submissions)
        self.assertEqual(restarted.production.get(p['id'])['budget'],before['budget']);self.assertEqual(self.count_posts(restarted),0)
        # Explicitly restoring the original bytes is not automatic recovery or consent.
        path.write_bytes(saved)
        restarted.replies=iter([{'retained':{'status':{'status_str':'success'},'outputs':{}}},
                               {'queue_running':[],'queue_pending':[]},{'prompt_id':'stage-two'},
                               {'stage-two':{'status':{'status_str':'success'},'outputs':{}}}])
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(self.count_posts(restarted),1);self.assertEqual(len(restarted.jobs),2)
        self.assertEqual(restarted.production.get(p['id'])['state']['status'],'awaiting_review')
        self.assertEqual(restarted.production.get(p['id'])['budget'],before['budget'])

    def test_native_export_actual_planning_rolls_back_failed_plan_write(self):
        from test_server import png
        scripts=self.root/'scripts';scripts.mkdir()
        for name in ('game_asset_media.py','godot_asset_adapter.py'):(scripts/name).write_bytes((ROOT/'scripts'/name).read_bytes())
        studio=self.Studio(self.root,[]);asset=studio.import_image('fixture.png','image/png',png())['asset']
        with patch.object(studio,'_write_json_atomic',side_effect=OSError('plan write refused')):
            with self.assertRaisesRegex(OSError,'plan write'):studio.production.native({'kind':'ora','ids':[asset['id']],'options':{'clip':'fixture'}})
        self.assertEqual(studio.production.list(),[]);self.assertEqual(studio.queue.qsize(),0)
        self.assertEqual(studio.assets.get(asset['id'])['sha256'],asset['sha256']);self.assertEqual(self.count_posts(studio),0)


if __name__=='__main__':unittest.main()
