"""Reject endpoint spellings that parsing or joining would silently reinterpret."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt._adult_illustration_source_transport_common import (
    HttpRequest, USER_AGENT, endpoint_provider,
)
from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport, SnapshotResponseCache, WireResponse, fetch_civitai,
    fetch_huggingface,
)
from tests.test_adult_illustration_source_transport import (
    HF_COMMIT, ScriptedExchange, _civitai_payload, _hf_payload, _json_response,
)

CIVITAI = "https://civitai.com/api/v1/model-versions/123"
HF = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
HEADERS = {"accept": "application/json", "user-agent": USER_AGENT}


class ProviderEndpointIdentityTests(unittest.TestCase):
    def test_semicolon_parameters_are_not_an_allowlisted_endpoint(self):
        for url in (CIVITAI + ";download=true", HF.replace("main?", "main;ignored?")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                endpoint_provider(url)

    def test_url_parser_cannot_erase_invalid_spelling(self):
        urls = [
            " " + CIVITAI, "\x00" + CIVITAI, CIVITAI + "#",
            CIVITAI.replace("123", "12\t3"), CIVITAI.replace("123", "12\n3"),
            CIVITAI.replace("https://", "https://@"),
            CIVITAI.replace("civitai.com", "civitai.com:"),
            HF.replace("main?", "..?"), HF.replace("main?", "%2e%2e?"),
            HF.replace("main?", "broken%escape?"),
        ]
        for url in urls:
            with self.subTest(url=repr(url)), self.assertRaises(ValueError):
                endpoint_provider(url)

    def test_invalid_initial_endpoint_is_refused_before_exchange(self):
        for url in (CIVITAI + ";ignored", CIVITAI.replace("123", "12\t3")):
            with self.subTest(url=url):
                exchange = ScriptedExchange(_json_response(url, _civitai_payload()))
                transport = BoundedProviderTransport(exchange=exchange)
                with self.assertRaises(ValueError):
                    transport(HttpRequest(url, HEADERS))
                self.assertEqual(exchange.calls, [])

    def test_redirect_join_cannot_repair_an_unreviewed_reference(self):
        references = [
            "/api/v1/model-versions/123;ignored",
            "/api/v1/model-versions/12\t3",
            "/api/v1/model-versions/extra/../123",
            "./123", "https:/api/v1/model-versions/123", "#",
            "https://@civitai.com/api/v1/model-versions/123",
        ]
        for location in references:
            with self.subTest(location=repr(location)), tempfile.TemporaryDirectory() as directory:
                def unexpected_follow(request, timeout):
                    return _json_response(request.url, _civitai_payload())
                exchange = ScriptedExchange(
                    WireResponse(CIVITAI, 302, {"location": location}, b""),
                    unexpected_follow,
                )
                transport = BoundedProviderTransport(
                    exchange=exchange, cache=SnapshotResponseCache(directory),
                )
                with self.assertRaises(ValueError):
                    fetch_civitai(123, transport)
                self.assertEqual(len(exchange.calls), 1)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_cache_reentry_rechecks_full_endpoint_spelling(self):
        for changed in (CIVITAI + ";ignored", CIVITAI.replace("123", "12\t3")):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                cache = SnapshotResponseCache(directory)
                fetch_civitai(123, BoundedProviderTransport(
                    exchange=ScriptedExchange(_json_response(CIVITAI, _civitai_payload())),
                    cache=cache,
                ))
                path = cache.path_for(HttpRequest(CIVITAI, HEADERS))
                record = json.loads(path.read_bytes())
                record["response"]["final_url"] = changed
                record["response"]["redirect_chain"] = [changed]
                path.write_text(json.dumps(record), encoding="utf-8")
                exchange = ScriptedExchange()
                with self.assertRaises(ValueError):
                    fetch_civitai(123, BoundedProviderTransport(exchange=exchange, cache=cache))
                self.assertEqual(exchange.calls, [])

    def test_reviewed_urls_and_encoded_revision_components_remain_valid(self):
        for url, provider in (
            (CIVITAI, "civitai"),
            (CIVITAI.replace("civitai.com", "www.civitai.com:443"), "civitai"),
            (HF, "huggingface"),
            (HF.replace("main?", "refs%2Fpr%2F3?"), "huggingface"),
            (HF.replace("main?", "r%C3%A9vision?"), "huggingface"),
        ):
            with self.subTest(url=url):
                self.assertEqual(endpoint_provider(url), provider)

    def test_valid_relative_redirect_retains_exact_route_and_zero_authority(self):
        exact = HF.replace("main?", HF_COMMIT + "?")
        exchange = ScriptedExchange(
            WireResponse(HF, 302, {"location": HF_COMMIT + "?blobs=true"}, b""),
            _json_response(exact, _hf_payload()),
        )
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            result = fetch_huggingface("owner/model", "main", BoundedProviderTransport(exchange=exchange))
        self.assertEqual([call[0].url for call in exchange.calls], [HF, exact])
        receipt = result["transport_receipt"]
        self.assertEqual(receipt["final_url"], exact)
        self.assertEqual(receipt["redirects"], 1)
        self.assertEqual(receipt["authority"], "none")
        self.assertFalse(receipt["execution_authorized"])
        self.assertFalse(receipt["credentials_used"])


if __name__ == "__main__":
    unittest.main()
