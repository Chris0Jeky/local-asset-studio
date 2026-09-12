"""Bounded PNG text metadata inspection. No pixel decoding, imports or workflow execution."""
import hashlib
import struct
import zlib
from .core import need, decode, canonical
from .graph_provenance import inspect_graph

PNG = b'\x89PNG\r\n\x1a\n'
TEXT_CAP = 128 * 1024
FILE_CAP = 16 * 1024 * 1024
REPORT_CAP = 2 * 1024 * 1024


def inflate(data):
    obj = zlib.decompressobj()
    try:
        out = obj.decompress(data, TEXT_CAP + 1)
    except zlib.error as exc:
        raise ValueError('Invalid compressed metadata') from exc
    need(len(out) <= TEXT_CAP and not obj.unconsumed_tail and obj.eof and not obj.unused_data, 'Invalid/oversize compressed metadata')
    return out


def inspect_png(raw):
    need(isinstance(raw, bytes) and len(raw) <= FILE_CAP and raw.startswith(PNG), 'Expected bounded PNG bytes')
    offset = 8; entries = []; dimensions = None; done = False; chunks = 0; expanded = 0
    while offset < len(raw):
        chunks += 1; need(chunks <= 4096 and offset + 12 <= len(raw), 'Chunk count/truncation error')
        n = struct.unpack_from('>I', raw, offset)[0]; kind = raw[offset+4:offset+8]
        end = offset + 12 + n; need(end <= len(raw), 'Truncated PNG chunk')
        data = raw[offset+8:offset+8+n]; crc = struct.unpack_from('>I', raw, offset+8+n)[0]
        need(zlib.crc32(kind+data) & 0xffffffff == crc, 'PNG CRC mismatch')
        if chunks == 1:
            need(kind == b'IHDR' and n == 13, 'Missing PNG IHDR')
            dimensions = list(struct.unpack_from('>II', data))
            need(all(dimensions) and dimensions[0]*dimensions[1] <= 64*1024*1024, 'Image dimensions exceed inspection budget')
        if kind in (b'tEXt', b'zTXt', b'iTXt'):
            need(len(entries) < 32 and n <= TEXT_CAP, 'Metadata count/size cap exceeded')
            key, tail = data.split(b'\0', 1); need(1 <= len(key) <= 79, 'Invalid PNG keyword')
            if kind == b'tEXt': value = tail.decode('latin-1')
            elif kind == b'zTXt':
                need(tail[:1] == b'\0', 'Unsupported compression method')
                value = inflate(tail[1:]).decode('latin-1')
            else:
                need(len(tail) >= 2 and tail[0] in (0, 1) and tail[1] == 0, 'Invalid iTXt flags')
                language, translated, body = tail[2:].split(b'\0', 2)
                language.decode('ascii'); translated.decode('utf-8')
                value = (inflate(body) if tail[0] else body).decode('utf-8')
            expanded += len(value.encode('utf-8')); need(expanded <= TEXT_CAP, 'Expanded text budget exceeded')
            entries.append({'keyword': key.decode('latin-1'), 'value': value, 'authority': 'embedded_claim'})
        offset = end
        if kind == b'IEND': need(n == 0 and offset == len(raw), 'Malformed PNG end'); done = True; break
    need(done, 'Missing PNG end')
    claims = []
    for item in entries:
        if item['keyword'] == 'prompt':
            try: graph = decode(item['value'].encode('utf-8'))
            except (ValueError, RecursionError): continue
            if not isinstance(graph, dict): continue
            for node_id, node in list(graph.items())[:512]:
                if not isinstance(node, dict) or not isinstance(node.get('inputs'), dict): continue
                cls = node.get('class_type'); inputs = node['inputs']
                for field in {'CLIPTextEncode': ('text',), 'TextEncodeQwenImageEditPlus': ('prompt',),
                              'KSampler': ('seed', 'steps', 'cfg', 'sampler_name', 'scheduler'),
                              'CheckpointLoaderSimple': ('ckpt_name',)}.get(cls, ()):
                    value = inputs.get(field)
                    if type(value) in (str, int, float, bool):
                        claims.append({'node': str(node_id), 'class_type': cls, 'field': field, 'value': value})
    return enrich_report({'kind': 'png_recipe_inspection', 'sha256': hashlib.sha256(raw).hexdigest(), 'dimensions': dimensions,
            'entries': entries, 'node_claims': claims, 'workflow_executed': False,
            'status': 'metadata_claims_found' if entries else 'no_text_metadata',
            'pixel_data_validated': False})


def enrich_report(report):
    """Attach independent graph reports without choosing between conflicting claims."""
    graphs = []; grouped = {}; diagnostics = list(report.get('diagnostics', []))
    report_bytes = len(canonical(report['entries'])) + len(canonical(report.get('node_claims', [])))
    # Re-enrichment after explicit sidecar attachment is idempotent.
    diagnostics = [d for d in diagnostics if d.get('code') not in ('uninterpreted_prompt_claim',)]
    for index, item in enumerate(report['entries']):
        item.setdefault('location', f"png/text/{index}")
        item.setdefault('source_sha256', report['sha256'])
        value = item.get('value')
        item['text_sha256'] = hashlib.sha256(value.encode('utf-8')).hexdigest() if isinstance(value, str) else None
        grouped.setdefault(item['keyword'], []).append(index)
        if item['keyword'] != 'prompt' or not isinstance(value, str): continue
        try:
            graph = inspect_graph(decode(value.encode('utf-8')))
            cost = len(canonical(graph))
            need(report_bytes + cost <= REPORT_CAP, 'Combined graph report byte budget exceeded')
            report_bytes += cost
        except (ValueError, TypeError, RecursionError) as exc:
            diagnostics.append({'code': 'uninterpreted_prompt_claim', 'entry': index, 'reason': str(exc)})
            continue
        graph['entry'] = index; graph['source_sha256'] = item['source_sha256']; graphs.append(graph)
    conflicts = []
    for keyword, indices in grouped.items():
        if len(indices) < 2: continue
        hashes = {report['entries'][i].get('text_sha256') or report['entries'][i].get('payload_sha256') for i in indices}
        conflicts.append({'keyword': keyword, 'entries': indices,
                          'status': 'conflicting_claims' if len(hashes) > 1 else 'duplicate_claims'})
    report.update({'graphs': graphs, 'duplicate_records': conflicts, 'diagnostics': diagnostics,
                   'schema_version': 2, 'workflow_executed': False,
                   'warning': 'Embedded and sidecar metadata are editable claims, not authenticated provenance. '
                              'Known graph links can trace sampler roles but do not prove which output produced these pixels '
                              'or that negative guidance affected execution. Unknown operators stay unresolved. '
                              'Missing metadata cannot reveal an exact original prompt, seed or model.'})
    if report['entries']: report['status'] = 'metadata_claims_found'
    return report
