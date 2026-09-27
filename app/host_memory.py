"""Read the Windows system commit counters without inspecting GPU or process state."""
import ctypes
import os
import threading
import time


class _PerformanceInformation(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('CommitTotal', ctypes.c_size_t), ('CommitLimit', ctypes.c_size_t),
               ('CommitPeak', ctypes.c_size_t), ('PhysicalTotal', ctypes.c_size_t), ('PhysicalAvailable', ctypes.c_size_t),
               ('SystemCache', ctypes.c_size_t), ('KernelTotal', ctypes.c_size_t), ('KernelPaged', ctypes.c_size_t),
               ('KernelNonpaged', ctypes.c_size_t), ('PageSize', ctypes.c_size_t), ('HandleCount', ctypes.c_ulong),
               ('ProcessCount', ctypes.c_ulong), ('ThreadCount', ctypes.c_ulong)]


def read():
    """Return system commit headroom in bytes, or an explicit reason it is unknown.

    ``CommitLimit - CommitTotal`` is Windows commit headroom.  It is deliberately
    different from available physical RAM, which is not the limit for the large
    ComfyUI routes this gate protects.
    """
    unknown = {'available_bytes': None, 'limit_bytes': None, 'committed_bytes': None, 'unknown_reason': None}
    if os.name != 'nt': return dict(unknown, unknown_reason='Windows GetPerformanceInfo is unavailable on this host')
    try:
        info = _PerformanceInformation(); info.cb = ctypes.sizeof(info)
        getter = ctypes.windll.psapi.GetPerformanceInfo
        if not getter(ctypes.byref(info), info.cb):
            return dict(unknown, unknown_reason='Windows GetPerformanceInfo failed')
        if not info.PageSize or not info.CommitLimit or info.CommitTotal > info.CommitLimit:
            return dict(unknown, unknown_reason='Windows returned invalid system commit counters')
        committed = int(info.CommitTotal * info.PageSize); limit = int(info.CommitLimit * info.PageSize)
        return {'available_bytes': limit - committed, 'limit_bytes': limit, 'committed_bytes': committed, 'unknown_reason': None}
    except (AttributeError, OSError, ValueError):
        return dict(unknown, unknown_reason='Windows system commit counters could not be read')


# Bound at import: a patched gate reading or clock (tests, callers) is never consumed by the telemetry thread.
_counters, _clock = read, time.time


class Sampler:
    """Samples Windows commit on its own thread while one prompt runs (#302).

    Commit peaks are short: a qwen21 cache release took headroom from 27.4 to 12.7 GiB and back above 32 GiB within
    about 3 s (27 September 2026), so a 0.5 s cadence is used. ``take()`` hands the window to the caller's thread once;
    the thread touches only this object. Unknown readings are counted, never folded in as zero."""
    def __init__(self, interval=0.5, reader=None):
        self.interval, self._reader, self._window = interval, reader, None
        self._lock, self._stop = threading.Lock(), threading.Event()
        self._thread = threading.Thread(target=self._run, name='host-commit-sampler', daemon=True)

    def start(self): self.sample(); self._thread.start(); return self

    def stop(self):
        self._stop.set()
        if self._thread.is_alive(): self._thread.join(timeout=5)
        self.sample()   # the window's last reading, after the prompt settled

    def _run(self):
        while not self._stop.wait(self.interval): self.sample()

    def sample(self):
        try: reading = (self._reader or _counters)()
        except Exception: reading = None
        now = _clock(); committed = reading.get('committed_bytes') if isinstance(reading, dict) else None
        available = reading.get('available_bytes') if isinstance(reading, dict) else None
        known = isinstance(committed, int) and isinstance(available, int) and not reading.get('unknown_reason')
        with self._lock:
            window = self._window or {'samples': 0, 'unknown_samples': 0, 'first_at': now}
            window['last_at'] = now
            if not known: window['unknown_samples'] += 1
            else:
                window['samples'] += 1
                if committed > window.get('peak_committed_bytes', -1):
                    window.update(peak_committed_bytes=committed, peak_at=now, limit_bytes=reading.get('limit_bytes'))
                window['min_available_bytes'] = min(available, window.get('min_available_bytes', available))
            self._window = window

    def take(self):
        """The window seen since the previous call, or None."""
        with self._lock: window, self._window = self._window, None
        return window
