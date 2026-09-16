"""Read-only control proposals composed onto the ordinary Studio handler."""
from urllib.parse import urlparse
from urllib.error import URLError
from .core import MAX_BYTES, decode, need
from .control_preview import request

PATH = '/api/workflow-studio/control-preview'


def extend_handler(base):
    class ControlPreviewHandler(base):
        def do_POST(self):
            if urlparse(self.path).path != PATH: return super().do_POST()
            if not self._safe_mutation():
                return self._json(403, {'code': 'same_origin_required', 'error': 'Local same-origin request required', 'generation_submitted': False})
            try:
                need(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'application/json required')
                value = decode(self.rfile.read(self._content_length(MAX_BYTES)))
                return self._json(200, request(value, self.studio))
            except (ValueError, KeyError, TypeError, IndexError, OSError, URLError, RecursionError) as exc:
                return self._json(400, {'code': 'control_preview_invalid', 'error': str(exc), 'committed': False, 'generation_submitted': False})
    return ControlPreviewHandler
