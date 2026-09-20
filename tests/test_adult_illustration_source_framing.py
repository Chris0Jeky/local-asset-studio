"""Real HTTP parser, fake byte transport: no provider or socket access."""
from __future__ import annotations

import io
import tempfile
import unittest
from http.client import HTTPResponse
from pathlib import Path
from unittest import mock

from studio_prompt._adult_illustration_source_transport_http import (
    BoundedProviderTransport, StdlibMetadataExchange, _read_bounded_stream,
)
from studio_prompt._adult_illustration_source_transport_cache import SnapshotResponseCache
from studio_prompt._adult_illustration_source_transport_common import (
    HttpRequest, MetadataPolicy, USER_AGENT,
)

URL = "https://civitai.com/api/v1/model-versions/123"


class _ByteSocket:
    def __init__(self, raw: bytes):
        self.raw = raw

    def makefile(self, mode: str):
        return io.BytesIO(self.raw)


def response(headers: bytes, body: bytes = b"{}", status: int = 200) -> HTTPResponse:
    value = HTTPResponse(_ByteSocket(
        f"HTTP/1.1 {status} Fixture\r\n".encode("ascii")
        + b"Content-Type: application/json\r\n" + headers + b"\r\n" + body
    ))
    value.begin()
    value.url = URL
    return value


class ProviderResponseFramingTests(unittest.TestCase):
    def test_valid_json_prefix_is_not_a_complete_declared_response(self):
        with response(b"Content-Length: 20\r\n") as value:
            with self.assertRaises(ConnectionError):
                _read_bounded_stream(value, 128)

    def test_declared_oversize_is_refused_before_read(self):
        with response(b"Content-Length: 129\r\n") as value:
            with mock.patch.object(value, "read", wraps=value.read) as read:
                with self.assertRaises(ValueError):
                    _read_bounded_stream(value, 128)
                read.assert_not_called()

    def test_ambiguous_framing_is_refused_before_read(self):
        cases = (
            b"Content-Length: 2\r\nContent-Length: 2\r\n",
            b"Content-Length: 2\r\ncontent-length: 7\r\n",
            b"Content-Length: 2, 2\r\n",
            b"Content-Length: -1\r\n",
            b"Content-Length: +2\r\n",
            b"Content-Length: invalid\r\n",
            b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n",
            b"Transfer-Encoding: gzip\r\n",
            b"Transfer-Encoding: chunked\r\nTransfer-Encoding: chunked\r\n",
        )
        for headers in cases:
            with self.subTest(headers=headers), response(headers) as value:
                with mock.patch.object(value, "read", wraps=value.read) as read:
                    with self.assertRaises(ValueError):
                        _read_bounded_stream(value, 128)
                    read.assert_not_called()

    def test_complete_length_eof_and_chunked_responses_remain_supported(self):
        cases = (
            (b"Content-Length: 2\r\n", b"{}"),
            (b"Content-Length: 0002\r\n", b"{}"),
            (b"", b"{}"),
            (b"Transfer-Encoding: chunked\r\n", b"2\r\n{}\r\n0\r\n\r\n"),
        )
        for headers, body in cases:
            with self.subTest(headers=headers), response(headers, body) as value:
                self.assertEqual(_read_bounded_stream(value, 2), b"{}")

    def test_no_body_status_does_not_require_advertised_representation_bytes(self):
        with response(b"Content-Length: 2048\r\n", b"", 304) as value:
            self.assertEqual(_read_bounded_stream(value, 128), b"")

    def test_truncated_json_retries_without_receipt_or_cache_publication(self):
        request = HttpRequest(URL, {"accept": "application/json", "user-agent": USER_AGENT})
        exchange = StdlibMetadataExchange(128)
        opened = []

        def open_response(*args, **kwargs):
            value = response(b"Content-Length: 20\r\n")
            opened.append(value)
            return value

        exchange._opener = mock.Mock()
        exchange._opener.open.side_effect = open_response
        with tempfile.TemporaryDirectory() as directory:
            cache = SnapshotResponseCache(directory)
            transport = BoundedProviderTransport(
                exchange=exchange, cache=cache,
                policy=MetadataPolicy(max_attempts=2, max_response_bytes=128),
                sleeper=lambda _: None,
            )
            with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(ValueError, "after 2 attempt"):
                    transport(request)
            self.assertEqual(exchange._opener.open.call_count, 2)
            self.assertTrue(all(value.isclosed() for value in opened))
            self.assertEqual(list(Path(directory).iterdir()), [])
            with self.assertRaises(RuntimeError):
                _ = transport.receipt


if __name__ == "__main__":
    unittest.main()
