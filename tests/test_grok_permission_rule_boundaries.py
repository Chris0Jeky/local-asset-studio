import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GrokPermissionRuleBoundaryTests(unittest.TestCase):
    def test_bash_rules_avoid_unseparated_wildcard_expansion(self):
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

        self.assertEqual(deny, {'git push'})
        for pattern in allow | deny:
            self.assertLessEqual(pattern.count('*'), 1, pattern)
            if '*' in pattern:
                self.assertTrue(
                    pattern.endswith(' *'),
                    f'{pattern!r} widens a command token rather than its arguments',
                )


if __name__ == '__main__':
    unittest.main()
