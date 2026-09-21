"""Bounded task-submission ownership for reused ``ThreadPoolExecutor`` workers."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextvars
import json
from pathlib import Path
import threading

from runtime_observability import (
    bounded_call_stack,
    callable_identity,
    current_test,
    current_thread_origin,
)

_MAX_TEXT = 160
_MAX_TEST_ID = 320
_WORK_CONTEXT = contextvars.ContextVar("las_executor_work_origin", default=None)
_WORK_OBSERVER_STATE_LOCK = threading.RLock()
_ACTIVE_WORK_OBSERVER = None


def _safe_text(value, *, limit: int = _MAX_TEXT) -> str:
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text[:limit]


def _clone(value: dict) -> dict:
    return json.loads(json.dumps(value))


def current_work_origin() -> dict | None:
    """Return bounded ownership for the executor task running on this context."""
    origin = _WORK_CONTEXT.get()
    return None if origin is None else _clone(origin)


class ExecutorWorkObserver:
    """Attribute executor tasks independently from their reusable worker thread."""

    def __init__(self, *, max_tasks: int = 1024, max_frames: int = 12):
        if type(max_tasks) is not int or not 1 <= max_tasks <= 8192:
            raise ValueError("max_tasks must be an integer from 1 to 8192")
        if type(max_frames) is not int or not 1 <= max_frames <= 32:
            raise ValueError("max_frames must be an integer from 1 to 32")
        self.max_tasks = max_tasks
        self.max_frames = max_frames
        self._lock = threading.RLock()
        self._root_thread = None
        self._previous_observer = None
        self._inflight = 0
        self._overflow = 0
        self._installed = False
        self._original_submit = None
        self._submit_proxy = None

    def install(self) -> None:
        global _ACTIVE_WORK_OBSERVER
        if self._installed:
            raise RuntimeError("executor work observer is already installed")
        with _WORK_OBSERVER_STATE_LOCK:
            self._previous_observer = _ACTIVE_WORK_OBSERVER
            self._original_submit = ThreadPoolExecutor.submit
            self._root_thread = threading.current_thread()
            self._inflight = 0
            self._overflow = 0

            def submit_proxy(executor, fn, /, *args, **kwargs):
                return self._submit(executor, fn, args, kwargs)

            self._submit_proxy = submit_proxy
            ThreadPoolExecutor.submit = submit_proxy
            _ACTIVE_WORK_OBSERVER = self
            self._installed = True

    def restore(self) -> None:
        global _ACTIVE_WORK_OBSERVER
        if not self._installed:
            return
        with _WORK_OBSERVER_STATE_LOCK:
            if _ACTIVE_WORK_OBSERVER is not self:
                raise RuntimeError(
                    "executor work observers must be restored in LIFO order"
                )
            if ThreadPoolExecutor.submit is self._submit_proxy:
                ThreadPoolExecutor.submit = self._original_submit
            _ACTIVE_WORK_OBSERVER = self._previous_observer
            self._installed = False
        with self._lock:
            self._root_thread = None
            self._previous_observer = None
            self._original_submit = None
            self._submit_proxy = None

    @staticmethod
    def _descendant_reason(prefix: str, origin: dict | None) -> str:
        if origin is None:
            return f"ancestor-{prefix}-observer-inactive"
        reason = origin.get("reason", "unobserved")
        if reason.startswith("ancestor-"):
            return reason
        return f"ancestor-{prefix}-{reason}"

    def _parent_origin(self, submitter, submitted_during: str) -> dict:
        parent_work = _WORK_CONTEXT.get()
        if parent_work is not None:
            if parent_work.get("status") == "observed":
                return {
                    "status": "observed",
                    "owner_test": parent_work["owner_test"],
                    "ownership_source": "parent-work",
                }
            return {
                "status": "unobserved",
                "reason": self._descendant_reason("work", parent_work),
                "ownership_source": "parent-work",
            }

        if submitter is self._root_thread:
            return {
                "status": "observed",
                "owner_test": submitted_during,
                "ownership_source": "runner-thread",
            }

        thread_origin = current_thread_origin()
        if thread_origin is not None and thread_origin.get("status") == "observed":
            return {
                "status": "observed",
                "owner_test": thread_origin["owner_test"],
                "ownership_source": "thread-origin",
            }
        return {
            "status": "unobserved",
            "reason": self._descendant_reason("thread", thread_origin),
            "ownership_source": "thread-origin",
        }

    def _reserve(self) -> tuple[bool, int]:
        with self._lock:
            attributed = self._inflight < self.max_tasks
            self._inflight += 1
            if not attributed:
                self._overflow += 1
            return attributed, self._overflow

    def _release_factory(self):
        released = False
        release_lock = threading.Lock()

        def release(*_args):
            nonlocal released
            with release_lock:
                if released:
                    return
                released = True
            with self._lock:
                if self._inflight:
                    self._inflight -= 1

        return release

    def _submit(self, executor, fn, args, kwargs):
        original_submit = self._original_submit
        if original_submit is None:
            raise RuntimeError("executor work observer is not installed")

        submitter = threading.current_thread()
        submitted_during = current_test()
        attributed, overflow = self._reserve()
        release = self._release_factory()

        if attributed:
            parent = self._parent_origin(submitter, submitted_during)
            record = {
                "status": parent["status"],
                "callable": callable_identity(fn),
                "submitted_during_test": _safe_text(
                    submitted_during,
                    limit=_MAX_TEST_ID,
                ),
                "submitter_thread": _safe_text(submitter.name),
                "ownership_source": parent["ownership_source"],
                "submit_stack": bounded_call_stack(
                    skip_files=(Path(__file__).name,),
                    max_frames=self.max_frames,
                ),
            }
            if parent["status"] == "observed":
                record["owner_test"] = parent["owner_test"]
            else:
                record.update(
                    {
                        "reason": parent["reason"],
                        "max_tasks": self.max_tasks,
                        "unattributed_submissions": overflow,
                    }
                )
        else:
            record = {
                "status": "unobserved",
                "reason": "observer-capacity",
                "callable": callable_identity(fn),
                "submitted_during_test": _safe_text(
                    submitted_during,
                    limit=_MAX_TEST_ID,
                ),
                "submitter_thread": _safe_text(submitter.name),
                "ownership_source": "capacity",
                "max_tasks": self.max_tasks,
                "unattributed_submissions": overflow,
            }

        def observed_call():
            token = _WORK_CONTEXT.set(record)
            try:
                return fn(*args, **kwargs)
            finally:
                _WORK_CONTEXT.reset(token)
                release()

        try:
            future = original_submit(executor, observed_call)
        except BaseException:
            release()
            raise
        future.add_done_callback(release)
        return future
