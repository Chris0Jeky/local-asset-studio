"""Bounded recipe claims from JPEG/WebP or explicitly supplied JSON sidecars.

No pixel decode, filesystem lookup, XML interpretation, network access or execution.
Original files remain untouched; locations and hashes identify every retained claim.
"""
import hashlib
import struct
from .core import decode, fields, need
from .metadata import FILE_CAP, TEXT_CAP, PNG, inspect_png

ENTRY_CAP = 32
SEGMENT_CAP = 4096
EXIF_TAGS = {0x010e: 'ImageDescription', 0x010f: 'Make', 0x0110: 'Model',
             0x0131: 'Software', 0x013b: 'Artist', 0x8298: 'Copyright', 0x9286: 'UserComment'}
XMP = b'http://ns.adobe.com/xap/1.0/\0'


def sha(raw): return hashlib.sha256(raw).hexdigest()


class Records:
    def __init__(self): self.entries = []; self.expanded = 0; self.diagnostics = []

    def add(self, keyword, value, payload, location, encoding='utf-8', **extra):
        self.expanded += max(len(payload), len(value.encode('utf-8')) if value is not None else 0)
        need(len(self.entries) < ENTRY_CAP and self.expanded <= TEXT_CAP, 'Metadata count/expanded budget exceeded')
        self.entries.append({'keyword': keyword, 'value': value, 'payload_sha256': sha(payload),
                             'payload_bytes': len(payload), 'location': location, 'encoding': encoding,
                             'authority': 'embedded_claim', **extra})

    def exif(self, raw, location):
        need(len(raw) <= TEXT_CAP, 'EXIF byte budget exceeded')
        preamble = 6 if raw.startswith(b'Exif\0\0') else 0; data = raw[preamble:]
        need(len(data) >= 8 and data[:2] in (b'II', b'MM'), 'Invalid TIFF byte order/header')
        order = '<' if data[:2] == b'II' else '>'
        def read(fmt, pos):
            need(0 <= pos <= len(data) - struct.calcsize(order + fmt), 'EXIF offset outside payload')
            return struct.unpack_from(order + fmt, data, pos)
        need(read('H', 2)[0] == 42, 'Unsupported TIFF header')
        todo = [(read('I', 4)[0], 'IFD0')]; seen = set(); total = 0
        while todo:
            offset, label = todo.pop(0)
            if not offset: continue
            need(offset >= 8 and offset not in seen and len(seen) < 8, 'Cyclic/oversize EXIF directory graph')
            seen.add(offset); count = read('H', offset)[0]; total += count
            need(count <= 256 and total <= 1024, 'EXIF entry count exceeded')
            read('I', offset + 2 + 12 * count)  # Validate the whole directory before reading entries.
            for index in range(count):
                pos = offset + 2 + 12 * index; tag, typ, count_value = read('HHI', pos)
                if tag == 0x8769:  # ExifIFD pointer, never arbitrary MakerNote/GPS traversal.
                    need(typ == 4 and count_value == 1, 'Invalid EXIF directory pointer')
                    todo.append((read('I', pos + 8)[0], label + '/Exif')); continue
                if tag not in EXIF_TAGS: continue
                need(typ in (1, 2, 7) and count_value <= TEXT_CAP, 'Unsupported/oversize EXIF text field')
                start = pos + 8 if count_value <= 4 else read('I', pos + 8)[0]
                need(start <= len(data) and count_value <= len(data) - start, 'EXIF text offset outside payload')
                payload = data[start:start + count_value]; value = None; encoding = 'unsupported'
                try:
                    if tag == 0x9286:
                        if payload.startswith(b'ASCII\0\0\0'):
                            value = payload[8:].decode('ascii').rstrip('\0'); encoding = 'ascii'
                        elif payload.startswith(b'UNICODE\0') and payload[8:10] in (b'\xff\xfe', b'\xfe\xff'):
                            value = payload[8:].decode('utf-16').rstrip('\0'); encoding = 'utf-16-bom'
                    elif typ == 2:
                        value = payload.rstrip(b'\0').decode('utf-8'); encoding = 'utf-8'
                except UnicodeError: pass
                keyword = 'exif.' + EXIF_TAGS[tag]
                # Comfy's WebP convention stores labelled JSON in Make/Model. Keep the prefix as raw_text.
                raw_text = value
                if tag in (0x010f, 0x0110) and value is not None:
                    for prefix in ('prompt:', 'workflow:'):
                        if value.startswith(prefix): keyword = prefix[:-1]; value = value[len(prefix):]; break
                self.add(keyword, value, payload, f'{location}/{label}/{index}:{tag:04x}', encoding,
                         raw_text=raw_text)
                if value is None:
                    self.diagnostics.append({'code': 'unsupported_exif_text_encoding', 'location': self.entries[-1]['location']})
            following = read('I', offset + 2 + 12 * count)[0]
            if following: todo.append((following, label + '/next'))


def _text(raw):
    try: return raw.decode('utf-8'), 'utf-8'
    except UnicodeError: return raw.decode('latin-1'), 'latin-1'


def _jpeg(raw, records):
    need(raw.startswith(b'\xff\xd8'), 'Expected JPEG SOI'); pos = 2; segments = 0; dimensions = None; scan = False
    while pos < len(raw):
        if scan:
            pos = raw.find(b'\xff', pos)
            need(pos >= 0, 'Missing JPEG end marker')
        need(pos + 1 < len(raw) and raw[pos] == 255, 'Malformed JPEG marker')
        start = pos
        while pos < len(raw) and raw[pos] == 255: pos += 1
        need(pos < len(raw), 'Truncated JPEG marker'); marker = raw[pos]; pos += 1
        if scan and (marker == 0 or 0xd0 <= marker <= 0xd7): continue
        scan = False; segments += 1; need(segments <= SEGMENT_CAP, 'JPEG segment count exceeded')
        if marker == 0xd9:
            need(pos == len(raw), 'Trailing JPEG bytes'); return dimensions
        need(marker not in (0, 0xd8) and not 0xd0 <= marker <= 0xd7, 'Unexpected JPEG marker')
        if marker == 1: continue  # TEM has no payload.
        need(pos + 2 <= len(raw), 'Truncated JPEG segment'); size = int.from_bytes(raw[pos:pos+2], 'big')
        need(size >= 2 and pos + size <= len(raw), 'JPEG segment outside file')
        data = raw[pos + 2:pos + size]; pos += size; location = f'jpeg/{start}:ff{marker:02x}'
        if marker == 0xfe:
            text, encoding = _text(data); records.add('comment', text, data, location, encoding)
        elif marker == 0xe1 and data.startswith(b'Exif\0\0'): records.exif(data, location)
        elif marker == 0xe1 and data.startswith(XMP):
            text, encoding = _text(data[len(XMP):]); records.add('xmp', text, data, location, encoding)
            records.diagnostics.append({'code': 'xmp_retained_not_interpreted', 'location': location})
        elif marker in (0xc0, 0xc1, 0xc2):
            need(len(data) >= 6, 'Truncated JPEG frame header')
            dimensions = [int.from_bytes(data[3:5], 'big'), int.from_bytes(data[1:3], 'big')]
        elif marker == 0xda: scan = True
    raise ValueError('Missing JPEG end marker')


def _webp(raw, records):
    need(len(raw) >= 12 and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP', 'Expected WebP RIFF')
    need(int.from_bytes(raw[4:8], 'little') + 8 == len(raw), 'WebP RIFF size mismatch')
    pos = 12; count = 0; dimensions = None
    while pos < len(raw):
        count += 1; need(count <= SEGMENT_CAP and pos + 8 <= len(raw), 'WebP chunk count/truncation error')
        start = pos; kind = raw[pos:pos+4]; size = int.from_bytes(raw[pos+4:pos+8], 'little'); pos += 8
        end = pos + size; padded = end + (size & 1)
        need(padded <= len(raw), 'Truncated WebP chunk')
        if size & 1: need(raw[end] == 0, 'Invalid WebP padding')
        data = raw[pos:end]; location = f'webp/{start}:{kind.decode("ascii", errors="replace")}'
        if kind == b'EXIF': records.exif(data, location)
        elif kind == b'XMP ':
            text, encoding = _text(data); records.add('xmp', text, data, location, encoding)
            records.diagnostics.append({'code': 'xmp_retained_not_interpreted', 'location': location})
        elif kind == b'VP8X':
            need(size == 10, 'Invalid WebP extended header')
            dimensions = [1 + int.from_bytes(data[4:7], 'little'), 1 + int.from_bytes(data[7:10], 'little')]
        pos = padded
    return dimensions


def inspect_sidecar(raw):
    """An explicit schema, never filename-based discovery or an executable job."""
    need(isinstance(raw, bytes) and 0 < len(raw) <= TEXT_CAP, 'Sidecar exceeds byte budget')
    value = decode(raw)
    fields(value, ('schema_version', 'image_sha256', 'producer', 'entries'))
    need(type(value['schema_version']) is int and value['schema_version'] == 1, 'Unknown recipe sidecar schema')
    digest = value['image_sha256']
    need(isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
         'Sidecar requires lowercase image SHA-256')
    fields(value['producer'], ('name', 'version'))
    need(all(isinstance(v, str) and 0 < len(v) <= 200 for v in value['producer'].values()), 'Invalid producer claim')
    need(isinstance(value['entries'], list) and len(value['entries']) <= ENTRY_CAP, 'Sidecar entry count exceeded')
    records = Records()
    for index, item in enumerate(value['entries']):
        fields(item, ('keyword', 'value'))
        need(isinstance(item['keyword'], str) and 0 < len(item['keyword']) <= 79
             and isinstance(item['value'], str), 'Invalid sidecar text record')
        records.add(item['keyword'], item['value'], item['value'].encode('utf-8'), f'sidecar/{index}')
    for entry in records.entries: entry['authority'] = 'sidecar_claim'
    result = _report(raw, 'json_sidecar', records, None)
    result.update({'image_sha256': digest, 'image_binding': 'not_checked', 'producer': value['producer']})
    return result


def _report(raw, kind, records, dimensions):
    from .metadata import enrich_report
    return enrich_report({'kind': kind + '_recipe_inspection', 'sha256': sha(raw), 'dimensions': dimensions,
                          'entries': records.entries, 'node_claims': [], 'diagnostics': records.diagnostics,
                          'workflow_executed': False, 'pixel_data_validated': False,
                          'status': 'metadata_claims_found' if records.entries else 'no_text_metadata'})


def inspect_media(raw, sidecar=None, output_node=None):
    need(isinstance(raw, bytes) and 0 < len(raw) <= FILE_CAP, 'Expected bounded media bytes')
    if raw.startswith(PNG): result = inspect_png(raw)
    elif raw.startswith(b'\xff\xd8'):
        records = Records(); dimensions = _jpeg(raw, records); result = _report(raw, 'jpeg', records, dimensions)
    elif raw.startswith(b'RIFF'):
        records = Records(); dimensions = _webp(raw, records); result = _report(raw, 'webp', records, dimensions)
    elif raw.lstrip().startswith(b'{'): result = inspect_sidecar(raw)
    else: raise ValueError('Expected PNG, JPEG, WebP or recipe-sidecar JSON bytes')
    if sidecar is not None:
        need(result['kind'] != 'json_sidecar_recipe_inspection', 'Cannot attach a sidecar to another sidecar')
        attached = inspect_sidecar(sidecar)
        need(attached['image_sha256'] == result['sha256'], 'Sidecar image SHA-256 does not match original bytes')
        entries = result['entries'] + [dict(e, authority='sidecar_claim', source_sha256=attached['sha256'])
                                       for e in attached['entries']]
        need(len(entries) <= ENTRY_CAP and sum(max(e.get('payload_bytes', 0), len((e.get('value') or '').encode('utf-8'))) for e in entries) <= TEXT_CAP,
             'Combined metadata budget exceeded')
        result['entries'] = entries
        result['sidecar'] = {'sha256': attached['sha256'], 'image_binding': 'hash_matched_not_authenticated',
                             'producer': attached['producer']}
        from .metadata import enrich_report
        result = enrich_report(result)
    if output_node is not None:
        need(isinstance(output_node, str) and 0 < len(output_node) <= 128, 'Invalid output node')
        # Multiple graph records are competing claims, never silently select one.
        need(len(result['graphs']) == 1, 'Output selection requires exactly one interpretable graph claim')
        graph = result['graphs'][0]
        need(output_node in {o['node'] for o in graph['outputs']}, 'Unknown output node')
        graph['selected_output'] = output_node
    return result
