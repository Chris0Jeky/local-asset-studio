"""Production plan publication and read-only admission checks, not a job executor.

SQLite owns project visibility; an incomplete-create marker retains filesystem
work across rollback/process loss. No automatic adoption, deletion or repair.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re

KINDS = frozenset(('comparison', 'native', 'articulated'))
PLAN_LIMIT = 16 * 1024**2
MARKER = '.incomplete-create'


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def directory(root, identifier):
    if not isinstance(identifier, str) or not re.fullmatch('[0-9a-f]{32}', identifier):
        raise ValueError('Unknown experiment storage identity')
    path = Path(root) / identifier
    if _linked(path):raise ValueError('Project directory is a link; preserved for inspection')
    return path


def problem(root, identifier, plan, *, preparing=False):
    """Explain missing/inconsistent evidence without writing or changing job state."""
    if plan.get('kind') not in KINDS:return None
    try:
        path = directory(root, identifier)
        if not path.is_dir():return 'Project directory is missing or is not a directory'
        marker = path / MARKER
        if not preparing and (marker.exists() or _linked(marker)):
            return 'Project creation is incomplete; its marker was retained'
        target = path / 'plan.json'
        if _linked(target) or not target.is_file():return 'Project plan.json is missing, not a file, or a link'
        with target.open('rb') as stream:raw = stream.read(PLAN_LIMIT + 1)
        if len(raw) > PLAN_LIMIT:return 'Project plan.json exceeds the 16 MiB inspection limit'
        saved = json.loads(raw)
        if not isinstance(saved, dict) or _canonical(saved) != _canonical(plan):
            return 'Project plan.json differs from the retained database plan'
        digest = hashlib.sha256(_canonical({k: v for k, v in plan.items() if k != 'sha256'})).hexdigest()
        if digest != plan.get('sha256'):return 'Retained project plan fingerprint is invalid'
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        return 'Project storage cannot be inspected: ' + str(exc)[:240]
    return None


def require(root, identifier, plan):
    reason = problem(root, identifier, plan)
    if reason:
        raise ValueError(reason + '. No new work authorized. Inspect retained project files and plan before explicitly starting or resuming; jobs and reservations are preserved.')


def materialize(root, identifier, plan, write_json):
    """Write and read back a new plan before its SQLite project row is committed.

    Called inside the existing writer transaction, after budget/duplicate checks.
    Only bounded metadata I/O happens here, never preparation, network or inference.
    """
    if len(json.dumps(plan, indent=2).encode()) > PLAN_LIMIT:
        raise ValueError('Project plan exceeds the 16 MiB publication limit')
    path = directory(root, identifier)
    path.mkdir()  # A collision belongs to another attempt; never overwrite it.
    with (path / MARKER).open('x', encoding='utf-8') as marker:
        json.dump({'project_id': identifier, 'plan_sha256': plan['sha256'],
                   'note': 'Inspect SQLite and plan.json before recovery. No automatic retry.'}, marker)
        marker.flush();os.fsync(marker.fileno())
    write_json(path / 'plan.json', plan)
    # The shared writer provides atomic replacement. Flush/readback precede DB visibility.
    target = path / 'plan.json'
    if _linked(target):raise ValueError('Project plan became a link; publication refused')
    with target.open('r+b') as stream:os.fsync(stream.fileno())
    reason = problem(root, identifier, plan, preparing=True)
    if reason:raise ValueError(reason)


def complete(root, identifier, plan):
    """Clear only this publication marker after commit; failure leaves admission blocked."""
    reason = problem(root, identifier, plan, preparing=True)
    if reason:raise ValueError(reason)
    (directory(root, identifier) / MARKER).unlink()
