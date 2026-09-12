"""Pure fixtures exercise provenance, malformed containers and the real HTTP/CLI seam."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_prompt.graph_provenance import inspect_graph
from studio_prompt.metadata import inspect_png, PNG, TEXT_CAP
from studio_prompt.recipe_intake import inspect_media, inspect_sidecar, FILE_CAP
from studio_prompt.http_extension import dispatch


def node(kind, **inputs): return {'class_type': kind, 'inputs': inputs}


def graph():
    return {'pos': node('CLIPTextEncode', text='observatory keeper'),
            'neg': node('CLIPTextEncode', text='extra fingers'),
            'unused': node('CLIPTextEncode', text='UNUSED PROMPT'),
            'sample': node('KSampler', positive=['pos', 0], negative=['neg', 0], seed=12, cfg=1),
            'decode': node('VAEDecode', samples=['sample', 0]),
            'save': node('SaveImage', images=['decode', 0])}


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def png(*records):
    header = struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0)
    return (PNG + chunk(b'IHDR', header) + b''.join(chunk(b'tEXt', k.encode() + b'\0' + v.encode()) for k, v in records)
            + chunk(b'IDAT', zlib.compress(b'\0\0\0\0\xff')) + chunk(b'IEND', b''))


def exif(entries, order='<', next_ifd=0):
    """Construct an actual TIFF directory, preserving duplicate tags."""
    header = (b'II' if order == '<' else b'MM') + struct.pack(order + 'HI', 42, 8)
    offset = 8 + 2 + 12 * len(entries) + 4; directory = []; payloads = []
    for tag, typ, value in entries:
        count = len(value)
        if count <= 4: field = value.ljust(4, b'\0')
        else:
            field = struct.pack(order + 'I', offset); offset += len(value); payloads.append(value)
        directory.append(struct.pack(order + 'HHI', tag, typ, count) + field)
    return header + struct.pack(order + 'H', len(entries)) + b''.join(directory) + struct.pack(order + 'I', next_ifd) + b''.join(payloads)


def jpeg(*segments, entropy=b'abc\xff\x00def\xff\xd0xyz'):
    def seg(marker, data): return b'\xff' + bytes([marker]) + struct.pack('>H', len(data) + 2) + data
    return (b'\xff\xd8' + b''.join(seg(m, d) for m, d in segments)
            + seg(0xc0, b'\x08\0\x01\0\x01\x01\x01\x11\0')
            + seg(0xda, b'\x01\x01\0\0\x3f\0') + entropy + b'\xff\xd9')


def webp(*chunks):
    def part(kind, value): return kind + struct.pack('<I', len(value)) + value + (b'\0' if len(value) & 1 else b'')
    body = b'WEBP' + b''.join(part(k, v) for k, v in chunks)
    return b'RIFF' + struct.pack('<I', len(body)) + body


def sidecar(raw, entries=None):
    return json.dumps({'schema_version': 1, 'image_sha256': hashlib.sha256(raw).hexdigest(),
                       'producer': {'name': 'synthetic-test-fixture', 'version': '1'},
                       'entries': entries if entries is not None else [{'keyword': 'prompt', 'value': json.dumps(graph())}]}).encode()


class DemoFixtureTests(unittest.TestCase):
    def test_runnable_demo_preserves_conflicts_and_refuses_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'demo'
            command = [sys.executable, str(ROOT / 'examples/prompt-studio/recipe-inspection/create_demo.py'), str(output)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = json.loads(first.stdout); self.assertFalse(receipt['generation_submitted'])
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
            self.assertEqual(len(files), 6)
            report = json.loads((output / 'source-report.json').read_text(encoding='utf-8'))
            self.assertEqual(len(report['graphs'][0]['outputs']), 2)
            self.assertEqual(len(report['graphs'][0]['stages']), 2)
            selected = json.loads((output / 'selected-report.json').read_text(encoding='utf-8'))
            self.assertEqual(selected['graphs'][0]['selected_output'], 'final')
            conflict = json.loads((output / 'conflict-report.json').read_text(encoding='utf-8'))
            self.assertEqual(conflict['duplicate_records'][0]['status'], 'conflicting_claims')
            self.assertNotEqual(subprocess.run(command, capture_output=True, timeout=15).returncode, 0)
            self.assertEqual(files, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()})


class GraphProvenanceTests(unittest.TestCase):
    def test_large_shared_text_cannot_expand_into_unbounded_stage_reports(self):
        value = graph(); value['pos']['inputs']['text'] = 'x' * 60000
        for i in range(20):
            value[f'stage{i}'] = node('KSampler', positive=['pos', 0], negative=['neg', 0],
                                     latent_image=[f'stage{i-1}' if i else 'sample', 0])
        value['decode']['inputs']['samples'] = ['stage19', 0]
        with self.assertRaisesRegex(ValueError, 'report byte budget'):
            inspect_graph(value)
        report = inspect_media(png(('prompt', json.dumps(value))))
        self.assertEqual(report['graphs'], [])
        self.assertEqual(json.loads(report['entries'][0]['value']), value)
        self.assertIn('report byte budget', report['diagnostics'][0]['reason'])

    def test_combined_graph_reports_are_bounded_without_dropping_records(self):
        value = graph(); value['pos']['inputs']['text'] = 'x' * 16000
        for i in range(40):
            value[f'stage{i}'] = node('KSampler', positive=['pos', 0], negative=['neg', 0],
                                     latent_image=[f'stage{i-1}' if i else 'sample', 0])
        value['decode']['inputs']['samples'] = ['stage39', 0]
        report = inspect_media(png(*[('prompt', json.dumps(value))] * 4))
        self.assertEqual(len(report['entries']), 4)
        self.assertLess(len(report['graphs']), 4)
        self.assertTrue(any('Combined graph report' in d.get('reason', '') for d in report['diagnostics']))
        self.assertLess(len(json.dumps(report)), 3 * 1024 * 1024)

    def test_unknown_output_dependencies_and_missing_stages_are_visible(self):
        value = graph(); value['custom'] = node('ThirdPartySampler', conditioning=['pos', 0])
        value['save']['inputs']['images'] = ['custom', 0]
        report = inspect_graph(value)
        self.assertEqual(report['outputs'][0]['samplers'], [])
        self.assertEqual(report['uninterpreted_nodes'][0]['node'], 'custom')
        self.assertIn('no_known_sampler_for_output', [d['code'] for d in report['diagnostics']])
        self.assertEqual(report['stages'], [])

    def test_conditioning_cycle_is_not_labelled_completely_traced(self):
        value = graph(); value['loop'] = node('ConditioningCombine', conditioning_1=['pos', 0], conditioning_2=['loop', 0])
        value['sample']['inputs']['positive'] = ['loop', 0]
        report = inspect_graph(value)
        self.assertEqual(report['stages'][0]['positive']['status'], 'partial')
        self.assertIn('cycle_or_dependent_on_cycle', [d['reason'] for d in report['stages'][0]['positive']['unresolved']])

    def test_invalid_python_input_keys_fail_with_validation_error(self):
        value = graph(); value['pos']['inputs'][1] = 'ambiguous'
        with self.assertRaisesRegex(ValueError, 'input port'): inspect_graph(value)

    def test_only_output_ancestors_have_sampler_roles(self):
        report = inspect_graph(graph()); stage = report['stages'][0]
        self.assertEqual([t['value'] for t in stage['positive']['texts']], ['observatory keeper'])
        self.assertEqual([t['value'] for t in stage['negative']['texts']], ['extra fingers'])
        unused = next(c for c in report['text_claims'] if c['node'] == 'unused')
        self.assertEqual(unused['scope'], 'not_connected_to_known_output')
        self.assertIsNone(report['selected_output']); self.assertFalse(report['workflow_executed'])
        self.assertEqual(stage['runtime_effect'], 'unverified')  # CFG=1 is not proof of negative influence.

    def test_multi_output_does_not_select_arbitrarily(self):
        value = graph(); value['other'] = node('SaveImage', images=['unused', 0])
        report = inspect_graph(value)
        self.assertEqual(len(report['outputs']), 2); self.assertIsNone(report['selected_output'])
        self.assertIn('multiple_outputs', [d['code'] for d in report['diagnostics']])
        self.assertEqual(inspect_graph(value, 'save')['selected_output'], 'save')
        with self.assertRaises(ValueError): inspect_graph(value, 'sample')

    def test_refiner_stages_remain_separate(self):
        value = graph(); value['refine'] = node('KSamplerAdvanced', positive=['neg', 0], negative=['pos', 0],
                                                latent_image=['sample', 0], noise_seed=99)
        value['decode']['inputs']['samples'] = ['refine', 0]
        report = inspect_graph(value); stages = {s['node']: s for s in report['stages']}
        self.assertEqual(set(stages), {'sample', 'refine'})
        self.assertEqual(stages['refine']['positive']['texts'][0]['value'], 'extra fingers')
        self.assertEqual(stages['sample']['positive']['texts'][0]['value'], 'observatory keeper')

    def test_controlnet_output_slot_not_input_name_decides_source(self):
        for slot, expected in ((0, 'observatory keeper'), (1, 'extra fingers')):
            with self.subTest(slot=slot):
                value = graph(); value['control'] = node('ControlNetApplyAdvanced', positive=['pos', 0], negative=['neg', 0])
                value['sample']['inputs']['positive'] = ['control', slot]
                texts = inspect_graph(value)['stages'][0]['positive']['texts']
                self.assertEqual([t['value'] for t in texts], [expected])

    def test_zero_out_is_not_reported_as_live_negative_text(self):
        value = graph(); value['zero'] = node('ConditioningZeroOut', conditioning=['pos', 0])
        value['sample']['inputs']['negative'] = ['zero', 0]
        stage = inspect_graph(value)['stages'][0]
        self.assertEqual(stage['negative']['texts'][0]['effect'], 'zeroed_text_embeddings')
        self.assertEqual(stage['positive']['texts'][0]['effect'], 'declared_conditioning')

    def test_combined_live_and_zeroed_paths_are_retained(self):
        value = graph(); value['zero'] = node('ConditioningZeroOut', conditioning=['pos', 0])
        value['combine'] = node('ConditioningCombine', conditioning_1=['pos', 0], conditioning_2=['zero', 0])
        value['sample']['inputs']['positive'] = ['combine', 0]
        texts = inspect_graph(value)['stages'][0]['positive']['texts']
        self.assertEqual({t['effect'] for t in texts}, {'declared_conditioning', 'zeroed_text_embeddings'})

    def test_unknown_operator_stops_role_guessing(self):
        value = graph(); value['mystery'] = node('CustomPython', positive=['pos', 0], negative=['neg', 0], code='raise RuntimeError()')
        value['sample']['inputs']['positive'] = ['mystery', 0]
        report = inspect_graph(value)['stages'][0]['positive']
        self.assertEqual(report['texts'], []); self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['unresolved'][0]['node'], 'mystery')

    def test_dynamic_text_is_not_interpreted(self):
        value = graph(); value['pos']['inputs']['text'] = ['unused', 0]
        report = inspect_graph(value)['stages'][0]['positive']
        self.assertEqual(report['texts'], []); self.assertEqual(report['unresolved'][0]['reason'], 'dynamic_or_missing_text')

    def test_missing_node_and_cycle_are_diagnostics_not_hangs(self):
        value = graph(); value['pos'] = node('ConditioningCombine', conditioning_1=['pos', 0], conditioning_2=['missing', 0])
        codes = [d['code'] for d in inspect_graph(value)['diagnostics']]
        self.assertIn('missing_node', codes); self.assertIn('cycle_or_dependent_on_cycle', codes)

    def test_boolean_and_invalid_slots_are_not_links(self):
        for slot in (True, -1, 256, 0.0):
            with self.subTest(slot=slot):
                value = graph(); value['sample']['inputs']['positive'] = ['pos', slot]
                report = inspect_graph(value)['stages'][0]['positive']
                self.assertEqual(report['texts'], []); self.assertEqual(report['status'], 'partial')

    def test_model_filenames_are_not_certified_pins(self):
        value = graph(); value['model'] = node('CheckpointLoaderSimple', ckpt_name='renamed.safetensors')
        value['sample']['inputs']['model'] = ['model', 0]
        item = inspect_graph(value)['model_claims'][0]
        self.assertFalse(item['identity_verified']); self.assertEqual(item['outputs'], ['save'])

    def test_no_known_output_keeps_ambiguity(self):
        value = graph(); value['save']['class_type'] = 'UnknownSaveNode'
        report = inspect_graph(value); self.assertEqual(report['stages'], [])
        self.assertTrue(all(c['scope'] == 'output_unknown' for c in report['text_claims']))

    def test_input_unchanged_and_deterministic(self):
        value = graph(); before = copy.deepcopy(value)
        first = inspect_graph(value); self.assertEqual(value, before); self.assertEqual(first, inspect_graph(value))

    def test_resource_and_shape_limits(self):
        for value in ({}, {'nodes': []}, {str(i): node('CLIPTextEncode', text='x') for i in range(513)},
                      {'a': node('CLIPTextEncode', text='x' * (TEXT_CAP + 1))}):
            with self.subTest(kind=type(value)), self.assertRaises(ValueError): inspect_graph(value)
        value = graph(); value.update({str(i): node('SaveImage', images=['decode', 0]) for i in range(17)})
        with self.assertRaisesRegex(ValueError, 'Output-node'): inspect_graph(value)

    def test_shared_subgraphs_do_not_enumerate_exponential_paths(self):
        value = graph(); previous = 'pos'
        for i in range(150):
            key = f'c{i}'; value[key] = node('ConditioningCombine', conditioning_1=[previous, 0], conditioning_2=[previous, 0]); previous = key
        value['sample']['inputs']['positive'] = [previous, 0]
        report = inspect_graph(value); self.assertEqual(len(report['stages'][0]['positive']['texts']), 1)


class RecipeIntakeTests(unittest.TestCase):
    def test_png_has_independent_conflicting_graph_claims(self):
        other = graph(); other['pos']['inputs']['text'] = 'edited claim'
        raw = png(('prompt', json.dumps(graph())), ('prompt', json.dumps(other)))
        result = inspect_png(raw)
        self.assertEqual(len(result['graphs']), 2)
        self.assertEqual(result['duplicate_records'][0]['status'], 'conflicting_claims')
        self.assertEqual(result['graphs'][1]['entry'], 1)
        self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())

    def test_identical_duplicates_preserved(self):
        raw = png(('parameters', 'one'), ('parameters', 'one'))
        report = inspect_media(raw); self.assertEqual(len(report['entries']), 2)
        self.assertEqual(report['duplicate_records'][0]['status'], 'duplicate_claims')

    def test_ambiguous_json_is_retained_uninterpreted(self):
        text = '{"a":1,"a":2}'
        report = inspect_media(png(('prompt', text)))
        self.assertEqual(report['entries'][0]['value'], text); self.assertEqual(report['graphs'], [])
        self.assertIn('Duplicate JSON key', report['diagnostics'][0]['reason'])

    def test_exif_byte_orders_and_duplicate_tags(self):
        for order in ('<', '>'):
            with self.subTest(order=order):
                payload = exif([(0x010e, 2, b'first\0'), (0x010e, 2, b'second\0')], order)
                report = inspect_media(jpeg((0xe1, b'Exif\0\0' + payload)))
                self.assertEqual([e['value'] for e in report['entries']], ['first', 'second'])
                self.assertEqual(report['duplicate_records'][0]['status'], 'conflicting_claims')

    def test_jpeg_comments_and_stuffed_entropy(self):
        raw = jpeg((0xfe, 'text: keeper'.encode()), (0xfe, b'legacy \xe9'))
        report = inspect_media(raw)
        self.assertEqual(report['dimensions'], [1, 1]); self.assertEqual(report['entries'][1]['encoding'], 'latin-1')
        self.assertEqual(report['kind'], 'jpeg_recipe_inspection'); self.assertFalse(report['pixel_data_validated'])

    def test_webp_comfy_labelled_exif_graph(self):
        payload = exif([(0x0110, 2, ('prompt:' + json.dumps(graph())).encode() + b'\0')])
        for prefix in (b'', b'Exif\0\0'):
            with self.subTest(prefix=prefix):
                raw = webp((b'VP8X', b'\0' * 10), (b'EXIF', prefix + payload))
                report = inspect_media(raw)
                self.assertEqual(report['dimensions'], [1, 1]); self.assertEqual(len(report['graphs']), 1)
                self.assertTrue(report['entries'][0]['raw_text'].startswith('prompt:'))

    def test_exif_comment_encoding_unknown_is_not_guessed(self):
        for payload, expected in ((b'ASCII\0\0\0hello', 'hello'),
                                  (b'UNICODE\0' + 'keeper'.encode('utf-16'), 'keeper'),
                                  (b'UNICODE\0\0a', None), (b'JIS\0\0\0\0\0xx', None)):
            with self.subTest(payload=payload):
                report = inspect_media(webp((b'EXIF', exif([(0x9286, 7, payload)]))))
                self.assertEqual(report['entries'][0]['value'], expected)
                if expected is None: self.assertEqual(report['diagnostics'][0]['code'], 'unsupported_exif_text_encoding')

    def test_xmp_entities_remain_literal_not_interpreted(self):
        payload = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///secret">]><x>&e;</x>'
        with patch('builtins.open', side_effect=AssertionError('No file access')):
            report = inspect_media(webp((b'XMP ', payload)))
        self.assertEqual(report['entries'][0]['value'], payload.decode())
        self.assertEqual(report['diagnostics'][0]['code'], 'xmp_retained_not_interpreted')

    def test_sidecar_binding_matches_original_not_decoded_pixels(self):
        raw = png(); original = bytes(raw); claim = sidecar(raw)
        report = inspect_media(raw, claim)
        self.assertEqual(raw, original); self.assertEqual(report['sidecar']['image_binding'], 'hash_matched_not_authenticated')
        self.assertEqual(report['entries'][0]['authority'], 'sidecar_claim'); self.assertEqual(len(report['graphs']), 1)
        with self.assertRaisesRegex(ValueError, 'does not match'): inspect_media(png(('note', 'same pixels')), claim)

    def test_standalone_sidecar_does_not_claim_image_verification(self):
        report = inspect_sidecar(sidecar(png()))
        self.assertEqual(report['image_binding'], 'not_checked')
        self.assertEqual(report['producer']['name'], 'synthetic-test-fixture')

    def test_sidecar_does_not_overwrite_embedded_claim(self):
        raw = png(('prompt', json.dumps(graph())))
        different = graph(); different['pos']['inputs']['text'] = 'sidecar variant'
        attached = sidecar(raw, [{'keyword': 'prompt', 'value': json.dumps(different)}])
        report = inspect_media(raw, attached)
        self.assertEqual(len(report['graphs']), 2)
        self.assertEqual(report['duplicate_records'][0]['status'], 'conflicting_claims')
        self.assertNotEqual(report['graphs'][0]['source_sha256'], report['graphs'][1]['source_sha256'])
        with self.assertRaisesRegex(ValueError, 'exactly one'): inspect_media(raw, attached, 'save')

    def test_explicit_output_selection(self):
        raw = png(('prompt', json.dumps(graph())))
        self.assertEqual(inspect_media(raw, output_node='save')['graphs'][0]['selected_output'], 'save')
        for output in ('no-such-node', True, ''):
            with self.subTest(output=output), self.assertRaises(ValueError): inspect_media(raw, output_node=output)

    def test_sidecar_shape_and_count_fail_closed(self):
        value = json.loads(sidecar(png()))
        for field, replacement in (('image_sha256', '../file'), ('schema_version', True),
                                    ('producer', {'name': 'missing-version'}), ('entries', [{}] * 33)):
            changed = copy.deepcopy(value); changed[field] = replacement
            with self.subTest(field=field), self.assertRaises(ValueError): inspect_sidecar(json.dumps(changed).encode())
        value['path'] = '/secret'
        with self.assertRaises(ValueError): inspect_sidecar(json.dumps(value).encode())

    def test_exif_offsets_and_cycles_are_rejected(self):
        raw = exif([(0x010e, 2, b'hello\0')]); changed = bytearray(raw); changed[18:22] = b'\xff' * 4
        for payload in (bytes(changed), exif([], next_ifd=8), b'II\x2a\0\xff\xff\xff\xff', b'II\0\0' + b'\0' * 8):
            with self.subTest(payload=payload), self.assertRaises(ValueError): inspect_media(webp((b'EXIF', payload)))

    def test_nested_exif_ifd(self):
        # IFD0's only entry points at a second directory with an ASCII UserComment.
        payload = b'ASCII\0\0\0hello'; offset = 26
        raw = (b'II*\0\x08\0\0\0' + struct.pack('<HHHIII', 1, 0x8769, 4, 1, offset, 0)
               + struct.pack('<HHHIII', 1, 0x9286, 7, len(payload), 44, 0) + payload)
        report = inspect_media(webp((b'EXIF', raw)))
        self.assertEqual(report['entries'][0]['value'], 'hello')
        self.assertIn('IFD0/Exif', report['entries'][0]['location'])

    def test_container_truncations_and_padding_fail_closed(self):
        original = webp((b'XMP ', b'x')); badpad = original[:-1] + b'x'
        values = (original[:-1], badpad, b'RIFF\0\0\0\0WEBP', jpeg()[:-2], jpeg() + b'extra',
                  b'\xff\xd8\xff\xe1\0\1\xff\xd9', b'\xff\xd8x\xff\xd9')
        for raw in values:
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError): inspect_media(raw)

    def test_metadata_budget_covers_whole_document(self):
        raw = webp(*[(b'XMP ', b'x' * 5000)] * 27)
        with self.assertRaisesRegex(ValueError, 'budget'): inspect_media(raw)
        with self.assertRaises(ValueError): inspect_media(b'x' * (FILE_CAP + 1))
        with self.assertRaises(ValueError): inspect_sidecar(b' ' * (TEXT_CAP + 1))
        with self.assertRaises(ValueError): inspect_media(webp(*[(b'XMP ', b'x')] * 33))

    def test_real_pillow_containers(self):
        from PIL import Image
        for kind in ('PNG', 'JPEG', 'WEBP'):
            with self.subTest(kind=kind):
                stream = io.BytesIO(); Image.new('RGB', (4, 3), (1, 2, 3)).save(stream, format=kind)
                report = inspect_media(stream.getvalue())
                self.assertFalse(report['workflow_executed']); self.assertEqual(report['graphs'], [])

    def test_dispatch_backward_compatible_and_no_generation(self):
        class NoWork:
            def __getattr__(self, name): raise AssertionError(f'Studio must not be accessed: {name}')
        for key, raw in (('png_base64', png()), ('media_base64', jpeg()), ('media_base64', sidecar(png()))):
            with self.subTest(key=key):
                report = dispatch('/api/prompt/metadata', {key: base64.b64encode(raw).decode()}, NoWork())
                self.assertFalse(report['workflow_executed'])
        for body in ({}, {'png_base64': 'AA==', 'media_base64': 'AA=='}, {'media_base64': '!!'},
                     {'png_base64': base64.b64encode(jpeg()).decode()}, {'media_base64': 4}):
            with self.subTest(body=body), self.assertRaises(ValueError): dispatch('/api/prompt/metadata', body)

    def test_cli_explicit_sidecar_and_output_exclusive_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); image = root/'source.png'; claim = root/'claim.json'; result = root/'report.json'
            image.write_bytes(png()); claim.write_bytes(sidecar(image.read_bytes()))
            command = [sys.executable, str(ROOT/'scripts/studio_prompt.py'), 'inspect-media', str(image),
                       '--sidecar', str(claim), '--output-node', 'save', '--out', str(result)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(first.returncode, 0, first.stderr)
            content = result.read_bytes(); report = json.loads(content)
            self.assertEqual(report['graphs'][0]['selected_output'], 'save')
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 2); self.assertEqual(result.read_bytes(), content)


if __name__ == '__main__': unittest.main()
