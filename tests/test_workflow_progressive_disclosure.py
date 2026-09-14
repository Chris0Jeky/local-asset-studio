"""Static contracts for Workflow Studio's default reading load."""
from html.parser import HTMLParser
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'app' / 'static' / 'workflow-studio.html'
STYLE = ROOT / 'app' / 'static' / 'workflow-progressive-disclosure.css'


class Structure(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.nodes = {}
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        identifier = values.get('id')
        ancestors = [item[1] for item in self.stack if item[1]]
        if identifier:
            self.nodes[identifier] = {'tag': tag, 'attrs': values, 'ancestors': ancestors}
        self.stack.append((tag, identifier))

    def handle_startendtag(self, tag, attrs):
        values = dict(attrs)
        identifier = values.get('id')
        ancestors = [item[1] for item in self.stack if item[1]]
        if identifier:
            self.nodes[identifier] = {'tag': tag, 'attrs': values, 'ancestors': ancestors}

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


class WorkflowProgressiveDisclosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PAGE.read_text(encoding='utf-8')
        cls.style = STYLE.read_text(encoding='utf-8')
        cls.structure = Structure(cls.source)

    def node(self, identifier):
        self.assertIn(identifier, self.structure.nodes, f'Missing #{identifier}')
        return self.structure.nodes[identifier]

    def assert_closed_details(self, identifier):
        node = self.node(identifier)
        self.assertEqual(node['tag'], 'details')
        self.assertNotIn('open', node['attrs'], f'#{identifier} must be collapsed by default')

    def test_builder_scope_and_canvas_instructions_are_optional(self):
        self.assert_closed_details('builderScopeHelp')
        self.assertIn('builderScopeHelp', self.node('builderScopeCopy')['ancestors'])
        self.assert_closed_details('canvasHelp')
        self.assertIn('canvasHelp', self.node('canvasHint')['ancestors'])

    def test_agent_manual_is_collapsed_but_the_tab_opens_it(self):
        self.assert_closed_details('agentGuide')
        self.assertIn('agents', self.node('agentGuide')['ancestors'])
        self.assertIn('agentGuide', self.node('agentGuideBody')['ancestors'])
        self.assertEqual(self.node('agentTitle')['tag'], 'summary')
        self.assertIn("a[href=\"#agents\"]", self.source)
        self.assertIn("agentGuide.open = true", self.source)
        self.assertIn("location.hash === '#agents'", self.source)

    def test_default_builder_copy_keeps_one_actionable_sentence(self):
        self.assertIn('Use Steps for focused controls or Nodes for the full supported graph.', self.source)
        self.assertIn('What can this builder run?', self.source)
        self.assertIn('Move, zoom and connect', self.source)

    def test_closed_help_is_removed_from_layout_for_measurement_and_accessibility(self):
        self.assertIn('.wf-context-help:not([open])>:not(summary)', self.style)
        self.assertIn('.wf-agents:not([open])>:not(summary)', self.style)
        self.assertIn('display:none!important', self.style)


if __name__ == '__main__':
    unittest.main()
