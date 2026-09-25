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
    fetch_civitai,
    fetch_huggingface,
)


HF_URL = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
HF_COMMIT = "a" * 40
CIVITAI_URL = "https://civitai.com/api/v1/model-versions/123"
CIVITAI_HEADERS = {
    "accept": "application/json",
    "user-agent": "local-asset-studio-source-snapshot/1",
}
FILE_SHA = "b" * 64


def _civitai_payload() -> dict[str, object]:
    return {
        "id": 123,
        "modelId": 9,
        "name": "Version 1",
        "baseModel": "SDXL 1.0",
        "trainedWords": ["example trigger"],
        "model": {
            "id": 9,
            "name": "Example model",
            "type": "Checkpoint",
            "allowNoCredit": False,
            "allowCommercialUse": "Image",
            "allowDerivatives": True,
            "allowDifferentLicense": False,
        },
        "files": [
            {
                "id": 55,
                "name": "model.safetensors",
                "sizeKB": 1.0,
                "hashes": {"SHA256": FILE_SHA},
                "primary": True,
            }
        ],
    }


def _civitai_json_response(url: str, payload: object) -> WireResponse:
    return WireResponse(
        url=url,
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
    )


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
        headers={
            "content-type": "application/json",
            "etag": '"v1"',
        },
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

    def test_304_must_not_change_the_cached_metadata_route(self) -> None:
        redirect_url = (
            "https://huggingface.co/api/models/owner/model/revision/"
            + HF_COMMIT
            + "?blobs=true"
        )
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            cache.store(_request(), _response())
            exchange = ScriptedExchange(
                WireResponse(
                    url=HF_URL,
                    status=302,
                    headers={"location": redirect_url},
                    body=b"",
                ),
                WireResponse(
                    url=redirect_url,
                    status=304,
                    headers={"etag": '"v1"'},
                    body=b"",
                ),
            )
            with self.assertRaisesRegex(ValueError, "304.*route|route.*304"):
                fetch_huggingface(
                    "owner/model",
                    "main",
                    BoundedProviderTransport(
                        exchange=exchange,
                        cache=SnapshotResponseCache(Path(tmp)),
                        refresh=True,
                    ),
                )
            self.assertEqual(len(exchange.calls), 2)

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

    def test_civitai_bare_query_delimiter_is_refused_before_exchange(self) -> None:
        exchange = ScriptedExchange()
        transport = BoundedProviderTransport(exchange=exchange)
        with self.assertRaisesRegex(ValueError, "not a supported metadata endpoint"):
            transport(HttpRequest(url=CIVITAI_URL + "?", headers=dict(CIVITAI_HEADERS)))
        self.assertEqual(exchange.calls, [])

    def test_civitai_bare_query_redirect_is_refused_without_follow(self) -> None:
        exchange = ScriptedExchange(
            WireResponse(
                url=CIVITAI_URL,
                status=302,
                headers={"location": "?"},
                body=b"",
            ),
            _civitai_json_response(CIVITAI_URL + "?", _civitai_payload()),
        )
        with self.assertRaisesRegex(ValueError, "empty query"):
            fetch_civitai(123, BoundedProviderTransport(exchange=exchange))
        self.assertEqual(len(exchange.calls), 1)


if __name__ == "__main__":
    unittest.main()
