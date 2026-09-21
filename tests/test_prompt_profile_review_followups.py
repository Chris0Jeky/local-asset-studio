"""Review follow-ups for exact prompt-profile binding and documentation."""
from pathlib import Path
import unittest

from studio_prompt.http_extension import dispatch
from studio_prompt.schema import profiles

ROOT = Path(__file__).resolve().parents[1]


class PromptBindingScopeTests(unittest.TestCase):
    def test_text_only_http_binding_refuses_non_image_presets_before_graph_access(self):
        class NoGraph:
            def preset(self, key):
                self.asserted_key = key
                return {
                    'id': key,
                    'modality': 'video',
                    'positive': ['2', 'text'],
                    'negative': ['3', 'text'],
                }

            def graph_for(self, preset):
                raise AssertionError('A non-image preset was inspected by the text-only binder')

        with self.assertRaisesRegex(ValueError, 'explicit source handoff'):
            dispatch(
                '/api/prompt/bind',
                {
                    'compiled': {},
                    'binding': {'preset_id': 'wan22-t2v', 'bindings': {}},
                },
                NoGraph(),
            )


class PromptProfileDocumentationTests(unittest.TestCase):
    def test_architecture_names_the_current_reviewed_profile_count(self):
        text = (ROOT / 'docs/prompt-studio/ARCHITECTURE.md').read_text(encoding='utf-8')
        self.assertIn(
            f'The shipped {len(profiles())} profiles are reviewed projections',
            text,
        )
        self.assertNotIn('The shipped nine profiles are reviewed projections', text)


if __name__ == '__main__':
    unittest.main()
