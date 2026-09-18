from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_source_transport import WireResponse


HF_COMMIT = "a" * 40
FILE_SHA = "b" * 64


def _payload() -> bytes:
    return json.dumps(
        {
            "id": "owner/model",
            "sha": HF_COMMIT,
            "private": False,
            "gated": False,
            "cardData": {"license": "apache-2.0"},
            "siblings": [
                {
                    "rfilename": "model.safetensors",
                    "size": 1024,
                    "sha256": FILE_SHA,
                }
            ],
        }
    ).encode("utf-8")


class FakeExchange:
    def __init__(self):
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        return WireResponse(
            url=request.url,
            status=200,
            headers={"content-type": "application/json", "etag": '"v1"'},
            body=_payload(),
        )


class SourceTransportCliTests(unittest.TestCase):
    def test_cli_refuses_network_without_explicit_flag(self) -> None:
        from scripts.studio_adult_illustration_source_fetch import main

        exchange = FakeExchange()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main(
                ["huggingface", "--repo", "owner/model", "--revision", "main"],
                exchange=exchange,
            )
        self.assertEqual(status, 2)
        self.assertEqual(exchange.calls, [])
        error = json.loads(stderr.getvalue())
        self.assertIn("allow-network", error["error"])
        self.assertFalse(error["download_authorized"])
        self.assertFalse(error["execution_authorized"])

    def test_cli_uses_fake_exchange_cache_and_exclusive_output(self) -> None:
        from scripts.studio_adult_illustration_source_fetch import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "fetch.json"
            cache = root / "cache"
            exchange = FakeExchange()
            args = [
                "huggingface",
                "--repo",
                "owner/model",
                "--revision",
                "main",
                "--allow-network",
                "--cache-dir",
                str(cache),
                "--out",
                str(output),
            ]
            self.assertEqual(main(args, exchange=exchange), 0)
            first = output.read_bytes()
            value = json.loads(first)
            self.assertEqual(value["kind"], "source-snapshot-fetch")
            self.assertEqual(value["transport_receipt"]["cache_state"], "miss")
            self.assertEqual(len(exchange.calls), 1)

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(main(args, exchange=FakeExchange()), 2)
            self.assertEqual(output.read_bytes(), first)
            self.assertIn("already exists", json.loads(stderr.getvalue())["error"])

    def test_cli_cache_hit_does_not_call_exchange(self) -> None:
        from scripts.studio_adult_illustration_source_fetch import main

        class NoNetwork:
            def __init__(self):
                self.calls = 0

            def __call__(self, request, timeout):
                self.calls += 1
                raise AssertionError("cache hit contacted network")

        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "cache"
            first = FakeExchange()
            common = [
                "huggingface",
                "--repo",
                "owner/model",
                "--revision",
                "main",
                "--allow-network",
                "--cache-dir",
                str(cache),
            ]
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(common, exchange=first), 0)
            no_network = NoNetwork()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(common, exchange=no_network), 0)
            value = json.loads(stdout.getvalue())
            self.assertEqual(value["transport_receipt"]["cache_state"], "hit")
            self.assertEqual(no_network.calls, 0)


if __name__ == "__main__":
    unittest.main()
