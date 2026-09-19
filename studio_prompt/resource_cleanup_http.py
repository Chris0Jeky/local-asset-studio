"""Same-origin large-job resource preparation on the existing Studio server."""
from urllib.parse import urlparse

from studio_workflow.http_body import reject_json
from .core import decode

ROUTE = '/api/large-job-preparation'
HTTP_LIMIT = 128 * 1024


def extend_handler(base):
    class ResourceCleanupHandler(base):
        def do_POST(self):
            if urlparse(self.path).path != ROUTE:
                return super().do_POST()
            if not self._safe_mutation():
                return reject_json(self, 403, {'error': 'Local same-origin request required'})
            try:
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    return reject_json(self, 400, {
                        'error': 'application/json required',
                        'generation_submitted': False,
                    })
                body = self.rfile.read(self._content_length(HTTP_LIMIT))
                from large_job_preparation import controller_for
                result = controller_for(self.studio).run(decode(body, limit=HTTP_LIMIT))
                return self._json(200, result)
            except ValueError as exc:
                return self._json(400, {'error': str(exc)[:500], 'generation_submitted': False})
            except (OSError, KeyError, TypeError, IndexError, RecursionError) as exc:
                return self._json(503, {
                    'error': 'Large-job preparation is unavailable: ' + str(exc)[:200],
                    'generation_submitted': False,
                })

    return ResourceCleanupHandler
