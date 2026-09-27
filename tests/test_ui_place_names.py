"""One visible name per place (design handoff 02: Library had four names, Runs three).

The sidebar names are the reference until the owner answers handoff Q1 (Library / Runs renames);
routes, ids and API names are untouched."""
from pathlib import Path
import re
import unittest

STATIC = Path(__file__).resolve().parents[1] / 'app' / 'static'
RETIRED = ('Your experiments', 'EXPERIMENTS & FINISHING', 'Experiments view', 'from Experiments')


class PlaceNames(unittest.TestCase):
    def test_retired_place_names_are_not_shown(self):
        for name in ('index.html', 'production.js', 'review.js', 'workshop.js', 'studio-shell.js'):
            text = (STATIC / name).read_text(encoding='utf-8')
            for retired in RETIRED:
                self.assertNotIn(retired, text, f'{name} still shows "{retired}"')

    def test_page_labels_match_the_sidebar(self):
        shell = (STATIC / 'studio-shell.js').read_text(encoding='utf-8')
        for label in ('Asset library', 'Runs &amp; review' if 'Runs &amp; review' in shell else 'Runs & review'):
            self.assertIn(label, shell)
        index = (STATIC / 'index.html').read_text(encoding='utf-8')
        library = index[index.index('id="assetsView"'):index.index('id="assetScopes"')]
        self.assertIn('<h3>Asset library</h3>', library)
        runs = index[index.index('id="productionView"'):]
        self.assertRegex(runs[:400], r'class="eyebrow">RUNS &(amp;)? REVIEW<')
        self.assertIn('Runs & review', (STATIC / 'review.js').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
