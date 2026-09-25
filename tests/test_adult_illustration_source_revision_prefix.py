"""Issue #804: abbreviated Hugging Face commits bind as immutable prefixes."""
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
        with self.assertRaises(ValueError):
            source.read_snapshot_json(_encode(mutated))


if __name__ == "__main__":
    unittest.main()
