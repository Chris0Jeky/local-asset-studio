"""Same-origin routes composed onto the existing Studio HTTP handler."""
from urllib.parse import urlparse, unquote
from urllib.error import URLError
from .core import catalog, new_document, compile_document, document, decode, need
from .guides import guides
from .execution import prepare_ticket, run_ticket
from .document_http import extend_handler as extend_documents

PREFIX = '/api/workflow-studio'


def capabilities():
    return {'version': 1, 'guides': True, 'installed_nodes': True, 'api_graph_authoring': True,
            'registered_recipe_tickets': True, 'arbitrary_graph_execution': False,
            'native_visual_roundtrip': False, 'server_saved_workflow_documents': True,
            'shared_document_commands': True, 'named_steps': True, 'agent_sdk': True, 'mcp': False,
            'custom_frontend_widgets': False, 'shared_worker': True,
            'limits': {'document_bytes': 1048576, 'nodes': 256, 'graph_invocations_per_ticket': 1},
            'generation_submitted': False}


def schema(studio, refresh=False):
    # Existing cache and backend ownership; no parallel polling worker.
    with studio.lock:
        need(not studio.backends.busy, 'Environment switch is in progress')
        return catalog(studio.node_info(refresh), studio.backends.active)


def get(path, studio):
    if path == PREFIX + '/guides': return guides()
    if path == PREFIX + '/capabilities': return capabilities()
    if path == PREFIX + '/nodes': return schema(studio)
    if path.startswith(PREFIX + '/presets/'):
        identifier = unquote(path.rsplit('/', 1)[-1])
        with studio.lock:
            live = schema(studio)
            preset = studio.preset(identifier)
            need(preset.get('backend_id', 'primary') == live['backend_id'], 'Switch to the recipe’s environment explicitly before importing')
            graph, _ = studio.graph_for(preset)
            doc = new_document(graph, live, preset.get('name', identifier))
            doc['source'] = {'preset_id': identifier, 'authoring_only': True}
            return {'document': doc, 'generation_submitted': False}
    raise ValueError('Unknown Workflow Studio route')


def post(path, value, studio):
    need(isinstance(value, dict), 'JSON object required')
    if path == PREFIX + '/nodes/refresh':
        need(not value, 'Refresh takes an empty object')
        return schema(studio, True)
    if path == PREFIX + '/open':
        need(set(value) == {'content'} and isinstance(value['content'], str), 'Supply JSON file contents')
        data = decode(value['content'])
        opened = document(data) if isinstance(data, dict) and 'format' in data else new_document(data, schema(studio))
        return {'document': opened, 'generation_submitted': False}
    if path == PREFIX + '/import':
        need(set(value) <= {'graph', 'name'} and 'graph' in value, 'Supply graph and optional name')
        return {'document': new_document(value['graph'], schema(studio), value.get('name', 'Imported workflow')), 'generation_submitted': False}
    if path == PREFIX + '/compile':
        need(set(value) == {'document'}, 'Supply one document')
        return compile_document(value['document'], schema(studio))
    if path == PREFIX + '/prepare':
        need(set(value) == {'recipe'}, 'Supply one registered recipe')
        return prepare_ticket(studio, value['recipe'])
    if path == PREFIX + '/run':
        need(set(value) == {'ticket', 'approved'}, 'Supply ticket and explicit approval')
        return run_ticket(studio, value['ticket'], value['approved'])
    raise ValueError('Unknown Workflow Studio operation')


def extend_handler(base):
    class WorkflowHandler(base):
        def do_GET(self):
            path = urlparse(self.path).path
            if not path.startswith(PREFIX + '/'): return super().do_GET()
            if not self._safe_host(): return self._json(403, {'error': 'Loopback Host required'})
            try:
                return self._json(200, get(path, self.studio))
            except (ValueError, KeyError, TypeError, OSError, URLError) as exc:
                return self._json(400, {'error': str(exc), 'generation_submitted': False})

        def do_POST(self):
            path = urlparse(self.path).path
            if not path.startswith(PREFIX + '/'): return super().do_POST()
            if not self._safe_mutation(): return self._json(403, {'error': 'Local same-origin request required'})
            is_run = path == PREFIX + '/run'
            try:
                need(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'application/json required')
                value = decode(self.rfile.read(self._content_length(1048576)))
                result = post(path, value, self.studio)
                return self._json(200, result)
            except (ValueError, KeyError, TypeError, IndexError, OSError, URLError, RecursionError) as exc:
                result = {'error': str(exc)}
                # Never advertise generation_submitted=False on an ambiguous run.
                if not is_run: result['generation_submitted'] = False
                else: result['recovery'] = 'Inspect the same ticket/job; never retry with a new request identity.'
                return self._json(400, result)
    return extend_documents(WorkflowHandler)
