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
import weakref

_MAX_RAW_STACK = 64
_MAX_TEXT = 160
_MAX_TEST_ID = 320
_MAX_IDENTITY = 2 * _MAX_TEXT + 1
_CANCEL_TOKEN_TAG = "local-asset-studio::atexit-observer-cancel::v1"
_PROXY_TYPE_TAG = "local-asset-studio::atexit-observer-proxy::v1"
_CURRENT_TEST = "<not started>"
_CURRENT_TEST_LOCK = threading.Lock()
_THREAD_OBSERVER_STATE_LOCK = threading.RLock()
_ACTIVE_THREAD_OBSERVER = None


def _safe_text(value, *, limit: int = _MAX_TEXT) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text[:limit]


def set_current_test(value: str) -> None:
    """Publish the current unittest identity for cross-thread diagnostics."""
    global _CURRENT_TEST
    text = _safe_text(value, limit=_MAX_TEST_ID)
    with _CURRENT_TEST_LOCK:
        _CURRENT_TEST = text


def current_test() -> str:
    with _CURRENT_TEST_LOCK:
        return _CURRENT_TEST


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


class ThreadOwnershipObserver:
    """Attribute later thread starts to the active test and parent thread."""

    def __init__(
        self,
        *,
        max_threads: int = 512,
        max_frames: int = 12,
    ):
        if type(max_threads) is not int or not 1 <= max_threads <= 4096:
            raise ValueError("max_threads must be an integer from 1 to 4096")
        if type(max_frames) is not int or not 1 <= max_frames <= 32:
            raise ValueError("max_frames must be an integer from 1 to 32")
        self.max_threads = max_threads
        self.max_frames = max_frames
        self._lock = threading.RLock()
        self._origins = weakref.WeakKeyDictionary()
        self._preexisting = weakref.WeakSet()
        self._root_thread = None
        self._overflow = 0
        self._installed = False
        self._original_start = None
        self._start_proxy = None

    def install(self) -> None:
        global _ACTIVE_THREAD_OBSERVER
        if self._installed:
            raise RuntimeError("thread ownership observer is already installed")
        with _THREAD_OBSERVER_STATE_LOCK:
            if _ACTIVE_THREAD_OBSERVER is not None:
                raise RuntimeError("another thread ownership observer is already installed")
            self._original_start = threading.Thread.start

            def start_proxy(thread, *args, **kwargs):
                return self._start(thread, *args, **kwargs)

            self._start_proxy = start_proxy
            self._root_thread = threading.current_thread()
            self._preexisting = weakref.WeakSet(threading.enumerate())
            threading.Thread.start = start_proxy
            _ACTIVE_THREAD_OBSERVER = self
            self._installed = True

    def restore(self) -> None:
        global _ACTIVE_THREAD_OBSERVER
        if not self._installed:
            return
        with _THREAD_OBSERVER_STATE_LOCK:
            if threading.Thread.start is self._start_proxy:
                threading.Thread.start = self._original_start
            if _ACTIVE_THREAD_OBSERVER is self:
                _ACTIVE_THREAD_OBSERVER = None
            self._installed = False
        with self._lock:
            self._origins.clear()
            self._preexisting.clear()
            self._root_thread = None

    def _prune_finished_locked(self) -> None:
        for thread in list(self._origins):
            try:
                finished = thread.ident is not None and not thread.is_alive()
            except (AssertionError, RuntimeError):
                finished = False
            if finished:
                self._origins.pop(thread, None)

    def _parent_origin_locked(self, parent, started_during: str) -> dict:
        if parent is self._root_thread:
            return {
                "status": "observed",
                "owner_test": started_during,
            }
        origin = self._origins.get(parent)
        if origin is not None:
            return origin
        if parent in self._preexisting:
            reason = "started-before-observer"
        elif self._overflow:
            reason = "observer-capacity"
        else:
            reason = "unobserved-thread-start"
        return {
            "status": "unobserved",
            "reason": reason,
        }

    @staticmethod
    def _descendant_reason(parent_origin: dict) -> str:
        reason = parent_origin.get("reason", "unobserved-thread-start")
        if reason.startswith("ancestor-"):
            return reason
        return f"ancestor-{reason}"

    def _start(self, thread, *args, **kwargs):
        original_start = self._original_start
        if original_start is None:
            raise RuntimeError("thread ownership observer is not installed")

        parent = threading.current_thread()
        started_during = current_test()
        with self._lock:
            self._prune_finished_locked()
            parent_origin = self._parent_origin_locked(parent, started_during)
            record = {
                "status": parent_origin["status"],
                "started_during_test": started_during,
                "parent_thread": _safe_text(parent.name),
                "start_stack": bounded_call_stack(
                    skip_files=(Path(__file__).name,),
                    max_frames=self.max_frames,
                ),
            }
            if parent_origin["status"] == "observed":
                record["owner_test"] = parent_origin["owner_test"]
            else:
                record.update(
                    {
                        "reason": self._descendant_reason(parent_origin),
                        "max_threads": self.max_threads,
                        "unattributed_starts": self._overflow,
                    }
                )

            recorded = len(self._origins) < self.max_threads
            if recorded:
                self._origins[thread] = record
            else:
                self._overflow += 1

        try:
            return original_start(thread, *args, **kwargs)
        except BaseException:
            if recorded:
                with self._lock:
                    self._origins.pop(thread, None)
            raise

    def origin_for(self, thread) -> dict:
        with self._lock:
            origin = self._origins.get(thread)
            if origin is not None:
                return json.loads(json.dumps(origin))
            if thread in self._preexisting:
                reason = "started-before-observer"
            elif self._overflow:
                reason = "observer-capacity"
            else:
                reason = "unobserved-thread-start"
            return {
                "status": "unobserved",
                "reason": reason,
                "max_threads": self.max_threads,
                "unattributed_starts": self._overflow,
            }


def current_thread_origin() -> dict | None:
    """Return bounded ownership for the calling thread when observation is active."""
    with _THREAD_OBSERVER_STATE_LOCK:
        observer = _ACTIVE_THREAD_OBSERVER
    if observer is None:
        return None
    return observer.origin_for(threading.current_thread())


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


def _is_observed_proxy(value) -> bool:
    """Recognize LAS observer proxies without invoking instance or metaclass code."""
    try:
        marker = type.__getattribute__(type(value), "_las_atexit_proxy_tag")
    except (AttributeError, TypeError):
        return False
    return type(marker) is str and marker == _PROXY_TYPE_TAG


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
    _las_atexit_proxy_tag = _PROXY_TYPE_TAG

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
            if self is other[1]:
                return True
            callback = self.registration.callback
            if _is_observed_proxy(callback):
                equal = bool(callback == other)
                if equal:
                    # A nested observer owns the target proxy. CPython removes this
                    # outer proxy, so its registry must forget the same entry.
                    self.registration.active = False
                return equal
            return False
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
