"""Revisioned comparison reviews in Production's existing SQLite database.

This module observes retained jobs/assets; it never prepares or submits generation.
Blindness reduces accidental settings bias, not access by the local machine owner.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import threading
import time
import uuid
import zipfile
import character_review

from review_media import (FULL_CROP, MAX_CANDIDATES, MAX_TOTAL_BYTES, canonical,
                          checked_bytes, crop_box, digest, make_preview, render_sheet, write_new)

OBSERVATIONS = ('constraints', 'identity', 'pose_contact', 'composition', 'detail')
VERDICTS = ('unreviewed', 'keep', 'needs_work', 'reject')
MAX_REVISIONS = 256
MAX_EXPORTS = 8
MAX_STORAGE_BYTES = 1024**3
TERMINAL = ('awaiting_review', 'reviewed', 'failed')


def text(value, name, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f'{name} must be text up to {maximum} characters')
    return value


def fields(payload, allowed):
    unknown = set(payload) - set(allowed)
    if unknown:raise ValueError('Unsupported review fields: ' + ', '.join(sorted(unknown)))


def rating(payload):
    if not isinstance(payload, dict):raise ValueError('Candidate assessment must be an object')
    fields(payload, ('verdict', 'observations', 'notes', 'cleanup_seconds', 'preference'))
    verdict = payload.get('verdict', 'unreviewed')
    if not isinstance(verdict, str) or verdict not in VERDICTS:raise ValueError('Unknown candidate verdict')
    observations = payload.get('observations', {})
    if not isinstance(observations, dict):raise ValueError('Observations must be an object')
    fields(observations, OBSERVATIONS)
    if any(not isinstance(v, str) or v not in ('pass', 'fail', 'not_assessed') for v in observations.values()):
        raise ValueError('Observations must be pass, fail or not_assessed')
    seconds = payload.get('cleanup_seconds')
    if seconds is not None and (type(seconds) is not int or not 0 <= seconds <= 86400):
        raise ValueError('Measured cleanup must be null or integer seconds from 0 to 86400')
    preference = payload.get('preference')
    if preference is not None and (type(preference) is not int or not 1 <= preference <= 5):
        raise ValueError('Preference must be null or an integer from 1 to 5')
    return {'verdict': verdict, 'observations': {key: observations.get(key, 'not_assessed') for key in OBSERVATIONS},
            'notes': text(payload.get('notes', ''), 'Candidate notes', 4000),
            'cleanup_seconds': seconds, 'preference': preference}


class ReviewDesk:
    def __init__(self, production):
        self.production = production
        # CPU derivatives have one bounded, nonqueued operation per Studio instance.
        self.media_lock = threading.Lock()
        with production.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS comparison_reviews (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id), revision INTEGER NOT NULL, document TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS comparison_review_events (
                    project_id TEXT REFERENCES projects(id), revision INTEGER NOT NULL, event TEXT NOT NULL,
                    PRIMARY KEY(project_id, revision));
                CREATE TABLE IF NOT EXISTS comparison_review_files (
                    project_id TEXT REFERENCES projects(id), path TEXT NOT NULL, record TEXT NOT NULL,
                    PRIMARY KEY(project_id, path));
                CREATE TABLE IF NOT EXISTS comparison_review_exports (
                    project_id TEXT REFERENCES projects(id), revision INTEGER NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(project_id, revision));
            ''')

    def exists(self, identifier):
        self.production._get(identifier)
        with self.production.connect() as db:
            return db.execute('SELECT 1 FROM comparison_reviews WHERE project_id=?', (identifier,)).fetchone() is not None

    @staticmethod
    def _read(db, identifier):
        row = db.execute('SELECT * FROM comparison_reviews WHERE project_id=?', (identifier,)).fetchone()
        return json.loads(row['document']) if row else None

    def _capture(self, identifier, db=None):
        project = self.production._get(identifier, db)
        plan = project['plan']
        if plan.get('kind') != 'comparison':raise ValueError('Review desk currently supports image comparison projects')
        if project['state']['status'] not in TERMINAL:
            raise ValueError('Finish or reconcile the comparison before reviewing; no work was submitted')
        if digest({k: v for k, v in plan.items() if k != 'sha256'}) != plan['sha256']:
            raise ValueError('Experiment plan changed; preserve this evidence and branch explicitly')
        candidates = []; stages = []; seen = set()
        for index, stage in enumerate(plan['stages']):
            attempt = project['state'].get('attempts', {}).get(str(index), {})
            job = self.production.studio.jobs.get(attempt.get('job_id'))
            if job and job.get('status') in ('queued', 'waiting', 'submitting', 'running', 'uncertain'):
                raise ValueError('A comparison job is still unresolved; review cannot certify its output')
            public = self.production.studio.public(job) if job else {}
            record = {'stage': index, 'label': stage['label'], 'attempt': copy.deepcopy(attempt),
                      'job_id': job.get('id') if job else None, 'status': public.get('status', 'not_started'),
                      'prompt_ids': copy.deepcopy(public.get('prompt_ids', [])),
                      'elapsed_seconds': public.get('elapsed_seconds'),
                      'peak_memory_bytes': None, 'cache_condition': None,
                      'message': public.get('message'), 'graph_sha256': stage['graph_sha256'],
                      'recipe': self.production.studio.export_recipe(job) if job else None}
            stages.append(record)
            for output_index, output in enumerate((job or {}).get('outputs', [])):
                if output.get('media_type') != 'image' or not output.get('asset_id'):continue
                identifier_asset = output['asset_id']
                if identifier_asset in seen:raise ValueError('A comparison output is duplicated; inspect its lineage')
                seen.add(identifier_asset)
                asset = self.production.studio.assets.get(identifier_asset)
                if asset.get('trashed_at') is not None:raise ValueError('Restore comparison outputs before reviewing them')
                if asset['job_id'] != job['id'] or asset['output_index'] != output_index:
                    raise ValueError('Comparison output does not match its registered job lineage')
                candidates.append({'asset_id': identifier_asset, 'sha256': asset['sha256'], 'bytes': asset['bytes'],
                                   'filename': asset['filename'], 'stage': index, 'output_index': output_index,
                                   'lineage': copy.deepcopy(asset.get('lineage', []))})
        if not 1 <= len(candidates) <= MAX_CANDIDATES:
            raise ValueError('Review requires one to sixteen retained images; no outputs are silently truncated')
        if any(type(c['bytes']) is not int or c['bytes'] <= 0 for c in candidates) or sum(c['bytes'] for c in candidates) > MAX_TOTAL_BYTES:
            raise ValueError('Review sources exceed the 256 MiB total budget')
        evidence = {'plan': copy.deepcopy(plan), 'stages': stages, 'candidates': candidates}
        if len(canonical(evidence)) > 1024**2:raise ValueError('Review recipe metadata exceeds the 1 MiB budget')
        return project, evidence, digest(evidence)

    def _current(self, identifier, document, db=None):
        project, _, key = self._capture(identifier, db)
        if key != document['evidence_sha256']:
            raise ValueError('Review inputs or execution evidence changed; preserve this review and create a branch')
        return project

    def _path(self, identifier, relative):
        if not isinstance(relative, str) or not re.fullmatch(r'reviews/[0-9a-f]{32}/[A-Za-z0-9_./-]+', relative):
            raise ValueError('Invalid review artifact path')
        if any(part in ('', '.', '..') for part in relative.split('/')):
            raise ValueError('Invalid review artifact path')
        raw_base = self.production.root / identifier
        base = raw_base.resolve()
        if not base.is_relative_to(self.production.root) or raw_base.is_symlink() or (hasattr(raw_base, 'is_junction') and raw_base.is_junction()):
            raise ValueError('Linked or escaped project directories are unsupported')
        path = base / relative
        if not path.resolve().is_relative_to(base):raise ValueError('Review artifact escaped its project')
        for part in (path, *path.parents):
            if part == self.production.root:break
            if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                raise ValueError('Linked review artifact paths are unsupported')
        return path

    @staticmethod
    def _revision(document, payload):
        expected = payload.get('expected_revision')
        if type(expected) is not int or expected != document['revision']:
            raise ValueError('Review conflict: reload the current revision before applying this change')

    @staticmethod
    def _reviewer(payload):
        reviewer = payload.get('reviewer', 'local-user')
        if not isinstance(reviewer, str) or reviewer not in ('local-user', 'local-agent'):
            raise ValueError('Reviewer must be local-user or local-agent; this is a declaration, not authentication')
        return reviewer

    def _public(self, identifier, document):
        result = {key: copy.deepcopy(document[key]) for key in
                  ('revision', 'revealed', 'finalized', 'selected', 'notes', 'crop', 'background', 'created_at', 'finalized_by', 'finalized_at')}
        result.update(exists=True, project_id=identifier,
                      scope='Image review only; execution, model terms and engine acceptance are independent',
                      preview_note='Metadata-stripped previews, maximum 1536 px; exported crops use source resolution')
        scope = character_review.context(document['evidence']['plan'])
        result.update(character_context=scope, character_review=copy.deepcopy(document.get('character_review')))
        result['candidates'] = []
        for candidate in document['candidates']:
            item = {'alias': candidate['alias'], 'preview_url': self._url(identifier, candidate['preview_path']),
                    'assessment': copy.deepcopy(candidate['assessment'])}
            if scope:item['character_checks'] = copy.deepcopy(candidate.get('character_checks', character_review.unobserved(scope)))
            if document['revealed']:
                item['source'] = {k: copy.deepcopy(candidate[k]) for k in
                                  ('asset_id', 'sha256', 'bytes', 'filename', 'stage', 'output_index', 'lineage', 'transform')}
                item['original_url'] = '/api/assets/' + candidate['asset_id'] + '/file'
            result['candidates'].append(item)
        if document['revealed']:
            result.update(evidence=copy.deepcopy(document['evidence']), evidence_sha256=document['evidence_sha256'])
        with self.production.connect() as db:
            exported = db.execute('SELECT result FROM comparison_review_exports WHERE project_id=? AND revision=?',
                                  (identifier, document['revision'])).fetchone()
        result['history'] = self.history(identifier)
        result['export'] = json.loads(exported['result']) if exported else None
        return result

    def history(self, identifier):
        with self.production.connect() as db:
            events = [json.loads(r['event']) for r in db.execute('SELECT event FROM comparison_review_events WHERE project_id=? ORDER BY revision DESC', (identifier,))]
        return [{**{k: e[k] for k in ('revision', 'action', 'reviewer', 'at')},
                 'alias': e['details'].get('alias'), 'assessment': e['details'].get('assessment'),
                 'character_checks': e['details'].get('character_checks')} for e in events]

    def _storage_budget(self, identifier, extra):
        directory = self.production.root / identifier / 'reviews'
        used = sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()) if directory.exists() else 0
        if used + extra > MAX_STORAGE_BYTES:raise ValueError('Review storage budget would exceed 1 GiB; preserve or archive earlier evidence first')
        if shutil.disk_usage(self.production.root).free < extra + 1024**3:raise ValueError('Review media needs its output space plus 1 GiB free headroom')

    @staticmethod
    def _url(identifier, relative):return f'/api/production/{identifier}/files/{relative}'

    def inspect(self, identifier):
        self.production._get(identifier)
        with self.production.connect() as db:document = self._read(db, identifier)
        return self._public(identifier, document) if document else {'exists': False, 'project_id': identifier}

    def _register(self, db, identifier, relative, receipt, role):
        record = {key: receipt[key] for key in ('sha256', 'bytes')}
        record.update(path=relative, url=self._url(identifier, relative), role=role)
        db.execute('INSERT INTO comparison_review_files VALUES (?,?,?)', (identifier, relative, json.dumps(record)))
        return record

    def _save(self, db, identifier, document, action, reviewer, details):
        raw = canonical(document).decode()
        db.execute('INSERT INTO comparison_reviews VALUES (?,?,?) ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision,document=excluded.document',
                   (identifier, document['revision'], raw))
        event = {'revision': document['revision'], 'action': action, 'reviewer': reviewer, 'at': time.time(),
                 'details': copy.deepcopy(details), 'document_sha256': digest(document)}
        db.execute('INSERT INTO comparison_review_events VALUES (?,?,?)', (identifier, document['revision'], canonical(event).decode()))

    def open(self, identifier, payload):
        with self.production.connect() as db:existing = self._read(db, identifier)
        if existing:return self._public(identifier, existing)
        if not self.media_lock.acquire(blocking=False):raise ValueError('Another bounded review media operation is running')
        try:
            with self.production.lock:_, evidence, key = self._capture(identifier)
            self._storage_budget(identifier, sum(c['bytes'] for c in evidence['candidates']) + len(evidence['candidates']) * 16 * 1024**2)
            session = uuid.uuid4().hex; directory = self._path(identifier, f'reviews/{session}/sources')
            directory.mkdir(parents=True, exist_ok=False)
            candidates = copy.deepcopy(evidence['candidates']);random.SystemRandom().shuffle(candidates)
            files = []
            for index, candidate in enumerate(candidates):
                alias = chr(65 + index);candidate['alias'] = alias
                source = self.production.studio.assets.file(candidate['asset_id'])
                data = checked_bytes(source, candidate['sha256'], candidate['bytes'])
                suffix = source.suffix.lower()
                if suffix not in ('.png', '.jpg', '.jpeg', '.webp'):raise ValueError('Review source extension is unsupported')
                relative = f'reviews/{session}/sources/{alias}{suffix}'
                write_new(self._path(identifier, relative), data)
                preview = f'reviews/{session}/{alias}.png'
                transform, receipt = make_preview(data, self._path(identifier, preview))
                candidate.update(source_path=relative, preview_path=preview, transform=transform, assessment=rating({}))
                files.append((preview, receipt))
            document = {'version': 1, 'session_id': session, 'revision': 0, 'created_at': time.time(),
                        'evidence_sha256': key, 'evidence': evidence, 'candidates': candidates,
                        'revealed': False, 'finalized': False, 'selected': None, 'notes': '', 'finalized_by': None, 'finalized_at': None,
                        'crop': FULL_CROP.copy(), 'background': 'dark'}
            with self.production.lock, self.production.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                # Other processes may have completed the same explicit open during decoding.
                existing = self._read(db, identifier)
                if existing:document = existing
                else:
                    project = self._current(identifier, document, db)
                    document['prior_review'] = copy.deepcopy(project['state'].get('review'))
                    for relative, receipt in files:self._register(db, identifier, relative, receipt, 'blind-review-preview')
                    self._save(db, identifier, document, 'open', self._reviewer(payload), {'evidence_sha256': key})
                    state = project['state'];state.setdefault('review', {})['desk_url'] = '/review.html?project=' + identifier
                    db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps(state), identifier))
            return self._public(identifier, document)
        finally:self.media_lock.release()

    def _verify_sources(self, identifier, document):
        for candidate in document['candidates']:
            checked_bytes(self._path(identifier, candidate['source_path']), candidate['sha256'], candidate['bytes'])
            checked_bytes(self.production.studio.assets.file(candidate['asset_id']), candidate['sha256'], candidate['bytes'])

    def change(self, identifier, payload):
        action = payload['action']; reviewer = self._reviewer(payload)
        with self.production.connect() as db:document = self._read(db, identifier)
        if document is None:raise ValueError('Open a review explicitly before changing it')
        self._revision(document, payload)
        if action == 'finalize':self._verify_sources(identifier, document)
        with self.production.lock, self.production.connect() as db:
            db.execute('BEGIN IMMEDIATE');document = self._read(db, identifier)
            self._revision(document, payload);project = self._current(identifier, document, db)
            scope = character_review.context(document['evidence']['plan'])
            if 'character_checks' in payload and scope is None:raise ValueError('Character checks require an imported character case')
            if document['revision'] >= MAX_REVISIONS:raise ValueError('Review revision budget reached; preserve evidence and branch the study')
            if action == 'rate':
                candidate = next((c for c in document['candidates'] if c['alias'] == payload.get('alias')), None)
                if candidate is None:raise ValueError('Choose a candidate alias from this review')
                candidate['assessment'] = rating(payload.get('assessment'))
                if scope:candidate['character_checks'] = character_review.observations(payload.get('character_checks', character_review.unobserved(scope)), scope)
                document.update(finalized=False, selected=None, finalized_by=None, finalized_at=None)
                document['character_review'] = None
            elif action == 'restore':
                source_revision = payload.get('source_revision')
                if type(source_revision) is not int:raise ValueError('Choose a recorded assessment revision')
                row = db.execute('SELECT event FROM comparison_review_events WHERE project_id=? AND revision=?', (identifier, source_revision)).fetchone()
                event = json.loads(row['event']) if row else None
                if not event or event['action'] != 'rate':raise ValueError('Only recorded candidate assessments can be restored')
                candidate = next(c for c in document['candidates'] if c['alias'] == event['details']['alias'])
                candidate['assessment'] = rating(event['details']['assessment'])
                if scope:candidate['character_checks'] = character_review.observations(event['details'].get('character_checks', character_review.unobserved(scope)), scope)
                document.update(finalized=False, selected=None, finalized_by=None, finalized_at=None)
                document['character_review'] = None
            elif action == 'view':
                crop = payload.get('crop');crop_box(crop, (1, 1))
                background = payload.get('background')
                if background not in ('dark', 'light'):raise ValueError('Choose a dark or light background')
                document.update(crop=crop, background=background)
            elif action == 'reveal':
                if document['revealed']:raise ValueError('Settings are already revealed; this cannot become a new blind review')
                document['revealed'] = True
            elif action == 'finalize':
                if not document['revealed']:raise ValueError('Reveal the provenance before finalizing a selection')
                if any(c['assessment']['verdict'] == 'unreviewed' for c in document['candidates']):
                    raise ValueError('Record a verdict for every candidate, including rejected results')
                selected = payload.get('selected')
                candidate = None
                if selected is not None:
                    candidate = next((c for c in document['candidates'] if c['alias'] == selected), None)
                    if not candidate or candidate['assessment']['verdict'] != 'keep':raise ValueError('Only a kept candidate can be selected')
                    if candidate['assessment']['observations']['constraints'] != 'pass':
                        raise ValueError('Confirm the selected candidate meets the stated constraints before finalizing')
                    if document['evidence']['stages'][candidate['stage']]['status'] != 'completed':
                        raise ValueError('An incomplete execution may be reviewed but cannot become the selected result')
                notes = text(payload.get('notes', ''), 'Summary notes', 8000)
                if payload.get('character_decision') == 'accepted' and payload.get('reviewer') != 'local-user':
                    raise ValueError('Character acceptance needs an explicit local-user human declaration')
                document['character_review'] = character_review.receipt(document, candidate, payload['character_decision'], reviewer, notes) if 'character_decision' in payload else None
                document.update(finalized=True, selected=selected, notes=notes, finalized_by=reviewer, finalized_at=time.time())
            else:raise ValueError('Unknown review action')
            document['revision'] += 1
            reviewer = self._reviewer(payload)
            details = {k: v for k, v in payload.items() if k not in ('action', 'expected_revision', 'reviewer')}
            if action == 'finalize' and document.get('character_review'):details['character_review'] = copy.deepcopy(document['character_review'])
            self._save(db, identifier, document, action, reviewer, details)
            # Reuse the current state row, not a stale whole-project copy from the caller.
            state = project['state'];selected = next((c for c in document['candidates'] if c['alias'] == document['selected']), None)
            state['review'] = {'status': ('selected' if selected else 'needs_work') if document['finalized'] else 'in_progress',
                               'asset_id': selected['asset_id'] if selected else None, 'notes': document['notes'],
                               'reviewer': document['finalized_by'] or reviewer, 'revision': document['revision'], 'at': time.time(),
                               'desk_url': '/review.html?project=' + identifier}
            if document.get('character_review'):state['review']['character_review'] = copy.deepcopy(document['character_review'])
            if state['status'] in ('awaiting_review', 'reviewed'):
                state['status'] = 'reviewed' if document['finalized'] else 'awaiting_review'
            db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps(state), identifier))
        return self._public(identifier, document)

    def export(self, identifier, payload):
        with self.production.connect() as db:
            document = self._read(db, identifier)
            if document is None:raise ValueError('Open a review first')
            self._revision(document, payload)
            previous = db.execute('SELECT result FROM comparison_review_exports WHERE project_id=? AND revision=?',
                                  (identifier, document['revision'])).fetchone()
        if previous:return json.loads(previous['result'])
        with self.production.connect() as db:
            if db.execute('SELECT COUNT(*) FROM comparison_review_exports WHERE project_id=?', (identifier,)).fetchone()[0] >= MAX_EXPORTS:
                raise ValueError('Review export budget reached; reuse a published receipt or archive this study')
        if not document['revealed'] or not document['finalized']:raise ValueError('Finalize a revealed review before exporting its evidence')
        self._current(identifier, document)
        if not self.media_lock.acquire(blocking=False):raise ValueError('Another bounded review media operation is running')
        try:
            self._verify_sources(identifier, document)
            self._storage_budget(identifier, sum(c['bytes'] for c in document['candidates']) + 48 * 1024**2)
            prefix = f"reviews/{document['session_id']}/export-{uuid.uuid4().hex}"
            directory = self._path(identifier, prefix);directory.mkdir(exist_ok=False)
            def read(candidate):return checked_bytes(self._path(identifier, candidate['source_path']), candidate['sha256'], candidate['bytes'])
            sheet = render_sheet(document['candidates'], read, document['crop'], directory/'contact-sheet.png', document['background'])
            with self.production.connect() as db:
                history = [json.loads(r['event']) for r in db.execute('SELECT event FROM comparison_review_events WHERE project_id=? ORDER BY revision', (identifier,))]
            report = {'version': 1, 'kind': 'comparison-review-evidence', 'project_id': identifier,
                      'review': document, 'history': history, 'sheet': sheet,
                      'execution': 'See individual recorded stage statuses; no new generation performed',
                      'rights_status': 'not_assessed_by_review_desk', 'engine_acceptance': 'not_assessed_by_review_desk',
                      'reviewer_authentication': 'local declaration only',
                      'scope': 'Review evidence, not a commercially cleared asset pack; normalized crops are not semantic registration'}
            report_receipt = write_new(directory/'review.json', canonical(report))
            plan_receipt = write_new(directory/'plan.json', canonical(document['evidence']['plan']))
            receipts = {'review.json': report_receipt, 'plan.json': plan_receipt,
                        'contact-sheet.png': {k: sheet[k] for k in ('sha256', 'bytes')}}
            pack = directory/'review-evidence.zip'
            with zipfile.ZipFile(pack, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                for name in receipts:archive.write(directory/name, name)
                for candidate in document['candidates']:
                    name = 'sources/' + Path(candidate['source_path']).name
                    data = read(candidate);archive.writestr(name, data)
                    receipts[name] = {'sha256': candidate['sha256'], 'bytes': len(data)}
                archive.writestr('checksums.json', canonical({'algorithm': 'sha256', 'files': receipts}))
            pack_receipt = {'sha256': self.production._file_hash(pack), 'bytes': pack.stat().st_size}
            result = {'revision': document['revision'], 'artifacts': [], 'scope': 'review-evidence-only'}
            with self.production.lock, self.production.connect() as db:
                db.execute('BEGIN IMMEDIATE');current = self._read(db, identifier)
                self._revision(current, payload);self._current(identifier, current, db)
                previous = db.execute('SELECT result FROM comparison_review_exports WHERE project_id=? AND revision=?',
                                      (identifier, document['revision'])).fetchone()
                if previous:return json.loads(previous['result'])
                for name, receipt in (('review.json', report_receipt), ('contact-sheet.png', sheet), ('review-evidence.zip', pack_receipt)):
                    result['artifacts'].append(self._register(db, identifier, prefix+'/'+name, receipt, 'review-evidence'))
                db.execute('INSERT INTO comparison_review_exports VALUES (?,?,?)', (identifier, document['revision'], json.dumps(result)))
            return result
        finally:self.media_lock.release()

    def file(self, identifier, relative):
        self.production._get(identifier)
        with self.production.connect() as db:
            row = db.execute('SELECT record FROM comparison_review_files WHERE project_id=? AND path=?', (identifier, relative)).fetchone()
        if row is None:raise ValueError('This review artifact has not been published')
        record = json.loads(row['record']);path = self._path(identifier, relative)
        if not path.is_file() or path.stat().st_size != record['bytes'] or self.production._file_hash(path) != record['sha256']:
            raise ValueError('Published review artifact changed or is unavailable; no substitute was served')
        return path

    def command(self, identifier, payload):
        action = payload.get('action')
        options = {'inspect': (), 'open': ('reviewer',), 'rate': ('alias', 'assessment', 'character_checks'),
                   'view': ('crop', 'background'), 'reveal': (), 'finalize': ('selected', 'notes', 'character_decision'), 'export': (), 'restore': ('source_revision',)}
        if not isinstance(action, str) or action not in options:raise ValueError('Unknown review action')
        allowed = {'action', *options[action]}
        if action not in ('inspect', 'open'):allowed.update(('expected_revision', 'reviewer'))
        fields(payload, allowed)
        self.production._get(identifier)
        if action == 'inspect':return self.inspect(identifier)
        if action == 'open':return self.open(identifier, payload)
        if action == 'export':return self.export(identifier, payload)
        return self.change(identifier, payload)
