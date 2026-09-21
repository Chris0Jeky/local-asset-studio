from __future__ import annotations

from http.client import IncompleteRead
import json
import unittest

from studio_prompt.adult_illustration_source_intake import HttpRequest
from studio_prompt.adult_illustration_source_transport import (
    BoundedProviderTransport,
    MetadataPolicy,
    StdlibMetadataExchange,
    fetch_huggingface,
)


HF_URL = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
HF_COMMIT = "a" * 40


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


class _Response:
    def __init__(self, body: bytes, *, truncate: bool = False):
        self.status = 200
        self.headers = {"content-type": "application/json"}
        self._body = body
        self._truncate = truncate

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def geturl(self) -> str:
        return HF_URL

    def read(self, amount: int) -> bytes:
        if self._truncate:
            partial = self._body[:8]
            raise IncompleteRead(partial=partial, expected=len(self._body) - len(partial))
        return self._body[:amount]


class _FlakyOpener:
    def __init__(self):
        self.calls: list[tuple[object, float]] = []
        self._responses = [
            _Response(_body(), truncate=True),
            _Response(_body()),
        ]

    def open(self, request: object, timeout: float):
        self.calls.append((request, timeout))
        if not self._responses:
            raise AssertionError("unexpected metadata exchange")
        return self._responses.pop(0)


class IncompleteReadTransportTests(unittest.TestCase):
    def test_truncated_stdlib_response_is_retried_as_a_connection_failure(self) -> None:
        exchange = StdlibMetadataExchange()
        opener = _FlakyOpener()
        exchange._opener = opener  # type: ignore[attr-defined]
        sleeps: list[float] = []

        result = fetch_huggingface(
            "owner/model",
            "main",
            BoundedProviderTransport(
                exchange=exchange,
                policy=MetadataPolicy(max_attempts=2),
                sleeper=sleeps.append,
            ),
        )

        self.assertEqual(result["transport_receipt"]["attempts"], 2)
        self.assertEqual(len(opener.calls), 2)
        self.assertEqual(sleeps, [0.25])
        self.assertEqual(
            result["snapshot"]["request"],
            {
                "method": "GET",
                "url": HF_URL,
                "headers": {
                    "accept": "application/json",
                    "user-agent": "local-asset-studio-source-snapshot/1",
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
