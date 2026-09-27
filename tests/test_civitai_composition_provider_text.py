"""Provider descriptive text is tolerant evidence, never snapshot refusal."""
import unittest

from studio_workflow import civitai_composition as C


SHA = 'a' * 64
FILE_SHA = 'B' * 64


def receipt(host='civitai.com', route='/api/v1/model-versions/101', query=None,
            outcome='ok', response_sha256=SHA):
    return {'host': host, 'route': route, 'query': {} if query is None else query,
            'retrieved_at': '2026-09-21T00:00:00Z',
            'response_sha256': response_sha256, 'etag': None, 'last_modified': None,
            'outcome': outcome, 'auth_context': 'anonymous'}


def payload(model_name='Example', version_name='Example v1', trained=None,
            model_type='LORA', base_model='Illustrious', base_model_type='Standard'):
    return {'id': 101, 'modelId': 10, 'name': version_name,
            'air': 'urn:air:sdxl:lora:civitai:10@101',
            'baseModel': base_model, 'baseModelType': base_model_type,
            'trainedWords': [] if trained is None else trained,
            'model': {'id': 10, 'name': model_name, 'type': model_type},
            'files': [{'id': 1001, 'name': 'example.safetensors', 'sizeKB': 1,
                       'hashes': {'SHA256': FILE_SHA}}]}


def image(image_id=1, post_id=11):
    return {'id': image_id, 'postId': post_id, 'username': 'alice',
            'modelVersionIds': [101, 202],
            'meta': {'civitaiResources': [
                {'type': 'lora', 'modelVersionId': 101, 'weight': 0.8},
                {'type': 'checkpoint', 'modelVersionId': 202}], 'steps': 24},
            'width': 1024, 'height': 1024, 'stats': {}}


def page(items=None, *, query=None, sha='c' * 64):
    if query is None:
        query = {'modelVersionId': '101', 'withMeta': 'true', 'browsingLevel': '31'}
    return {'receipt': receipt(host='civitai.com', route='/api/v1/images',
                              query=query, response_sha256=sha),
            'payload': {'items': [image()] if items is None else items,
                        'metadata': {'nextCursor': None}}}


def request(model_payload=None, pages=None):
    return {'format': C.INPUT_FORMAT,
            'model_version': {'receipt': receipt(),
                              'payload': payload() if model_payload is None else model_payload},
            'image_pages': [page()] if pages is None else pages}


class CivitaiCompositionProviderTextTests(unittest.TestCase):
    def test_whitespace_provider_text_is_kept_verbatim(self):
        value = payload(model_name='Example ', version_name='v1\tfinal')
        result = C.normalize(request(model_payload=value))
        self.assertEqual(result['resource']['model_name'], 'Example ')
        self.assertEqual(result['resource']['version_name'], 'v1\tfinal')
        self.assertNotIn('invalid_provider_text',
                         [item['code'] for item in result['diagnostics']])

    def test_trained_words_are_kept_verbatim_and_deduplicated(self):
        words = ['masterpiece, best quality, ', 'a\nb', 'dup', 'dup']
        result = C.normalize(request(model_payload=payload(trained=words)))
        self.assertEqual(result['resource']['trained_words'],
                         ['masterpiece, best quality, ', 'a\nb', 'dup'])

    def test_invalid_trained_words_are_omitted_with_index(self):
        words = ['ok', 'x' * 1001, 123, 'fine']
        result = C.normalize(request(model_payload=payload(trained=words)))
        self.assertEqual(result['resource']['trained_words'], ['ok', 'fine'])
        bad = [item for item in result['diagnostics'] if item['code'] == 'invalid_trained_word']
        self.assertEqual([item['index'] for item in bad], [1, 2])

    def test_distinct_trained_words_truncate_at_256(self):
        words = ['word-%d' % index for index in range(300)]
        result = C.normalize(request(model_payload=payload(trained=words)))
        self.assertEqual(result['resource']['trained_words'], words[:256])
        truncated = [item for item in result['diagnostics']
                     if item['code'] == 'trained_words_truncated']
        self.assertEqual(len(truncated), 1)
        self.assertEqual(truncated[0]['count'], 300)

    def test_non_list_trained_words_are_omitted(self):
        result = C.normalize(request(model_payload=payload(trained='x')))
        self.assertEqual(result['resource']['trained_words'], [])
        self.assertIn('invalid_trained_words',
                      [item['code'] for item in result['diagnostics']])

    def test_invalid_model_name_is_omitted_with_field(self):
        for name in ('x' * 501, 'bad\x00name'):
            with self.subTest(name=name[:8]):
                result = C.normalize(request(model_payload=payload(model_name=name)))
                self.assertIsNone(result['resource']['model_name'])
                bad = [item for item in result['diagnostics']
                       if item['code'] == 'invalid_provider_text']
                self.assertEqual(len(bad), 1)
                self.assertEqual(bad[0]['field'], 'model name')

    def test_model_type_with_trailing_space_still_refuses(self):
        with self.assertRaisesRegex(ValueError, 'Invalid model type'):
            C.normalize(request(model_payload=payload(model_type='LORA ')))


if __name__ == '__main__': unittest.main()
