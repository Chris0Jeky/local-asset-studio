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

    def test_full_editor_uses_plain_heading_and_look_names(self):
        index = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<h1>Full editor — every setting for one recipe</h1>', index)
        self.assertIn('<h1>Full editor — every setting for one recipe</h1>', (STATIC / 'studio-workbench.js').read_text(encoding='utf-8'))
        for name in ('app.js', 'looks.js'):
            text = (STATIC / name).read_text(encoding='utf-8')
            self.assertNotIn('saved look', text.lower())
        self.assertIn('Use a look <small>', (STATIC / 'looks.js').read_text(encoding='utf-8'))

    def test_page_labels_match_the_sidebar(self):
        shell = (STATIC / 'studio-shell.js').read_text(encoding='utf-8')
        for label in ('Library', 'Compare &amp; review' if 'Compare &amp; review' in shell else 'Compare & review'):
            self.assertIn(label, shell)
        index = (STATIC / 'index.html').read_text(encoding='utf-8')
        library = index[index.index('id="assetsView"'):index.index('id="assetScopes"')]
        self.assertIn('<h3>Library</h3>', library)
        runs = index[index.index('id="productionView"'):]
        self.assertRegex(runs[:400], r'class="eyebrow">COMPARE &(amp;)? REVIEW<')
        self.assertIn('<a href="/#production">Compare &amp; review</a>', (STATIC / 'review.html').read_text(encoding='utf-8'))  # the Review desk's empty state links back


if __name__ == '__main__':
    unittest.main()
