"""Security regression for project-scoped Grok Bash auto-approval rules."""
from __future__ import annotations

import fnmatch
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _matches_grok_bash(pattern: str, command: str) -> bool:
    """Model Grok's documented Bash prefix/glob matching semantics."""

    command = command.lstrip()
    if any(marker in pattern for marker in ("*", "?", "[")):
        return fnmatch.fnmatchcase(command, pattern)
    return command.startswith(pattern)


class GrokSensitivePermissionTests(unittest.TestCase):
    def test_allow_rules_do_not_auto_approve_authentication_token_output(self):
        config = tomllib.loads(
            (ROOT / ".grok/config.toml").read_text(encoding="utf-8")
        )
        allow_patterns = {
            rule["pattern"]
            for rule in config["permission"]["rules"]
            if rule.get("action") == "allow" and rule.get("tool") == "bash"
        }
        sensitive_commands = (
            "gh auth status --show-token",
            "gh auth status -t",
            "gh auth status --json hosts --show-token",
        )
        for command in sensitive_commands:
            with self.subTest(command=command):
                matched = sorted(
                    pattern
                    for pattern in allow_patterns
                    if _matches_grok_bash(pattern, command)
                )
                self.assertEqual(
                    matched,
                    [],
                    f"{command!r} would expose authentication material under {matched!r}",
                )


if __name__ == "__main__":
    unittest.main()
