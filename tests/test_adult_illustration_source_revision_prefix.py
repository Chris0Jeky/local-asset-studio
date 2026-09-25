"""Issue #804: abbreviated Hugging Face commits bind as immutable prefixes.

Issue #1017: a hex-named moving branch must be selected with an explicit
``refs/heads/<hex-name>`` ref; an unqualified 7-39-hex revision stays a
commit prefix and keeps rejecting an unrelated resolved SHA.
"""
from __future__ import annotations

import copy
import json
import unittest

from studio_prompt import adult_illustration_source_intake as source

HF_SHA = "abcdef1234567890abcdef1234567890abcdef12"
HF_FILE_SHA = "a" * 64
REPO = "example-org/example-model"


def _encode(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _hf_payload(sha=HF_SHA):
    return {
        "id": REPO,
        "sha": sha,
        "private": False,
        "gated": False,
        "cardData": {"license": "apache-2.0"},
        "siblings": [
            {
                "rfilename": "model.safetensors",
                "size": 1234,
                "lfs": {"sha256": HF_FILE_SHA, "size": 1234},
            },
            {"rfilename": "config.json", "size": 321},
        ],
    }


def _snapshot(revision, sha=HF_SHA):
    from urllib.parse import quote

    url = (
        f"https://huggingface.co/api/models/{REPO}/revision/"
        f"{quote(revision.strip(), safe='')}?blobs=true"
    )

    def transport(request):
        assert request.url == url
        return source.HttpResponse(
            request_url=request.url,
            final_url=request.url,
            status=200,
            headers={"content-type": "application/json"},
            body=_encode(_hf_payload(sha)),
        )

    return source.snapshot_huggingface(REPO, revision, transport)


class RevisionPrefixTests(unittest.TestCase):
    def test_7_hex_prefix_match_resolves(self):
        value = _snapshot(HF_SHA[:7])
        self.assertEqual(value["record"]["immutable_revision"], HF_SHA)
        self.assertEqual(
            source.read_snapshot_json(_encode(value)),
            value,
        )

    def test_7_hex_prefix_mismatch_fails_before_snapshot(self):
        bad = ("0" if HF_SHA[0] != "0" else "1") * 7
        with self.assertRaisesRegex(ValueError, "conflict"):
            _snapshot(bad)

    def test_39_hex_prefix_match_resolves(self):
        value = _snapshot(HF_SHA[:39])
        self.assertEqual(value["record"]["immutable_revision"], HF_SHA)

    def test_39_hex_prefix_mismatch_fails_before_snapshot(self):
        bad = HF_SHA[:38] + ("0" if HF_SHA[38] != "0" else "1")
        self.assertNotEqual(bad.casefold(), HF_SHA[:39].casefold())
        with self.assertRaisesRegex(ValueError, "conflict"):
            _snapshot(bad)

    def test_prefix_match_is_case_insensitive(self):
        value = _snapshot(HF_SHA[:12].upper())
        self.assertEqual(value["record"]["immutable_revision"], HF_SHA)

    def test_full_40_hex_mismatch_fails(self):
        bad = ("0" if HF_SHA[0] != "0" else "1") + HF_SHA[1:]
        with self.assertRaisesRegex(ValueError, "conflict"):
            _snapshot(bad)

    def test_main_still_resolves_as_moving_ref(self):
        value = _snapshot("main")
        self.assertEqual(value["record"]["immutable_revision"], HF_SHA)

    def test_stored_prefix_mismatch_is_rejected(self):
        value = _snapshot(HF_SHA[:7])
        mutated = copy.deepcopy(value)
        mutated["record"]["immutable_revision"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "conflicts with requested commit"):
            source.read_snapshot_json(_encode(mutated))


class HexNamedBranchTests(unittest.TestCase):
    """Issue #1017: explicit ``refs/heads/<hex-name>`` selects a hex-named branch."""

    HEX_NAME = "deadbeef"
    HEX_BRANCH = "refs/heads/deadbeef"

    def test_unrelated_sha_is_not_in_hex_prefix_family(self):
        self.assertFalse(HF_SHA.casefold().startswith(self.HEX_NAME.casefold()))

    def test_namespaced_hex_branch_resolves_to_unrelated_sha(self):
        from urllib.parse import quote

        expected_url = (
            f"https://huggingface.co/api/models/{REPO}/revision/"
            f"{quote(self.HEX_BRANCH, safe='')}?blobs=true"
        )
        self.assertIn("refs%2Fheads%2Fdeadbeef", expected_url)
        calls: list[str] = []

        def transport(request):
            calls.append(request.url)
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url, expected_url)
            return source.HttpResponse(
                request_url=request.url,
                final_url=request.url,
                status=200,
                headers={"content-type": "application/json"},
                body=_encode(_hf_payload(HF_SHA)),
            )

        value = source.snapshot_huggingface(REPO, self.HEX_BRANCH, transport)
        self.assertEqual(value["record"]["requested_revision"], self.HEX_BRANCH)
        self.assertEqual(value["record"]["immutable_revision"], HF_SHA)
        self.assertEqual(value["request"]["url"], expected_url)
        self.assertEqual(value["response"]["final_url"], expected_url)
        self.assertFalse(value["download_authorized"])
        self.assertFalse(value["record"]["download_authorized"])
        self.assertEqual(calls, [expected_url])
        self.assertEqual(source.read_snapshot_json(_encode(value)), value)

    def test_unqualified_same_hex_rejects_unrelated_sha(self):
        with self.assertRaisesRegex(ValueError, "conflict"):
            _snapshot(self.HEX_NAME, sha=HF_SHA)

    def test_stored_tampering_namespaced_to_unqualified_hex_fails(self):
        from urllib.parse import quote

        value = _snapshot(self.HEX_BRANCH, sha=HF_SHA)
        mutated = copy.deepcopy(value)
        mutated["record"]["requested_revision"] = self.HEX_NAME
        unqualified_url = (
            f"https://huggingface.co/api/models/{REPO}/revision/"
            f"{quote(self.HEX_NAME, safe='')}?blobs=true"
        )
        mutated["request"]["url"] = unqualified_url
        mutated["response"]["final_url"] = unqualified_url
        mutated["response"]["redirect_chain"] = []
        with self.assertRaisesRegex(ValueError, "conflicts with requested commit"):
            source.read_snapshot_json(_encode(mutated))


if __name__ == "__main__":
    unittest.main()
