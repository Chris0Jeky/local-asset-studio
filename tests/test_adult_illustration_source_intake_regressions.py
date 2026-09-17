import copy
import json
import unittest

from studio_prompt import adult_illustration_source_intake as source

HF_SHA = "b" * 40
HF_FILE_SHA = "a" * 64
CIVITAI_SHA = "d" * 64


def _encode(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _hf_payload():
    return {
        "id": "example-org/example-model",
        "sha": HF_SHA,
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


def _civitai_payload(size_kb=1024.0):
    return {
        "id": 654321,
        "modelId": 123456,
        "model": {"id": 123456},
        "files": [
            {
                "id": 998877,
                "name": "example.safetensors",
                "sizeKB": size_kb,
                "hashes": {"SHA256": CIVITAI_SHA},
            }
        ],
    }


class _Transport:
    def __init__(self, url, payload):
        self.url = url
        self.payload = payload

    def __call__(self, request):
        return source.HttpResponse(
            request_url=request.url,
            final_url=request.url,
            status=200,
            headers={"content-type": "application/json"},
            body=_encode(self.payload),
        )


class AdultIllustrationSourceIntakeRegressionTests(unittest.TestCase):
    def _hf(self, payload=None):
        url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        return source.snapshot_huggingface(
            "example-org/example-model",
            "main",
            _Transport(url, payload or _hf_payload()),
        )

    def test_huggingface_file_identity_survives_reordering_and_insertions(self):
        before = self._hf()
        payload = _hf_payload()
        payload["siblings"] = [
            {"rfilename": "README.md", "size": 42},
            payload["siblings"][1],
            payload["siblings"][0],
        ]
        after = self._hf(payload)

        before_ids = {
            item["path"]: item["id"] for item in before["record"]["files"]
        }
        after_ids = {
            item["path"]: item["id"] for item in after["record"]["files"]
        }
        self.assertEqual(
            before_ids["model.safetensors"], after_ids["model.safetensors"]
        )
        self.assertEqual(before_ids["config.json"], after_ids["config.json"])
        diff = source.diff_snapshots(before, after)
        self.assertEqual(diff["added_files"], ["README.md"])
        self.assertEqual(diff["changed_files"], [])

    def test_stored_snapshot_revalidates_identity_hashes_and_authority(self):
        original = self._hf()
        mutations = []
        for path, value in (
            (("raw_payload_sha256",), "bad"),
            (("record", "immutable_revision"), "main"),
            (("record", "execution_authorized"), True),
            (("record", "files", 0, "sha256"), "bad"),
            (("record", "files", 0, "id"), "hf-file-1"),
        ):
            mutated = copy.deepcopy(original)
            target = mutated
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = value
            mutations.append(mutated)

        credential = copy.deepcopy(original)
        credential["request"]["headers"]["authorization"] = "secret"
        mutations.append(credential)

        for index, mutated in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                source.read_snapshot_json(_encode(mutated))

    def test_civitai_size_is_rejected_before_float_or_integer_overflow(self):
        url = "https://civitai.com/api/v1/model-versions/654321"
        for value in (1e308, 10**400):
            with self.subTest(value_type=type(value).__name__), self.assertRaisesRegex(
                ValueError, "sizeKB"
            ):
                source.snapshot_civitai(
                    654321,
                    _Transport(url, _civitai_payload(value)),
                )


if __name__ == "__main__":
    unittest.main()
