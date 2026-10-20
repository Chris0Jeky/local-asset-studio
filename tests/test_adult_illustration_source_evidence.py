"""Immutable metadata evidence; all exchanges are fixtures and sockets are forbidden."""
import base64
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from studio_prompt import adult_illustration_source_transport as api
from tests.test_adult_illustration_source_transport import (
    ScriptedExchange, _civitai_payload, _hf_payload, _json_response,
)

URL = 'https://civitai.com/api/v1/model-versions/123'


class SourceEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        sockets = patch('socket.create_connection', side_effect=AssertionError('Sockets forbidden'))
        sockets.start(); self.addCleanup(sockets.stop)

    def store(self, **limits):
        return api.SnapshotEvidenceStore(self.root/'evidence', policy=api.EvidencePolicy(**limits) if limits else None)

    def fetch(self, store, payload=None, **options):
        return api.fetch_civitai(123, api.BoundedProviderTransport(
            exchange=ScriptedExchange(_json_response(URL, payload or _civitai_payload(), headers={'etag': '"fixture"', 'set-cookie': 'not retained'})),
            evidence_store=store, **options))

    def body(self, result):
        return base64.b64decode(result['body_base64'], validate=True)

    def assert_authority(self, value):
        for key in ('download_authorized', 'install_authorized', 'execution_authorized', 'generation_submitted', 'training_authorized'):
            self.assertIs(value[key], False)

    def test_refresh_preserves_changed_bodies_and_provenance_after_restart(self):
        store = self.store(); cache = api.SnapshotResponseCache(self.root/'cache')
        first = self.fetch(store, cache=cache)
        changed = _civitai_payload(); changed['model']['allowCommercialUse'] = 'None'
        second = self.fetch(store, changed, cache=cache, refresh=True)
        self.assertNotEqual(first['raw_payload_ref']['sha256'], second['raw_payload_ref']['sha256'])
        restarted = self.store()
        for original, expected in ((first, 'Image'), (second, 'None')):
            resolved = restarted.resolve(original['raw_payload_ref'])
            self.assertEqual(resolved['state'], 'available')
            raw = self.body(resolved)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), original['snapshot']['raw_payload_sha256'])
            self.assertEqual(json.loads(raw)['model']['allowCommercialUse'], expected)
            self.assertEqual(resolved['provenance']['request']['url'], URL)
            self.assertNotIn('set-cookie', resolved['provenance']['response']['headers'])
            self.assert_authority(original); self.assert_authority(resolved)

    def test_304_hit_and_no_cache_retain_one_body_with_truthful_provenance(self):
        store = self.store(); cache = api.SnapshotResponseCache(self.root/'cache')
        first = self.fetch(store, cache=cache)
        hit = api.fetch_civitai(123, api.BoundedProviderTransport(exchange=ScriptedExchange(), cache=cache, evidence_store=store))
        revalidated = api.fetch_civitai(123, api.BoundedProviderTransport(
            exchange=ScriptedExchange(api.WireResponse(URL, 304, {'etag': '"fixture"'}, b'')),
            cache=cache, evidence_store=store, refresh=True))
        uncached = self.fetch(store)
        for result, kind in ((first, 'network-200'), (hit, 'cache-hit'), (revalidated, 'revalidated-304'), (uncached, 'network-200')):
            resolved = store.resolve(result['raw_payload_ref'])
            self.assertEqual(resolved['state'], 'available')
            self.assertEqual(resolved['provenance']['acquisition'], kind)
            self.assertEqual(self.body(resolved), self.body(store.resolve(first['raw_payload_ref'])))
        self.assertEqual(store.stats()['available_payloads'], 1)
        self.assertEqual(store.stats()['observations'], 4)

    def test_same_content_from_two_request_identities_keeps_both_sources(self):
        store = self.store(); refs = []
        for revision in ('main', 'a'*40):
            url = f'https://huggingface.co/api/models/owner/model/revision/{revision}?blobs=true'
            result = api.fetch_huggingface('owner/model', revision, api.BoundedProviderTransport(
                exchange=ScriptedExchange(_json_response(url, _hf_payload())), evidence_store=store))
            refs.append(result['raw_payload_ref'])
        self.assertEqual(refs[0]['sha256'], refs[1]['sha256'])
        self.assertNotEqual(refs[0]['observation_id'], refs[1]['observation_id'])
        self.assertNotEqual(store.resolve(refs[0])['provenance']['request'], store.resolve(refs[1])['provenance']['request'])
        self.assertEqual(store.stats()['available_payloads'], 1)

    def test_missing_corrupt_and_pruned_evidence_are_distinct_after_restart(self):
        for failure, expected in (('missing', 'missing'), ('corrupt', 'corrupt'), ('prune', 'pruned')):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                store = api.SnapshotEvidenceStore(root); ref = self.fetch(store)['raw_payload_ref']
                if failure == 'prune': self.assertEqual(store.prune(ref['sha256'])['state'], 'pruned')
                else:
                    with closing(sqlite3.connect(store.path)) as db, db:
                        if failure == 'missing': db.execute('DELETE FROM payloads WHERE sha256=?', (ref['sha256'],))
                        else: db.execute('UPDATE payloads SET body=? WHERE sha256=?', (b'changed', ref['sha256']))
                self.assertEqual(api.SnapshotEvidenceStore(root).resolve(ref)['state'], expected)
                if failure != 'missing':
                    retry = self.fetch(store)['raw_payload_ref']
                    self.assertEqual(retry['retention_state'], expected)

    def test_quota_dimensions_do_not_discard_existing_evidence(self):
        for limits in ({'max_total_bytes': 1}, {'max_payloads': 1}, {'max_observations': 1}):
            with self.subTest(limits=limits), tempfile.TemporaryDirectory() as root:
                store = api.SnapshotEvidenceStore(root, policy=api.EvidencePolicy(**limits))
                first = self.fetch(store)['raw_payload_ref']
                changed = _civitai_payload(); changed['name'] = 'new metadata'
                second = self.fetch(store, changed if 'max_payloads' in limits else None)['raw_payload_ref']
                self.assertEqual(second['retention_state'], 'quota_exceeded')
                self.assertEqual(store.resolve(second)['state'], 'quota_exceeded')
                if first['retention_state'] == 'retained': self.assertEqual(store.resolve(first)['state'], 'available')

    def test_concurrent_store_instances_serialize_quota_and_same_body_deduplication(self):
        for same in (False, True):
            with self.subTest(same=same), tempfile.TemporaryDirectory() as root:
                owners = [api.SnapshotEvidenceStore(root, policy=api.EvidencePolicy(max_payloads=1)) for _ in range(2)]
                entered = threading.Barrier(2); results = []; errors = []
                def work(index):
                    try:
                        payload = _civitai_payload(); payload['name'] = 'same' if same else str(index)
                        entered.wait(5); results.append(self.fetch(owners[index], payload)['raw_payload_ref'])
                    except BaseException as exc: errors.append(exc)
                workers = [threading.Thread(target=work, args=(i,)) for i in range(2)]
                for worker in workers: worker.start()
                for worker in workers: worker.join(10)
                self.assertFalse(any(worker.is_alive() for worker in workers)); self.assertEqual(errors, [])
                self.assertEqual(sorted(r['retention_state'] for r in results), ['retained', 'retained'] if same else ['quota_exceeded', 'retained'])
                self.assertEqual(owners[0].stats()['available_payloads'], 1)

    def test_publication_failure_returns_a_distinct_unretained_reference(self):
        store = self.store()
        with patch.object(store, '_commit', side_effect=sqlite3.OperationalError('synthetic disk full')):
            result = self.fetch(store)
        self.assertEqual(result['raw_payload_ref']['retention_state'], 'publication_failed')
        self.assertEqual(store.stats()['payloads'], 0)
        self.assertEqual(store.stats()['observations'], 0)
        self.assertEqual(store.resolve(result['raw_payload_ref'])['state'], 'publication_failed')

    def test_unconfirmed_commit_does_not_claim_retention_even_when_bytes_committed(self):
        store = self.store()
        def lost_ack(db):
            db.commit(); raise OSError('synthetic lost commit acknowledgement')
        with patch.object(store, '_commit', side_effect=lost_ack): result = self.fetch(store)
        self.assertEqual(result['raw_payload_ref']['retention_state'], 'publication_failed')
        self.assertEqual(store.resolve(result['raw_payload_ref'])['state'], 'publication_failed')
        self.assertEqual(store.stats()['payloads'], 1)
        recovered = self.fetch(store)
        self.assertEqual(store.resolve(recovered['raw_payload_ref'])['state'], 'available')
        self.assertEqual(store.stats()['payloads'], 1)

    def test_independent_processes_cannot_overadmit_the_same_store_quota(self):
        root = self.root/'processes'; api.SnapshotEvidenceStore(root, policy=api.EvidencePolicy(max_payloads=1))
        script = '''
import json,sys,time
from pathlib import Path
from unittest.mock import patch
from studio_prompt import adult_illustration_source_transport as api
from tests.test_adult_illustration_source_transport import ScriptedExchange,_json_response,_civitai_payload
root=Path(sys.argv[1]); index=sys.argv[2]; store=api.SnapshotEvidenceStore(root)
(root/('ready-'+index)).touch(); deadline=time.monotonic()+20
while not (root/'go').exists():
 if time.monotonic()>deadline: raise RuntimeError('process admission barrier timed out')
 time.sleep(.01)
payload=_civitai_payload(); payload['name']=index
with patch('socket.create_connection',side_effect=AssertionError('Sockets forbidden')):
 result=api.fetch_civitai(123,api.BoundedProviderTransport(exchange=ScriptedExchange(_json_response('https://civitai.com/api/v1/model-versions/123',payload)),evidence_store=store))
print(json.dumps(result['raw_payload_ref']))
'''
        workers = [subprocess.Popen([sys.executable, '-c', script, str(root), str(i)],
                   cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(2)]
        try:
            deadline = time.monotonic()+20
            while not all((root/('ready-'+str(i))).exists() for i in range(2)) and time.monotonic()<deadline:
                if any(worker.poll() is not None for worker in workers): break
                time.sleep(.01)
            self.assertTrue(all((root/('ready-'+str(i))).exists() for i in range(2)), 'both processes must reach admission')
            (root/'go').touch(); refs = []
            for worker in workers:
                stdout, stderr = worker.communicate(timeout=10)
                self.assertEqual(worker.returncode, 0, stderr); refs.append(json.loads(stdout))
            self.assertEqual(sorted(ref['retention_state'] for ref in refs), ['quota_exceeded', 'retained'])
            self.assertEqual(api.SnapshotEvidenceStore(root).stats()['payloads'], 1)
        finally:
            for worker in workers:
                if worker.poll() is None: worker.kill()
                worker.communicate(timeout=5)

    def test_prune_serializes_with_publication_without_a_partial_visible_record(self):
        store = self.store(); other = self.store(); entered, release = threading.Event(), threading.Event()
        results, pruned, errors = [], [], []
        def held_commit(db):
            entered.set()
            if not release.wait(10): raise RuntimeError('publication release timed out')
            db.commit()
        def publish():
            try: results.append(self.fetch(store))
            except BaseException as exc: errors.append(exc)
        def prune():
            try: pruned.append(other.prune(hashlib.sha256(_json_response(URL, _civitai_payload()).body).hexdigest()))
            except BaseException as exc: errors.append(exc)
        with patch.object(store, '_commit', side_effect=held_commit):
            writer = threading.Thread(target=publish); writer.start()
            cleaner = None
            try:
                self.assertTrue(entered.wait(5)); self.assertEqual(other.stats()['payloads'], 0)
                cleaner = threading.Thread(target=prune); cleaner.start()
            finally:
                release.set(); writer.join(10)
                if cleaner is not None: cleaner.join(10)
        self.assertFalse(writer.is_alive()); self.assertFalse(cleaner.is_alive()); self.assertEqual(errors, [])
        self.assertEqual(results[0]['raw_payload_ref']['retention_state'], 'retained')
        self.assertEqual(pruned[0]['state'], 'pruned')
        self.assertEqual(other.resolve(results[0]['raw_payload_ref'])['state'], 'pruned')

    def test_finalization_owns_hit_and_304_bytes_even_after_another_cache_refresh(self):
        for revalidate in (False, True):
            with self.subTest(revalidate=revalidate):
                store = self.store(); cache = api.SnapshotResponseCache(self.root/str(revalidate))
                first = self.fetch(store, cache=cache)
                request = api.HttpRequest(URL, {'accept': 'application/json', 'user-agent': 'local-asset-studio-source-snapshot/1'})
                exchange = ScriptedExchange(api.WireResponse(URL, 304, {'etag': '"fixture"'}, b'')) if revalidate else ScriptedExchange()
                transport = api.BoundedProviderTransport(exchange=exchange, cache=cache, evidence_store=store, refresh=revalidate)
                response = transport(request)
                changed = _civitai_payload(); changed['name'] = 'replacement'
                self.fetch(store, changed, cache=cache, refresh=True)
                transport.finalize(hashlib.sha256(response.body).hexdigest())
                self.assertEqual(transport.raw_payload_ref['sha256'], first['raw_payload_ref']['sha256'])
                self.assertEqual(self.body(store.resolve(transport.raw_payload_ref)), response.body)
                count = store.stats()['observations']; transport.finalize(hashlib.sha256(response.body).hexdigest())
                self.assertEqual(store.stats()['observations'], count)

    def test_cache_failure_keeps_raw_ownership_and_retry_does_not_duplicate_provenance(self):
        store = self.store(); cache = api.SnapshotResponseCache(self.root/'cache')
        transport = api.BoundedProviderTransport(exchange=ScriptedExchange(_json_response(URL, _civitai_payload())), cache=cache, evidence_store=store)
        request = api.HttpRequest(URL, {'accept': 'application/json', 'user-agent': 'local-asset-studio-source-snapshot/1'})
        response = transport(request); receipt = transport.receipt; digest = hashlib.sha256(response.body).hexdigest()
        with patch.object(cache, 'store', side_effect=OSError('cache failure')):
            with self.assertRaises(OSError): transport.finalize(digest)
        self.assertEqual(transport.receipt, receipt)
        with self.assertRaises(RuntimeError): _ = transport.raw_payload_ref
        self.assertEqual(store.stats()['observations'], 1)
        transport.finalize(digest); self.assertEqual(store.stats()['observations'], 1)
        self.assertEqual(store.resolve(transport.raw_payload_ref)['state'], 'available')

    def test_new_raw_exchange_cannot_expose_a_previous_completed_retention_reference(self):
        store = self.store(); transport = None
        def following(request, timeout):
            with self.assertRaises(RuntimeError): _ = transport.raw_payload_ref
            with self.assertRaises(RuntimeError): _ = transport.receipt
            changed = _civitai_payload(); changed['name'] = 'following response'
            return _json_response(URL, changed)
        transport = api.BoundedProviderTransport(evidence_store=store,
            exchange=ScriptedExchange(_json_response(URL, _civitai_payload()), following))
        first = api.fetch_civitai(123, transport)
        request = api.HttpRequest(URL, {'accept': 'application/json', 'user-agent': 'local-asset-studio-source-snapshot/1'})
        response = transport(request)
        transport.finalize(hashlib.sha256(response.body).hexdigest())
        self.assertNotEqual(transport.raw_payload_ref['sha256'], first['raw_payload_ref']['sha256'])

    def test_abort_and_invalid_provider_identity_never_retain_unvalidated_response(self):
        store = self.store(); invalid = _civitai_payload(); invalid['id'] = 456
        with self.assertRaises(ValueError): self.fetch(store, invalid)
        transport = api.BoundedProviderTransport(exchange=ScriptedExchange(_json_response(URL, _civitai_payload())), evidence_store=store)
        request = api.HttpRequest(URL, {'accept': 'application/json', 'user-agent': 'local-asset-studio-source-snapshot/1'})
        response = transport(request); transport.abort()
        with self.assertRaises(RuntimeError): transport.finalize(hashlib.sha256(response.body).hexdigest())
        self.assertEqual(store.stats()['payloads'], 0)

    def test_legacy_refs_match_only_their_original_body_and_never_fetch(self):
        cache = api.SnapshotResponseCache(self.root/'cache'); result = self.fetch(None, cache=cache)
        legacy = {'sha256': result['snapshot']['raw_payload_sha256'], 'cache_key': result['transport_receipt']['request_key'], 'retained_in_cache': True}
        request = api.HttpRequest(URL, {'accept': 'application/json', 'user-agent': 'local-asset-studio-source-snapshot/1'})
        resolved = api.resolve_payload_reference(legacy, cache=cache, request=request)
        self.assertEqual(resolved['state'], 'available'); self.assertEqual(resolved['source'], 'legacy-mutable-cache')
        changed = _civitai_payload(); changed['name'] = 'changed'
        self.fetch(None, changed, cache=cache, refresh=True)
        self.assertEqual(api.resolve_payload_reference(legacy, cache=cache, request=request)['state'], 'legacy_unavailable')
        self.assertEqual(self.fetch(None)['raw_payload_ref']['retention_state'], 'disabled')

    def test_tampered_provenance_wrong_store_and_oversize_reads_fail_closed(self):
        store = self.store(); ref = self.fetch(store)['raw_payload_ref']
        with tempfile.TemporaryDirectory() as elsewhere:
            self.assertEqual(api.SnapshotEvidenceStore(elsewhere).resolve(ref)['state'], 'store_mismatch')
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute('UPDATE observations SET document=? WHERE id=?', ('x'*140000, ref['observation_id']))
        self.assertEqual(store.resolve(ref)['state'], 'corrupt')
        with self.assertRaises(ValueError): api.SnapshotEvidenceStore(self.root/'evidence', policy=api.EvidencePolicy(max_payloads=1))

    def test_wrong_sqlite_storage_classes_are_corrupt_even_when_bytes_match(self):
        for field in ('document', 'body'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                store = api.SnapshotEvidenceStore(root); ref = self.fetch(store)['raw_payload_ref']
                with closing(sqlite3.connect(store.path)) as db, db:
                    if field == 'document':
                        db.execute('UPDATE observations SET document=CAST(document AS BLOB) WHERE id=?', (ref['observation_id'],))
                        raw = db.execute('SELECT document FROM observations WHERE id=?', (ref['observation_id'],)).fetchone()[0]
                        self.assertIsInstance(raw, bytes)
                        self.assertEqual(hashlib.sha256(raw).hexdigest(), ref['observation_id'])
                    else:
                        db.execute('UPDATE payloads SET body=CAST(body AS TEXT) WHERE sha256=?', (ref['sha256'],))
                        raw = db.execute('SELECT body FROM payloads WHERE sha256=?', (ref['sha256'],)).fetchone()[0]
                        self.assertIsInstance(raw, str)
                        self.assertEqual(hashlib.sha256(raw.encode('utf-8')).hexdigest(), ref['sha256'])
                self.assertEqual(api.SnapshotEvidenceStore(root).resolve(ref)['state'], 'corrupt')

    def test_credential_and_payload_limits_refuse_before_any_evidence_commit(self):
        store = self.store(); exchange = ScriptedExchange(AssertionError('credential request escaped'))
        transport = api.BoundedProviderTransport(exchange=exchange, evidence_store=store)
        with self.assertRaises(ValueError):
            transport(api.HttpRequest(URL, {'accept': 'application/json', 'user-agent': 'local-asset-studio-source-snapshot/1', 'authorization': 'secret'}))
        limited = api.BoundedProviderTransport(exchange=ScriptedExchange(_json_response(URL, _civitai_payload())),
            evidence_store=store, policy=api.MetadataPolicy(max_response_bytes=10))
        with self.assertRaises(ValueError): api.fetch_civitai(123, limited)
        self.assertEqual(store.stats()['observations'], 0)
        for limit in ({'max_total_bytes': True}, {'max_payloads': 0}, {'max_observations': 100001}):
            with self.assertRaises(ValueError): api.EvidencePolicy(**limit)

    def test_provenance_byte_budget_does_not_turn_valid_metadata_into_a_parse_failure(self):
        store = self.store()
        headers = {key: '\U0001f600'*8192 for key in ('etag', 'last-modified', 'x-request-id',
                   'x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-reset', 'retry-after')}
        result = api.fetch_civitai(123, api.BoundedProviderTransport(evidence_store=store,
            exchange=ScriptedExchange(_json_response(URL, _civitai_payload(), headers=headers))))
        self.assertEqual(result['snapshot']['record']['provider_version_id'], 123)
        self.assertEqual(result['raw_payload_ref']['retention_state'], 'quota_exceeded')
        self.assertEqual(store.stats()['observations'], 0)


if __name__ == '__main__': unittest.main()
