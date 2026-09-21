"""Temporary exact-match patcher for PR #813; removed by its guarded workflow."""
from pathlib import Path
from textwrap import dedent


def replace(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected one patch anchor, found {count}')
    target.write_text(text.replace(old, new), encoding='utf-8')


Path('studio_workflow/setup_context_client.py').write_text(dedent('''\
    """Bounded read-only client for exact setup compatibility reports."""
    from __future__ import annotations

    import copy
    from http.client import HTTPException
    from urllib.error import HTTPError

    from . import setup_context_compatibility as evaluator
    from .client import ClientError, read_response
    from .core import canonical, decode, need

    PREFIX = '/api/workflow-studio/setup-compatibility'
    MAX_ERROR_BYTES = 65536
    ZERO_AUTHORITY_FIELDS = (
        'provider_accessed',
        'file_hashed',
        'model_downloaded',
        'installation_authorized',
        'backend_switched',
        'selection_changed',
        'generation_submitted',
    )


    def validate_reply(result, expected):
        message = 'Setup compatibility response does not match this exact retained context'
        need(
            isinstance(result, dict)
            and all(result.get(field) is False for field in ZERO_AUTHORITY_FIELDS)
            and canonical(result) == canonical(expected),
            message,
        )
        return result


    def observe(transport, value):
        """Evaluate one immutable snapshot and accept only its exact server report."""
        query = copy.deepcopy(value)
        expected = evaluator.evaluate(query)
        try:
            result = transport(PREFIX, copy.deepcopy(query))
        except HTTPError as exc:
            try:
                with exc:
                    detail = decode(read_response(exc, MAX_ERROR_BYTES))
            except (ValueError, OSError, HTTPException):
                detail = {}
            message = detail.get('error') if isinstance(detail, dict) else None
            error = {
                'error': message if isinstance(message, str)
                else 'Setup compatibility is unavailable; check again explicitly.',
                'code': 'setup_compatibility_unavailable',
                **{field: False for field in ZERO_AUTHORITY_FIELDS},
            }
            raise ClientError(exc.code, error) from exc
        return validate_reply(result, expected)
'''), encoding='utf-8')


replace(
    'studio_workflow/http_extension.py',
    "            'recipe_setup_proposal': True, 'recipe_setup_apply': True, 'shared_setup_drafts': True, 'setup_request_recovery': True, 'recipe_shortlist': True, 'recipe_shortlist_source': True, 'recipe_shortlist_ordered_sources': True, 'resource_scoped_guidance': True, 'saved_run_exact_review': True, 'saved_run_hash_dispatch': True,\n",
    "            'recipe_setup_proposal': True, 'setup_context_compatibility': True, 'recipe_setup_apply': True, 'shared_setup_drafts': True, 'setup_request_recovery': True, 'recipe_shortlist': True, 'recipe_shortlist_source': True, 'recipe_shortlist_ordered_sources': True, 'resource_scoped_guidance': True, 'saved_run_exact_review': True, 'saved_run_hash_dispatch': True,\n",
)
replace(
    'studio_workflow/http_extension.py',
    "    if path == PREFIX + '/setup-proposal':\n        from .setup_proposal import request\n        return request(value, studio)\n",
    "    if path == PREFIX + '/setup-compatibility':\n        from .setup_context_compatibility import evaluate\n        return evaluate(value)\n    if path == PREFIX + '/setup-proposal':\n        from .setup_proposal import request\n        return request(value, studio)\n",
)

replace(
    'studio_workflow/sdk.py',
    "    def setup_proposal(self, request: dict) -> dict:\n        \"\"\"Preview a caller-declared draft change; never stages, saves or applies it.\"\"\"\n        from .setup_proposal import observe\n        return observe(self.request, request)\n\n    def shortlist(self, goal: str, *, reference_count: int | None = None, limit: int = 6,\n",
    "    def setup_proposal(self, request: dict) -> dict:\n        \"\"\"Preview a caller-declared draft change; never stages, saves or applies it.\"\"\"\n        from .setup_proposal import observe\n        return observe(self.request, request)\n\n    def setup_compatibility(self, request: dict) -> dict:\n        \"\"\"Evaluate retained setup context without reading or mutating Studio.\"\"\"\n        from .setup_context_client import observe\n        return observe(self.request, request)\n\n    def shortlist(self, goal: str, *, reference_count: int | None = None, limit: int = 6,\n",
)

replace(
    'studio_workflow/agent_bridge.py',
    "    'recipe_setup_proposal': tool('Preview a source-bound setup diff against a caller-declared browser draft. Read-only; no staging, application, saving or execution. Draft hashes are not server revisions.',\n        {'request_json': {'type':'string','maxLength':131072}}, ('request_json',)),\n",
    "    'recipe_setup_proposal': tool('Preview a source-bound setup diff against a caller-declared browser draft. Read-only; no staging, application, saving or execution. Draft hashes are not server revisions.',\n        {'request_json': {'type':'string','maxLength':131072}}, ('request_json',)),\n    'setup_compatibility': tool('Evaluate exact retained source candidates against caller-supplied local/runtime observations. Read-only; no provider access, hashing, install, backend switch, selection change or generation.',\n        {'request_json': {'type':'string','maxLength':MAX_BYTES}}, ('request_json',)),\n",
)
replace(
    'studio_workflow/agent_bridge.py',
    "            elif name == 'recipe_setup_proposal':\n                from .setup_proposal import observe\n                data = observe(request, payload('request_json'))\n            elif name == 'recipe_shortlist':\n",
    "            elif name == 'recipe_setup_proposal':\n                from .setup_proposal import observe\n                data = observe(request, payload('request_json'))\n            elif name == 'setup_compatibility':\n                from .setup_context_client import observe\n                data = observe(request, payload('request_json'))\n            elif name == 'recipe_shortlist':\n",
)

replace(
    'docs/bundle-studio/SETUP-COMPATIBILITY.md',
    '\n## Verification\n',
    '''\n## Read-only transport seam\n\nThe live-context adapter is exposed through the existing loopback boundary as\n`POST /api/workflow-studio/setup-compatibility`. The route evaluates only the\ncaller-supplied versioned request; it does not read the Studio object, inspect a\nprovider or file, refresh a schema, install a resource, switch a backend, change a\nselection or submit generation. Capability discovery reports\n`setup_context_compatibility: true`.\n\n`WorkflowClient.setup_compatibility(request)` and the read-mode agent tool\n`setup_compatibility` use that same route. Before transport, the client snapshots\nthe request and computes the deterministic expected report with the pure evaluator.\nIt accepts only a byte-equivalent canonical report with every zero-authority flag\nstill false. A stale, tampered or version-skewed response is therefore refused\ninstead of becoming selection authority. The agent accepts at most 1 MiB of strict\nJSON text and returns the normal exact-JSON envelope; it exposes no ticket, command\nor apply operation.\n\nThis seam remains advice only. A later selector/application slice must bind the\nreport fingerprint and preconditions to the current draft, inventory, backend and\nschema, then recheck them atomically before any mutation.\n\n## Verification\n''',
)
