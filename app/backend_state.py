"""Conservative ownership and compare-and-publish for shared backend switch records.

All cooperating Studio writers use the permanent OS-held lock. This is not a
runtime launch lease, and older Studio versions do not participate in it.
"""
from contextlib import contextmanager
import copy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid

import psutil
import file_replace

MAX_BYTES = 128 * 1024
LOCK_TIMEOUT = 2.0
WINDOWS = os.name == 'nt'


class StateError(ValueError): pass
class StateConflict(StateError): pass
class StateUnconfirmed(StateError): pass


def _finite(value):
    try:return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0
    except OverflowError:return False


def valid_owner(owner):
    return (isinstance(owner, dict) and type(owner.get('version')) is int and owner['version'] == 1
            and type(owner.get('pid')) is int and 0 < owner['pid'] <= 2**32 - 1
            and _finite(owner.get('created_at')) and isinstance(owner.get('instance_id'), str)
            and 1 <= len(owner['instance_id']) <= 128)


def current_owner():
    """Capture this Studio process, never the backend child or a record's PID."""
    try:
        owner = {'version': 1, 'pid': os.getpid(), 'created_at': psutil.Process(os.getpid()).create_time(),
                 'instance_id': uuid.uuid4().hex}
        return owner if valid_owner(owner) else None
    except (psutil.Error, OSError, ValueError): return None


def owner_status(owner):
    """Only a fresh NoSuchProcess proves absence. Clock/PID-reuse mismatches are unknown."""
    if not valid_owner(owner): return 'unknown'
    try: created = psutil.Process(owner['pid']).create_time()
    except psutil.ZombieProcess: return 'unknown'
    except psutil.NoSuchProcess: return 'absent'
    except (psutil.Error, OSError, ValueError): return 'unknown'
    return 'live' if _finite(created) and created == owner['created_at'] else 'unknown'


def blocker(value):
    operation = value.get('operation')
    if not isinstance(operation, dict): return None
    if operation.get('inspection_required'):
        return ('The saved backend switch requires inspection: its Studio may have started a runtime before '
                'recording the outcome. Inspect the runtimes and use Resolve saved switch in Models & setup when offered; Reset recovery does not clear it.')
    if operation.get('status') == 'running':
        if 'owner' not in operation:
            return ('The shared running backend switch has no recorded Studio owner (legacy record). '
                    'After closing other Studios and inspecting the runtimes, use Resolve saved switch in Models & setup. Reset recovery does not clear it.')
        if not valid_owner(operation.get('owner')):
            return ('The shared running backend switch has an unreadable or unsupported Studio owner. '
                    'Preserve its record and logs for inspection; resolution is unavailable while ownership is unknown.')
        return (f"Shared backend state records a switch to '{operation.get('target') or 'unknown'}' as running. "
                'Its Studio owner has not been proven absent. Wait for it, or restart Studio after inspection; '
                'Models & setup cannot replace an unresolved switch. Reset recovery does not clear a shared switch.')
    if operation.get('status') not in ('completed', 'failed', 'interrupted'):
        return 'The saved backend switch status is unknown; preserve its record and logs for inspection. Switching is blocked.'
    return None


def resolution_allowed(value, this_owner=None):
    """The manager separately excludes its active worker under the Studio lock."""
    operation = value.get('operation')
    if not isinstance(operation, dict) or not (operation.get('status') == 'running' or operation.get('inspection_required')): return False
    # Legacy ownership cannot be reconstructed. Only the explicit operator attestation can resolve it.
    if 'owner' not in operation: return True
    if not valid_owner(operation['owner']) or not valid_owner(this_owner): return False
    if operation['owner'] == this_owner: return True
    return owner_status(operation['owner']) == 'absent'


def _regular(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, 'st_file_attributes', 0) & 0x400:
        raise StateError('Backend state and lock must be regular files without links')


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


@dataclass(frozen=True)
class Snapshot:
    value: dict
    identity: tuple | None


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise StateError('Backend state has duplicate fields')
        result[key] = value
    return result


def read(path):
    """An absent file is a first-run snapshot; unreadable or changing state is not absence."""
    path = Path(path)
    try:
        try: before = path.lstat()
        except FileNotFoundError: return Snapshot({'active': 'primary', 'operation': None}, None)
        _regular(before)
        if not 1 <= before.st_size <= MAX_BYTES: raise StateError('Backend state has an invalid size')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno()); _regular(opened)
            # Python's Windows path and descriptor ctime may differ.
            if _identity(opened)[:4] != _identity(before)[:4]: raise StateConflict('Backend state changed while opening')
            raw = stream.read(MAX_BYTES + 1)
            if _identity(os.fstat(stream.fileno())) != _identity(opened): raise StateConflict('Backend state changed while reading')
        if len(raw) != before.st_size or _identity(path.lstat()) != _identity(before):
            raise StateConflict('Backend state changed while reading')
        value = json.loads(raw, object_pairs_hook=_object, parse_constant=lambda _: (_ for _ in ()).throw(StateError('Backend state has a non-finite number')))
        if (not isinstance(value, dict) or not isinstance(value.get('active'), str) or not value['active']
                or (value.get('operation') is not None and not isinstance(value['operation'], dict))
                or type(value.get('revision', 0)) is not int or value.get('revision', 0) < 0):
            raise StateError('Backend state has an invalid record')
        return Snapshot(value, (_identity(before), hashlib.sha256(raw).hexdigest()))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, StateError): raise
        raise StateError('Cannot read backend state: ' + str(exc)[:200]) from exc


def _lock_fd(descriptor, release=False):
    os.lseek(descriptor, 0, os.SEEK_SET)
    if WINDOWS:
        import msvcrt
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB)


class _Lock:
    def __init__(self, path, descriptor):
        self.path, self.descriptor = path, descriptor
        parent = path.parent.stat(); self.parent = parent.st_dev, parent.st_ino
        self.check()

    def check(self):
        parent = self.path.parent.stat()
        if (parent.st_dev, parent.st_ino) != self.parent: raise StateConflict('Backend state lock parent changed')
        named, opened = self.path.lstat(), os.fstat(self.descriptor)
        _regular(named); _regular(opened)
        if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino): raise StateConflict('Backend state lock changed')


@contextmanager
def writer_lock(path, timeout=LOCK_TIMEOUT):
    """Keep the lock file permanently; process exit releases its OS-held ownership."""
    path = Path(path).with_name(Path(path).name + '.lock')
    descriptor = None; locked = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(path): _regular(path.lstat())
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        owner = _Lock(path, descriptor); deadline = time.monotonic() + timeout
        while True:
            try: _lock_fd(descriptor); locked = True; break
            except OSError as exc:
                if time.monotonic() >= deadline: raise StateError('Backend state writer lock is busy or inaccessible') from exc
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        owner.check(); yield owner
    except OSError as exc: raise StateError('Backend state writer lock failed: ' + str(exc)[:200]) from exc
    finally:
        if descriptor is not None:
            try:
                if locked: _lock_fd(descriptor, release=True)
            finally: os.close(descriptor)


class Store:
    def __init__(self, path):
        path = Path(path); self.path = path.parent.resolve(strict=False) / path.name

    def read(self): return read(self.path)

    def _expected(self, expected, lock):
        lock.check(); current = self.read()
        if expected is None or current.identity != expected.identity: raise StateConflict('Shared backend state changed; inspect its current operation and retry explicitly')
        return current

    @staticmethod
    def _owned(current, token):
        operation = current.value.get('operation')
        if (not isinstance(operation, dict) or operation.get('status') != 'running'
                or not token or operation.get('id') != token['id'] or operation.get('owner') != token['owner']):
            raise StateConflict('This Studio no longer owns the saved backend switch')

    def check_owned(self, expected, token):
        with writer_lock(self.path) as lock: self._owned(self._expected(expected, lock), token)

    def _publish(self, expected, value, lock):
        self._expected(expected, lock)
        try:
            value = copy.deepcopy(value); value['revision'] = expected.value.get('revision', 0) + 1
            raw = json.dumps(value, indent=2, allow_nan=False).encode('utf-8')
        except (TypeError, ValueError, RecursionError) as exc:
            raise StateError('Backend state could not be serialized; the saved operation was preserved') from exc
        if len(raw) > MAX_BYTES: raise StateError('Backend state exceeds the observation limit')
        pending = None; replacing = False
        try:
            descriptor, name = tempfile.mkstemp(prefix='.backend-state-', suffix='.tmp', dir=self.path.parent)
            pending = Path(name)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            pending_identity=_identity(pending.stat())[:4]
            self._expected(expected, lock)
            replacing = True; file_replace.replace(pending, self.path); pending = None
            if os.name == 'posix':
                directory=os.open(self.path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
                try:os.fsync(directory)
                finally:os.close(directory)
            lock.check(); landed = self.read()
            if landed.value != value or landed.identity[0][:4] != pending_identity:
                raise StateUnconfirmed('Backend state publication could not be confirmed')
            return landed
        except (OSError, StateError) as exc:
            if replacing: raise StateUnconfirmed('Backend state publication is unconfirmed; inspect the saved operation before retrying') from exc
            if isinstance(exc, StateError): raise
            raise StateError('Cannot publish backend state: ' + str(exc)[:200]) from exc
        finally:
            if pending is not None:
                try: pending.unlink()
                except OSError: pass

    def reserve(self, expected, operation):
        if not valid_owner(operation.get('owner')): raise StateError('Cannot identify this Studio process; no backend switch was started')
        with writer_lock(self.path) as lock:
            current = self._expected(expected, lock); reason = blocker(current.value)
            if reason: raise StateError(reason)
            value = copy.deepcopy(current.value); value['operation'] = copy.deepcopy(operation)
            return self._publish(current, value, lock)

    def update(self, expected, token, operation, active=None):
        with writer_lock(self.path) as lock:
            current = self._expected(expected, lock); self._owned(current, token)
            if operation.get('id') != token['id'] or operation.get('owner') != token['owner']:
                raise StateConflict('Backend switch owner cannot change during an operation')
            value = copy.deepcopy(current.value); value['operation'] = copy.deepcopy(operation)
            if active is not None: value['active'] = active
            return self._publish(current, value, lock)

    def reconcile(self, expected):
        operation = expected.value.get('operation')
        if not isinstance(operation, dict) or operation.get('status') != 'running': return expected
        with writer_lock(self.path) as lock:
            current = self._expected(expected, lock); operation = current.value['operation']
            if owner_status(operation.get('owner')) != 'absent': return current
            value = copy.deepcopy(current.value); operation = value['operation']
            inspect = bool(operation.get('inspection_required')) or operation.get('phase') not in ('checking', 'stopping')
            operation.update(status='interrupted', reconciled_at=time.time(), reconciliation='owner_process_absent',
                             inspection_required=inspect,
                             message='The recorded Studio owner exited. ' + ('Runtime launch outcome requires inspection.' if inspect else 'The switch ended before launch intent.'))
            return self._publish(current, value, lock)

    def resolve(self, expected, payload, this_owner=None):
        if (not isinstance(payload,dict) or payload.get('acknowledge_studios_closed') is not True
                or payload.get('acknowledge_runtimes_inspected') is not True):
            raise StateError('Confirm that every other Studio instance is closed and the runtimes and startup logs were inspected')
        if expected.identity is None or payload.get('expected_sha256') != expected.identity[1]:
            raise StateConflict('The saved switch changed; refresh Models & setup and inspect the current operation')
        with writer_lock(self.path) as lock:
            current=self._expected(expected,lock)
            if not resolution_allowed(current.value,this_owner):
                raise StateError('The switch owner is live or unverified, or this record does not need resolution; the saved operation was preserved')
            value=copy.deepcopy(current.value);operation=value['operation']
            operation.update(status='interrupted',inspection_required=False,
                             message='Saved switch resolved after explicit inspection. Select the intended environment in Models & setup.')
            operation['resolution']={'at':time.time(),'expected_sha256':payload['expected_sha256'],
                                     'acknowledge_studios_closed':True,'acknowledge_runtimes_inspected':True,
                                     'resolved_by':copy.deepcopy(this_owner)}
            return self._publish(current,value,lock)
