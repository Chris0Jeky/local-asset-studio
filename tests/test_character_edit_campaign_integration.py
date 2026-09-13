"""Shared edit allowances through real HTTP/Production with inert model work."""
import copy
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

import test_character_edit_bridge_integration as fixtures
from scripts import character_edit as edit, character_edit_bridge as bridge
from scripts import character_edit_bridge_plan as contracts, character_edit_campaign as campaigns
from scripts.character_study import read_json, write_json, sha


class CampaignHTTP(unittest.TestCase):
    def setUp(self):
        fixtures.NativeHTTP.setUp(self)
        self.plan = read_json(self.art/'bridge-plan.json')
        self.campaign = campaigns.write(self.art, 'campaign.json', self.plan['budget_owner'], 3,
                                        campaign_id='1'*32)

    def shutdown(self):
        fixtures.NativeHTTP.shutdown(self)

    def register(self):
        return self.client.request('POST', '/api/production/campaigns', {'campaign': self.campaign})

    def revision(self, name, seeds=(11,22), number=1):
        plan = copy.deepcopy(self.plan)
        plan['document']['revision'] = number
        plan['intent']['document_sha256'] = sha(plan['document'])
        plan = edit.make_plan(plan['document'], plan['intent'], plan['catalog'])
        plan_name = name+'-plan.json'; write_json(self.art/plan_name, plan)
        handoff = bridge.prepare(self.art, plan_name, name, list(seeds), repo=self.repo, campaign='campaign.json')
        client = bridge.Bridge(self.art, name+'/handoff.json', self.client)
        return client, plan, handoff

    def payload(self, plan, handoff):
        uploads = []
        for index, ref in enumerate(handoff['references']):
            uploaded = self.studio.upload(str(index)+'.png', 'image/png', (self.art/ref['image']['path']).read_bytes())
            uploads.append({'role': ref['role'], 'file': uploaded['file']})
        return {'character_edit_campaign': copy.deepcopy(self.campaign), 'character_edit_plan': copy.deepcopy(plan),
                'character_edit_handoff': copy.deepcopy(handoff), 'uploads': uploads,
                'name': 'Edit bridge '+handoff['edit_plan_sha256']}

    def test_registration_is_explicit_idempotent_and_cannot_change_an_existing_cap(self):
        first = self.register(); again = self.register()
        self.assertEqual(first['campaign'], self.campaign); self.assertEqual(again['budget'], {'allowance':3,'reserved':0})
        changed = campaigns.create(self.campaign['budget_owner'], 4, campaign_id=self.campaign['campaign_id'])
        with self.assertRaises(ValueError):
            self.client.request('POST','/api/production/campaigns',{'campaign':changed})
        current = self.client.request('GET','/api/production/campaigns/'+self.campaign['campaign_id'])
        self.assertEqual(current['campaign'], self.campaign)
        self.assertEqual([], self.studio.production.list()); self.assertTrue(self.studio.queue.empty())
        self.assertEqual({}, self.studio.jobs); self.assertEqual([], self.inference_calls)

    def test_unregistered_campaign_refuses_stage_before_upload_or_budget_creation(self):
        client, _, _ = self.revision('unknown')
        with self.assertRaises(ValueError): client.stage()
        self.assertEqual([], list((self.studio.experiments/'uploads').glob('*')))
        with self.studio.production.connect() as db:
            self.assertEqual(0, db.execute('SELECT COUNT(*) FROM budgets').fetchone()[0])
        self.assertEqual([],self.studio.production.list()); self.assertTrue(self.studio.queue.empty())

    def test_two_revisions_share_cap_under_concurrent_starts_and_reopen(self):
        self.register()
        one, _, _ = self.revision('one'); two, _, _ = self.revision('two', (33,44), number=2)
        a = one.stage()['project']; b = two.stage()['project']
        self.assertNotEqual(a['id'], b['id']); self.assertEqual(a['root_id'],b['root_id'])
        self.assertEqual(a['root_id'],'character-edit:'+'1'*32)
        self.assertEqual(a['budget'],{'allowance':3,'reserved':0}); self.assertTrue(self.studio.queue.empty())
        barrier = threading.Barrier(3); errors=[]
        def start(identifier):
            try: barrier.wait(); self.studio.production.start(identifier)
            except ValueError as exc: errors.append(str(exc))
        workers=[threading.Thread(target=start,args=(project['id'],)) for project in (a,b)]
        for worker in workers: worker.start()
        barrier.wait()
        for worker in workers: worker.join(timeout=10)
        self.assertTrue(all(not worker.is_alive() for worker in workers)); self.assertEqual(1,len(errors))
        self.assertIn('budget',errors[0].lower()); self.assertEqual(1,self.studio.queue.qsize())
        reopened=fixtures.server.Production(self.studio)
        self.assertEqual(reopened.get(a['id'])['budget'],{'allowance':3,'reserved':2})
        self.assertEqual(reopened.get(b['id'])['budget'],{'allowance':3,'reserved':2})
        self.assertEqual([],self.inference_calls); self.assertEqual({},self.studio.jobs)

    def test_bridge_starts_a_later_revision_with_shared_capacity_already_reserved(self):
        self.register()
        one,_,_=self.revision('first-start',(11,)); two,_,_=self.revision('later-start',(22,),number=2)
        a=one.stage()['project']; b=two.stage()['project']
        one.start()
        self.assertEqual(self.studio.production.get(b['id'])['budget']['reserved'],1)
        two.start()
        self.assertEqual(self.studio.production.get(a['id'])['budget'],{'allowance':3,'reserved':2})
        self.assertEqual(self.studio.queue.qsize(),2); self.assertEqual([],self.inference_calls)
        with self.assertRaises(ValueError):one.start()
        self.assertEqual(self.studio.queue.qsize(),2)

    def test_server_contract_has_no_workspace_reads_and_rejects_changed_bindings(self):
        self.register(); _, plan, handoff = self.revision('pinned')
        payload = self.payload(plan,handoff)
        mutations=(lambda h:h.__setitem__('positive','Unrelated instruction'),
                   lambda h:h.__setitem__('budget_owner','another-owner'),
                   lambda h:h.__setitem__('max_candidates',4),
                   lambda h:h.__setitem__('document_sha256','f'*64),
                   lambda h:h['references'][1]['image'].__setitem__('sha256','f'*64))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                bad=copy.deepcopy(payload); h=bad['character_edit_handoff']; mutate(h)
                h['sha256']=bridge.hashed({k:v for k,v in h.items() if k!='sha256'})
                with self.assertRaises(ValueError):self.studio.production.create(bad)
                self.assertEqual([],self.studio.production.list()); self.assertTrue(self.studio.queue.empty())
        with patch.object(contracts,'bytes_of',side_effect=AssertionError('Server read a client workspace')):
            imported=self.client.request('POST','/api/production',payload)
        self.assertEqual(imported['root_id'],'character-edit:'+'1'*32)
        self.assertEqual(imported['budget'],{'allowance':3,'reserved':0})
        first_plan=(self.studio.production.root/imported['id']/'plan.json').read_bytes()
        duplicate=copy.deepcopy(payload); duplicate['name']='A changed display name'
        duplicate['character_edit_handoff']['seeds']=[77]
        duplicate['character_edit_handoff']['sha256']=bridge.hashed({k:v for k,v in duplicate['character_edit_handoff'].items() if k!='sha256'})
        with self.assertRaisesRegex(ValueError,'already imported'):self.studio.production.create(duplicate)
        self.assertEqual(first_plan,(self.studio.production.root/imported['id']/'plan.json').read_bytes())
        self.assertEqual(1,len(self.studio.production.list()))

    def test_local_raw_plan_change_stops_before_http_even_with_same_semantic_plan(self):
        client,plan,_=self.revision('raw')
        path=self.art/'raw-plan.json'; path.write_bytes(path.read_bytes()+b'\n')
        self.assertEqual(read_json(path),plan)
        with patch.object(self.client,'request',side_effect=AssertionError('Stale local plan made an HTTP request')):
            with self.assertRaisesRegex(ValueError,'Artifact changed'):client.stage()

    def test_forged_campaign_and_changed_uploads_cannot_materialize_or_grant_credit(self):
        self.register(); _,plan,handoff=self.revision('forgery'); payload=self.payload(plan,handoff)
        changed=campaigns.create(self.campaign['budget_owner'],4,campaign_id=self.campaign['campaign_id'])
        bad=copy.deepcopy(payload); bad['character_edit_campaign']=changed
        bad['character_edit_handoff']['campaign_sha256']=changed['campaign_sha256']
        bad['character_edit_handoff']['sha256']=bridge.hashed({k:v for k,v in bad['character_edit_handoff'].items() if k!='sha256'})
        with self.assertRaisesRegex(ValueError,'Registered campaign differs'):self.studio.production.create(bad)
        with self.assertRaises(ValueError):self.studio.production.create(dict(payload,root_id='another-root'))
        upload=self.studio.experiments/'uploads'/payload['uploads'][0]['file']
        upload.write_bytes(b'changed upload bytes')
        with self.assertRaisesRegex(ValueError,'reference bytes differ'):self.studio.production.create(payload)
        self.assertEqual([],self.studio.production.list());self.assertTrue(self.studio.queue.empty())
        self.assertEqual(self.studio.production.edit_campaign(self.campaign['campaign_id'])['budget'],{'allowance':3,'reserved':0})
        self.assertEqual([], [p for p in self.studio.production.root.iterdir() if p.is_dir() and len(p.name)==32])

    def test_v1_bridge_and_existing_exhausted_study_root_are_unchanged(self):
        study_root='character-study:'+'a'*64
        with self.studio.production.connect() as db:
            db.execute('INSERT INTO budgets(id,allowance,reserved) VALUES (?,12,12)',(study_root,))
        self.register(); current,_,_=self.revision('campaign')
        campaign_project=current.stage()['project']
        # A different legacy plan retains the original per-project behavior.
        legacy_plan=copy.deepcopy(self.plan); legacy_plan['document']['revision']=3
        legacy_plan['intent']['document_sha256']=sha(legacy_plan['document'])
        legacy_plan=edit.make_plan(legacy_plan['document'],legacy_plan['intent'],legacy_plan['catalog'])
        write_json(self.art/'legacy-plan.json',legacy_plan)
        bridge.prepare(self.art,'legacy-plan.json','legacy',[77],repo=self.repo)
        legacy=bridge.Bridge(self.art,'legacy/handoff.json',self.client).stage()['project']
        self.assertEqual(legacy['id'],legacy['root_id']); self.assertNotEqual(legacy['root_id'],campaign_project['root_id'])
        with self.studio.production.connect() as db:
            row=db.execute('SELECT allowance,reserved FROM budgets WHERE id=?',(study_root,)).fetchone()
        self.assertEqual(dict(row),{'allowance':12,'reserved':12})


if __name__ == '__main__': unittest.main()
