import concurrent.futures
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from review_fixture import FixtureStudio, seed, seed_matrix, seed_comparison
from production import Production, fingerprint
import review_desk
from review_desk import ReviewDesk, rating
import review_media
from review_media import crop_box, decode, digest, FULL_CROP


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.studio=FixtureStudio(self.root);self.production=self.studio.production;self.id=seed(self.studio)
    def tearDown(self):self.temp.cleanup()
    def command(self,action,**fields):return self.production.review(self.id,{'action':action,**fields})
    def open(self):return self.command('open')
    def get(self):return self.command('inspect')
    def change(self,action,**fields):return self.command(action,expected_revision=self.get()['revision'],**fields)
    def rate(self,alias='A',verdict='keep',**extra):
        return self.change('rate',alias=alias,assessment={'verdict':verdict,'observations':{'constraints':'pass'},**extra})
    def finalize(self):
        self.open()
        for alias in ('A','B','C'):self.rate(alias,'keep' if alias=='A' else 'reject')
        self.change('reveal');return self.change('finalize',selected='A',notes='Fixture preference, not art acceptance')
    def document(self):
        with self.production.connect() as db:return self.production.reviews._read(db,self.id)

    def test_project_directory_symlink_cannot_redirect_review_outputs(self):
        directory=self.production.root/self.id
        external=self.root/'outside-project';directory.rename(external)
        try:directory.symlink_to(external,target_is_directory=True)
        except OSError as exc:
            external.rename(directory);self.skipTest('Directory symlink unavailable: '+str(exc))
        try:
            with self.assertRaisesRegex(ValueError,'project directories'):self.open()
            self.assertFalse((external/'reviews').exists())
        finally:
            directory.unlink();external.rename(directory)

    def test_inspect_does_not_start_review_or_generation(self):
        self.assertEqual(self.get(),{'exists':False,'project_id':self.id})
        self.assertFalse((self.production.root/self.id/'reviews').exists());self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)
    def test_open_is_idempotent_with_stable_randomized_aliases(self):
        with patch.object(review_desk.random.SystemRandom,'shuffle',side_effect=lambda xs:xs.reverse()):first=self.open()
        self.assertEqual(first,self.open());self.assertEqual([c['alias'] for c in first['candidates']],['A','B','C'])
        doc=self.document();self.assertEqual(doc['candidates'][0]['stage'],2)
        self.assertEqual(len(list((self.production.root/self.id/'reviews').iterdir())),1)
    def test_blind_view_has_no_recipe_identity_paths_or_settings(self):
        state=self.open();encoded=json.dumps(state)
        for token in ('fixture-job','inert-prompt','original-','graph_sha256','PRIVATE-SEED','asset_id','fixture_recipe','plan','evidence_sha256'):
            self.assertNotIn(token,encoded)

    def test_engine_seed_grid_is_anonymous_then_reveals_recorded_coordinates(self):
        self.id=seed_matrix(self.studio);blind=self.open()
        self.assertIsNotNone(blind.get('grid'),'A recorded 3x2 comparison must offer Grid')
        grid=blind['grid'];self.assertEqual(len(grid['rows']),3);self.assertEqual(len(grid['columns']),2)
        self.assertEqual(len(grid['cells']),6)
        self.assertCountEqual([a for cell in grid['cells'] for a in cell['candidates']],list('ABCDEF'))
        self.assertTrue(all(set(row)=={'alias'} for row in grid['rows']))
        self.assertTrue(all(set(column)=={'alias'} for column in grid['columns']))
        for token in ('engine-copper','engine-indigo','engine-jade','712031','915047','Do not derive','original-'):
            self.assertNotIn(token,json.dumps(blind))
        self.assertEqual(self.open()['grid'],grid)
        revealed=self.change('reveal');actual=revealed['grid']
        rows={r['alias']:r['engine'] for r in actual['rows']};columns={c['alias']:c['seed'] for c in actual['columns']}
        sources={c['alias']:c['source']['filename'] for c in revealed['candidates']}
        coordinates={(rows[cell['row']],columns[cell['column']]):[sources[a] for a in cell['candidates']] for cell in actual['cells']}
        self.assertEqual(coordinates,{('engine-copper','712031'):['original-0.png'],('engine-copper','915047'):['original-1.png'],
                                     ('engine-indigo','712031'):['original-2.png'],('engine-indigo','915047'):['original-3.png'],
                                     ('engine-jade','712031'):['original-4.png'],('engine-jade','915047'):['original-5.png']})
        self.assertEqual([(c['row'],c['column'],c['candidates']) for c in actual['cells']],
                         [(c['row'],c['column'],c['candidates']) for c in grid['cells']])
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)

    def test_wording_grid_uses_frozen_plan_and_reveals_both_texts_at_the_exact_shared_seed(self):
        variants=[{'label':'Wording A','controls':{'positive':'A lantern in rain'}},
                  {'label':'Wording B','controls':{'positive':'Rain glows around a lantern'}}]
        self.id=seed_comparison(self.studio,'variants',variants)
        before=copy.deepcopy(self.production._get(self.id)['plan'])
        plan_path=self.production.root/self.id/'plan.json';before_bytes=plan_path.read_bytes()
        blind=self.open();grid=blind.get('grid')
        self.assertIsNotNone(grid,'Two prepared wordings must offer the existing Grid')
        self.assertEqual((len(grid['rows']),len(grid['columns']),len(grid['cells'])),(2,1,2))
        self.assertTrue(all(set(row)=={'alias'} for row in grid['rows']))
        for token in ('Wording A','Wording B','lantern','9223372036854775807','positive'):
            self.assertNotIn(token,json.dumps(blind))
        self.studio.production=Production(self.studio);self.production=self.studio.production
        self.assertEqual(self.get()['grid'],grid)
        revealed=self.change('reveal')['grid']
        self.assertEqual(revealed['columns'][0]['seed'],'9223372036854775807')
        self.assertEqual({row['label']:row['settings']['positive'] for row in revealed['rows']},
                         {'Wording A':'A lantern in rain','Wording B':'Rain glows around a lantern'})
        self.assertEqual(revealed['cells'],grid['cells'])
        self.assertEqual(self.production._get(self.id)['plan'],before)
        self.assertEqual(plan_path.read_bytes(),before_bytes)
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)

    def test_setting_and_seed_grids_project_recorded_values_without_rewriting_plans(self):
        for axis,values,prefix in (('cfg',[1,3,5],'Guidance'),('steps',[8,12,16],'Steps'),
                                   ('denoise',[0.3,0.6,0.9],'Denoise'),
                                   ('seed',[9223372036854775805,9223372036854775806,9223372036854775807],'Shared settings')):
            with self.subTest(axis=axis):
                self.id=seed_comparison(self.studio,axis,values)
                before=copy.deepcopy(self.production._get(self.id)['plan'])
                blind=self.open();grid=blind.get('grid')
                self.assertIsNotNone(grid,'An ordinary saved comparison must offer Grid')
                self.assertEqual((len(grid['rows']),len(grid['columns'])),(1,3) if axis=='seed' else (3,1))
                self.assertCountEqual([alias for cell in grid['cells'] for alias in cell['candidates']],list('ABC'))
                self.assertTrue(all(set(row)=={'alias'} for row in grid['rows']))
                revealed=self.change('reveal')['grid']
                if axis=='seed':
                    self.assertEqual(revealed['rows'][0]['label'],'Shared settings')
                    self.assertCountEqual([column['seed'] for column in revealed['columns']],[str(v) for v in values])
                else:
                    self.assertEqual(revealed['columns'][0]['seed'],'9223372036854775807')
                    self.assertCountEqual([row['label'] for row in revealed['rows']],[f'{prefix} {v}' for v in values])
                self.assertEqual(revealed['cells'],grid['cells'])
                self.assertEqual(self.production._get(self.id)['plan'],before)
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)

    def test_ordinary_grid_falls_back_for_missing_ambiguous_or_conflicting_frozen_evidence(self):
        variants=[{'label':'Wording A','controls':{'positive':'A lantern in rain'}},
                  {'label':'Wording B','controls':{'positive':'Rain glows around a lantern'}}]
        cases={
            'missing axis':lambda p:p.pop('axis'),
            'invalid axis':lambda p:p.update(axis=[]),
            'missing recipe':lambda p:p.pop('recipe'),
            'mismatched labels':lambda p:p.update(values=['A','B']),
            'missing variant':lambda p:p['variants'].pop(),
            'duplicate labels':lambda p:p['variants'][1].update(label='Wording A'),
            'invalid override':lambda p:p['variants'][0].update(controls={'positive':{}}),
            'missing seed':lambda p:p['stages'][0]['request']['controls'].pop('seed'),
            'different seed':lambda p:p['stages'][0]['request']['controls'].update(seed='17'),
            'different text':lambda p:p['stages'][0]['request']['controls'].update(positive='Unrecorded wording'),
            'different recipe':lambda p:p['stages'][0]['request'].update(preset_id='other'),
            'different template':lambda p:p['stages'][0]['request'].update(expected_template_sha256='e'*64),
            'different references':lambda p:p['stages'][0]['request'].update(references=[{'role':'other'}]),
        }
        for name,mutate in cases.items():
            with self.subTest(reason=name):
                self.id=seed_comparison(self.studio,'variants',variants)
                plan=self.production._get(self.id)['plan'];mutate(plan)
                plan['sha256']=fingerprint({k:v for k,v in plan.items() if k!='sha256'})
                with self.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(plan),self.id))
                state=self.open();self.assertIsNone(state['grid']);self.assertEqual(len(state['candidates']),2)
                self.assertEqual(self.production._get(self.id)['plan'],plan)
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)

    def test_ordinary_grid_does_not_invent_a_seed_from_graphs_or_labels(self):
        for value in (None,True,-1,'random','1e3',float(2**63-1),str(2**63)):
            with self.subTest(seed=value):
                self.id=seed_comparison(self.studio,'cfg',[1,3,5]);plan=self.production._get(self.id)['plan']
                plan['recipe']['controls']['seed']=value
                for stage in plan['stages']:stage['request']['controls']['seed']=value
                plan['sha256']=fingerprint({k:v for k,v in plan.items() if k!='sha256'})
                with self.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(plan),self.id))
                self.assertIsNone(self.open()['grid'])

    def test_wording_grid_preserves_failed_and_multiple_outputs_without_creating_runs(self):
        self.id=seed_comparison(self.studio,'variants',[{'label':'Wording A','controls':{'positive':'A lantern in rain'}},
                                                      {'label':'Wording B','controls':{'positive':'Rain glows around a lantern'}}])
        project=self.production._get(self.id);jobs=[self.studio.jobs[project['state']['attempts'][str(i)]['job_id']] for i in range(2)]
        first=jobs[0]['outputs'][0]['asset_id'];extra='e'*32
        self.studio.assets.paths[extra]=self.studio.assets.paths[first]
        self.studio.assets.records[extra]={**self.studio.assets.records[first],'id':extra,'output_index':1,'filename':'extra-wording-output.png'}
        jobs[0]['outputs'].append({'asset_id':extra,'media_type':'image'});jobs[1].update(status='failed',outputs=[])
        before=copy.deepcopy(project);blind=self.open();grid=blind['grid']
        self.assertEqual(len(grid['cells']),2)
        self.assertCountEqual([len(cell['candidates']) for cell in grid['cells']],[2,0])
        self.assertCountEqual([run['status'] for cell in grid['cells'] for run in cell['runs']],['completed','failed'])
        after=self.production._get(self.id)
        self.assertEqual(after['plan'],before['plan']);self.assertEqual(after['state']['attempts'],before['state']['attempts'])
        self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)

    def test_grid_order_cannot_be_reconstructed_from_public_session_and_known_axes(self):
        self.id=seed_matrix(self.studio);blind=self.open();document=self.document()
        session=blind['candidates'][0]['preview_url'].split('/reviews/')[1].split('/')[0]
        self.assertEqual(session,document['session_id'])
        self.assertNotIn('evidence_sha256',blind)
        engines={s['engine'] for s in document['evidence']['plan']['stages']}
        guessed=sorted(engines,key=lambda value:digest([session,'engine',value]))
        # Hold every public input fixed while varying the hidden frozen evidence.
        # An ordering derived only from the preview URL would expose every mapping.
        document['revealed']=True;orders=[]
        for index in range(16):
            document['evidence_sha256']=digest(['private evidence fixture',index])
            orders.append([row['engine'] for row in ReviewDesk._grid(document)['rows']])
        self.assertTrue(any(order!=guessed for order in orders),'Public preview identifiers must not determine the hidden axis mapping')

    def test_grid_keeps_multiple_outputs_and_truthful_empty_outcomes(self):
        self.id=seed_matrix(self.studio);project=self.production._get(self.id)
        jobs=[self.studio.jobs[project['state']['attempts'][str(i)]['job_id']] for i in range(6)]
        first=jobs[0]['outputs'][0]['asset_id'];second='f'*32
        self.studio.assets.paths[second]=self.studio.assets.paths[first]
        self.studio.assets.records[second]={**self.studio.assets.records[first],'id':second,'output_index':1,'filename':'second-output.png'}
        jobs[0]['outputs'].append({'asset_id':second,'media_type':'image'})
        for index,status in ((1,'failed'),(2,'cancelled'),(3,'completed')):
            jobs[index].update(status=status,outputs=[])
        del project['state']['attempts']['4'];self.production._state(self.id,project['state'])
        blind=self.open();self.assertEqual(len(blind['candidates']),3)
        self.assertCountEqual([run['status'] for c in blind['grid']['cells'] for run in c['runs']],
                              ['completed','failed','cancelled','completed','not_started','completed'])
        revealed=self.change('reveal');grid=revealed['grid']
        rows={r['alias']:r['engine'] for r in grid['rows']};columns={c['alias']:c['seed'] for c in grid['columns']}
        cells={(rows[c['row']],columns[c['column']]):c for c in grid['cells']}
        self.assertEqual(len(cells['engine-copper','712031']['candidates']),2)
        self.assertEqual(cells['engine-copper','915047']['runs'],[{'status':'failed','candidates':[]}])
        self.assertEqual(cells['engine-indigo','712031']['runs'],[{'status':'cancelled','candidates':[]}])
        self.assertEqual(cells['engine-indigo','915047']['runs'],[{'status':'completed','candidates':[]}])
        self.assertEqual(cells['engine-jade','712031']['runs'],[{'status':'not_started','candidates':[]}])

    def test_grid_never_guesses_missing_or_invalid_coordinates(self):
        for fields in ({'engine':'engine-copper'}, {'seed':712031}, {'engine':'','seed':1},
                       {'engine':['engine-copper'],'seed':1}, {'engine':'engine-copper','seed':True},
                       {'engine':'engine-copper','seed':'712031'}):
            with self.subTest(fields=fields):
                self.id=seed_matrix(self.studio);project=self.production._get(self.id)
                stage=project['plan']['stages'][0];stage.pop('engine');stage.pop('seed');stage.update(fields)
                stage['label']='engine-copper seed 712031';stage['request']['controls']['seed']=712031
                project['plan']['sha256']=fingerprint({k:v for k,v in project['plan'].items() if k!='sha256'})
                with self.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(project['plan']),self.id))
                state=self.open();self.assertIsNone(state['grid']);self.assertEqual(len(state['candidates']),6)

    def test_grid_aliases_assessment_and_reveal_survive_restart(self):
        self.id=seed_matrix(self.studio);before=self.open();alias=before['grid']['cells'][0]['candidates'][0]
        saved=self.rate(alias,notes='Evidence, not an automatic winner')
        self.assertEqual(saved['grid'],before['grid']);self.assertFalse(saved['revealed'])
        self.studio.production=Production(self.studio);self.production=self.studio.production
        self.assertEqual(self.get(),saved)
        revealed=self.change('reveal');self.studio.production=Production(self.studio);self.production=self.studio.production
        self.assertEqual(self.get(),revealed)

    def test_grid_distinguishes_unplanned_positions_and_missing_job_records(self):
        self.id=seed_matrix(self.studio);project=self.production._get(self.id)
        project['plan']['stages'][5]['seed']=712031
        project['plan']['sha256']=fingerprint({k:v for k,v in project['plan'].items() if k!='sha256'})
        with self.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(project['plan']),self.id))
        del self.studio.jobs[project['state']['attempts']['1']['job_id']]
        blind=self.open();self.assertEqual(sum(not c['runs'] for c in blind['grid']['cells']),1)
        self.assertEqual(sum(r['status']=='unavailable' for c in blind['grid']['cells'] for r in c['runs']),1)
        revealed=self.change('reveal');grid=revealed['grid']
        row=next(r['alias'] for r in grid['rows'] if r['engine']=='engine-jade')
        empty=next(c for c in grid['cells'] if c['row']==row and not c['runs'])
        self.assertEqual(empty['candidates'],[])
        retained=next(c for c in grid['cells'] if c['row']==row and c['runs'])
        self.assertEqual(len(retained['candidates']),2);self.assertEqual(len(retained['runs']),2)

    def test_grid_does_not_relax_live_private_or_revoked_source_refusals(self):
        self.id=seed_matrix(self.studio);project=self.production._get(self.id)
        job=self.studio.jobs[project['state']['attempts']['0']['job_id']]
        for status in ('queued','waiting','submitting','running','uncertain'):
            job['status']=status
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'unresolved'):self.open()
        job['status']='completed';job['privacy']='private'
        with self.assertRaisesRegex(ValueError,'Unknown job'):self.open()
        del job['privacy'];self.open();before=self.get()
        asset=self.studio.assets.records[job['outputs'][0]['asset_id']];asset['trashed_at']=1
        with self.assertRaisesRegex(ValueError,'Restore comparison outputs'):self.rate()
        self.assertEqual(self.get(),before)

    def test_grid_preserves_large_seed_identity_as_exact_json_text(self):
        self.id=seed_matrix(self.studio);project=self.production._get(self.id)
        project['plan']['stages'][0]['seed']=9223372036854775807
        project['plan']['sha256']=fingerprint({k:v for k,v in project['plan'].items() if k!='sha256'})
        with self.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(project['plan']),self.id))
        self.open();state=self.change('reveal')
        self.assertIn('"seed": "9223372036854775807"',json.dumps(state['grid']))
        self.assertIn('"seed": 9223372036854775807',state.get('evidence_json',''))
        self.assertEqual(json.loads(state['evidence_json']),state['evidence'])
    def test_blind_previews_strip_embedded_prompt_and_metadata(self):
        from PIL import Image
        self.open()
        for candidate in self.document()['candidates']:
            path=self.production.file(self.id,candidate['preview_path'])
            with Image.open(path) as image:
                self.assertFalse(image.info);self.assertEqual(image.mode,'RGBA');self.assertEqual(image.size,(192,256))
            self.assertNotIn(b'PRIVATE-SEED',path.read_bytes())
    def test_sources_are_preserved_byte_for_byte_and_not_published_blind(self):
        self.open()
        for c in self.document()['candidates']:
            path=self.production.root/self.id/c['source_path']
            self.assertEqual(path.read_bytes(),self.studio.assets.file(c['asset_id']).read_bytes())
            with self.assertRaisesRegex(ValueError,'not been published'):self.production.file(self.id,c['source_path'])
    def test_no_review_action_uses_generation_or_spends_budget(self):
        before=self.production.get(self.id)['budget'];self.finalize();self.change('export')
        self.assertEqual(before,self.production.get(self.id)['budget']);self.assertTrue(self.studio.queue.empty());self.assertEqual(self.studio.network_calls,0)
    def test_rate_and_unknown_measurements_roundtrip(self):
        self.open();state=self.rate(cleanup_seconds=0,preference=4,notes='Keep zero distinct from unknown')
        self.assertEqual(state['revision'],1);self.assertEqual(state['candidates'][0]['assessment']['cleanup_seconds'],0)
        self.assertIsNone(state['candidates'][1]['assessment']['cleanup_seconds'])
        self.assertEqual(state['candidates'][0]['assessment']['observations']['identity'],'not_assessed')
    def test_stale_revision_cannot_overwrite_another_editor(self):
        self.open();self.rate(notes='first')
        with self.assertRaisesRegex(ValueError,'Review conflict'):self.command('rate',expected_revision=0,alias='A',assessment={'notes':'lost update'})
        self.assertEqual(self.get()['candidates'][0]['assessment']['notes'],'first')
    def test_two_independent_services_have_one_revision_winner(self):
        self.open();other=ReviewDesk(self.production)
        def update(desk):
            try:return desk.command(self.id,{'action':'rate','expected_revision':0,'alias':'A','assessment':{'notes':'concurrent'}})['revision']
            except ValueError:return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(update,[self.production.reviews,other]))
        self.assertCountEqual(results,[1,'conflict']);self.assertEqual(len(self.get()['history']),2)
    def test_boolean_or_missing_revision_rejected(self):
        self.open()
        for revision in (None,False,'0',-1,1.0):
            with self.subTest(revision=revision),self.assertRaisesRegex(ValueError,'conflict'):self.command('reveal',expected_revision=revision)
        self.assertFalse(self.get()['revealed'])
    def test_reveal_is_irreversible_and_records_actor(self):
        self.open();revealed=self.change('reveal',reviewer='local-agent')
        self.assertTrue(revealed['revealed']);self.assertIn('evidence',revealed);self.assertIn('source',revealed['candidates'][0])
        self.assertEqual(revealed['history'][0]['reviewer'],'local-agent')
        with self.assertRaisesRegex(ValueError,'already revealed'):self.change('reveal')
    def test_finalize_requires_reveal_all_verdicts_and_constraints(self):
        self.open()
        with self.assertRaisesRegex(ValueError,'Reveal'):self.change('finalize',selected=None)
        self.change('reveal')
        with self.assertRaisesRegex(ValueError,'every candidate'):self.change('finalize',selected=None)
        for alias in ('A','B','C'):self.rate(alias,'reject')
        with self.assertRaisesRegex(ValueError,'kept candidate'):self.change('finalize',selected='A')
        self.change('rate',alias='A',assessment={'verdict':'keep'})
        with self.assertRaisesRegex(ValueError,'stated constraints'):self.change('finalize',selected='A')
    def test_reject_all_is_valid_and_does_not_invent_accepted_result(self):
        self.open()
        for alias in ('A','B','C'):self.rate(alias,'reject')
        self.change('reveal');state=self.change('finalize',selected=None)
        self.assertIsNone(state['selected']);self.assertTrue(state['finalized'])
        self.assertEqual(self.production.get(self.id)['state']['review']['status'],'needs_work')
    def test_finalize_updates_review_not_terms_engine_or_budget(self):
        before=self.production._get(self.id);state=self.finalize();after=self.production._get(self.id)
        self.assertTrue(state['finalized']);self.assertEqual(state['finalized_by'],'local-user')
        self.assertEqual(after['plan'],before['plan']);self.assertEqual(after['state']['attempts'],before['state']['attempts'])
        self.assertEqual(after['state']['status'],'reviewed');self.assertEqual(after['state']['review']['status'],'selected')
        self.assertNotIn('engine',after['state']);self.assertNotIn('rights',after['state'])
    def test_edit_invalidates_selection_but_keeps_reveal_and_history(self):
        self.finalize();state=self.rate('A','needs_work',notes='New issue')
        self.assertFalse(state['finalized']);self.assertIsNone(state['selected']);self.assertIsNone(state['finalized_by'])
        self.assertTrue(state['revealed']);self.assertIn('finalize',[e['action'] for e in state['history']])
    def test_restore_is_a_new_revision_and_does_not_erase_history(self):
        self.open();self.rate(notes='earlier');self.rate(notes='later')
        state=self.change('restore',source_revision=1)
        self.assertEqual(state['revision'],3);self.assertEqual(state['candidates'][0]['assessment']['notes'],'earlier')
        self.assertEqual(len(state['history']),4);self.assertEqual(state['history'][0]['action'],'restore')
        for rev in (0,999,True):
            with self.subTest(rev=rev),self.assertRaises(ValueError):self.change('restore',source_revision=rev)
    def test_revision_budget_rejects_without_mutation(self):
        self.open();self.rate()
        with patch.object(review_desk,'MAX_REVISIONS',1):
            with self.assertRaisesRegex(ValueError,'budget'):self.rate(notes='beyond')
        self.assertEqual(self.get()['revision'],1)
    def test_restarting_production_retains_aliases_assessments_and_does_not_submit(self):
        self.open();expected=self.rate(notes='persisted')
        self.studio.production=Production(self.studio);self.production=self.studio.production
        self.assertEqual(self.get(),expected);self.assertTrue(self.studio.queue.empty())
    def test_legacy_review_cannot_bypass_active_desk(self):
        self.open()
        with self.assertRaisesRegex(ValueError,'legacy selection'):self.production.review(self.id,{'asset_id':None})
    def test_legacy_review_still_works_for_unopened_projects(self):
        state=self.production.review(self.id,{'asset_id':None,'notes':'legacy'})
        self.assertEqual(state['state']['review']['notes'],'legacy');self.assertFalse(self.get()['exists'])
    def test_changed_plan_is_rejected(self):
        project=self.production._get(self.id);project['plan']['values']=[123]
        with self.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(project['plan']),self.id))
        with self.assertRaisesRegex(ValueError,'plan changed'):self.open()
    def test_changed_execution_evidence_refuses_stale_assessment(self):
        self.open();next(iter(self.studio.jobs.values()))['prompt_ids']=['changed']
        with self.assertRaisesRegex(ValueError,'evidence changed'):self.rate()
        self.assertEqual(self.get()['revision'],0)
    def test_changed_workspace_or_snapshot_bytes_cannot_be_finalized(self):
        self.finalize();candidate=self.document()['candidates'][0]
        self.studio.assets.file(candidate['asset_id']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.change('finalize',selected='A')
        with self.assertRaisesRegex(ValueError,'changed'):self.change('export')
    def test_changed_snapshot_rejected_before_export(self):
        self.finalize();candidate=self.document()['candidates'][0]
        (self.production.root/self.id/candidate['source_path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.change('export')
    def test_failed_stage_retained_but_not_selected_or_relabelled_success(self):
        self.id=seed(self.studio,failed_stage=True);self.open();state=self.change('reveal')
        failed=next(c['alias'] for c in state['candidates'] if c['source']['stage']==2)
        for alias in ('A','B','C'):self.rate(alias,'keep')
        with self.assertRaisesRegex(ValueError,'incomplete execution'):self.change('finalize',selected=failed)
        state=self.change('finalize',selected=None)
        self.assertEqual(self.production.get(self.id)['state']['status'],'failed');self.assertEqual(state['evidence']['stages'][2]['status'],'failed')
    def test_active_or_uncertain_jobs_cannot_be_reviewed(self):
        job=next(iter(self.studio.jobs.values()))
        for status in ('queued','waiting','submitting','running','uncertain'):
            job['status']=status
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'unresolved'):self.open()
    def test_native_active_and_stopped_projects_are_not_misrepresented(self):
        for status in ('planned','running','stopped','interrupted','uncertain'):
            self.production._mutate(self.id,status=status)
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'Finish or reconcile'):self.open()
    def test_foreign_lineage_and_trashed_assets_are_rejected(self):
        asset=next(iter(self.studio.assets.records.values()));original=copy.deepcopy(asset)
        asset['job_id']='foreign'
        with self.assertRaisesRegex(ValueError,'lineage'):self.open()
        asset.update(original);asset['trashed_at']=0
        with self.assertRaisesRegex(ValueError,'Restore'):self.open()
    def test_candidates_not_silently_truncated_and_total_cap(self):
        with patch.object(review_desk,'MAX_CANDIDATES',2):
            with self.assertRaisesRegex(ValueError,'sixteen'):self.open()
        with patch.object(review_desk,'MAX_TOTAL_BYTES',1):
            with self.assertRaisesRegex(ValueError,'total budget'):self.open()
    def test_disk_and_storage_caps(self):
        with patch.object(review_desk.shutil,'disk_usage',return_value=type('Disk',(),{'free':0})()):
            with self.assertRaisesRegex(ValueError,'headroom'):self.open()
        with patch.object(review_desk,'MAX_STORAGE_BYTES',1):
            with self.assertRaisesRegex(ValueError,'storage budget'):self.open()
    def test_open_failure_does_not_publish_partial_files_and_releases_lock(self):
        with patch.object(review_desk,'make_preview',side_effect=OSError('simulated disk fault')):
            with self.assertRaises(OSError):self.open()
        self.assertFalse(self.get()['exists']);self.assertFalse(self.production.reviews.media_lock.locked())
        with self.production.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM comparison_review_files').fetchone()[0],0)
        self.assertTrue(list((self.production.root/self.id/'reviews').rglob('*.png')))
    def test_open_failure_keeps_the_folder_with_an_incomplete_marker(self):
        before=time.time()
        with patch.object(review_desk,'make_preview',side_effect=OSError('simulated disk fault')):
            with self.assertRaises(OSError):self.open()
        after=time.time()
        self.assertFalse(self.get()['exists']);self.assertFalse(self.production.reviews.media_lock.locked())
        with self.production.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM comparison_review_files').fetchone()[0],0)
        folders=list((self.production.root/self.id/'reviews').iterdir());self.assertEqual(len(folders),1)
        self.assertTrue(list(folders[0].rglob('*.png')))
        marker=json.loads((folders[0]/'INCOMPLETE.json').read_text(encoding='utf-8'))
        self.assertEqual(marker['version'],1);self.assertEqual(marker['kind'],'incomplete-review-open')
        self.assertEqual(marker['project_id'],self.id);self.assertEqual(marker['session_id'],folders[0].name)
        self.assertEqual(marker['step'],'preview');self.assertEqual(marker['alias'],'A')
        self.assertEqual(marker['error'],{'type': 'OSError', 'message': 'simulated disk fault'})
        self.assertIs(marker['registered'],False);self.assertIsNone(marker['superseded_by'])
        self.assertIsInstance(marker['at'],float);self.assertGreaterEqual(marker['at'],before);self.assertLessEqual(marker['at'],after)
    def test_open_hash_mismatch_marks_the_copy_step(self):
        with patch.object(review_desk,'checked_bytes',side_effect=ValueError('bytes changed')):
            with self.assertRaises(ValueError):self.open()
        folders=list((self.production.root/self.id/'reviews').iterdir());self.assertEqual(len(folders),1)
        marker=json.loads((folders[0]/'INCOMPLETE.json').read_text(encoding='utf-8'))
        self.assertEqual(marker['step'],'copy_source');self.assertEqual(marker['alias'],'A')
        self.assertEqual(marker['error'],{'type': 'ValueError', 'message': 'bytes changed'})
        self.assertIs(marker['registered'],False);self.assertIsNone(marker['superseded_by'])
        self.assertEqual(marker['session_id'],folders[0].name)
    def test_lost_open_race_keeps_its_folder_marked_superseded(self):
        first=self.open();winner=self.document()['session_id']
        original=review_desk.ReviewDesk._read;calls=[]
        def wrapper(db,identifier):
            if not calls:calls.append(1);return None
            return original(db,identifier)
        with patch.object(review_desk.ReviewDesk,'_read',staticmethod(wrapper)):second=self.open()
        self.assertEqual(second,first)
        folders=sorted((self.production.root/self.id/'reviews').iterdir());self.assertEqual(len(folders),2)
        new=next(p for p in folders if p.name!=winner)
        marker=json.loads((new/'INCOMPLETE.json').read_text(encoding='utf-8'))
        self.assertEqual(marker['step'],'superseded');self.assertEqual(marker['superseded_by'],winner)
        self.assertIsNone(marker['error']);self.assertIsNone(marker['alias']);self.assertIs(marker['registered'],False)
        self.assertEqual(marker['session_id'],new.name)
        self.assertFalse((self.production.root/self.id/'reviews'/winner/'INCOMPLETE.json').exists())
    def test_successful_open_writes_no_marker(self):
        self.open()
        self.assertEqual(list((self.production.root/self.id/'reviews').rglob('INCOMPLETE.json')),[])
    def test_view_records_exact_integer_crop_and_background(self):
        self.open();state=self.change('view',crop=[2500,1000,7500,9000],background='light')
        self.assertEqual(state['crop'],[2500,1000,7500,9000]);self.assertEqual(state['background'],'light')
        for crop in ([0,0,0,0],[-1,0,10,10],[0,0,10001,10000],[0.,0,10000,10000],[False,0,10000,10000],None):
            with self.subTest(crop=crop),self.assertRaises(ValueError):self.change('view',crop=crop,background='light')
    def test_bad_ratings_do_not_mutate(self):
        self.open()
        for assessment in (None,{'verdict':'accept'},{'notes':3},{'cleanup_seconds':False},{'cleanup_seconds':-1},
                           {'preference':6},{'observations':[]},{'observations':{'invented':'pass'}},
                           {'observations':{'identity':'maybe'}},{'command':'run'}):
            with self.subTest(assessment=assessment),self.assertRaises(ValueError):self.change('rate',alias='A',assessment=assessment)
        self.assertEqual(self.get()['revision'],0)
    def test_unknown_actions_keys_aliases_reviewers_and_payloads(self):
        for payload in ([],None,{'action':'generate'},{'action':'inspect','script':'bad'}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):self.production.review(self.id,payload)
        self.open()
        with self.assertRaisesRegex(ValueError,'alias'):self.change('rate',alias='Z',assessment={})
        with self.assertRaisesRegex(ValueError,'Reviewer'):self.change('reveal',reviewer='verified-author')
    def test_revealed_timings_keep_null_distinct_from_zero(self):
        self.open();state=self.change('reveal')
        stages=state['evidence']['stages'];self.assertEqual(stages[0]['elapsed_seconds'],0)
        self.assertIsNone(stages[1]['elapsed_seconds']);self.assertIsNone(stages[0]['peak_memory_bytes'])
    def test_export_requires_finalized_revealed_revision(self):
        self.open()
        with self.assertRaisesRegex(ValueError,'Finalize'):self.change('export')
        self.finalize()
        with self.assertRaisesRegex(ValueError,'conflict'):self.command('export',expected_revision=0)
    def test_export_manifest_hashes_every_member_and_preserves_sources(self):
        self.finalize();result=self.change('export');pack=next(a for a in result['artifacts'] if a['path'].endswith('.zip'))
        path=self.production.file(self.id,pack['path'])
        with zipfile.ZipFile(path) as archive:
            manifest=json.loads(archive.read('checksums.json'))
            self.assertEqual(set(archive.namelist()),set(manifest['files'])|{'checksums.json'})
            for name,record in manifest['files'].items():
                data=archive.read(name);self.assertEqual(hashlib.sha256(data).hexdigest(),record['sha256']);self.assertEqual(len(data),record['bytes'])
            report=json.loads(archive.read('review.json'))
            self.assertEqual(report['rights_status'],'not_assessed_by_review_desk');self.assertEqual(report['engine_acceptance'],'not_assessed_by_review_desk')
            self.assertEqual(len(report['review']['candidates']),3);self.assertEqual(len(report['history']),6)
        self.assertEqual(self.get()['export'],result)
    def test_export_is_idempotent_and_revision_changes_create_new_artifacts(self):
        self.finalize();first=self.change('export')
        with patch.object(review_desk,'render_sheet') as render:self.assertEqual(first,self.change('export'))
        render.assert_not_called();self.change('view',crop=[2000,0,8000,10000],background='light')
        second=self.change('export');self.assertNotEqual(first['artifacts'][0]['path'],second['artifacts'][0]['path'])
        for a in first['artifacts']:self.assertTrue(self.production.file(self.id,a['path']).is_file())
    def test_export_preserves_finalization_author_when_crop_changes(self):
        self.finalize();self.change('view',crop=FULL_CROP,background='light',reviewer='local-agent')
        state=self.production.get(self.id)['state'];self.assertEqual(state['review']['reviewer'],'local-user')
    def test_export_failure_never_publishes_or_overwrites_prior_receipts(self):
        self.finalize();before=self.change('export');self.change('view',crop=FULL_CROP,background='light')
        with patch.object(review_desk,'render_sheet',side_effect=OSError('disk failed')):
            with self.assertRaises(OSError):self.change('export')
        self.assertIsNone(self.get()['export']);self.assertFalse(self.production.reviews.media_lock.locked())
        self.assertTrue(self.production.file(self.id,before['artifacts'][0]['path']).is_file())
    def test_edit_during_export_rejects_publication(self):
        self.finalize();original=review_desk.render_sheet
        def edit(*args,**kwargs):
            value=original(*args,**kwargs);self.rate(notes='new evidence');return value
        with patch.object(review_desk,'render_sheet',side_effect=edit):
            with self.assertRaisesRegex(ValueError,'conflict'):self.change('export')
        self.assertIsNone(self.get()['export'])
    def test_export_budget_is_explicit(self):
        self.finalize();self.change('export');self.change('view',crop=FULL_CROP,background='light')
        with patch.object(review_desk,'MAX_EXPORTS',1):
            with self.assertRaisesRegex(ValueError,'export budget'):self.change('export')
    def test_unpublished_traversal_and_modified_artifacts_not_served(self):
        self.open();c=self.document()['candidates'][0]
        for path in ('reviews/../projects.sqlite3',c['preview_path']+'/../sources/A.png','reviews/'+'0'*32+'/unregistered.png'):
            with self.subTest(path=path),self.assertRaises(ValueError):self.production.file(self.id,path)
        target=self.production.file(self.id,c['preview_path']);data=bytearray(target.read_bytes());data[-1]^=1;target.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'changed'):self.production.file(self.id,c['preview_path'])
    def test_foreign_project_cannot_fetch_another_reviews_file(self):
        self.open();c=self.document()['candidates'][0];other=seed(self.studio)
        with self.assertRaisesRegex(ValueError,'not been published'):self.production.file(other,c['preview_path'])
    def test_cpu_operation_gate_is_released_and_does_not_queue(self):
        self.production.reviews.media_lock.acquire()
        try:
            with self.assertRaisesRegex(ValueError,'bounded review'):self.open()
        finally:self.production.reviews.media_lock.release()
        self.assertTrue(self.studio.queue.empty())
    def test_sheet_receipt_keeps_its_own_copy_of_the_crop(self):
        from PIL import Image
        stream=io.BytesIO();Image.new('RGBA',(20,20),(1,2,3,255)).save(stream,'PNG');png=stream.getvalue()
        crop=[0,0,10000,10000]
        with tempfile.TemporaryDirectory() as folder:
            receipt=review_media.render_sheet([{'alias':'A'},{'alias':'B'}],lambda candidate:png,crop,Path(folder)/'sheet.png')
        crop[0]=5000
        self.assertEqual([t['basis_points'] for t in receipt['transforms']],[[0,0,10000,10000]]*2,'the receipt describes the rendered crop')

    def test_crop_rounding_covers_nonempty_exact_regions(self):
        self.assertEqual(crop_box([0,0,10000,10000],(13,17)),(0,0,13,17))
        self.assertEqual(crop_box([3333,3333,6666,6666],(3,3)),(0,0,2,2))
        self.assertEqual(crop_box([9999,9999,10000,10000],(3,3)),(2,2,3,3))
    def test_orientation_is_applied_once_and_original_bytes_unchanged(self):
        from PIL import Image
        image=Image.new('RGB',(9,15));exif=Image.Exif();exif[274]=6;buffer=io.BytesIO();image.save(buffer,format='JPEG',exif=exif);data=buffer.getvalue()
        oriented,transform=decode(data)
        try:self.assertEqual(oriented.size,(15,9));self.assertEqual(transform['encoded_size'],[9,15]);self.assertEqual(transform['exif_orientation'],6);self.assertFalse(oriented.info)
        finally:oriented.close();image.close()
    def test_review_busy_status_and_export_reason_wired(self):
        js=(Path(__file__).resolve().parent.parent/'app/static/review.js').read_text(encoding='utf-8');html=(Path(__file__).resolve().parent.parent/'app/static/review.html').read_text(encoding='utf-8')
        self.assertIn("$('#export').disabled=busy||!state?.finalized||dirty()",js)
        self.assertIn('aria-busy',js);self.assertIn("$('#desk').setAttribute('aria-busy'",js)
        self.assertIn('Saving…',js);self.assertIn('Loading…',js)
        self.assertIn('Save your unsaved changes first',js);self.assertIn('Finalize the review first',js)
        self.assertIn("$('#export').title",js);self.assertIn("$('#exportHint').textContent",js)
        self.assertIn('id="exportHint"',html)
    def test_animated_oversized_and_nonimage_decodes_refused(self):
        from PIL import Image
        image=Image.new('RGBA',(5,5));buffer=io.BytesIO();image.save(buffer,format='PNG',save_all=True,append_images=[Image.new('RGBA',(5,5),'red')],duration=10)
        with self.assertRaisesRegex(ValueError,'still images'):decode(buffer.getvalue())
        buffer=io.BytesIO();image.save(buffer,format='PNG')
        with patch.object(review_media,'MAX_PIXELS',1):
            with self.assertRaisesRegex(ValueError,'decode budget'):decode(buffer.getvalue())
        with self.assertRaisesRegex(ValueError,'could not be decoded'):decode(b'not an image')
        image.close()

    def test_a_pillow_syntax_error_is_the_still_image_refusal(self):
        # Pillow reports some damaged files as SyntaxError; references.py and upload() already map it.
        from PIL import Image
        with patch.object(Image,'open',side_effect=SyntaxError('broken PNG file')):
            with self.assertRaisesRegex(ValueError,'could not be decoded'):decode(b'damaged png bytes')


if __name__=='__main__':unittest.main()
