#!/usr/bin/env python3
"""Hash-bound transcript QA and separate immutable owner listening records."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

from spoken_brief_archive import checked_directory, checked_json, inspect_run, require_archive
from spoken_brief_compile import SPEAKER_RE, SpokenBriefError, canonical_digest, digest_bytes
from spoken_brief_exports import _claim, _json_bytes
from spoken_brief_inbox import HEX, _capture, _lineage
from spoken_brief_transport import MAX_JSON_BYTES, _sync_parent
from spoken_brief_transcript import NORMALIZATION_VERSION, _text, compare_text, validate_lexicon

MAX_RECORDS = 128
FINDINGS = ('pronunciation', 'omissions_repetitions', 'delivery', 'fatigue')
MAX_COMPARISON_EDITS = 64


def _hash(value):
    if not isinstance(value, str) or not HEX.fullmatch(value): raise SpokenBriefError('Expected a full SHA-256 identity')
    return value


def archive_binding(archive):
    return {key: archive[key] for key in ('manifest_sha256', 'manifest_file_sha256', 'assembly_receipt_sha256', 'producer_sha256')} | {
        'source_sha256': archive['source']['sha256'], 'master_sha256': archive['master']['sha256']}


def _targets(archive):
    return [{'id': s['id'], 'text': s['text'], 'audio_sha256': s['audio_sha256']} for s in archive['segments']] + [
        {'id': 'master', 'text': ' '.join(s['text'] for s in archive['segments']), 'audio_sha256': archive['master']['sha256']}]


def _observations(archive, evidence):
    if (not isinstance(evidence, dict) or set(evidence) != {'schema_version', 'manifest_sha256', 'master_sha256', 'observations'}
            or type(evidence['schema_version']) is not int or evidence['schema_version'] != 1
            or evidence['manifest_sha256'] != archive['manifest_sha256'] or evidence['master_sha256'] != archive['master']['sha256']
            or not isinstance(evidence['observations'], list) or len(evidence['observations']) > len(archive['segments']) + 1):
        raise SpokenBriefError('Transcription evidence schema or archive binding differs')
    targets = {s['id']: s for s in _targets(archive)}; found = {}
    for item in evidence['observations']:
        if (not isinstance(item, dict) or set(item) != {'target', 'audio_sha256', 'text', 'method', 'producer'}
                or not isinstance(item['target'], str) or item['target'] not in targets or item['target'] in found
                or item['audio_sha256'] != targets[item['target']]['audio_sha256']
                or item['method'] not in ('independent-asr', 'manual-transcript', 'forced-alignment')):
            raise SpokenBriefError('Transcription target, audio identity or method is invalid/duplicated')
        _text(item['text']); producer = item['producer']
        if (not isinstance(producer, dict) or set(producer) != {'id', 'revision', 'runtime_sha256', 'configuration_sha256'}
                or not isinstance(producer['id'], str) or not SPEAKER_RE.fullmatch(producer['id'])
                or not isinstance(producer['revision'], str) or not 1 <= len(producer['revision']) <= 200):
            raise SpokenBriefError('Transcript producer evidence is incomplete')
        _text(producer['revision'])
        if item['method'] == 'manual-transcript':
            if producer['runtime_sha256'] is not None or producer['configuration_sha256'] is not None:
                raise SpokenBriefError('Manual transcription must not claim a model/runtime hash')
        else:
            _hash(producer['runtime_sha256']); _hash(producer['configuration_sha256'])
        found[item['target']] = item
    _json_bytes(evidence)  # Bound aggregate bytes as well as each individual text.
    return found


def _bound_comparison(comparison, remaining_edits):
    """Bound stored edit details while keeping exact aggregates, rate and status.

    Comparisons that fit the remaining report budget are returned unchanged.
    Larger ones keep the first details in deterministic comparator order plus
    an explicit edits_omitted count. The marker appears only for omissions.
    """
    if comparison is None or len(comparison['edits']) <= remaining_edits:
        return comparison
    trimmed = dict(comparison)
    trimmed['edits'] = comparison['edits'][:remaining_edits]
    trimmed['edits_omitted'] = len(comparison['edits']) - remaining_edits
    return trimmed


def _assemble_report(archive, evidence, lexicon, *, bound_edits):
    book = validate_lexicon(lexicon); observations = _observations(archive, evidence)
    targets = []; remaining_edits = MAX_COMPARISON_EDITS
    for target in _targets(archive):
        observation = observations.get(target['id']); comparison = None
        if observation is None: status = 'not-transcribed'
        elif observation['method'] == 'forced-alignment': status = 'not-independent'
        else:
            full = compare_text(target['text'], observation['text'], book); status = full['status']
            comparison = _bound_comparison(full, remaining_edits) if bound_edits else full
            if bound_edits:
                remaining_edits -= len(comparison['edits'])
        targets.append({'id': target['id'], 'intended_text': target['text'],
            'text_sha256': digest_bytes(target['text'].encode('utf-8')), 'audio_sha256': target['audio_sha256'],
            'transcript_status': status, 'listening_status': 'unreviewed', 'comparison': comparison,
            'observed_text_sha256': digest_bytes(observation['text'].encode('utf-8')) if observation else None})
    value = {'schema_version': 1, 'kind': 'spoken-brief-qa', 'archive': archive_binding(archive),
        'normalization_version': NORMALIZATION_VERSION, 'lexicon': book, 'lexicon_sha256': canonical_digest(book),
        'evidence': evidence, 'evidence_sha256': canonical_digest(evidence), 'targets': targets,
        'review_targets': [x['id'] for x in targets if x['transcript_status'] != 'match']}
    value['report_sha256'] = canonical_digest(value)
    _json_bytes(value)
    return value


def build_report(archive, evidence, lexicon=None):
    """Pure projection over a verified archive; producer independence is attributed.

    Importing a producer's claimed hashes/method does not execute or independently
    authenticate that producer. Forced alignment is explicitly non-certifying.
    """
    return _assemble_report(archive, evidence, lexicon, bound_edits=True)


def _target(archive, identifier, audio_sha256):
    if not isinstance(identifier, str): raise SpokenBriefError('Invalid review target')
    for target in _targets(archive):
        if target['id'] == identifier and target['audio_sha256'] == audio_sha256: return target
    raise SpokenBriefError('Review target/audio does not match this verified archive')


def _review(archive, identifier, audio_sha256, decision, findings, reviewer, reason, report_sha256):
    target = _target(archive, identifier, audio_sha256)
    if (not isinstance(decision, str) or decision not in ('keep', 'replace', 'unreviewed')
            or not isinstance(findings, dict) or set(findings) != set(FINDINGS)
            or any(not isinstance(v, str) or v not in ('not-reviewed', 'acceptable', 'needs-work') for v in findings.values())
            or not isinstance(reviewer, str) or not SPEAKER_RE.fullmatch(reviewer)
            or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000):
        raise SpokenBriefError('Explicit owner decision, reviewer, reason and complete listening findings are required')
    _text(reason)
    if report_sha256 is not None: _hash(report_sha256)
    value = {'schema_version': 1, 'kind': 'spoken-brief-owner-review', 'archive': archive_binding(archive),
        'target': identifier, 'audio_sha256': audio_sha256, 'text_sha256': digest_bytes(target['text'].encode('utf-8')),
        'decision': decision, 'findings': findings, 'reviewer': reviewer, 'reason': reason, 'report_sha256': report_sha256}
    value['review_sha256'] = canonical_digest(value)
    return value


def _record_path(directory, group, identifier):
    _hash(identifier)
    return directory / 'qa' / group / (identifier + '.json')


def _same_record(path, raw):
    current, _ = _capture(path, MAX_JSON_BYTES)
    if current != raw: raise SpokenBriefError('Existing immutable QA record differs or is corrupt')


def _publish(directory, archive, group, record, key):
    raw = _json_bytes(record); identifier = record[key]; target = _record_path(directory, group, identifier)
    if os.path.lexists(target):
        _same_record(target, raw)
        return {'id': identifier, 'path': str(target), 'reused': True}
    temporary = None
    try:
        with _claim(directory, archive['manifest_sha256']) as verify:
            if inspect_run(directory) != archive: raise SpokenBriefError('Archive changed before QA publication')
            parent = target.parent
            parent.parent.mkdir(exist_ok=True); _lineage(parent.parent)
            parent.mkdir(exist_ok=True); lineage = _lineage(parent)
            if os.path.lexists(target):
                _same_record(target, raw)
                return {'id': identifier, 'path': str(target), 'reused': True}
            with os.scandir(parent) as entries:
                for count, _ in enumerate(entries, 1):
                    if count >= MAX_RECORDS: raise SpokenBriefError('QA record capacity reached; no history was pruned')
            descriptor, name = tempfile.mkstemp(prefix='.qa-', suffix='.tmp', dir=parent); temporary = Path(name)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            _same_record(temporary, raw)
            if _lineage(parent) != lineage or inspect_run(directory) != archive:
                raise SpokenBriefError('Archive or QA parent changed before publication')
            verify()
            # Atomic no-overwrite publication on local NTFS/POSIX filesystems.
            # Unsupported hard links fail visibly; never fall back to replacement.
            os.link(temporary, target)
            _sync_parent(target)
            return {'id': identifier, 'path': str(target), 'reused': False}
    except OSError as exc: raise SpokenBriefError(f'Cannot publish immutable QA record: {exc}') from exc
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def save_report(run_dir, evidence, lexicon=None):
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    return _publish(directory, archive, 'reports', build_report(archive, evidence, lexicon), 'report_sha256')


def load_report(run_dir, identifier):
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    value, _ = checked_json(_record_path(directory, 'reports', identifier))
    try: expected = build_report(archive, value['evidence'], value['lexicon'])
    except (KeyError, TypeError) as exc: raise SpokenBriefError('Malformed retained QA report') from exc
    if canonical_digest(value) == canonical_digest(expected) and value['report_sha256'] == identifier:
        return value
    # Retained pre-change reports carry full edit details with no omission
    # marker. Verify them against the legacy full-edit projection so valid
    # history keeps loading; anything else still fails closed below.
    try: legacy = _assemble_report(archive, value['evidence'], value['lexicon'], bound_edits=False)
    except (KeyError, TypeError, SpokenBriefError) as exc:
        raise SpokenBriefError('Retained QA report differs from a fresh evidence projection') from exc
    if canonical_digest(value) != canonical_digest(legacy) or value['report_sha256'] != identifier:
        raise SpokenBriefError('Retained QA report differs from a fresh evidence projection')
    return value


def record_review(run_dir, identifier, audio_sha256, *, decision, findings, reviewer, reason,
                  report_sha256=None, expected_archive_sha256=None):
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    require_archive(archive, expected_archive_sha256)
    value = _review(archive, identifier, audio_sha256, decision, findings, reviewer, reason, report_sha256)
    if report_sha256 is not None: load_report(directory, report_sha256)
    return _publish(directory, archive, 'reviews', value, 'review_sha256')


def load_review(run_dir, identifier):
    directory = checked_directory(run_dir); archive = inspect_run(directory)
    value, _ = checked_json(_record_path(directory, 'reviews', identifier))
    try:
        expected = _review(archive, *(value[k] for k in ('target', 'audio_sha256', 'decision', 'findings', 'reviewer', 'reason', 'report_sha256')))
        if value['report_sha256'] is not None: load_report(directory, value['report_sha256'])
    except (KeyError, TypeError) as exc: raise SpokenBriefError('Malformed retained owner review') from exc
    if canonical_digest(value) != canonical_digest(expected) or value['review_sha256'] != identifier:
        raise SpokenBriefError('Owner review binding or digest differs')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); commands = parser.add_subparsers(dest='command', required=True)
    for name in ('report', 'show-report', 'review', 'show-review'):
        command = commands.add_parser(name); command.add_argument('run_dir')
        if name == 'report':
            command.add_argument('transcripts'); command.add_argument('--lexicon')
        elif name.startswith('show-'): command.add_argument('id')
        else:
            command.add_argument('target'); command.add_argument('--audio-sha256', required=True)
            command.add_argument('--decision', choices=['keep', 'replace', 'unreviewed'], required=True)
            command.add_argument('--reviewer', required=True); command.add_argument('--reason', required=True)
            command.add_argument('--report-sha256')
            for finding in FINDINGS: command.add_argument('--' + finding.replace('_', '-'), choices=['not-reviewed', 'acceptable', 'needs-work'], default='not-reviewed')
    args = parser.parse_args(argv)
    try:
        if args.command == 'report':
            value = save_report(args.run_dir, checked_json(Path(args.transcripts))[0], checked_json(Path(args.lexicon))[0] if args.lexicon else None)
        elif args.command == 'show-report': value = load_report(args.run_dir, args.id)
        elif args.command == 'show-review': value = load_review(args.run_dir, args.id)
        else:
            value = record_review(args.run_dir, args.target, args.audio_sha256, decision=args.decision,
                findings={key: getattr(args, key) for key in FINDINGS}, reviewer=args.reviewer, reason=args.reason, report_sha256=args.report_sha256)
        print(json.dumps(value, ensure_ascii=False, indent=2)); return 0
    except (SpokenBriefError, OSError) as exc:
        print('spoken brief QA: ' + str(exc), file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
