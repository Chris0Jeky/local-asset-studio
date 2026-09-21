"""Bounded, test-only ownership diagnostics for retained runtime work."""
from __future__ import annotations

import atexit
from dataclasses import dataclass
import functools
import json
from pathlib import Path
import sys
import sysconfig
import threading
import traceback
import types
from typing import Callable, TextIO

_MAX_RAW_STACK = 64
_MAX_TEXT = 160
_MAX_IDENTITY = 2 * _MAX_TEXT + 1
_CANCEL_TOKEN_TAG = "local-asset-studio::atexit-observer-cancel::v1"


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


def _identity_text(module, qualname, fallback_module: str, fallback_name: str) -> str:
    if not isinstance(module, str) or not module:
        module = fallback_module
    if not isinstance(qualname, str) or not qualname:
        qualname = fallback_name
    return f"{module}.{qualname}"[:_MAX_IDENTITY]


def _type_parts(callback_type: type) -> tuple[str, str]:
    """Read class metadata without dispatching through a custom metaclass."""
    try:
        module = type.__getattribute__(callback_type, "__module__")
        qualname = type.__getattribute__(callback_type, "__qualname__")
    except BaseException:
        return "builtins", "type"
    if not isinstance(module, str) or not module:
        module = "builtins"
    if not isinstance(qualname, str) or not qualname:
        qualname = "type"
    return module, qualname


def _type_identity(callback_type: type) -> str:
    module, qualname = _type_parts(callback_type)
    return _identity_text(module, qualname, "builtins", "type")


def callable_identity(callback) -> str:
    """Name a callback without repr() or callback-controlled attribute access."""
    if isinstance(callback, functools.partial):
        try:
            target = object.__getattribute__(callback, "func")
        except BaseException:
            return _type_identity(type(callback))
        return f"functools.partial({callable_identity(target)})"[:_MAX_IDENTITY]

    if isinstance(callback, types.MethodType):
        callback = callback.__func__

    if isinstance(
        callback,
        (types.FunctionType, types.BuiltinFunctionType, types.BuiltinMethodType),
    ):
        fallback_module, fallback_name = _type_parts(type(callback))
        try:
            module = callback.__module__
            qualname = callback.__qualname__ or callback.__name__
        except BaseException:
            module = None
            qualname = None
        return _identity_text(
            module,
            qualname,
            fallback_module,
            fallback_name,
        )

    if isinstance(callback, type):
        return _type_identity(callback)
    return _type_identity(type(callback))


@dataclass
class _Registration:
    identifier: int
    callback: Callable
    identity: str
    wrapper: Callable
    registered_thread: str
    stack: list[dict]
    active: bool = True


class _ObservedCallback:
    """Callable proxy whose equality mirrors the registered callback."""

    __slots__ = ("observer", "registration")

    def __init__(self, observer: "AtexitCallbackObserver", registration: _Registration):
        self.observer = observer
        self.registration = registration

    def __call__(self, *args, **kwargs):
        return self.observer._invoke(self.registration, args, kwargs)

    def __eq__(self, other):
        # Cancellation uses an exact built-in tuple. This avoids exposing a proxy as
        # the unregister query: unrelated callbacks can return NotImplemented and
        # reflect comparison into the query object's __eq__ before the target entry.
        if (
            type(other) is tuple
            and len(other) == 2
            and type(other[0]) is str
            and other[0] == _CANCEL_TOKEN_TAG
        ):
            return self is other[1]
        if isinstance(other, _ObservedCallback):
            return self is other
        equal = self.observer._callbacks_equal(self.registration.callback, other)
        if equal:
            # CPython deletes this proxy immediately after the successful equality
            # result. Record that decision so a later comparison error still leaves
            # earlier matches removed from the observer's registry as well.
            self.registration.active = False
        return equal


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
                original_unregister(
                    (_CANCEL_TOKEN_TAG, registration.wrapper)
                )
        self._installed = False

    @staticmethod
    def _callbacks_equal(left, right) -> bool:
        if left is right:
            return True
        # Match atexit.unregister's equality contract, including propagation of
        # callback-defined comparison errors instead of silently retaining work.
        return bool(left == right)

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
                identity=callable_identity(callback),
                wrapper=lambda: None,
                registered_thread=threading.current_thread().name[:_MAX_TEXT],
                stack=bounded_call_stack(
                    skip_files=(Path(__file__).name,),
                    max_frames=self.max_frames,
                ),
            )
            self._next_identifier += 1
            registration.wrapper = _ObservedCallback(self, registration)
            original_register(registration.wrapper, *args, **kwargs)
            self._registrations.append(registration)
        return callback

    def _unregister(self, callback):
        original_unregister = self._original_unregister
        if original_unregister is None:
            raise RuntimeError("atexit callback observer is not installed")
        with self._lock:
            try:
                # Let CPython perform its one ordered comparison pass. The callable
                # proxies delegate equality to the original callbacks, preserving
                # pre-observer ordering and incremental deletion before errors.
                return original_unregister(callback)
            finally:
                retained = []
                for registration in self._registrations:
                    if registration.active:
                        retained.append(registration)
                    else:
                        # Break the registration/proxy cycle once CPython has
                        # removed the proxy from its callback array.
                        registration.wrapper = lambda: None
                self._registrations = retained

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
            "callback": registration.identity,
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
