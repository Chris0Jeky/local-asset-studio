"""Cache age evidence for adult-illustration source transport receipts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport,
    SnapshotResponseCache,
    WireResponse,
    fetch_huggingface,
)
from tests.test_adult_illustration_source_transport import (
    ScriptedExchange,
    _hf_payload,
    _json_response,
)

HF_URL = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"


def _request_headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "user-agent": "local-asset-studio-source-snapshot/1",
    }


class CacheAgeTests(unittest.TestCase):
    def test_persisted_hit_exposes_timestamp_and_bounded_age(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            seed = ScriptedExchange(
                _json_response(HF_URL, _hf_payload(), headers={"etag": '"age-v1"'})
            )
            first = fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(exchange=seed, cache=cache),
            )
            self.assertEqual(first["transport_receipt"]["cache_state"], "miss")
            self.assertIsNone(first["transport_receipt"]["cache_stored_at"])
            self.assertIsNone(first["transport_receipt"]["cache_age_seconds"])
            record = json.loads(next(Path(tmp).glob("*.json")).read_text(encoding="utf-8"))
            stored_at = record.get("stored_at")
            self.assertIsInstance(stored_at, str)
            parsed = datetime.fromisoformat(stored_at.replace("Z", "+00:00"))
            self.assertIsNotNone(parsed.tzinfo)

            no_network = ScriptedExchange(AssertionError("cache hit contacted network"))
            second = fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=no_network,
                    cache=SnapshotResponseCache(Path(tmp)),
                ),
            )
            receipt = second["transport_receipt"]
            self.assertEqual(receipt["cache_state"], "hit")
            self.assertEqual(receipt["cache_stored_at"], stored_at)
            self.assertIsInstance(receipt["cache_age_seconds"], float)
            self.assertGreaterEqual(receipt["cache_age_seconds"], 0.0)
            self.assertLess(receipt["cache_age_seconds"], 120.0)
            self.assertEqual(no_network.calls, [])
            self.assertFalse(receipt["download_authorized"])

    def test_revalidated_304_retains_original_payload_write_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=ScriptedExchange(
                        _json_response(
                            HF_URL, _hf_payload(), headers={"etag": '"age-v1"'}
                        )
                    ),
                    cache=cache,
                ),
            )
            path = next(Path(tmp).glob("*.json"))
            record = json.loads(path.read_text(encoding="utf-8"))
            aged = (datetime.now(timezone.utc) - timedelta(seconds=3600)).isoformat()
            record["stored_at"] = aged
            path.write_text(json.dumps(record), encoding="utf-8")

            def not_modified(request, timeout):
                return WireResponse(
                    url=HF_URL, status=304, headers={"etag": '"age-v1"'}, body=b""
                )

            refreshed = fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=ScriptedExchange(not_modified),
                    cache=SnapshotResponseCache(Path(tmp)),
                    refresh=True,
                ),
            )
            receipt = refreshed["transport_receipt"]
            self.assertEqual(receipt["cache_state"], "revalidated")
            self.assertEqual(receipt["cache_stored_at"], aged)
            self.assertIsInstance(receipt["cache_age_seconds"], float)
            self.assertGreaterEqual(receipt["cache_age_seconds"], 3500.0)
            self.assertLess(receipt["cache_age_seconds"], 3700.0)

    def test_legacy_record_reports_unknown_age(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=ScriptedExchange(_json_response(HF_URL, _hf_payload())),
                    cache=cache,
                ),
            )
            path = next(Path(tmp).glob("*.json"))
            record = json.loads(path.read_text(encoding="utf-8"))
            del record["stored_at"]
            path.write_text(json.dumps(record), encoding="utf-8")

            no_network = ScriptedExchange(AssertionError("legacy hit contacted network"))
            result = fetch_huggingface(
                "owner/model",
                "main",
                BoundedProviderTransport(
                    exchange=no_network,
                    cache=SnapshotResponseCache(Path(tmp)),
                ),
            )
            receipt = result["transport_receipt"]
            self.assertEqual(receipt["cache_state"], "hit")
            self.assertIsNone(receipt["cache_stored_at"])
            self.assertIsNone(receipt["cache_age_seconds"])
            self.assertEqual(no_network.calls, [])

    def test_malformed_and_future_timestamps_are_rejected(self) -> None:
        bad_values: list[object] = [
            "not-a-date",
            123,
            "2026-09-25T00:00:00",
            "2026-09-25T00:00:00+05:00",
            (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "",
        ]
        for bad in bad_values:
            with self.subTest(stored_at=bad), tempfile.TemporaryDirectory() as tmp:
                fetch_huggingface(
                    "owner/model",
                    "main",
                    BoundedProviderTransport(
                        exchange=ScriptedExchange(
                            _json_response(HF_URL, _hf_payload())
                        ),
                        cache=SnapshotResponseCache(Path(tmp)),
                    ),
                )
                path = next(Path(tmp).glob("*.json"))
                record = json.loads(path.read_text(encoding="utf-8"))
                record["stored_at"] = bad
                path.write_text(json.dumps(record), encoding="utf-8")
                no_network = ScriptedExchange(
                    AssertionError("corrupt timestamp contacted network")
                )
                with self.assertRaisesRegex(ValueError, "cache|write time|future"):
                    fetch_huggingface(
                        "owner/model",
                        "main",
                        BoundedProviderTransport(
                            exchange=no_network,
                            cache=SnapshotResponseCache(Path(tmp)),
                        ),
                    )
                self.assertEqual(no_network.calls, [])

    def test_no_persisted_timestamp_before_finalize(self) -> None:
        from studio_prompt.adult_illustration_source_intake import HttpRequest

        with tempfile.TemporaryDirectory() as tmp:
            cache = SnapshotResponseCache(Path(tmp))
            exchange = ScriptedExchange(_json_response(HF_URL, _hf_payload()))
            transport = BoundedProviderTransport(exchange=exchange, cache=cache)
            request = HttpRequest(url=HF_URL, headers=dict(_request_headers()))
            response = transport(request)
            receipt = transport.receipt
            self.assertEqual(receipt["cache_state"], "miss")
            self.assertIsNone(receipt["cache_stored_at"])
            self.assertIsNone(receipt["cache_age_seconds"])
            self.assertEqual(list(Path(tmp).glob("*.json")), [])
            transport.finalize(hashlib.sha256(response.body).hexdigest())
            paths = list(Path(tmp).glob("*.json"))
            self.assertEqual(len(paths), 1)
            record = json.loads(paths[0].read_text(encoding="utf-8"))
            self.assertIsInstance(record.get("stored_at"), str)


if __name__ == "__main__":
    unittest.main()
