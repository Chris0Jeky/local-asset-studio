"""Bounded, test-only ownership diagnostics for retained runtime work."""
from __future__ import annotations

import atexit
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import sysconfig
import threading
import traceback
from typing import Callable, TextIO

_MAX_RAW_STACK = 64
_MAX_TEXT = 160


def _outside_stdlib(filename: str) -> bool:
    try:
        path = Path(filename).resolve()
        stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
        path.relative_to(stdlib)
        return "site-packages" in path.parts
    except (KeyError, OSError, RuntimeError, ValueError):
        return True


def bounded_call_stack(*, skip_files=(), max_frames: int = 12) -> list[dict]:
    """Return a basename-only caller projection suitable for retained CI output."""
    if type(max_frames) is not int or not 1 <= max_frames <= 32:
        raise ValueError("max_frames must be an integer from 1 to 32")
    skipped = {str(name) for name in skip_files}
    frames = [
        frame
        for frame in traceback.extract_stack(limit=_MAX_RAW_STACK)[:-1]
        if Path(frame.filename).name not in skipped
    ]
    caller_frames = [frame for frame in frames if _outside_stdlib(frame.filename)] or frames
    return [
        {
            "file": Path(frame.filename).name[:_MAX_TEXT],
            "line": frame.lineno,
            "function": frame.name[:_MAX_TEXT],
        }
        for frame in caller_frames[-max_frames:]
    ]


def callable_identity(callback) -> str:
    """Name a callback without invoking repr() or retaining callback arguments."""
    try:
        module = getattr(callback, "__module__", None)
        qualname = getattr(callback, "__qualname__", None) or getattr(
            callback,
            "__name__",
            None,
        )
    except BaseException:
        module = None
        qualname = None
    if not isinstance(module, str) or not module:
        module = type(callback).__module__
    if not isinstance(qualname, str) or not qualname:
        qualname = type(callback).__qualname__
    return f"{module}.{qualname}"[: 2 * _MAX_TEXT + 1]


@dataclass
class _Registration:
    identifier: int
    callback: Callable
    wrapper: Callable
    registered_thread: str
    stack: list[dict]


class AtexitCallbackObserver:
    """Wrap later atexit registrations with bounded enter/exit ownership markers."""

    def __init__(
        self,
        *,
        stream: TextIO = sys.stderr,
        prefix: str = "LIFETIME ATEXIT",
        max_registrations: int = 256,
        max_frames: int = 12,
    ):
        if type(max_registrations) is not int or not 1 <= max_registrations <= 4096:
            raise ValueError("max_registrations must be an integer from 1 to 4096")
        if type(max_frames) is not int or not 1 <= max_frames <= 32:
            raise ValueError("max_frames must be an integer from 1 to 32")
        self.stream = stream
        self.prefix = prefix
        self.max_registrations = max_registrations
        self.max_frames = max_frames
        self._lock = threading.RLock()
        self._registrations: list[_Registration] = []
        self._next_identifier = 1
        self._overflow = 0
        self._installed = False
        self._original_register = None
        self._original_unregister = None
        self._register_proxy = None
        self._unregister_proxy = None

    def install(self) -> None:
        if self._installed:
            raise RuntimeError("atexit callback observer is already installed")
        self._original_register = atexit.register
        self._original_unregister = atexit.unregister

        def register_proxy(callback, *args, **kwargs):
            return self._register(callback, *args, **kwargs)

        def unregister_proxy(callback):
            return self._unregister(callback)

        self._register_proxy = register_proxy
        self._unregister_proxy = unregister_proxy
        atexit.register = register_proxy
        atexit.unregister = unregister_proxy
        self._installed = True

    def restore(self, *, cancel: bool = False) -> None:
        """Restore module hooks; focused tests may also cancel pending wrappers."""
        if not self._installed:
            return
        original_register = self._original_register
        original_unregister = self._original_unregister
        if atexit.register is self._register_proxy:
            atexit.register = original_register
        if atexit.unregister is self._unregister_proxy:
            atexit.unregister = original_unregister
        if cancel:
            with self._lock:
                registrations = list(self._registrations)
                self._registrations.clear()
            for registration in registrations:
                original_unregister(registration.wrapper)
        self._installed = False

    @staticmethod
    def _callbacks_equal(left, right) -> bool:
        if left is right:
            return True
        try:
            return bool(left == right)
        except BaseException:
            return False

    def _register(self, callback, *args, **kwargs):
        original_register = self._original_register
        if original_register is None:
            raise RuntimeError("atexit callback observer is not installed")
        if not callable(callback):
            return original_register(callback, *args, **kwargs)
        with self._lock:
            if len(self._registrations) >= self.max_registrations:
                self._overflow += 1
                if self._overflow == 1:
                    self._emit(
                        "SATURATED",
                        {
                            "max_registrations": self.max_registrations,
                            "unattributed_registrations": self._overflow,
                        },
                    )
                return original_register(callback, *args, **kwargs)
            registration = _Registration(
                identifier=self._next_identifier,
                callback=callback,
                wrapper=lambda: None,
                registered_thread=threading.current_thread().name[:_MAX_TEXT],
                stack=bounded_call_stack(
                    skip_files=(Path(__file__).name,),
                    max_frames=self.max_frames,
                ),
            )
            self._next_identifier += 1

            def observed_callback(*callback_args, **callback_kwargs):
                return self._invoke(registration, callback_args, callback_kwargs)

            registration.wrapper = observed_callback
            original_register(observed_callback, *args, **kwargs)
            self._registrations.append(registration)
        return callback

    def _unregister(self, callback):
        original_unregister = self._original_unregister
        if original_unregister is None:
            raise RuntimeError("atexit callback observer is not installed")
        with self._lock:
            matches = [
                registration
                for registration in self._registrations
                if self._callbacks_equal(registration.callback, callback)
            ]
            matched = {id(registration) for registration in matches}
            self._registrations = [
                registration
                for registration in self._registrations
                if id(registration) not in matched
            ]
            for registration in matches:
                original_unregister(registration.wrapper)
            # Preserve callbacks registered before observation began.
            original_unregister(callback)
        return None

    def _invoke(self, registration: _Registration, args, kwargs):
        self._emit_registration("ENTER", registration, include_origin=True)
        try:
            result = registration.callback(*args, **kwargs)
        except BaseException as error:
            self._emit_registration(
                "EXIT",
                registration,
                outcome="raised",
                exception=callable_identity(type(error)),
            )
            raise
        self._emit_registration("EXIT", registration, outcome="returned")
        return result

    def _emit_registration(
        self,
        event: str,
        registration: _Registration,
        *,
        include_origin: bool = False,
        **extra,
    ) -> None:
        payload = {
            "callback": callable_identity(registration.callback),
            "id": registration.identifier,
        }
        if include_origin:
            payload.update(
                {
                    "registered_stack": registration.stack,
                    "registered_thread": registration.registered_thread,
                }
            )
        payload.update(extra)
        self._emit(event, payload)

    def _emit(self, event: str, payload: dict) -> None:
        try:
            print(
                f"{self.prefix} {event}: "
                + json.dumps(payload, sort_keys=True, separators=(",", ":")),
                file=self.stream,
                flush=True,
            )
        except BaseException:
            # Diagnostics must never change callback execution or finalization.
            pass
