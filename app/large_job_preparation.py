"""Measured, owner-bound preparation for a large local generation job.

This facade never creates a Studio job or submits a prompt. It consumes the exact
stage-aware profile from ``resource_admission`` and composes bounded decision,
journal, runtime and owned-process lifecycle mixins.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import resource_admission
from large_job_prep_common import JOURNAL_SCHEMA, PreparationError, _digest, _normalize_request
from large_job_prep_actions import ActionMixin
from large_job_prep_flow import FlowMixin
from large_job_prep_journal import JournalMixin
from large_job_prep_lifecycle import LifecycleMixin
from large_job_prep_runtime import RuntimeMixin


class LargeJobPreparation(JournalMixin, RuntimeMixin, LifecycleMixin, ActionMixin, FlowMixin):
    """Serialize and journal one bounded local cleanup command at a time."""

    def __init__(self, studio: Any, *, observer=resource_admission.observe, sleeper=time.sleep,
                 monotonic=time.monotonic, clock=time.time):
        self.studio = studio
        self.observer = observer
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.clock = clock
        self.path = Path(studio.root) / ".runtime" / "large-job-preparation.json"
        self.lock = threading.RLock()


def controller_for(studio: Any) -> LargeJobPreparation:
    controller = getattr(studio, "_large_job_preparation", None)
    if controller is None:
        controller = LargeJobPreparation(studio)
        studio._large_job_preparation = controller
    return controller
