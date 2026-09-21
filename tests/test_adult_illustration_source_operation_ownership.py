"""A shared transport must not mix one fetch's snapshot with another receipt."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from studio_prompt import adult_illustration_source_transport as api
from tests.test_adult_illustration_source_transport import (
    ScriptedExchange, _hf_payload, _civitai_payload, _json_response,
)

HF_URL = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
PIN_URL = "https://huggingface.co/api/models/owner/model/revision/" + "a" * 40 + "?blobs=true"
CIV_URL = "https://civitai.com/api/v1/model-versions/123"


class SourceOperationOwnershipTests(unittest.TestCase):
    def test_overlapping_fetch_refuses_without_aborting_the_owning_operation(self):
        for cached in (False, True):
            with self.subTest(cached=cached), tempfile.TemporaryDirectory() as directory:
                exchange = ScriptedExchange(
                    _json_response(HF_URL, _hf_payload()),
                    _json_response(PIN_URL, _hf_payload()),
                )
                cache = api.SnapshotResponseCache(directory) if cached else None
                transport = api.BoundedProviderTransport(exchange=exchange, cache=cache)
                ready, release = threading.Event(), threading.Event()
                completed, errors = [], []
                original = api._fetch_result

                def held_result(snapshot, active):
                    if snapshot["request"]["url"] == HF_URL:
                        ready.set()
                        if not release.wait(5):
                            raise AssertionError("owner release was not signalled")
                    return original(snapshot, active)

                def owner():
                    try:
                        completed.append(api.fetch_huggingface("owner/model", "main", transport))
                    except BaseException as exc:
                        errors.append(exc)

                with mock.patch.object(api, "_fetch_result", held_result):
                    thread = threading.Thread(target=owner)
                    thread.start()
                    try:
                        self.assertTrue(ready.wait(5), "owner did not reach result boundary")
                        with self.assertRaisesRegex(RuntimeError, "already in use"):
                            api.fetch_huggingface("owner/model", "a" * 40, transport)
                    finally:
                        release.set()
                        thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(len(completed), 1)
                first = completed[0]
                self.assertEqual(first["snapshot"]["request"]["url"], HF_URL)
                self.assertEqual(first["transport_receipt"]["request_url"], HF_URL)
                self.assertEqual(len(exchange.calls), 1)
                if cached:
                    self.assertEqual(len(list(Path(directory).glob("*.json"))), 1)
                second = api.fetch_huggingface("owner/model", "a" * 40, transport)
                self.assertEqual(second["transport_receipt"]["request_url"], PIN_URL)
                self.assertEqual(first["transport_receipt"]["request_url"], HF_URL)

    def test_nested_cross_provider_fetch_refuses_without_deadlock_or_state_loss(self):
        nested_errors = []
        transport = None

        def outer_response(request, timeout):
            try:
                api.fetch_civitai(123, transport)
            except RuntimeError as exc:
                nested_errors.append(str(exc))
            return _json_response(request.url, _hf_payload())

        exchange = ScriptedExchange(outer_response, _json_response(CIV_URL, _civitai_payload()))
        transport = api.BoundedProviderTransport(exchange=exchange)
        result = api.fetch_huggingface("owner/model", "main", transport)
        self.assertEqual(len(nested_errors), 1)
        self.assertIn("already in use", nested_errors[0])
        self.assertEqual(len(exchange.calls), 1)
        self.assertEqual(result["transport_receipt"]["provider"], "huggingface")
        self.assertEqual(api.fetch_civitai(123, transport)["transport_receipt"]["provider"], "civitai")

    def test_failed_fetch_does_not_expose_a_previous_success_as_its_receipt(self):
        exchange = ScriptedExchange(
            _json_response(HF_URL, _hf_payload()), TimeoutError("fixture timeout"),
            _json_response(CIV_URL, _civitai_payload()),
        )
        transport = api.BoundedProviderTransport(exchange=exchange, policy=api.MetadataPolicy(max_attempts=1))
        first = api.fetch_huggingface("owner/model", "main", transport)
        retained = copy.deepcopy(first)
        with self.assertRaisesRegex(ValueError, "after 1 attempt"):
            api.fetch_civitai(123, transport)
        with self.assertRaises(RuntimeError):
            _ = transport.receipt
        self.assertEqual(first, retained)
        recovered = api.fetch_civitai(123, transport)
        self.assertEqual(recovered["transport_receipt"]["request_url"], CIV_URL)
        self.assertEqual(transport.receipt, recovered["transport_receipt"])

    def test_invalid_input_or_provider_identity_releases_ownership_without_publishing(self):
        for failure in ("argument", "identity"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                invalid = _civitai_payload()
                invalid["id"] = 456
                steps = [_json_response(HF_URL, _hf_payload())]
                if failure == "identity":
                    steps.append(_json_response(CIV_URL, invalid))
                steps.append(_json_response(CIV_URL, _civitai_payload()))
                exchange = ScriptedExchange(*steps)
                transport = api.BoundedProviderTransport(exchange=exchange, cache=api.SnapshotResponseCache(directory))
                api.fetch_huggingface("owner/model", "main", transport)
                before = {path.name: path.read_bytes() for path in Path(directory).glob("*.json")}
                with self.assertRaises(ValueError):
                    api.fetch_civitai(-1 if failure == "argument" else 123, transport)
                with self.assertRaises(RuntimeError):
                    _ = transport.receipt
                self.assertEqual({path.name: path.read_bytes() for path in Path(directory).glob("*.json")}, before)
                self.assertEqual(api.fetch_civitai(123, transport)["snapshot"]["record"]["provider"], "civitai")

    def test_unfinalized_raw_response_is_not_aborted_by_a_refused_facade_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = api.SnapshotResponseCache(directory)
            exchange = ScriptedExchange(_json_response(HF_URL, _hf_payload()))
            transport = api.BoundedProviderTransport(exchange=exchange, cache=cache)
            request = api.HttpRequest(HF_URL, {"accept": "application/json", "user-agent": "local-asset-studio-source-snapshot/1"})
            response = transport(request)
            receipt = transport.receipt
            with self.assertRaises(RuntimeError):
                api.fetch_civitai(123, transport)
            self.assertEqual(transport.receipt, receipt)
            transport.finalize(hashlib.sha256(response.body).hexdigest())
            self.assertEqual(cache.load(request), response)
            self.assertEqual(len(exchange.calls), 1)

    def test_interruption_releases_ownership_and_discards_unfinalized_response(self):
        with tempfile.TemporaryDirectory() as directory:
            exchange = ScriptedExchange(*[_json_response(HF_URL, _hf_payload()) for _ in range(2)])
            transport = api.BoundedProviderTransport(exchange=exchange, cache=api.SnapshotResponseCache(directory))
            with mock.patch.object(api, "_fetch_result", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    api.fetch_huggingface("owner/model", "main", transport)
            with self.assertRaises(RuntimeError):
                _ = transport.receipt
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertEqual(api.fetch_huggingface("owner/model", "main", transport)["transport_receipt"]["request_url"], HF_URL)

    def test_cache_publication_failure_releases_only_its_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = api.SnapshotResponseCache(directory)
            exchange = ScriptedExchange(*[_json_response(HF_URL, _hf_payload()) for _ in range(2)])
            transport = api.BoundedProviderTransport(exchange=exchange, cache=cache)
            with mock.patch.object(cache, "store", side_effect=OSError("fixture disk full")):
                with self.assertRaises(OSError):
                    api.fetch_huggingface("owner/model", "main", transport)
            with self.assertRaises(RuntimeError):
                _ = transport.receipt
            self.assertEqual(list(Path(directory).iterdir()), [])
            result = api.fetch_huggingface("owner/model", "main", transport)
            self.assertEqual(result["transport_receipt"]["request_url"], HF_URL)
            self.assertFalse(result["execution_authorized"])
            self.assertFalse(result["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
