"""Current CreativeIntent normalization at the reference-review boundary."""
import copy
import unittest

from studio_prompt.reference_review import _current
from studio_prompt.schema import new_brief, validate


class ReferenceReviewCurrentTests(unittest.TestCase):
    def test_adopted_empty_brief_returns_the_normalized_valid_copy(self):
        source = new_brief('Temporary editor text')
        source['brief'] = '   '
        before = copy.deepcopy(source)

        current = _current(source, True)

        self.assertEqual(current['brief'], 'Pending reviewed instruction')
        self.assertEqual(source, before, 'normalization must not mutate the caller draft')
        self.assertIsNot(current, source)
        self.assertIs(validate(current), current)

    def test_nonempty_brief_is_preserved_in_an_independent_copy(self):
        source = new_brief('Keep this instruction')
        current = _current(source, False)

        self.assertEqual(current, source)
        self.assertIsNot(current, source)
        self.assertIsNot(current['facets'], source['facets'])

    def test_empty_brief_without_explicit_adoption_is_rejected(self):
        source = new_brief('Temporary editor text')
        source['brief'] = ''

        with self.assertRaises(ValueError):
            _current(source, False)


if __name__ == '__main__':
    unittest.main()
