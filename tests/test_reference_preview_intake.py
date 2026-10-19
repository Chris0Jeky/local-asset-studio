"""The real preview handler must bound allocations before decoding original images."""
import base64
import copy
import hashlib
import io
import json
import unittest
import weakref
from email.message import Message
from unittest.mock import patch

from studio_prompt import reference_review
from studio_prompt import reference_analysis
from studio_prompt import reference_intake
from studio_prompt import http_extension
from studio_prompt.http_extension import extend_handler
import test_reference_review as fixtures
from test_server import server


class ObservedReader:
    def __init__(self, raw, short=None):
        self.stream = io.BytesIO(raw)
        self.requests = []
        self.short = short

    def read(self, size):
        self.requests.append(size)
        return self.stream.read(min(size, self.short) if self.short else size)

    @property
    def consumed(self): return self.stream.tell()


class PreviewIntakeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReferenceReviewTests(); self.fixture.setUp()

    def call(self, raw, *, short=None, lengths=None, extra_headers=(), reader=None, connection=None):
        class Base:
            _safe_host = server.Handler._safe_host
            _safe_mutation = server.Handler._safe_mutation
            _content_length = server.Handler._content_length
            def _json(self, status, value): return status, value
        handler = extend_handler(Base)()
        handler.path = '/api/prompt/reference-review/preview'
        handler.headers = Message()
        for key, value in [('Host', 'localhost:8191'), ('Origin', 'http://localhost:8191'),
                           ('Content-Type', 'application/json'), *extra_headers]:
            handler.headers[key] = value
        for length in lengths if lengths is not None else [str(len(raw))]:
            handler.headers['Content-Length'] = length
        handler.studio = None
        handler.close_connection = False
        handler.rfile = reader or ObservedReader(raw, short=short)
        if connection is not None: handler.connection = connection
        self.handler = handler
        return handler.do_POST()

    def encoded(self, value=None):
        return json.dumps(value if value is not None else self.fixture.payload).encode()

    def replace_original(self, raw):
        value = copy.deepcopy(self.fixture.payload)
        report = value['analysis']; sha = hashlib.sha256(raw).hexdigest()
        report['request']['references'][0]['sha256'] = sha
        report['analysis_inputs'][0]['source_sha256'] = sha
        value['analysis'] = reference_analysis.make_report(report['request'], report['answer'], report['analysis_inputs'])
        value['review'] = reference_analysis.review_template(value['analysis'])
        value['images'][0]['media_base64'] = base64.b64encode(raw).decode()
        return value

    def test_preview_never_requests_an_aggregate_body_allocation(self):
        status, result = self.call(self.encoded() + b' ' * (1024 * 1024))
        self.assertEqual(status, 200, result.get('error'))
        self.assertTrue(result['source_bytes_verified'])
        self.assertLessEqual(max(self.handler.rfile.requests), 64 * 1024)

    def test_short_reads_preserve_the_complete_current_client_payload(self):
        status, result = self.call(self.encoded(), short=7)
        self.assertEqual(status, 200, result.get('error'))
        self.assertEqual(result['base_intent'], self.fixture.intent)
        self.assertTrue(result['source_bytes_verified'])

    def test_per_image_limit_stops_intake_before_reading_the_rest_of_the_body(self):
        value = {'images': copy.deepcopy(self.fixture.images), **self.fixture.payload}
        value['images'] = copy.deepcopy(self.fixture.images)
        value['images'][0]['media_base64'] = 'A' * (256 * 1024)
        raw = self.encoded(value)
        with patch.object(reference_review, 'IMAGE_LIMIT', 8), patch.object(reference_review, 'ENCODED_LIMIT', 12):
            status, result = self.call(raw)
        self.assertEqual(status, 400)
        self.assertIn('8 MiB', result['error'])
        self.assertLessEqual(self.handler.rfile.consumed, 64 * 1024)
        self.assertTrue(self.handler.close_connection)

    def test_oversized_header_closes_without_reading(self):
        status, result = self.call(b'', lengths=[str(reference_review.HTTP_LIMIT + 1)])
        self.assertEqual(status, 400)
        self.assertEqual(result['error'], 'Request body is too large')
        self.assertEqual(self.handler.rfile.requests, [])
        self.assertTrue(self.handler.close_connection)

    def test_ambiguous_framing_is_refused_without_consuming_image_bytes(self):
        raw = self.encoded()
        cases = [dict(lengths=[str(len(raw)), str(len(raw))]),
                 dict(lengths=[str(len(raw)), str(len(raw) + 1)]),
                 dict(extra_headers=[('Transfer-Encoding', 'chunked')])]
        for case in cases:
            with self.subTest(case=case):
                status, result = self.call(raw, **case)
                self.assertEqual(status, 400, result.get('error'))
                self.assertEqual(self.handler.rfile.requests, [])
                self.assertTrue(self.handler.close_connection)

    def test_incomplete_declared_body_is_never_accepted_as_a_short_valid_document(self):
        raw = self.encoded()
        status, result = self.call(raw, lengths=[str(len(raw) + 1)])
        self.assertEqual(status, 400, result.get('error'))
        self.assertTrue(self.handler.close_connection)

    def test_metadata_budget_applies_before_decoding_a_large_ignored_helper_field(self):
        value = copy.deepcopy(self.fixture.payload)
        value['analysis'] = {'analysis': value['analysis'], 'helper_note': 'x' * (1024 * 1024 + 1)}
        raw = self.encoded(value) + b' ' * (256 * 1024)
        status, result = self.call(raw)
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('metadata', result['error'])
        self.assertLess(self.handler.rfile.consumed, len(raw))
        self.assertTrue(self.handler.close_connection)

    def test_nested_helper_metadata_is_refused_before_json_can_build_it(self):
        raw = self.encoded()
        helper = b'{"analysis":' + json.dumps(self.fixture.report).encode() + b',"helper":' + b'[' * 70 + b'0' + b']' * 70 + b'}'
        raw = raw.replace(json.dumps(self.fixture.report).encode(), helper, 1)
        status, result = self.call(raw)
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('nested', result['error'])
        self.assertTrue(self.handler.close_connection)

    def test_metadata_structure_budget_bounds_many_small_objects(self):
        value = copy.deepcopy(self.fixture.payload)
        value['analysis'] = {'analysis': value['analysis'], 'helper': [{}] * 20000}
        status, result = self.call(self.encoded(value))
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('metadata', result['error'])
        self.assertTrue(self.handler.close_connection)

    def test_arbitrary_field_order_and_unicode_keep_the_current_draft(self):
        value = copy.deepcopy(self.fixture.payload)
        value['intent']['brief'] = 'Keep 静かな夜 🌠 and the literal \\"quotation\\".'
        for keys in (['images', 'adopt_brief', 'intent', 'review', 'analysis'],
                     ['review', 'intent', 'analysis', 'images', 'adopt_brief']):
            reordered = {key: value[key] for key in keys}
            reordered['images'] = [dict(reversed(list(row.items()))) for row in value['images']]
            for ascii_only in (False, True):
                with self.subTest(keys=keys, ascii_only=ascii_only):
                    status, result = self.call(json.dumps(reordered, ensure_ascii=ascii_only).encode(), short=11)
                    self.assertEqual(status, 200, result.get('error'))
                    self.assertEqual(result['base_intent'], value['intent'])
                    self.assertTrue(result['source_bytes_verified'])

    def test_escaped_base64_and_padding_split_across_reads_preserve_original_bytes(self):
        original = base64.b64decode(self.fixture.images[0]['media_base64'])
        for extra in (b'\xff', b'\xff\xff', b'\xff\xff\xff'):
            value = self.replace_original(original + extra)
            encoded = value['images'][0]['media_base64']
            escaped = ''.join('\\u%04x' % ord(char) if index % 3 == 0 else
                              '\\/' if char == '/' else char for index, char in enumerate(encoded))
            raw = self.encoded(value).replace(encoded.encode(), escaped.encode())
            for short in (1, 2, 3, 5, 7):
                with self.subTest(extra=len(extra), short=short):
                    status, result = self.call(raw, short=short)
                    self.assertEqual(status, 200, result.get('error'))
                    self.assertTrue(result['source_bytes_verified'])

    def test_malformed_json_and_base64_do_not_become_valid_during_streaming(self):
        valid = self.encoded()
        cases = [valid + b'{}', valid[:-1], b'{"analysis":NaN}', b'{"analysis":1e999}',
                 b'{"images":[],,}', b'{"images":[,]}', b'{"images":[{}]}',
                 b'{"analysis":{"value":1 2}}', b'{"analysis":{"x":1,"x":2}}',
                 b'{"analysis":"\xff"}', b'{"analysis":"\\ud800"}']
        encoded = self.fixture.images[0]['media_base64'].encode()
        for bad in (b'AA=A', b'AAAA=', b'AA==AAAA', b'AA== ', b'AA===', b'====',
                    b'\\u00ff', b'\\n', b'\\q', b'\\u00zz', b'A', b'AAA'):
            cases.append(valid.replace(encoded, bad, 1))
        for raw in cases:
            with self.subTest(raw=raw[:80]):
                status, result = self.call(raw, short=3)
                self.assertEqual(status, 400, result.get('error'))
                self.assertTrue(self.handler.close_connection)

    def test_duplicate_keys_after_a_captured_image_are_refused(self):
        valid = self.encoded()
        image_json = json.dumps(self.fixture.images).encode()
        cases = [valid[:-1] + b',"images":[]}',
                 valid.replace(image_json, image_json[:-2] + b',"media_base64":"AAAA"}]', 1),
                 valid.replace(image_json, image_json[:-2] + b',"reference_id":"picture-2"}]', 1),
                 valid[:-1] + b',"im\\u0061ges":[]}']
        for raw in cases:
            with self.subTest(raw=raw[-100:]):
                status, result = self.call(raw)
                self.assertEqual(status, 400, result.get('error'))
                self.assertIn('Duplicate', result['error'])
                self.assertTrue(self.handler.close_connection)

    def test_fifth_image_is_refused_before_its_string_is_consumed(self):
        image = json.dumps(self.fixture.images[0]).encode()
        raw = b'{"images":[' + b','.join([image] * 4) + b',{"reference_id":"fifth","media_base64":"' + b'A' * (256 * 1024) + b'"}]}'
        status, result = self.call(raw)
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('four', result['error'])
        self.assertLessEqual(self.handler.rfile.consumed, 64 * 1024)
        self.assertTrue(self.handler.close_connection)

    def test_declared_body_does_not_consume_the_following_request(self):
        raw = self.encoded(); following = b'POST /api/prompt/compile HTTP/1.1\r\n'
        status, result = self.call(raw + following, lengths=[str(len(raw))], short=7)
        self.assertEqual(status, 200, result.get('error'))
        self.assertEqual(self.handler.rfile.consumed, len(raw))
        self.assertFalse(self.handler.close_connection)

    def test_decoded_pixels_are_explicitly_released_even_if_the_decoder_raises(self):
        real_open = reference_review.Image.open
        for fail in (False, True):
            loaded = []
            def open_image(*args, **kwargs):
                image = real_open(*args, **kwargs); real_load = image.load
                def load_image():
                    pixels = real_load(); loaded.append(image)
                    image.load = real_load
                    if fail: raise OSError('Injected failure after pixel allocation')
                    return pixels
                image.load = load_image
                return image
            with self.subTest(fail=fail), patch.object(reference_review.Image, 'open', open_image):
                status, result = self.call(self.encoded())
                self.assertEqual(status, 400 if fail else 200, result.get('error'))
                self.assertTrue(loaded)
                for image in loaded:
                    with self.assertRaisesRegex(ValueError, 'closed'):
                        image.getpixel((0, 0))

    def test_trickle_progress_cannot_extend_the_total_intake_deadline(self):
        clock = [0]
        class TrickleReader(ObservedReader):
            def read(self, size):
                clock[0] += 31
                return super().read(size)
        reader = TrickleReader(self.encoded(), short=1)
        with patch('time.monotonic', side_effect=lambda: clock[0]):
            status, result = self.call(self.encoded(), reader=reader)
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('timed out', result['error'])
        self.assertEqual(reader.consumed, 1)
        self.assertTrue(self.handler.close_connection)

    def test_captured_originals_are_cleared_before_success_or_failure_is_returned(self):
        original_dispatch = http_extension.dispatch
        for fail in (False, True):
            captures = []
            def dispatch(path, value, studio):
                captures.extend(row['media_base64'] for row in value['images'])
                if fail: raise ValueError('Injected dispatch refusal')
                return original_dispatch(path, value, studio)
            with self.subTest(fail=fail), patch.object(http_extension, 'dispatch', dispatch):
                status, result = self.call(self.encoded())
                self.assertEqual(status, 400 if fail else 200, result.get('error'))
                self.assertEqual(len(captures), 2)
                self.assertTrue(all(item.raw is None for item in captures))

    def test_parser_failure_clears_images_captured_before_a_duplicate_field(self):
        captures = []; original_init = reference_intake._CapturedImage.__init__
        def capture(instance, raw):
            original_init(instance, raw); captures.append(instance)
        with patch.object(reference_intake._CapturedImage, '__init__', capture):
            status, result = self.call(self.encoded()[:-1] + b',"images":[]}')
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('Duplicate', result['error'])
        self.assertEqual(len(captures), 2)
        self.assertTrue(all(item.raw is None for item in captures))

    def test_byte_cap_checks_decoded_size_before_base64_allocates_the_crossing_block(self):
        raw = base64.b64decode(self.fixture.images[0]['media_base64'])
        raw += b'\0' * max(0, max(len(base64.b64decode(row['media_base64'])) for row in self.fixture.images) - len(raw))
        cap = len(raw)
        while cap % 3 != 2:
            raw += b'\0'; cap += 1
        # At 3n+2 bytes, adding one original byte has the same encoded length.
        at_limit = self.replace_original(raw); over = self.replace_original(raw + b'\0')
        encoded_limit = len(at_limit['images'][0]['media_base64'])
        self.assertEqual(len(over['images'][0]['media_base64']), encoded_limit)
        decoder = base64.b64decode; allocated = []
        def decode_block(block, **kwargs):
            decoded = decoder(block, **kwargs); allocated.append(len(decoded))
            return decoded
        with patch.object(reference_review, 'IMAGE_LIMIT', cap), patch.object(reference_review, 'ENCODED_LIMIT', encoded_limit):
            status, result = self.call(self.encoded(at_limit))
            self.assertEqual(status, 200, result.get('error'))
            with patch.object(reference_intake.base64, 'b64decode', decode_block):
                status, result = self.call(self.encoded(over))
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('8 MiB', result['error'])
        self.assertEqual(allocated, [])

    def test_json_cannot_supply_an_internal_capture_or_skip_source_checks(self):
        for fake in ({'raw': 'AAAA'}, {'verified': True}, None, 1, ['AAAA']):
            value = copy.deepcopy(self.fixture.payload); value['images'][0]['media_base64'] = fake
            with self.subTest(fake=fake):
                self.assertEqual(self.call(self.encoded(value))[0], 400)

    def test_previous_codec_owner_is_released_before_opening_another_image(self):
        opened = []; previous_owners = []; original_open = reference_review.Image.open
        def open_image(*args, **kwargs):
            previous_owners.append(sum(reference() is not None for reference in opened))
            image = original_open(*args, **kwargs); opened.append(weakref.ref(image))
            return image
        with patch.object(reference_review.Image, 'open', open_image):
            status, result = self.call(self.encoded())
        self.assertEqual(status, 200, result.get('error'))
        self.assertEqual(max(previous_owners), 0)

    def test_metadata_budget_counts_utf8_bytes_at_the_exact_boundary(self):
        value = copy.deepcopy(self.fixture.payload)
        value['analysis'] = {'analysis': value['analysis'], 'note': '静かな 🌠'}
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
        metadata_bytes = len(raw) - sum(len(row['media_base64']) for row in value['images'])
        with patch.object(reference_intake, 'METADATA_LIMIT', metadata_bytes):
            status, result = self.call(raw, short=1)
            self.assertEqual(status, 200, result.get('error'))
        with patch.object(reference_intake, 'METADATA_LIMIT', metadata_bytes - 1):
            status, result = self.call(raw, short=1)
            self.assertEqual(status, 400, result.get('error'))
            self.assertIn('metadata', result['error'])

    def test_io_failure_releases_an_already_captured_original(self):
        value = {'images': self.fixture.images, **self.fixture.payload}
        raw = self.encoded(value); captures = []; original_init = reference_intake._CapturedImage.__init__
        first = json.dumps(self.fixture.images[0]).encode()
        stop = raw.index(first) + len(first) + 1
        class FailedReader(ObservedReader):
            def read(self, size):
                if self.consumed == stop: raise OSError('Injected interrupted upload')
                return super().read(min(size, stop - self.consumed))
        def capture(instance, data):
            original_init(instance, data); captures.append(instance)
        with patch.object(reference_intake._CapturedImage, '__init__', capture):
            status, result = self.call(raw, reader=FailedReader(raw))
        self.assertEqual(status, 400, result.get('error'))
        self.assertIn('interrupted', result['error'])
        self.assertEqual(len(captures), 1)
        self.assertIsNone(captures[0].raw)
        self.assertTrue(self.handler.close_connection)

    def test_intake_restores_the_socket_timeout_after_success_and_refusal(self):
        class Connection:
            def __init__(self, timeout): self.timeout = timeout
            def gettimeout(self): return self.timeout
            def settimeout(self, value): self.timeout = value
        for timeout in (None, 0.5):
            for raw, expected in ((self.encoded(), 200), (self.encoded()[:-1], 400)):
                connection = Connection(timeout)
                with self.subTest(timeout=timeout, expected=expected):
                    status, result = self.call(raw, short=7, connection=connection)
                    self.assertEqual(status, expected, result.get('error'))
                    self.assertEqual(connection.gettimeout(), timeout)


if __name__ == '__main__': unittest.main()
