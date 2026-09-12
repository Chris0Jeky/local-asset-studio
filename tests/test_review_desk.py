import concurrent.futures
import copy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from review_fixture import FixtureStudio, seed
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
    def test_animated_oversized_and_nonimage_decodes_refused(self):
        from PIL import Image
        image=Image.new('RGBA',(5,5));buffer=io.BytesIO();image.save(buffer,format='PNG',save_all=True,append_images=[Image.new('RGBA',(5,5),'red')],duration=10)
        with self.assertRaisesRegex(ValueError,'still images'):decode(buffer.getvalue())
        buffer=io.BytesIO();image.save(buffer,format='PNG')
        with patch.object(review_media,'MAX_PIXELS',1):
            with self.assertRaisesRegex(ValueError,'decode budget'):decode(buffer.getvalue())
        with self.assertRaisesRegex(ValueError,'could not be decoded'):decode(b'not an image')
        image.close()


if __name__=='__main__':unittest.main()
