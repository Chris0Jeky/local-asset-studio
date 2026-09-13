"""Loopback-only transport for assertions rejected before a request body is read."""
import json
import socket


def atomic_json_post(port, path, body, *, host='127.0.0.1:8191', origin='http://127.0.0.1:8191', timeout=5, response_details=False):
    """Send one nonempty JSON POST atomically and decode its JSON response."""
    if not isinstance(body, bytes) or not body:
        raise ValueError('Early-refusal checks require the original nonempty body bytes')
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Loopback request path required')
    header = (
        f'POST {path} HTTP/1.1\r\n'
        f'Host: {host}\r\n'
        f'Origin: {origin}\r\n'
        'Content-Type: application/json\r\n'
        f'Content-Length: {len(body)}\r\n'
        'Connection: close\r\n\r\n'
    ).encode('ascii')
    with socket.create_connection(('127.0.0.1', port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(header + body)
        received = bytearray()
        while b'\r\n\r\n' not in received:
            if not (chunk := connection.recv(65536)):
                raise ConnectionError('Response closed before headers')
            received.extend(chunk)
        raw_headers, raw_body = bytes(received).split(b'\r\n\r\n', 1)
        lines = raw_headers.decode('iso-8859-1').split('\r\n')
        version, status, _reason = lines[0].split(' ', 2)
        if not version.startswith('HTTP/'):
            raise ValueError('Invalid HTTP response')
        headers = {}; header_pairs = []
        for line in lines[1:]:
            name, value = line.split(':', 1)
            header_pairs.append((name, value.strip())); headers[name.lower()] = value.strip()
        size = int(headers['content-length'])
        while len(raw_body) < size:
            if not (chunk := connection.recv(65536)):
                raise ConnectionError('Response closed before declared body')
            raw_body += chunk
    if len(raw_body) != size:
        raise ValueError('Unexpected bytes after response body')
    if response_details: return int(status), raw_body, header_pairs
    return int(status), json.loads(raw_body)
