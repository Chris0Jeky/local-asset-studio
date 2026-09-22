"""Read-only recovery observation on the existing loopback HTTP extension seam."""
import json
import sqlite3
from urllib.parse import parse_qsl, urlsplit
from .asset_recovery_observation import observe
from .http_body import reject_json

PATH = '/api/assets/recovery-observation'


def read(raw, workspace):
    if len(raw.encode('utf-8')) > 64000:
        raise ValueError('Recovery query exceeds its byte limit')
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc or parsed.fragment or parsed.path != PATH:
        raise ValueError('Relative recovery observation route required')
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=3, errors='strict')
    query = dict(pairs)
    if (len(query) != len(pairs) or not {'workspace_id', 'ids'} <= set(query) or
            set(query) - {'workspace_id', 'ids', 'collection_id'}):
        raise ValueError('Supply exactly one Workspace identity and target list')
    try:
        ids = json.loads(query['ids'])
    except (ValueError, RecursionError):
        raise ValueError('Supply a bounded JSON target list') from None
    return observe(workspace, ids, query['workspace_id'], query.get('collection_id'))


def extend_handler(base):
    class RecoveryObservationHandler(base):
        def do_GET(self):
            if self.path.split('?', 1)[0] != PATH: return super().do_GET()
            if not self._safe_host(): return self._json(403, {'error': 'Loopback Host required'})
            try:
                result, status = read(self.path, self.studio.assets), 200
            except ValueError as error:
                if callable(getattr(error, 'response', None)):
                    result, status = error.response(), error.status
                else:
                    result, status = {'error': str(error), 'code': 'asset_observation_invalid'}, 400
            except (sqlite3.Error, OSError):
                result, status = {'error': 'Recovery observation unavailable; retained evidence is unchanged', 'code': 'asset_observation_unavailable'}, 503
            try: return self._json(status, result)
            except (BrokenPipeError, ConnectionResetError): return None

        def do_POST(self):
            if self.path.split('?', 1)[0] != PATH: return super().do_POST()
            self.close_connection = True
            return reject_json(self, 405, {'error': 'Recovery observation is GET-only; nothing changed'})
    return RecoveryObservationHandler
