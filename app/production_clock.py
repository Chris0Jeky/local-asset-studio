"""Persistent soft time allowance for a comparison, separate from generation caps.

Only in-process monotonic deltas are measured. A lost active interval or legacy
unmetered run conservatively spends the remaining allowance, explicitly labelled
unmeasured. Offline wall time is never passed off as elapsed execution time.
"""
from __future__ import annotations
import copy
import math

MAX_SECONDS = 14400


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def read(plan, state):
    if 'time_budget' not in state:
        legacy = state.get('started_at') is not None
        return {'version': 1, 'revision': 0, 'limit_seconds': plan['max_seconds'],
                'measured_seconds': 0.0, 'unmeasured_seconds': float(plan['max_seconds']) if legacy else 0.0,
                'recovery_reason': 'legacy_unmetered' if legacy else None, 'amendments': []}
    value = copy.deepcopy(state['time_budget'])
    if (not isinstance(value, dict) or value.get('version') != 1
            or type(value.get('revision')) is not int or value['revision'] < 0
            or type(value.get('limit_seconds')) is not int
            or not plan['max_seconds'] <= value['limit_seconds'] <= MAX_SECONDS
            or any(not _number(value.get(k)) for k in ('measured_seconds', 'unmeasured_seconds'))
            or not isinstance(value.get('amendments'), list)):
        raise ValueError('Invalid retained time budget; preserve the record and inspect it before continuing')
    if 'active' in value:
        active = value['active']
        if (not isinstance(active, dict) or not isinstance(active.get('token'), str) or not active['token']
                or not _number(active.get('reserved_seconds'))
                or active['reserved_seconds'] > remaining(value)):
            raise ValueError('Invalid active time interval; no fresh time allowance was granted')
    return value


def remaining(value):
    return max(0.0, value['limit_seconds'] - value['measured_seconds'] - value['unmeasured_seconds'])


def recover(value):
    value = copy.deepcopy(value)
    if 'active' in value:
        value['unmeasured_seconds'] += value.pop('active')['reserved_seconds']
        value['recovery_reason'] = 'interrupted_unmeasured_interval'
        value['revision'] += 1
    return value


def begin(value, token):
    value = copy.deepcopy(value)
    if 'active' in value: raise ValueError('This comparison already has an active time interval')
    value['active'] = {'token': token, 'reserved_seconds': remaining(value)}
    value['revision'] += 1
    return value


def checkpoint(value, token, elapsed, finish=False):
    value = copy.deepcopy(value)
    if value.get('active', {}).get('token') != token or not _number(elapsed):
        raise ValueError('Time interval identity or elapsed measurement changed; no allowance was reset')
    value['measured_seconds'] += elapsed
    value['revision'] += 1
    if finish: value.pop('active')
    else: value['active']['reserved_seconds'] = remaining(value)
    return value


def extend(value, seconds, reason, recorded_at):
    value = copy.deepcopy(value)
    if 'active' in value: raise ValueError('Wait for the active time interval to finish')
    if type(seconds) is not int or not 60 <= seconds or value['limit_seconds'] + seconds > MAX_SECONDS:
        raise ValueError('Add at least 60 seconds without exceeding the 4-hour total time allowance')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('Give a time extension reason of 1 to 1000 characters')
    previous = value['limit_seconds']
    value['limit_seconds'] += seconds
    value['revision'] += 1
    value['amendments'].append({'revision': value['revision'], 'previous_limit_seconds': previous,
                               'limit_seconds': value['limit_seconds'], 'added_seconds': seconds,
                               'reason': reason.strip(), 'recorded_at': recorded_at})
    return value
