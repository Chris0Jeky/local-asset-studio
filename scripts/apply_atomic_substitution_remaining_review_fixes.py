"""One-shot guarded fixes for remaining atomic substitution review findings."""
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
    'studio_workflow/setup_substitution.py',
    "CONTROL = re.compile(r'[a-z][a-z0-9_]{0,63}\\Z')\nSOURCE_STATES",
    "CONTROL = re.compile(r'[a-z][a-z0-9_]{0,63}\\Z')\nREVIEW_REVISION = re.compile(r'sha256:[a-f0-9]{64}\\Z')\nSOURCE_STATES",
    'review revision grammar',
)
replace(
    'studio_workflow/setup_substitution.py',
    """    result['review_revision'] = compatibility.identity(value['review_revision'])
    need(result['review_revision'] is not None,
         'Substitution profile needs an immutable review revision')
""",
    """    need(type(value['review_revision']) is str
         and REVIEW_REVISION.fullmatch(value['review_revision']) is not None,
         'Substitution profile review revision must be sha256:<64 lowercase hex>')
    result['review_revision'] = value['review_revision']
""",
    'immutable review revision',
)
replace(
    'studio_workflow/setup_substitution.py',
    """def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan a zero-side-effect atomic setup substitution')
    parser.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    try:
        raw = args.request.read_bytes()
        need(len(raw) <= MAX_BYTES, 'Request exceeds the 448 KiB limit')
        result = request(decode(raw))
""",
    """def read_json(path: Path):
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    need(len(raw) <= MAX_BYTES, 'Request exceeds the 448 KiB limit')
    return decode(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Plan a zero-side-effect atomic setup substitution')
    parser.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    try:
        result = request(read_json(args.request))
""",
    'bounded CLI read',
)

replace(
    'studio_workflow/agent_bridge.py',
    "TEXT = {'type': 'string', 'maxLength': MAX_BYTES}\nIDENTIFIER",
    """TEXT = {'type': 'string', 'maxLength': MAX_BYTES}
SETUP_COMMAND_JSON = {
    'type': 'string', 'maxLength': MAX_BYTES,
    'description': ('Persisted setup command JSON. action is create, replace, apply, '
                    'substitute, restore or abandon. apply and substitute require an '
                    'expected revision, exact reviewed proposal JSON and its approved '
                    'SHA-256; neither command submits generation.'),
}
IDENTIFIER""",
    'agent setup command schema',
)
replace(
    'studio_workflow/agent_bridge.py',
    """    'setup_draft_command': tool('Explicit Workspace setup create/replace/apply/restore/abandon. Requires exact workspace/request identity and revisions; apply also requires the exact acknowledged proposal. Apply copies source files through Studio but NEVER generates. Persist command JSON before calling; recover by original request ID after any unknown reply.',
        {'command_json': TEXT}, ('command_json',), 'author', True),
""",
    """    'setup_draft_command': tool('Explicit Workspace setup create/replace/apply/substitute/restore/abandon. Requires exact workspace/request identity and revisions. Apply and substitute require the exact acknowledged proposal and SHA-256; substitute appends one complete reviewed draft revision without staging, while apply may copy reviewed source files. Both NEVER generate. Persist command JSON before calling; recover by original request ID after any unknown reply.',
        {'command_json': SETUP_COMMAND_JSON}, ('command_json',), 'author', True),
""",
    'agent setup command discovery',
)

replace(
    'docs/bundle-studio/ATOMIC-SUBSTITUTIONS.md',
    """The planner accepts `studio.setup-substitution-request/v1` with exactly:
""",
    """The planner accepts `studio.setup-substitution-request/v1` with exactly. The CLI
reads at most 448 KiB plus one sentinel byte before decoding, so an oversized local
file is refused without an unbounded allocation:
""",
    'bounded CLI documentation',
)
replace(
    'docs/bundle-studio/ATOMIC-SUBSTITUTIONS.md',
    """- a content-addressed review revision;
""",
    """- a content-addressed `sha256:<64 lowercase hex>` review revision; mutable
  labels such as `review:latest` are refused;
""",
    'review pin documentation',
)

print('Atomic substitution review fixes applied.')
