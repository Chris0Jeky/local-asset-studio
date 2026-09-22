"""Bounded snapshots and OS-held publication ownership for narration registries."""
from contextlib import contextmanager
import hashlib
import math
import os
from pathlib import Path
import stat
import tempfile
import time

from voice_profile import VoiceProfileError


class RegistryUnconfirmed(VoiceProfileError):
    """Publication may have committed; inspect/replay the original request ID."""


def absolute(path):
    path = Path(os.path.abspath(path))
    if os.name == 'nt':
        try:
            # Inspect links BEFORE resolution; resolving alone erases their evidence.
            _parents(path)
            if os.path.lexists(path): _regular(path.lstat())
            canonical = path.resolve(strict=False)
            # A short filename can refer to the same file but derive a different
            # lock, and replacement via it can delete the long pathname. Refuse
            # aliases consistently for readers and writers instead of changing
            # the requested publication location behind the caller's back.
            if os.path.normcase(str(path)) != os.path.normcase(str(canonical)):
                raise VoiceProfileError('Registry requires its canonical long path; filename aliases are refused')
        except OSError as exc:
            raise VoiceProfileError(f'Cannot inspect registry path: {exc}') from exc
    return path


def _plain(info):
    return not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _parents(path):
    result = []
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not _plain(info) or not stat.S_ISDIR(info.st_mode):
            raise VoiceProfileError('Registry parent must be an existing directory without links')
        result.append((str(parent), info.st_dev, info.st_ino))
    return tuple(result)


def _regular(info):
    if not _plain(info) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise VoiceProfileError('Registry and lock must be regular files without links')


def capture(path, maximum_bytes):
    """Return bytes and a path/handle/content identity; absence is also a snapshot."""
    path = absolute(path)
    descriptor = None
    try:
        parents = _parents(path)
        try:
            before = path.lstat()
        except FileNotFoundError:
            if _parents(path) != parents: raise VoiceProfileError('Registry parent changed')
            return None, (parents, None)
        _regular(before)
        if not 1 <= before.st_size <= maximum_bytes:
            raise VoiceProfileError(f'Registry must contain 1 to {maximum_bytes} bytes')
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(path, flags)
        stream = os.fdopen(descriptor, 'rb')
        descriptor = None  # stream owns it only after fdopen succeeds
        with stream:
            opened = os.fstat(stream.fileno()); _regular(opened)
            # Windows path and descriptor ctime differ in Python 3.12/3.14.
            if _identity(opened)[:4] != _identity(before)[:4]:
                raise VoiceProfileError('Registry changed while opening')
            raw = stream.read(maximum_bytes + 1)
            after = os.fstat(stream.fileno()); _regular(after)
        if (len(raw) != before.st_size or not 1 <= len(raw) <= maximum_bytes
                or _identity(after) != _identity(opened) or _parents(path) != parents
                or _identity(path.lstat()) != _identity(before)):
            raise VoiceProfileError('Registry changed while reading')
        return raw, (parents, _identity(before), hashlib.sha256(raw).hexdigest())
    except OSError as exc:
        raise VoiceProfileError(f'Cannot read registry: {exc}') from exc
    finally:
        if descriptor is not None: os.close(descriptor)


def _unlock(descriptor):
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_UN)


class _Ownership:
    def __init__(self, path, descriptor, parents):
        self.path, self.descriptor, self.parents = path, descriptor, parents

    def check(self):
        if _parents(self.path) != self.parents: raise VoiceProfileError('Registry lock parent changed')
        named, opened = self.path.lstat(), os.fstat(self.descriptor)
        _regular(named); _regular(opened)
        if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
            raise VoiceProfileError('Registry lock changed')


@contextmanager
def writer_lock(path, timeout=5):
    """Keep the lock inode permanently; the OS releases ownership after process death."""
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 <= timeout <= 60:
        raise VoiceProfileError('Registry lock timeout must be from 0 to 60 seconds')
    path = absolute(path).with_name(Path(path).name + '.lock')
    descriptor = None; locked = False
    try:
        parents = _parents(path)
        if os.path.lexists(path): _regular(path.lstat())
        flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(path, flags, 0o600)
        _regular(os.fstat(descriptor))
        owner = _Ownership(path, descriptor, parents); owner.check()
        # Windows byte locks work beyond EOF; do not write before acquiring ownership.
        deadline = time.monotonic() + timeout
        while True:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise VoiceProfileError('Registry lock is busy or inaccessible') from exc
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        owner.check()
        yield owner
    except OSError as exc:
        raise VoiceProfileError(f'Registry lock failed: {exc}') from exc
    finally:
        if descriptor is not None:
            try:
                if locked: _unlock(descriptor)
            finally:
                os.close(descriptor)


def publish(path, raw, expected_identity, maximum_bytes, owner, recheck_catalog):
    """Publish profile and receipt in one replace; uncertain acknowledgements never retry."""
    path = absolute(path)
    temporary = None; descriptor = None; replacing = False
    try:
        owner.check()
        if capture(path, maximum_bytes)[1] != expected_identity:
            raise VoiceProfileError('Registry changed before publication')
        descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '.pending-', dir=path.parent)
        temporary = Path(name)
        stream = os.fdopen(descriptor, 'wb'); descriptor = None
        with stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        pending_identity = capture(temporary, maximum_bytes)[1]
        owner.check(); recheck_catalog()
        if capture(path, maximum_bytes)[1] != expected_identity:
            raise VoiceProfileError('Registry changed before replacement')
        replacing = True
        os.replace(temporary, path)
        temporary = None
        if os.name == 'posix':
            directory = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try: os.fsync(directory)
            finally: os.close(directory)
        owner.check(); recheck_catalog()
        published_raw, published_identity = capture(path, maximum_bytes)
        if (published_raw != raw or published_identity[1][:4] != pending_identity[1][:4]):
            raise VoiceProfileError('Registry changed before acknowledgement')
    except (OSError, VoiceProfileError) as exc:
        if replacing:
            raise RegistryUnconfirmed('Registry publication is unconfirmed; inspect or replay the exact request') from exc
        if isinstance(exc, VoiceProfileError): raise
        raise VoiceProfileError(f'Registry publication refused: {exc}') from exc
    finally:
        if descriptor is not None: os.close(descriptor)
        if temporary is not None:
            try: temporary.unlink()
            except FileNotFoundError: pass
