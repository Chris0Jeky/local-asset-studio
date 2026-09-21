import json
import unittest

from studio_prompt import adult_illustration_source_intake as source


class AdultIllustrationSourceLanguageTests(unittest.TestCase):
    def test_huggingface_accepts_scalar_model_card_language(self):
        repo_id = "example-org/example-model"
        revision = "main"
        url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        payload = {
            "id": repo_id,
            "sha": "a" * 40,
            "private": False,
            "gated": False,
            "cardData": {"language": "en"},
            "siblings": [],
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
        self.assertEqual(snapshot["record"]["metadata"]["languages"], ["en"])


if __name__ == "__main__":
    unittest.main()
