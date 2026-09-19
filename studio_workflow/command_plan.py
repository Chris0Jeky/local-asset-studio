"""Guarded snapshot inverses over the existing command reducer, never a journal."""
from __future__ import annotations
from .core import MAX_BYTES, canonical, decode, digest, document, need
from .commands import apply_commands, state_sha256

FORMAT = 'studio.workflow-command-plan/v1'


def _replacement(expected, replacement):
    commands = [{'op': 'assert_state', 'sha256': state_sha256(expected)},
                {'op': 'replace', 'document': replacement}]
    # Reserve a maximal supported request ID/revision so a returned inverse is
    # usable at the public command boundary, not merely in a local reducer.
    envelope = {'request_id': 'r' * 96, 'expected_revision': 2**53 - 1, 'commands': commands}
    need(len(canonical(envelope)) <= MAX_BYTES,
         'Inverse exceeds the command transport limit; use saved revision restore instead')
    return commands


def plan_commands(source, commands):
    before = document(source)
    commands = decode(canonical(commands))
    after = apply_commands(before, commands)
    return {'format': FORMAT, 'commands': commands, 'document': after,
            'before_document_sha256': digest(before), 'after_document_sha256': digest(after),
            'before_state_sha256': state_sha256(before), 'after_state_sha256': state_sha256(after),
            'inverse_commands': _replacement(after, before), 'redo_commands': _replacement(before, after),
            'committed': False, 'generation_submitted': False}
