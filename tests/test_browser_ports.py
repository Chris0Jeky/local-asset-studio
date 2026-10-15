"""Browser fixtures reject restricted ephemeral ports without leaking sockets."""
import unittest
from unittest.mock import Mock, call, patch

from browser_ports import browser_server


class BrowserPortsTests(unittest.TestCase):
    def test_retries_restricted_port_and_closes_rejected_server(self):
        unsafe, safe = Mock(server_port=6669), Mock(server_port=49152)
        handler = Mock()
        with patch('browser_ports.ThreadingHTTPServer', side_effect=[unsafe, safe]) as bind:
            self.assertIs(browser_server(handler), safe)
        self.assertEqual(bind.call_args_list, [call(('127.0.0.1', 0), handler)] * 2)
        unsafe.server_close.assert_called_once_with()
        safe.server_close.assert_not_called()

    def test_attempts_are_bounded_and_all_rejected_servers_are_closed(self):
        servers = [Mock(server_port=6669) for _ in range(20)]
        with patch('browser_ports.ThreadingHTTPServer', side_effect=servers) as bind:
            with self.assertRaisesRegex(RuntimeError, '20 attempts'): browser_server(Mock())
        self.assertEqual(bind.call_count, 20)
        for server in servers: server.server_close.assert_called_once_with()

    def test_explicit_port_is_preserved(self):
        server, handler = Mock(server_port=8191), Mock()
        with patch('browser_ports.ThreadingHTTPServer', return_value=server) as bind:
            self.assertIs(browser_server(handler, port=8191), server)
        bind.assert_called_once_with(('127.0.0.1', 8191), handler)
        server.server_close.assert_not_called()
