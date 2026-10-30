"""Which commit the Studio runs: read once at start from .git, so /api/health can show stale code without a shell per request."""
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r'[0-9a-f]{40}')


def _text(path):
    try: return Path(path).read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError): return ''


def head_sha(root):
    """Full HEAD commit of the checkout at root, or None. Reads .git/HEAD (a worktree's .git file points at its gitdir) and resolves the ref through loose files then packed-refs; git rev-parse runs once only when a .git exists but is not readable this way. Never raises."""
    try:
        root = Path(root); dot = root / '.git'
        if dot.is_file():
            line = _text(dot)
            if not line.startswith('gitdir:'): return None
            gitdir = Path(line[7:].strip()); gitdir = gitdir if gitdir.is_absolute() else root / gitdir
        elif dot.is_dir(): gitdir = dot
        else: return None
        common = _text(gitdir / 'commondir'); common = (gitdir / common) if common else gitdir
        head = _text(gitdir / 'HEAD')
        if SHA.fullmatch(head): return head
        if head.startswith('ref:'):
            ref = head[4:].strip()
            for base in (gitdir, common):
                found = _text(base / ref)
                if SHA.fullmatch(found): return found
            for entry in _text(common / 'packed-refs').splitlines():
                value, _, name = entry.partition(' ')
                if name == ref and SHA.fullmatch(value): return value
        out = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=5).stdout.strip()
        return out if SHA.fullmatch(out) else None
    except Exception: return None


def build_info(root):
    return {'sha': head_sha(root), 'started_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
