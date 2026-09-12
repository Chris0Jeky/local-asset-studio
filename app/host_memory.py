"""Read the Windows system commit counters without inspecting GPU or process state."""
import ctypes
import os


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
