"""Provider claims must agree before they become a retained source proposal."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio_prompt import adult_illustration_source_intake as source
from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport, SnapshotResponseCache, WireResponse, fetch_huggingface,
)
from tests.test_adult_illustration_source_intake import (
    HF_SHA, HF_FILE_SHA, hf_payload, civitai_payload,
)


def encoded(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def transport_for(payload, **overrides):
    def transport(request):
        fields = dict(request_url=request.url, final_url=request.url, status=200,
                      headers={"content-type": "application/json"}, body=encoded(payload))
        fields.update(overrides)
        return source.HttpResponse(**fields)
    return transport


def hf(payload=None, revision="main", **response):
    return source.snapshot_huggingface(
        "example-org/example-model", revision,
        transport_for(hf_payload() if payload is None else payload, **response),
    )


class SourceIdentityTests(unittest.TestCase):
    def test_exact_requested_commit_cannot_resolve_to_a_different_commit(self):
        with self.assertRaisesRegex(ValueError, "revision|commit"):
            hf(revision="f" * 40)

    def test_moving_revision_and_case_insensitive_exact_commit_round_trip(self):
        for revision in ("main", "refs/pr/7", HF_SHA.upper()):
            with self.subTest(revision=revision):
                value = hf(revision=revision)
                self.assertEqual(value["record"]["immutable_revision"], HF_SHA)
                self.assertEqual(source.read_snapshot_json(encoded(value)), value)
                self.assertEqual(value["authority"], "none")
                self.assertIs(value["execution_authorized"], False)

    def test_conflicting_top_level_and_lfs_hashes_or_sizes_are_refused(self):
        cases = ({"sha256": "f" * 64}, {"size": 1235})
        for changes in cases:
            with self.subTest(changes=changes):
                payload = hf_payload()
                payload["siblings"][0].update(changes)
                with self.assertRaisesRegex(ValueError, "conflict"):
                    hf(payload)

    def test_shadowed_lfs_claims_are_validated_not_discarded(self):
        for field, invalid in (("sha256", "not-a-hash"), ("size", True), ("size", -1)):
            with self.subTest(field=field, invalid=invalid):
                payload = hf_payload()
                payload["siblings"][0]["sha256"] = HF_FILE_SHA
                payload["siblings"][0]["lfs"][field] = invalid
                with self.assertRaises(ValueError):
                    hf(payload)

    def test_matching_claims_missing_metadata_and_empty_files_still_round_trip(self):
        payload = hf_payload()
        payload["siblings"][0]["sha256"] = HF_FILE_SHA.upper()
        payload["siblings"].extend([
            {"rfilename": "empty.txt", "size": 0},
            {"rfilename": "unknown.txt"},
        ])
        value = hf(payload)
        self.assertEqual(value["record"]["files"][0]["sha256"], HF_FILE_SHA)
        self.assertEqual(source.read_snapshot_json(encoded(value)), value)

    def test_generated_size_cannot_exceed_the_saved_snapshot_contract(self):
        payload = hf_payload()
        payload["siblings"][0]["size"] = 1 << 63
        payload["siblings"][0]["lfs"]["size"] = 1 << 63
        with self.assertRaisesRegex(ValueError, "byte|bound"):
            hf(payload)

    def test_civitai_returned_id_types_are_exact_integers(self):
        for location in ("id", "nested_id"):
            for invalid in (1.0, True):
                with self.subTest(location=location, invalid=invalid):
                    payload = civitai_payload()
                    payload.update(id=1, modelId=1)
                    payload["model"]["id"] = 1
                    if location == "id":
                        payload["id"] = invalid
                    else:
                        payload["model"]["id"] = invalid
                    with self.assertRaises(ValueError):
                        source.snapshot_civitai(1, transport_for(payload))

    def test_stored_request_is_bound_to_its_provider_record(self):
        values = [hf(), source.snapshot_civitai(654321, transport_for(civitai_payload()))]
        for original in values:
            value = copy.deepcopy(original)
            value["request"]["url"] = (
                "https://huggingface.co/api/models/other/repo/revision/main?blobs=true"
                if value["provider"] == "huggingface" else
                "https://civitai.com/api/v1/model-versions/1"
            )
            with self.subTest(provider=value["provider"]):
                with self.assertRaisesRegex(ValueError, "request.*identity"):
                    source.read_snapshot_json(encoded(value))
                with self.assertRaises(ValueError):
                    source.diff_snapshots(original, value)

    def test_stored_immutable_request_and_http_status_types_are_rechecked(self):
        original = hf(revision=HF_SHA)
        mutations = [
            lambda value: value["record"].update(requested_revision="f" * 40),
            lambda value: value["response"].update(status=200.0),
        ]
        for mutate in mutations:
            value = copy.deepcopy(original)
            mutate(value)
            with self.subTest(value=value["response"]["status"]):
                with self.assertRaises(ValueError):
                    source.read_snapshot_json(encoded(value))

    def test_live_and_saved_response_routes_cannot_claim_unobserved_identity(self):
        original = hf()
        wrong = "https://huggingface.co/api/models/other/repo/revision/main?blobs=true"
        cases = [
            dict(final_url=wrong, redirect_chain=(wrong,)),
            dict(final_url=original["request"]["url"], redirect_chain=(wrong,)),
            dict(final_url=wrong),
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, "route|identity|redirect"):
                    hf(**overrides)
                stored = copy.deepcopy(original)
                stored["response"].update(overrides)
                stored["response"]["redirect_chain"] = list(overrides.get("redirect_chain", ()))
                with self.assertRaises(ValueError):
                    source.read_snapshot_json(encoded(stored))

    def test_resolved_commit_redirect_and_civitai_www_remain_valid(self):
        url = f"https://huggingface.co/api/models/example-org/example-model/revision/{HF_SHA}?blobs=true"
        value = hf(final_url=url, redirect_chain=(url,))
        self.assertEqual(source.read_snapshot_json(encoded(value)), value)
        url = "https://www.civitai.com/api/v1/model-versions/654321"
        value = source.snapshot_civitai(654321, transport_for(civitai_payload(), final_url=url, redirect_chain=(url,)))
        self.assertEqual(source.read_snapshot_json(encoded(value)), value)

    def test_conflict_refuses_before_cache_publication_without_retry(self):
        payload = hf_payload()
        payload["siblings"][0]["sha256"] = "f" * 64
        calls = []
        def exchange(request, timeout):
            calls.append(request.url)
            return WireResponse(request.url, 200, {"content-type": "application/json"}, encoded(payload))
        with tempfile.TemporaryDirectory() as directory:
            transport = BoundedProviderTransport(exchange=exchange, cache=SnapshotResponseCache(directory))
            with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(ValueError, "conflict"):
                    fetch_huggingface("example-org/example-model", "main", transport)
            self.assertEqual(len(calls), 1)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
