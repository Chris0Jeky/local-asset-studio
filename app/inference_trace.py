"""Bounded offline PyTorch/Kineto span inventory, not job timing or authority.

Chrome trace timestamps/durations are microseconds; displayTimeUnit is cosmetic.
Arguments and arbitrary labels are never copied into the redacted result.
"""
from __future__ import annotations

from decimal import Decimal, DecimalException
import hashlib
import json
import re

MAX_BYTES = 1024 * 1024
MAX_EVENTS = 4096
MAX_LANES = 64
MAX_OPERATORS = 128
MAX_REPORT_BYTES = 64 * 1024
CATEGORIES = {'cpu_op': 'host_operator', 'cuda_runtime': 'host_runtime',
              'hip_runtime': 'host_runtime', 'kernel': 'device_kernel',
              'gpu_memcpy': 'device_copy', 'gpu_memset': 'device_set'}
SAFE_NAMES = frozenset(('aten::mm', 'aten::bmm', 'aten::matmul', 'aten::addmm',
    'aten::linear', 'aten::copy_', 'aten::_to_copy', 'aten::to', 'aten::clone',
    'aten::contiguous', 'aten::reshape', 'aten::view', 'aten::permute',
    'aten::as_strided', 'aten::conv2d', 'aten::convolution',
    'aten::scaled_dot_product_attention', 'aten::_scaled_dot_product_flash_attention'))


class TraceError(ValueError):
    """Stable payload-free refusal; source data never appears in diagnostics."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(condition, code):
    if not condition: raise TraceError(code)


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, 'trace_json_invalid')
        result[key] = value
    return result


def _constant(value):
    raise TraceError('trace_json_invalid')


def _bounded(value, depth=1):
    if isinstance(value, (dict, list)):
        _require(depth <= 32, 'trace_json_invalid')
    if isinstance(value, dict):
        for key, child in value.items():
            _bounded(key, depth + 1); _bounded(child, depth + 1)
    elif isinstance(value, list):
        for child in value: _bounded(child, depth + 1)
    elif isinstance(value, str):
        _require(not any(0xd800 <= ord(c) <= 0xdfff for c in value), 'trace_json_invalid')
    elif isinstance(value, Decimal):
        _require(value.is_finite(), 'trace_json_invalid')


def _identity(parts):
    raw = json.dumps(parts, separators=(',', ':'), ensure_ascii=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _lane_id(value):
    return (type(value) is int and 0 <= value <= 2**63 - 1
            or isinstance(value, str) and 0 < len(value) <= 128)


def _ns(value, maximum):
    _require(type(value) is int or isinstance(value, Decimal), 'trace_time_invalid')
    _require(0 <= value <= maximum, 'trace_time_invalid')
    if type(value) is int: return value * 1000
    if value == 0: return 0
    # Avoid Decimal's ambient precision rounding sub-nanosecond input to an
    # apparent exact integer, or constructing giant integers for tiny exponents.
    parts = value.as_tuple(); digits = list(parts.digits); exponent = parts.exponent
    while digits[-1] == 0:
        digits.pop(); exponent += 1
    _require(exponent >= -3, 'trace_time_precision')
    _require(len(digits) <= 32 and exponent <= 16, 'trace_time_invalid')
    coefficient = 0
    for digit in digits: coefficient = coefficient * 10 + digit
    return coefficient * 10 ** (exponent + 3)


def _union(spans):
    """Union within one category/process/thread only; no cross-clock addition."""
    total = 0; end = None
    for start, stop in sorted(spans):
        if end is None or start > end:
            total += stop - start; end = stop
        elif stop > end:
            total += stop - end; end = stop
    return total


def summarize_trace(raw: bytes, *, expected_sha256: str | None = None) -> dict:
    """Inspect a bounded saved trace without importing Torch or observing a process."""
    _require(isinstance(raw, bytes), 'trace_bytes_required')
    _require(len(raw) <= MAX_BYTES, 'trace_too_large')
    identity = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        _require(isinstance(expected_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_sha256),
                 'expected_hash_invalid')
        _require(identity == expected_sha256, 'trace_hash_mismatch')
    try:
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                              parse_float=Decimal, parse_constant=_constant)
        _bounded(document)
    except (ValueError, UnicodeError, RecursionError, OverflowError, DecimalException):
        raise TraceError('trace_json_invalid') from None
    _require(isinstance(document, dict) and type(document.get('schemaVersion')) is int
             and document['schemaVersion'] == 1 and isinstance(document.get('traceEvents'), list),
             'trace_format_unsupported')
    events = document['traceEvents']
    _require(len(events) <= MAX_EVENTS, 'trace_events_exceeded')
    lanes = {}; operators = {}; ignored = 0; unsupported = 0; recognized = 0
    for event in events:
        _require(isinstance(event, dict) and isinstance(event.get('ph'), str), 'trace_event_invalid')
        category = event.get('cat'); phase = event['ph']
        if not isinstance(category, str) or category not in CATEGORIES or phase != 'X':
            ignored += 1
            if phase in ('X', 'B', 'E', 'b', 'e'): unsupported += 1
            continue
        name = event.get('name')
        _require(isinstance(name, str) and 0 < len(name) <= 4096, 'trace_name_invalid')
        _require(_lane_id(event.get('pid')) and _lane_id(event.get('tid')), 'trace_lane_invalid')
        start = _ns(event.get('ts'), 2**53)
        duration = _ns(event.get('dur'), 300_000_000)
        _require(start + duration <= 2**53 * 1000, 'trace_time_invalid')
        lane_key = _identity([category, event['pid'], event['tid']])
        operator_key = _identity([category, name])
        if lane_key not in lanes:
            _require(len(lanes) < MAX_LANES, 'trace_lanes_exceeded')
            lanes[lane_key] = {'category': category, 'spans': []}
        if operator_key not in operators:
            _require(len(operators) < MAX_OPERATORS, 'trace_operators_exceeded')
            operators[operator_key] = {'identity_sha256': operator_key, 'category': category,
                'label': name if category == 'cpu_op' and name in SAFE_NAMES else 'redacted',
                'events': 0, 'inclusive_duration_ns': 0, 'max_duration_ns': 0, '_lanes': set()}
        lanes[lane_key]['spans'].append((start, start + duration))
        row = operators[operator_key]; row['events'] += 1; row['_lanes'].add(lane_key)
        row['inclusive_duration_ns'] += duration
        row['max_duration_ns'] = max(row['max_duration_ns'], duration)
        recognized += 1
    lane_rows = []
    for key, lane in sorted(lanes.items()):
        spans = lane['spans']
        lane_rows.append({'identity_sha256': key, 'category': lane['category'],
            'kind': CATEGORIES[lane['category']], 'events': len(spans),
            'inclusive_duration_ns': sum(stop-start for start, stop in spans),
            'active_union_ns': _union(spans),
            'span_ns': max(stop for _, stop in spans) - min(start for start, _ in spans)})
    for row in operators.values():
        row['lane_count'] = len(row.pop('_lanes'))
        row['aggregation'] = 'category_and_name_across_lanes'
    rows = sorted(operators.values(), key=lambda row: (-row['inclusive_duration_ns'], row['identity_sha256']))
    device = any(row['kind'].startswith('device_') for row in lane_rows)
    result = {'schema': 'studio.inference-trace-summary/v2', 'input_sha256': identity,
        'input_bytes': len(raw), 'reader_format': 'pytorch-kineto-chrome-x/v1',
        'producer_identity': 'unverified',
        'status': 'observed_subset' if recognized else 'no_supported_events',
        'input_events': len(events), 'recognized_events': recognized, 'ignored_events': ignored,
        'unsupported_duration_events': unsupported, 'lanes': lane_rows, 'operators': rows[:32],
        'omitted_operator_rows': max(0, len(rows)-32),
        'device_timing': {'status': 'observed' if device else 'unavailable', 'coverage': None,
                          'reason': 'supported_spans_only' if device else 'no_supported_device_spans'},
        'job_binding': 'unbound', 'job_wall_time_ns': None, 'causal_speedup_qualified': False,
        'limitations': ['inclusive_durations_can_overlap', 'lanes_are_not_additive_wall_time',
                       'operator_totals_aggregate_across_lanes',
                       'capture_completeness_and_clock_alignment_unverified',
                       'no_job_runtime_or_model_identity_inferred', 'unknown_labels_redacted']}
    _require(len(json.dumps(result, sort_keys=True, indent=2).encode('utf-8')) + 1 <= MAX_REPORT_BYTES,
             'trace_report_too_large')
    return result
