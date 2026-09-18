from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_source_intake import HttpRequest
from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport,
    MetadataPolicy,
    SnapshotResponseCache,
    WireResponse,
    fetch_civitai,
    fetch_huggingface,
)


HF_COMMIT = "a" * 40
FILE_SHA = "b" * 64


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _hf_payload() -> dict[str, object]:
    return {
        "id": "owner/model",
        "sha": HF_COMMIT,
        "private": False,
        "gated": False,
        "pipeline_tag": "text-to-image",
        "library_name": "diffusers",
        "tags": ["anime", "sdxl"],
        "cardData": {
            "license": "apache-2.0",
            "base_model": "base/model",
            "language": ["en"],
        },
        "siblings": [
            {
                "rfilename": "model.safetensors",
                "size": 1024,
                "sha256": FILE_SHA,
            }
        ],
    }


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


def _json_response(
    url: str,
    payload: object,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> WireResponse:
    values = {"content-type": "application/json; charset=utf-8"}
    values.update(headers or {})
    return WireResponse(url=url, status=status, headers=values, body=_body(payload))


class ScriptedExchange:
    def __init__(self, *steps: object):
        self.steps = list(steps)
        self.calls: list[tuple[HttpRequest, float]] = []

    def __call__(self, request: HttpRequest, timeout: float) -> WireResponse:
        self.calls.append((request, timeout))
        if not self.steps:
            raise AssertionError("Unexpected metadata exchange")
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            return step(request, timeout)
        if not isinstance(step, WireResponse):
            raise AssertionError(f"Unsupported scripted step: {step!r}")
        return step


def _assert_zero_authority(test: unittest.TestCase, value: dict[str, object]) -> None:
    test.assertFalse(value["download_authorized"])
    test.assertFalse(value["install_authorized"])
    test.assertFalse(value["execution_authorized"])
    test.assertFalse(value["generation_submitted"])
    test.assertFalse(value["training_authorized"])


class SourceTransportTests(unittest.TestCase):
    def test_huggingface_fetch_and_exact_cache_hit_share_one_transport_contract(self) -> None:
        url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            exchange = ScriptedExchange(
                _json_response(url, _hf_payload(), headers={"etag": '"hf-v1"'})
            )
            transport = BoundedProviderTransport(exchange=exchange, cache=cache)
            first = fetch_huggingface("owner/model", "main", transport)

            self.assertEqual(first["snapshot"]["record"]["immutable_revision"], HF_COMMIT)
            self.assertEqual(first["transport_receipt"]["cache_state"], "miss")
            self.assertTrue(first["transport_receipt"]["network_performed"])
            self.assertEqual(len(exchange.calls), 1)
            _assert_zero_authority(self, first)
            _assert_zero_authority(self, first["transport_receipt"])

            no_network = ScriptedExchange(AssertionError("cache hit contacted network"))
            cached_transport = BoundedProviderTransport(
                exchange=no_network,
                cache=SnapshotResponseCache(Path(tmp)),
            )
            second = fetch_huggingface("owner/model", "main", cached_transport)

            self.assertEqual(second["snapshot"], first["snapshot"])
            self.assertEqual(second["transport_receipt"]["cache_state"], "hit")
            self.assertFalse(second["transport_receipt"]["network_performed"])
            self.assertEqual(no_network.calls, [])
            self.assertEqual(
                second["raw_payload_ref"]["cache_key"],
                first["raw_payload_ref"]["cache_key"],
            )

    def test_civitai_uses_the_same_transport_and_retains_no_download_authority(self) -> None:
        url = "https://civitai.com/api/v1/model-versions/123"
        exchange = ScriptedExchange(_json_response(url, _civitai_payload()))
        transport = BoundedProviderTransport(exchange=exchange)

        result = fetch_civitai(123, transport)

        self.assertEqual(result["snapshot"]["record"]["provider_version_id"], 123)
        self.assertEqual(result["transport_receipt"]["provider"], "civitai")
        self.assertEqual(result["transport_receipt"]["cache_state"], "disabled")
        _assert_zero_authority(self, result)
        _assert_zero_authority(self, result["snapshot"])

    def test_refresh_sends_cached_validator_and_304_reuses_identical_payload(self) -> None:
        url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            first_exchange = ScriptedExchange(
                _json_response(url, _hf_payload(), headers={"etag": '"hf-v1"'})
            )
            first = fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(exchange=first_exchange, cache=cache),
            )

            def not_modified(request: HttpRequest, timeout: float) -> WireResponse:
                self.assertEqual(request.headers["if-none-match"], '"hf-v1"')
                self.assertEqual(timeout, 15.0)
                return WireResponse(
                    url=url,
                    status=304,
                    headers={"etag": '"hf-v1"'},
                    body=b"",
                )

            refresh_exchange = ScriptedExchange(not_modified)
            refreshed = fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=refresh_exchange,
                    cache=SnapshotResponseCache(Path(tmp)),
                    refresh=True,
                ),
            )

            self.assertEqual(refreshed["snapshot"], first["snapshot"])
            self.assertEqual(
                refreshed["transport_receipt"]["cache_state"], "revalidated"
            )
            self.assertTrue(refreshed["transport_receipt"]["network_performed"])
            self.assertEqual(refreshed["transport_receipt"]["attempts"], 1)

    def test_304_with_conflicting_validator_is_rejected(self) -> None:
        url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=ScriptedExchange(
                        _json_response(
                            url,
                            _hf_payload(),
                            headers={"etag": '"hf-v1"'},
                        )
                    ),
                    cache=cache,
                ),
            )
            stale = ScriptedExchange(
                WireResponse(
                    url=url,
                    status=304,
                    headers={"etag": '"hf-v2"'},
                    body=b"",
                )
            )
            with self.assertRaisesRegex(ValueError, "validator"):
                fetch_huggingface(
                    "owner/model",
                    "main",
                    BoundedProviderTransport(
                        exchange=stale,
                        cache=SnapshotResponseCache(Path(tmp)),
                        refresh=True,
                    ),
                )

    def test_transient_timeout_retries_get_only_with_bounded_policy(self) -> None:
        url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        sleeps: list[float] = []
        exchange = ScriptedExchange(
            TimeoutError("temporary timeout"),
            _json_response(url, _hf_payload()),
        )
        policy = MetadataPolicy(
            timeout_seconds=4.0,
            max_attempts=2,
            retry_backoff_seconds=0.0,
        )
        result = fetch_huggingface(
            "owner/model",
            "main",
            BoundedProviderTransport(
                exchange=exchange,
                policy=policy,
                sleeper=sleeps.append,
            ),
        )

        self.assertEqual(result["transport_receipt"]["attempts"], 2)
        self.assertEqual([timeout for _, timeout in exchange.calls], [4.0, 4.0])
        self.assertEqual(sleeps, [0.0])

    def test_same_provider_metadata_redirect_is_retained(self) -> None:
        first_url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        final_url = (
            "https://huggingface.co/api/models/owner/model/revision/"
            + HF_COMMIT
            + "?blobs=true"
        )
        exchange = ScriptedExchange(
            WireResponse(
                url=first_url,
                status=302,
                headers={"location": final_url},
                body=b"",
            ),
            _json_response(final_url, _hf_payload()),
        )
        result = fetch_huggingface(
            "owner/model",
            "main",
            BoundedProviderTransport(exchange=exchange),
        )

        self.assertEqual(
            result["snapshot"]["response"]["redirect_chain"], [final_url]
        )
        self.assertEqual(result["transport_receipt"]["redirects"], 1)

    def test_cross_provider_and_non_metadata_redirects_are_rejected_before_follow(self) -> None:
        url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        destinations = [
            "https://civitai.com/api/v1/model-versions/123",
            "https://huggingface.co/owner/model/resolve/main/model.safetensors",
        ]
        for destination in destinations:
            with self.subTest(destination=destination):
                exchange = ScriptedExchange(
                    WireResponse(
                        url=url,
                        status=302,
                        headers={"location": destination},
                        body=b"",
                    )
                )
                with self.assertRaisesRegex(ValueError, "redirect|metadata"):
                    fetch_huggingface(
                        "owner/model",
                        "main",
                        BoundedProviderTransport(exchange=exchange),
                    )
                self.assertEqual(len(exchange.calls), 1)

    def test_redirect_count_is_bounded(self) -> None:
        first = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        second = "https://huggingface.co/api/models/owner/model/revision/next?blobs=true"
        third = "https://huggingface.co/api/models/owner/model/revision/final?blobs=true"
        exchange = ScriptedExchange(
            WireResponse(first, 302, {"location": second}, b""),
            WireResponse(second, 302, {"location": third}, b""),
        )
        with self.assertRaisesRegex(ValueError, "redirect"):
            fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=exchange,
                    policy=MetadataPolicy(max_redirects=1),
                ),
            )

    def test_credentials_are_rejected_before_exchange(self) -> None:
        exchange = ScriptedExchange(AssertionError("credentialed request escaped"))
        transport = BoundedProviderTransport(exchange=exchange)
        request = HttpRequest(
            url="https://civitai.com/api/v1/model-versions/123",
            headers={
                "accept": "application/json",
                "user-agent": "local-asset-studio-source-snapshot/1",
                "authorization": "Bearer secret",
            },
        )
        with self.assertRaisesRegex(ValueError, "credential"):
            transport(request)
        self.assertEqual(exchange.calls, [])

    def test_oversized_and_html_payloads_fail_without_cache_write(self) -> None:
        url = "https://civitai.com/api/v1/model-versions/123"
        cases = [
            WireResponse(
                url=url,
                status=200,
                headers={"content-type": "application/json"},
                body=b"x" * 257,
            ),
            WireResponse(
                url=url,
                status=200,
                headers={"content-type": "text/html"},
                body=b"<html></html>",
            ),
        ]
        for response in cases:
            with self.subTest(headers=response.headers), tempfile.TemporaryDirectory() as tmp:
                cache = SnapshotResponseCache(Path(tmp))
                policy = MetadataPolicy(max_response_bytes=256)
                with self.assertRaises(ValueError):
                    fetch_civitai(
                        123,
                        BoundedProviderTransport(
                            exchange=ScriptedExchange(response),
                            cache=cache,
                            policy=policy,
                        ),
                    )
                self.assertEqual(list(Path(tmp).glob("*.json")), [])

    def test_cache_tampering_is_detected_before_network_or_parsing(self) -> None:
        url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            exchange = ScriptedExchange(_json_response(url, _hf_payload()))
            fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(exchange=exchange, cache=cache),
            )
            cache_path = cache.path_for(exchange.calls[0][0])
            record = json.loads(cache_path.read_text(encoding="utf-8"))
            record["body_sha256"] = "0" * 64
            cache_path.write_text(json.dumps(record), encoding="utf-8")

            no_network = ScriptedExchange(AssertionError("corrupt cache contacted network"))
            with self.assertRaisesRegex(ValueError, "cache|SHA-256"):
                fetch_huggingface(
                    "owner/model",
                    "main",
                    BoundedProviderTransport(
                        exchange=no_network,
                        cache=SnapshotResponseCache(Path(tmp)),
                    ),
                )
            self.assertEqual(no_network.calls, [])

    def test_policy_rejects_unbounded_or_ambiguous_values(self) -> None:
        invalid = [
            {"timeout_seconds": 0},
            {"timeout_seconds": 121},
            {"max_attempts": 0},
            {"max_attempts": 5},
            {"max_redirects": -1},
            {"max_response_bytes": True},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                MetadataPolicy(**values)


if __name__ == "__main__":
    unittest.main()
