"""Dangerous Git commands stay denied even when appended to an allowed shell prefix."""
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GrokPermissionDenyTests(unittest.TestCase):
    def test_git_push_has_an_explicit_catch_all_deny(self):
        config = tomllib.loads((ROOT / '.grok/config.toml').read_text(encoding='utf-8'))
        rules = config['permission']['rules']
        denies = {
            rule.get('pattern')
            for rule in rules
            if rule.get('action') == 'deny' and rule.get('tool') == 'bash'
        }
        self.assertIn('*git push*', denies)


if __name__ == '__main__':
    unittest.main()
