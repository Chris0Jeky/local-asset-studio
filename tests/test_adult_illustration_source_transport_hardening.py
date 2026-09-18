from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_source_intake import HttpRequest, HttpResponse
from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport,
    MetadataPolicy,
    SnapshotResponseCache,
    WireResponse,
    fetch_huggingface,
)


HF_URL = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
HF_COMMIT = "a" * 40


def _request() -> HttpRequest:
    return HttpRequest(
        url=HF_URL,
        headers={
            "accept": "application/json",
            "user-agent": "local-asset-studio-source-snapshot/1",
        },
    )


def _body() -> bytes:
    return json.dumps(
        {
            "id": "owner/model",
            "sha": HF_COMMIT,
            "private": False,
            "gated": False,
            "siblings": [],
        }
    ).encode("utf-8")


def _response() -> HttpResponse:
    return HttpResponse(
        request_url=HF_URL,
        final_url=HF_URL,
        status=200,
        headers={"content-type": "application/json"},
        body=_body(),
        redirect_chain=(),
    )


class ScriptedExchange:
    def __init__(self, *responses: WireResponse):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected exchange")
        return self.responses.pop(0)


class SourceTransportHardeningTests(unittest.TestCase):
    def test_cache_rejects_cross_provider_final_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            request = _request()
            cache.store(request, _response())
            path = cache.path_for(request)
            value = json.loads(path.read_text(encoding="utf-8"))
            value["response"]["final_url"] = (
                "https://civitai.com/api/v1/model-versions/123"
            )
            path.write_text(json.dumps(value), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "provider|endpoint|cache"):
                cache.load(request)

    def test_cache_rejects_non_metadata_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            request = _request()
            cache.store(request, _response())
            path = cache.path_for(request)
            value = json.loads(path.read_text(encoding="utf-8"))
            value["response"]["redirect_chain"] = [
                "https://huggingface.co/owner/model/resolve/main/model.safetensors"
            ]
            path.write_text(json.dumps(value), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "metadata|redirect|cache"):
                cache.load(request)

    def test_cache_hit_must_obey_current_response_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            cache.store(_request(), _response())
            exchange = ScriptedExchange()
            with self.assertRaisesRegex(ValueError, "response.*exceeds|byte"):
                fetch_huggingface(
                    "owner/model",
                    "main",
                    BoundedProviderTransport(
                        exchange=exchange,
                        cache=SnapshotResponseCache(Path(tmp)),
                        policy=MetadataPolicy(
                            max_response_bytes=len(_body()) - 1,
                        ),
                    ),
                )
            self.assertEqual(exchange.calls, [])

    def test_cache_hit_must_obey_current_redirect_limit(self) -> None:
        redirect_url = (
            "https://huggingface.co/api/models/owner/model/revision/"
            + HF_COMMIT
            + "?blobs=true"
        )
        response = HttpResponse(
            request_url=HF_URL,
            final_url=redirect_url,
            status=200,
            headers={"content-type": "application/json"},
            body=_body(),
            redirect_chain=(redirect_url,),
        )
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            cache.store(_request(), response)
            exchange = ScriptedExchange()
            with self.assertRaisesRegex(ValueError, "redirect"):
                fetch_huggingface(
                    "owner/model",
                    "main",
                    BoundedProviderTransport(
                        exchange=exchange,
                        cache=SnapshotResponseCache(Path(tmp)),
                        policy=MetadataPolicy(max_redirects=0),
                    ),
                )
            self.assertEqual(exchange.calls, [])

    def test_rate_limit_response_retries_get_and_succeeds(self) -> None:
        rate_limited = WireResponse(
            url=HF_URL,
            status=429,
            headers={
                "content-type": "application/json",
                "retry-after": "1",
            },
            body=b'{"error":"rate limited"}',
        )
        success = WireResponse(
            url=HF_URL,
            status=200,
            headers={"content-type": "application/json"},
            body=_body(),
        )
        exchange = ScriptedExchange(rate_limited, success)
        sleeps = []
        result = fetch_huggingface(
            "owner/model",
            "main",
            BoundedProviderTransport(
                exchange=exchange,
                sleeper=sleeps.append,
            ),
        )

        self.assertEqual(result["transport_receipt"]["attempts"], 2)
        self.assertEqual(len(exchange.calls), 2)
        self.assertEqual(sleeps, [0.25])

    def test_existing_output_refuses_before_any_exchange(self) -> None:
        from scripts.studio_adult_illustration_source_fetch import main

        exchange = ScriptedExchange(
            WireResponse(
                url=HF_URL,
                status=200,
                headers={"content-type": "application/json"},
                body=_body(),
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fetch.json"
            output.write_text("existing", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = main(
                    [
                        "huggingface",
                        "--repo",
                        "owner/model",
                        "--revision",
                        "main",
                        "--allow-network",
                        "--out",
                        str(output),
                    ],
                    exchange=exchange,
                )

        self.assertEqual(status, 2)
        self.assertEqual(exchange.calls, [])
        self.assertIn("already exists", json.loads(stderr.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
