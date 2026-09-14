"""Bounded, test-only attribution for loopback client connections.

The audit wraps ``socket.create_connection`` only while a fixture test is active,
records calls to one exact numeric loopback host/port, and delegates every network
operation unchanged. It stores no request bodies, headers, response bytes or socket
objects. The retained stack is deliberately reduced to file names, line numbers and
function names so a CI failure can identify an owner without leaking machine paths.
"""
from __future__ import annotations

import ipaddress
import json
from pathlib import Path
import socket
import sysconfig
import threading
import traceback
from unittest.mock import patch


_MAX_ROUTE_ROWS = 32
_MAX_RAW_STACK = 64


class LoopbackTransportAudit:
    """Observe Python callers that connect to one exact loopback fixture port."""

    def __init__(self, *, host: str, port: int, max_calls: int = 16, max_frames: int = 12):
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            raise ValueError("Audit host must be a numeric IP address") from error
        if not address.is_loopback:
            raise ValueError("Audit host must be loopback")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Audit port must be an integer from 1 to 65535")
        if type(max_calls) is not int or not 1 <= max_calls <= 64:
            raise ValueError("Audit max_calls must be an integer from 1 to 64")
        if type(max_frames) is not int or not 1 <= max_frames <= 32:
            raise ValueError("Audit max_frames must be an integer from 1 to 32")
        self.host = str(address)
        self.port = port
        self.max_calls = max_calls
        self.max_frames = max_frames
        self._lock = threading.Lock()
        self._observed = 0
        self._retained: list[dict] = []
        self._patcher = None
        self._original = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, _kind, _value, _traceback):
        self.stop()
        return False

    def start(self) -> None:
        if self._patcher is not None:
            raise RuntimeError("Loopback transport audit is already active")
        self._original = socket.create_connection
        self._patcher = patch.object(socket, "create_connection", new=self._connect)
        self._patcher.start()

    def stop(self) -> None:
        patcher, self._patcher = self._patcher, None
        if patcher is not None:
            patcher.stop()
        self._original = None

    def _matches(self, address) -> bool:
        if not isinstance(address, (tuple, list)) or len(address) < 2:
            return False
        host, port = address[0], address[1]
        if type(port) is not int or port != self.port:
            return False
        try:
            return str(ipaddress.ip_address(host)) == self.host
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _outside_stdlib(filename: str) -> bool:
        try:
            path = Path(filename).resolve()
            stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
            path.relative_to(stdlib)
            return "site-packages" in path.parts
        except (KeyError, OSError, RuntimeError, ValueError):
            return True

    def _stack(self) -> list[dict]:
        own_file = Path(__file__).name
        frames = [
            frame
            for frame in traceback.extract_stack(limit=_MAX_RAW_STACK)[:-1]
            if Path(frame.filename).name != own_file
        ]
        # Transport-library frames are usually the most recent frames and can push
        # the actual fixture/test caller out of a small retained tail. Prefer code
        # outside the Python standard library, falling back to the complete stack
        # when all frames are standard-library internals.
        caller_frames = [frame for frame in frames if self._outside_stdlib(frame.filename)] or frames
        return [
            {
                "file": Path(frame.filename).name[:160],
                "line": frame.lineno,
                "function": frame.name[:160],
            }
            for frame in caller_frames[-self.max_frames :]
        ]

    def _connect(self, address, *args, **kwargs):
        if self._matches(address):
            row = {
                "host": self.host,
                "port": self.port,
                "thread": threading.current_thread().name[:160],
                "stack": self._stack(),
            }
            with self._lock:
                self._observed += 1
                if len(self._retained) < self.max_calls:
                    self._retained.append(row)
        original = self._original
        if original is None:
            raise RuntimeError("Loopback transport audit is not active")
        return original(address, *args, **kwargs)

    def snapshot(self) -> dict:
        with self._lock:
            retained = json.loads(json.dumps(self._retained))
            observed = self._observed
        return {
            "observed": observed,
            "retained": retained,
            "truncated": observed > len(retained),
        }

    def describe(self, routes) -> str:
        safe_routes = []
        for row in list(routes)[:_MAX_ROUTE_ROWS]:
            if isinstance(row, (tuple, list)) and len(row) >= 2:
                safe_routes.append([str(row[0])[:16], str(row[1])[:256]])
            else:
                safe_routes.append(["unknown", str(row)[:256]])
        return json.dumps(
            {
                "routes": safe_routes,
                "routes_truncated": len(routes) > len(safe_routes),
                "transport": self.snapshot(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
