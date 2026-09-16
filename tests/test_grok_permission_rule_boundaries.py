import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GrokPermissionRuleBoundaryTests(unittest.TestCase):
    def test_bash_rules_use_exact_or_space_delimited_command_boundaries(self):
        config = tomllib.loads((ROOT / '.grok/config.toml').read_text(encoding='utf-8'))
        rules = config['permission']['rules']
        allow = {
            rule['pattern']
            for rule in rules
            if rule.get('action') == 'allow' and rule.get('tool') == 'bash'
        }
        deny = {
            rule['pattern']
            for rule in rules
            if rule.get('action') == 'deny' and rule.get('tool') == 'bash'
        }

        self.assertEqual(deny, {'git push', 'git push *'})
        for pattern in allow:
            if pattern.endswith('*'):
                self.assertTrue(
                    pattern.endswith(' *'),
                    f'{pattern!r} can also match another executable or subcommand prefix',
                )


if __name__ == '__main__':
    unittest.main()
