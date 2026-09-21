"""Every returned response owns its receipt, independently of pending cache writes."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt import adult_illustration_source_transport as api
from tests.test_adult_illustration_source_transport import (
    ScriptedExchange, _hf_payload, _json_response,
)

URL = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
PIN_URL = "https://huggingface.co/api/models/owner/model/revision/" + "a" * 40 + "?blobs=true"


class RawFinalizationOwnershipTests(unittest.TestCase):
    def response_owner(self, mode):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        cache = None if mode == "disabled" else api.SnapshotResponseCache(temporary.name)
        request = api.HttpRequest(URL, {
            "accept": "application/json",
            "user-agent": "local-asset-studio-source-snapshot/1",
        })
        if mode in {"hit", "revalidated"}:
            seed = api.BoundedProviderTransport(
                exchange=ScriptedExchange(_json_response(URL, _hf_payload(), headers={"etag": '"fixture"'})),
                cache=cache,
            )
            api.fetch_huggingface("owner/model", "main", seed)
        replies = []
        if mode == "revalidated":
            replies.append(api.WireResponse(URL, 304, {"etag": '"fixture"'}, b""))
        elif mode != "hit":
            replies.append(_json_response(URL, _hf_payload()))
        replies.append(_json_response(PIN_URL, _hf_payload()))
        exchange = ScriptedExchange(*replies)
        transport = api.BoundedProviderTransport(
            exchange=exchange, cache=cache, refresh=mode == "revalidated",
        )
        response = transport(request)
        self.assertEqual(transport.receipt["cache_state"], mode)
        return transport, response, exchange, Path(temporary.name)

    def test_facade_refuses_every_unfinalized_response_without_changing_its_receipt(self):
        for mode in ("disabled", "miss", "hit", "revalidated"):
            with self.subTest(mode=mode):
                transport, response, exchange, root = self.response_owner(mode)
                receipt = transport.receipt
                before = {p.name: p.read_bytes() for p in root.glob("*.json")}
                calls = len(exchange.calls)
                with self.assertRaisesRegex(RuntimeError, "not finalized"):
                    api.fetch_huggingface("owner/model", "a" * 40, transport)
                self.assertEqual(transport.receipt, receipt)
                self.assertEqual(len(exchange.calls), calls)
                self.assertEqual({p.name: p.read_bytes() for p in root.glob("*.json")}, before)
                transport.finalize(hashlib.sha256(response.body).hexdigest())
                with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
                    result = api.fetch_huggingface("owner/model", "a" * 40, transport)
                self.assertEqual(result["transport_receipt"]["request_url"], PIN_URL)
                self.assertEqual(result["snapshot"]["request"]["url"], PIN_URL)

    def test_raw_request_also_refuses_to_replace_an_unfinalized_receipt(self):
        for mode in ("disabled", "miss", "hit", "revalidated"):
            with self.subTest(mode=mode):
                transport, response, exchange, _ = self.response_owner(mode)
                receipt = transport.receipt
                calls = len(exchange.calls)
                second = api.HttpRequest(PIN_URL, {
                    "accept": "application/json",
                    "user-agent": "local-asset-studio-source-snapshot/1",
                })
                with self.assertRaisesRegex(RuntimeError, "not finalized"):
                    transport(second)
                self.assertEqual(transport.receipt, receipt)
                self.assertEqual(len(exchange.calls), calls)
                transport.abort()
                with self.assertRaises(RuntimeError):
                    _ = transport.receipt
                next_response = transport(second)
                transport.finalize(hashlib.sha256(next_response.body).hexdigest())
                self.assertEqual(transport.receipt["request_url"], PIN_URL)

    def test_failed_digest_finalization_invalidates_its_receipt_and_allows_recovery(self):
        transport, _, _, _ = self.response_owner("disabled")
        with self.assertRaisesRegex(ValueError, "identity does not match"):
            transport.finalize("0" * 64)
        with self.assertRaises(RuntimeError):
            _ = transport.receipt
        result = api.fetch_huggingface("owner/model", "a" * 40, transport)
        self.assertEqual(result["transport_receipt"]["request_url"], PIN_URL)

    def test_cache_write_failure_preserves_raw_ownership_until_explicit_abort(self):
        transport, response, exchange, _ = self.response_owner("miss")
        receipt = transport.receipt
        with mock.patch.object(transport.cache, "store", side_effect=OSError("fixture disk full")):
            with self.assertRaises(OSError):
                transport.finalize(hashlib.sha256(response.body).hexdigest())
        with self.assertRaisesRegex(RuntimeError, "not finalized"):
            api.fetch_huggingface("owner/model", "a" * 40, transport)
        self.assertEqual(transport.receipt, receipt)
        self.assertEqual(len(exchange.calls), 1)
        transport.abort()
        self.assertEqual(api.fetch_huggingface("owner/model", "a" * 40, transport)["transport_receipt"]["request_url"], PIN_URL)


if __name__ == "__main__":
    unittest.main()
