"""One-shot guarded patch for the atomic setup substitution command."""
from pathlib import Path


def replace(path, old, new, label):
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    print(f'{label}: {count} exact match(es)')
    if count != 1:
        raise SystemExit(f'{label}: expected one exact match, found {count}')
    target.write_text(text.replace(old, new), encoding='utf-8')


replace(
    'studio_workflow/setup_drafts.py',
    '"""Revisioned Create drafts and copy-only proposal application in AssetWorkspace.\n',
    '"""Revisioned Create drafts, proposal application and atomic setup substitution.\n',
    'module contract',
)
replace(
    'studio_workflow/setup_drafts.py',
    "from .setup_proposal import validate_draft, validate_reply, request as build_proposal\n",
    "from .setup_proposal import validate_draft, validate_reply, request as build_proposal\nfrom .setup_substitution import validate_reply as validate_substitution_reply\n",
    'substitution import',
)
replace(
    'studio_workflow/setup_drafts.py',
    """    extra={'create':{'draft'},'replace':{'draft_id','expected_revision','draft'},
           'apply':{'draft_id','expected_revision','proposal_json','approved_proposal_sha256'},
           'restore':{'draft_id','expected_revision','revision'},'abandon':{'draft_id','expected_revision','operation_id'}}
""",
    """    extra={'create':{'draft'},'replace':{'draft_id','expected_revision','draft'},
           'apply':{'draft_id','expected_revision','proposal_json','approved_proposal_sha256'},
           'substitute':{'draft_id','expected_revision','proposal_json','approved_proposal_sha256'},
           'restore':{'draft_id','expected_revision','revision'},'abandon':{'draft_id','expected_revision','operation_id'}}
""",
    'command fields',
)
replace(
    'studio_workflow/setup_drafts.py',
    "    if action=='apply':\n        need(type(value['proposal_json']) is str and len(value['proposal_json'].encode())<=MAX_COMMAND,'Supply bounded reviewed proposal JSON')\n        need(type(value['approved_proposal_sha256']) is str and re.fullmatch('[a-f0-9]{64}',value['approved_proposal_sha256']),'Invalid acknowledged proposal hash')\n",
    "    if action in ('apply','substitute'):\n        need(type(value['proposal_json']) is str and len(value['proposal_json'].encode())<=MAX_COMMAND,'Supply bounded reviewed proposal JSON')\n        need(type(value['approved_proposal_sha256']) is str and re.fullmatch('[a-f0-9]{64}',value['approved_proposal_sha256']),'Invalid acknowledged proposal hash')\n",
    'reviewed command validation',
)
replace(
    'studio_workflow/setup_drafts.py',
    "                elif action in ('replace','restore','apply'):self._revision(current['revision']+1)\n",
    "                elif action in ('replace','restore','apply','substitute'):self._revision(current['revision']+1)\n",
    'revision capacity',
)
replace(
    'studio_workflow/setup_drafts.py',
    "                if action!='apply':return self._result(db,receipt)\n            return self._apply(value,sha,receipt,current)\n",
    "                if action not in ('apply','substitute'):return self._result(db,receipt)\n            if action=='apply':return self._apply(value,sha,receipt,current)\n            return self._substitute(value,sha,receipt,current)\n",
    'command dispatch',
)
replace(
    'studio_workflow/setup_drafts.py',
    "    def _apply(self,value,sha,receipt,current):\n",
    """    def _substitute(self,value,sha,receipt,current):
        try:
            exact=value['proposal_json']
            need(type(exact) is str and len(exact.encode())<=MAX_COMMAND,
                 'Supply the exact bounded reviewed substitution JSON')
            need(hashlib.sha256(exact.encode()).hexdigest()==value['approved_proposal_sha256'],
                 'Approval must name the exact reviewed substitution')
            core=decode(exact)
            report={**core,'proposal_json':exact,
                    'proposal_sha256':value['approved_proposal_sha256']}
            fresh=validate_substitution_reply(report,core['request'])
            need(fresh['can_apply'],
                 'Substitution is inspectable but blocked: '+
                 ', '.join(row['code'] for row in fresh['blockers']))
            need(canonical(core['before'])==canonical(current['draft']),
                 'Reviewed before-state differs from the shared setup revision')
            self._check_record(current)
            need(fresh['proposal_sha256']==value['approved_proposal_sha256'],
                 'The substitution context changed; inspect a fresh complete diff')
            need(canonical(fresh['after'])==canonical(core['after']),
                 'Derived substitution differs from the reviewed complete diff')
            record={'draft':fresh['after'],'inputs':copy.deepcopy(current['inputs']),
                    'runtime':copy.deepcopy(current['runtime']),
                    'graph_sha256':current['graph_sha256']}
            with self.workspace.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                self.workspace._check_scope(db,value['workspace_id'])
                self._guard(db,current['draft_id'],current['revision'],receipt['request_id'])
                old=self._operation(db,receipt['request_id'])
                need(old and old[1]['status'] in ACTIVE,
                     'Setup substitution no longer owns the draft')
                revision=current['revision']+1
                self._append(db,current['draft_id'],revision,record)
                receipt.update(status='committed',revision=revision,
                               previous_revision=current['revision'],
                               approved_proposal_sha256=value['approved_proposal_sha256'],
                               changes=len(fresh['changes']))
                self._save_receipt(db,receipt,sha)
                return self._result(db,receipt)
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error,RecursionError) as exc:
            receipt.update(status='failed',message=str(exc)[:500])
            self._progress(receipt,sha)
            with self.workspace.connection() as db:return self._result(db,receipt)

    def _apply(self,value,sha,receipt,current):
""",
    'atomic substitution method',
)

print('Atomic setup substitution command patch applied.')
