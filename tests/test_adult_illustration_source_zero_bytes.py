"""Provider compatibility regression for legitimate zero-byte Hub files."""
from __future__ import annotations

import json
import unittest

from studio_prompt import adult_illustration_source_intake as source


class HuggingFaceZeroByteFileTests(unittest.TestCase):
    def test_snapshot_accepts_a_zero_byte_repository_file(self):
        repo_id = "example-org/example-model"
        revision = "main"
        url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        payload = {
            "id": repo_id,
            "sha": "b" * 40,
            "private": False,
            "gated": False,
            "cardData": {},
            "siblings": [{"rfilename": "STABLE", "size": 0}],
        }

        def transport(request):
            self.assertEqual(request.url, url)
            return source.HttpResponse(
                request_url=url,
                final_url=url,
                status=200,
                headers={"content-type": "application/json"},
                body=json.dumps(payload).encode("utf-8"),
            )

        snapshot = source.snapshot_huggingface(repo_id, revision, transport)
        self.assertEqual(snapshot["record"]["files"][0]["bytes"], 0)


if __name__ == "__main__":
    unittest.main()
