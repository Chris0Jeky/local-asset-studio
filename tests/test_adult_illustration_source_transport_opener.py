"""Pin the private metadata opener (issue #800): no env proxies, no redirects."""
from __future__ import annotations

import inspect
import os
import unittest
from unittest import mock
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request

from studio_prompt._adult_illustration_source_transport_http import (
    StdlibMetadataExchange,
    _NoRedirectHandler,
)

_HOSTILE_PROXIES = {
    "http_proxy": "http://127.0.0.1:9/",
    "https_proxy": "http://127.0.0.1:9/",
    "HTTP_PROXY": "http://127.0.0.1:9/",
    "HTTPS_PROXY": "http://127.0.0.1:9/",
}


def _opener_handlers() -> list:
    with mock.patch.dict(os.environ, _HOSTILE_PROXIES):
        return list(StdlibMetadataExchange()._opener.handlers)


class PrivateOpenerTests(unittest.TestCase):
    def test_ignores_environment_proxies(self) -> None:
        proxy_handlers = [
            h for h in _opener_handlers() if isinstance(h, ProxyHandler)
        ]
        # urllib leaves an empty ProxyHandler out of handlers because it
        # advertises no proxy_open methods. A default opener under this
        # hostile environment would install a nonempty handler here.
        self.assertEqual(proxy_handlers, [])
        self.assertIn("ProxyHandler({})", inspect.getsource(StdlibMetadataExchange.__init__))

    def test_disables_automatic_redirects(self) -> None:
        redirect_handlers = [
            h for h in _opener_handlers() if isinstance(h, HTTPRedirectHandler)
        ]
        self.assertEqual(len(redirect_handlers), 1)
        self.assertIs(type(redirect_handlers[0]), _NoRedirectHandler)
        request = Request("http://example.invalid/")
        self.assertIsNone(
            redirect_handlers[0].redirect_request(
                request, None, 302, "Found", {}, "http://example.invalid/next"
            )
        )

    def test_call_uses_private_opener_not_urlopen(self) -> None:
        source = inspect.getsource(StdlibMetadataExchange.__call__)
        self.assertNotIn("urlopen", source)
        self.assertIn("_opener.open", source)
