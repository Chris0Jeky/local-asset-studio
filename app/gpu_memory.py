"""Per-process GPU memory from the Windows "GPU Process Memory" counters, and the VRAM reserve ComfyUI needs.

ComfyUI sizes model loads from the free VRAM PyTorch reports, and on this Windows/ROCm box that figure does
not subtract what other processes hold (dwm alone held 2.3 GB on 23 September 2026). A load that ComfyUI logs
as "loaded completely" can therefore overflow into WDDM shared memory, where every step pages weights across
PCIe: Qwen-Image 2.1 ran at 12.5-17.7 s/step that way and at 0.68 s/step once `--reserve-vram` covered the
other processes (experiments/curated/vram-spill-20260923/qwen21-bench.json). `launch_reserve_gib` sizes the
reserve from a live reading; `spill` reports a running ComfyUI process's shared-memory use as evidence.
"""
from __future__ import annotations

import ctypes
import math
import os
import re
import threading

GIB = 1024 ** 3
# ComfyUI's own Windows margin for 16 GB cards (600 + 100 MiB, model_management.py EXTRA_RESERVED_VRAM).
MARGIN_GIB = 0.7
FLOOR_GIB = 0.6
CAP_GIB = 6.0
# Used when the counters cannot be read: other processes held 3.3-3.8 GB on 23 September 2026.
FALLBACK_GIB = 4.0
# Shared usage below this is ordinary driver bookkeeping (78 MB on a run that did not spill).
SPILL_BYTES = 512 * 1024 ** 2
_INSTANCE = re.compile(r'pid_(\d+)_luid_(0x[0-9A-Fa-f]+_0x[0-9A-Fa-f]+)_phys_(\d+)')


def parse(dedicated, shared):
    """Fold `{instance: bytes}` counter arrays into per-adapter, per-process totals.

    Instances look like ``pid_2304_luid_0x00000000_0x000102FB_phys_0``; one process can appear once per adapter.
    """
    adapters = {}
    for kind, values in (('dedicated_bytes', dedicated), ('shared_bytes', shared)):
        for name, value in values.items():
            match = _INSTANCE.fullmatch(name)
            if not match or not isinstance(value, (int, float)) or value < 0: continue
            pid, adapter = int(match.group(1)), match.group(2).lower() + '_' + match.group(3)
            record = adapters.setdefault(adapter, {}).setdefault(pid, {'dedicated_bytes': 0, 'shared_bytes': 0})
            record[kind] += int(value)
    return adapters


def select_adapter(adapters, pid=None):
    """The adapter a ComfyUI process uses, or else the one holding the most dedicated memory (the discrete GPU)."""
    if pid is not None:
        owned = [a for a, processes in adapters.items() if processes.get(pid, {}).get('dedicated_bytes', 0) > 0]
        if owned: return max(owned, key=lambda a: adapters[a][pid]['dedicated_bytes'])
    if not adapters: return None
    return max(adapters, key=lambda a: sum(p['dedicated_bytes'] for p in adapters[a].values()))


def _read_counter(pdh, path):
    """One PDH wildcard counter as `{instance: value}`; raises OSError on any PDH failure."""
    class Value(ctypes.Structure):
        _fields_ = [('CStatus', ctypes.c_ulong), ('largeValue', ctypes.c_longlong)]

    class Item(ctypes.Structure):
        _fields_ = [('szName', ctypes.c_wchar_p), ('FmtValue', Value)]

    query, counter = ctypes.c_void_p(), ctypes.c_void_p()
    if pdh.PdhOpenQueryW(None, None, ctypes.byref(query)): raise OSError('PdhOpenQuery failed')
    try:
        if pdh.PdhAddEnglishCounterW(query, path, None, ctypes.byref(counter)): raise OSError('PdhAddEnglishCounter failed')
        if pdh.PdhCollectQueryData(query): raise OSError('PdhCollectQueryData failed')
        size, count = ctypes.c_ulong(0), ctypes.c_ulong(0)
        PDH_MORE_DATA, PDH_FMT_LARGE = 0x800007D2, 0x00000400
        # PDH returns 32-bit status codes; ctypes hands them back as signed ints.
        status = pdh.PdhGetFormattedCounterArrayW(counter, PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count), None) & 0xFFFFFFFF
        if status != PDH_MORE_DATA: return {}
        buffer = (ctypes.c_byte * size.value)()
        if pdh.PdhGetFormattedCounterArrayW(counter, PDH_FMT_LARGE, ctypes.byref(size), ctypes.byref(count), buffer):
            raise OSError('PdhGetFormattedCounterArray failed')
        items = ctypes.cast(buffer, ctypes.POINTER(Item))
        return {items[i].szName: items[i].FmtValue.largeValue for i in range(count.value) if items[i].FmtValue.CStatus in (0, 1)}
    finally:
        pdh.PdhCloseQuery(query)


def read():
    """Return per-adapter, per-process GPU memory, or an explicit reason it is unknown. Never raises."""
    if os.name != 'nt': return {'adapters': None, 'unknown_reason': 'Windows GPU performance counters are unavailable on this host'}
    try:
        pdh = ctypes.windll.pdh
        dedicated = _read_counter(pdh, r'\GPU Process Memory(*)\Dedicated Usage')
        shared = _read_counter(pdh, r'\GPU Process Memory(*)\Shared Usage')
    except (AttributeError, OSError, ValueError) as exc:
        return {'adapters': None, 'unknown_reason': 'Windows GPU process memory counters could not be read: ' + str(exc)[:200]}
    adapters = parse(dedicated, shared)
    if not adapters: return {'adapters': None, 'unknown_reason': 'No GPU process memory instances were reported'}
    return {'adapters': adapters, 'unknown_reason': None}


def launch_reserve_gib(reading=None, exclude_pids=()):
    """`--reserve-vram` for a ComfyUI about to start: what every other process holds on the GPU plus ComfyUI's margin."""
    reading = read() if reading is None else reading
    adapters = reading.get('adapters') if isinstance(reading, dict) else None
    adapter = select_adapter(adapters) if adapters else None
    if adapter is None: return {'reserve_gib': FALLBACK_GIB, 'others_bytes': None, 'adapter': None,
                                'basis': 'fallback', 'unknown_reason': (reading or {}).get('unknown_reason') or 'No adapter reading'}
    exclude = set(exclude_pids)
    others = sum(p['dedicated_bytes'] for pid, p in adapters[adapter].items() if pid not in exclude)
    reserve = min(CAP_GIB, max(FLOOR_GIB, math.ceil((others / GIB + MARGIN_GIB) * 10) / 10))
    return {'reserve_gib': reserve, 'others_bytes': others, 'adapter': adapter, 'basis': 'measured', 'unknown_reason': None}


def others_bytes(reading, pid):
    """Dedicated memory every other process holds on `pid`'s adapter, or None when the reading has no adapters."""
    adapters = reading.get('adapters') if isinstance(reading, dict) else None
    adapter = select_adapter(adapters, pid) if adapters else None
    if adapter is None: return None
    return sum(p['dedicated_bytes'] for other, p in adapters[adapter].items() if other != pid)


def holders(reading, pid, top=3):
    """The largest other dedicated-memory holders on `pid`'s adapter as `[{pid, name, dedicated_bytes}]`, largest first."""
    adapters = reading.get('adapters') if isinstance(reading, dict) else None
    adapter = select_adapter(adapters, pid) if adapters else None
    if adapter is None: return []
    ranked = sorted(((other, p['dedicated_bytes']) for other, p in adapters[adapter].items() if other != pid), key=lambda item: -item[1])[:top]
    rows = []
    for other, value in ranked:
        try:
            import psutil
            name = psutil.Process(other).name()
        except Exception: name = None
        rows.append({'pid': other, 'name': name, 'dedicated_bytes': value})
    return rows


def spill(pid, reading=None):
    """A running ComfyUI process's dedicated and shared GPU memory; `spilled` when shared use shows WDDM paging."""
    if pid is None: return {'pid': None, 'dedicated_bytes': None, 'shared_bytes': None, 'spilled': None, 'unknown_reason': 'No ComfyUI process to measure'}
    reading = read() if reading is None else reading
    adapters = reading.get('adapters') if isinstance(reading, dict) else None
    if not adapters:
        return {'pid': pid, 'dedicated_bytes': None, 'shared_bytes': None, 'spilled': None,
                'unknown_reason': (reading or {}).get('unknown_reason') or 'No ComfyUI process to measure'}
    adapter = select_adapter(adapters, pid)
    usage = adapters.get(adapter, {}).get(pid)
    if usage is None: return {'pid': pid, 'dedicated_bytes': None, 'shared_bytes': None, 'spilled': None, 'unknown_reason': 'The ComfyUI process holds no GPU memory'}
    return {'pid': pid, 'adapter': adapter, 'dedicated_bytes': usage['dedicated_bytes'], 'shared_bytes': usage['shared_bytes'],
            'spilled': usage['shared_bytes'] >= SPILL_BYTES, 'unknown_reason': None}


class Sampler:
    """Samples one process's GPU memory on its own thread while a prompt runs.

    A VAE decode's overflow into shared memory lasts about 3 s (23 September 2026), so the Studio's 10 s poll cadence missed
    most of them. The thread touches only this object; `take()` hands the peaks since the last call to the caller's thread,
    so no job state is shared across threads. At each new shared-memory peak it keeps the largest other holders."""
    def __init__(self, pid, interval=0.5, reader=None):
        self.pid, self.interval, self._reader = pid, interval, reader
        self._lock, self._stop, self._peak = threading.Lock(), threading.Event(), None
        self._thread = threading.Thread(target=self._run, name='gpu-memory-sampler', daemon=True)

    def start(self): self._thread.start(); return self

    def stop(self):
        self._stop.set()
        if self._thread.is_alive(): self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.wait(self.interval): self.sample()

    def sample(self):
        """One reading folded into the pending peaks; failures record nothing."""
        try:
            reading = (self._reader or read)(); usage = spill(self.pid, reading)
            if usage.get('shared_bytes') is None: return
            top = holders(reading, self.pid) if usage['shared_bytes'] >= SPILL_BYTES else None
        except Exception: return
        with self._lock:
            peak = self._peak or {'peak_shared_bytes': 0, 'peak_dedicated_bytes': 0, 'samples': 0, 'holders': None}
            peak['samples'] += 1; peak['peak_dedicated_bytes'] = max(peak['peak_dedicated_bytes'], usage['dedicated_bytes'] or 0)
            if usage['shared_bytes'] > peak['peak_shared_bytes']:
                peak['peak_shared_bytes'] = usage['shared_bytes']
                if top: peak['holders'] = top
            self._peak = peak

    def take(self):
        """The peaks seen since the previous call, or None."""
        with self._lock: peak, self._peak = self._peak, None
        return peak


if __name__ == '__main__':
    import json, sys
    if sys.argv[1:] == ['--reserve']: print(json.dumps(launch_reserve_gib()))
    else:
        reading = read(); print(json.dumps(reading if reading['adapters'] is None else {a: {str(k): v for k, v in p.items()} for a, p in reading['adapters'].items()}, indent=1))
