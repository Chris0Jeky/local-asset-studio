"""One-shot guarded fixes for atomic substitution review findings."""
from pathlib import Path


def replace(path: str, old: str, new: str, label: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    print(f'{label}: {count} exact match(es)')
    if count != 1:
        raise SystemExit(f'{label}: expected one exact match, found {count}')
    target.write_text(text.replace(old, new), encoding='utf-8')


replace(
    'studio_workflow/setup_drafts.py',
    """        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error,RecursionError) as exc:
            receipt.update(status='failed',message=str(exc)[:500])
            self._progress(receipt,sha)
            with self.workspace.connection() as db:return self._result(db,receipt)

    def _apply(self,value,sha,receipt,current):
""",
    """        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error,RecursionError) as exc:
            # A commit-receipt failure rolls the SQLite transaction back, including
            # the appended revision. Do not persist metadata for that nonexistent
            # revision in the independent failed-operation receipt.
            for key in ('previous_revision','approved_proposal_sha256','changes'):
                receipt.pop(key,None)
            receipt.update(status='failed',revision=None,message=str(exc)[:500])
            self._progress(receipt,sha)
            with self.workspace.connection() as db:return self._result(db,receipt)

    def _apply(self,value,sha,receipt,current):
""",
    'rolled-back receipt metadata',
)

path = Path('studio_workflow/setup_substitution.py')
text = path.read_text(encoding='utf-8')
old = 'MAX_BYTES = 1024 * 1024\n'
new = "# Keep the canonical proposal below the shared command envelope even when\n# every byte must be JSON-escaped by the outer setup_draft_command.\nMAX_BYTES = 448 * 1024\n"
count = text.count(old)
print(f'proposal byte cap: {count} exact match(es)')
if count != 1:
    raise SystemExit(f'proposal byte cap: expected one exact match, found {count}')
text = text.replace(old, new)
count = text.count('1 MiB')
print(f'proposal limit labels: {count} occurrence(s)')
if count != 4:
    raise SystemExit(f'proposal limit labels: expected four occurrences, found {count}')
path.write_text(text.replace('1 MiB', '448 KiB'), encoding='utf-8')

replace(
    'docs/bundle-studio/ATOMIC-SUBSTITUTIONS.md',
    """The proposal hash covers the request and all derived output. The shared-draft
command requires both those exact bytes and the acknowledged SHA-256. It
recomputes the proposal before writing.
""",
    """The proposal hash covers the request and all derived output. Canonical proposal
bytes are capped at 448 KiB so even worst-case JSON escaping fits the existing
1 MiB shared-command envelope. The shared-draft command requires both those
exact bytes and the acknowledged SHA-256. It recomputes the proposal before
writing.
""",
    'command-envelope documentation',
)

print('Atomic substitution review fixes applied.')
