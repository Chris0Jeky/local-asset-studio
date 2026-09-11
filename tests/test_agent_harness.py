"""Structural gate for the agent harness: tier declaration, doc budgets and Claude/Codex skill parity.

Green means the files are present, well-formed and body-identical across runtimes. It does not prove
that a skill is correct or that an agent follows it.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = ROOT / '.claude/skills'
CODEX_SKILLS = ROOT / '.codex/skills'
SKILL_NAMES = ('studio-preset-slice', 'studio-execution-evidence', 'studio-native-adapter',
               'studio-runtime-models', 'studio-session-closeout')
BUDGETS = {'CLAUDE.md': 100, 'AGENTS.md': 80}  # T2 caps from agent-harness SPECS §3
SKILL_BUDGET = 80


def split_frontmatter(text):
    match = re.match(r'---\n(.*?)\n---\n(.*)\Z', text, re.S)
    if not match: raise AssertionError('missing frontmatter fences at column 0')
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(':')
        if sep and not line.startswith((' ', '\t')): fields[key.strip()] = value.strip()
    return fields, match.group(2)


class TierDeclarationTests(unittest.TestCase):
    def test_tier_json_declares_t2_authority(self):
        tier = json.loads((ROOT / '.agent-harness/tier.json').read_text(encoding='utf-8'))
        self.assertEqual(tier['tier'], 2)
        self.assertEqual(tier['authority'], {'push': 'free', 'merge': 'free'})
        self.assertIs(tier['flags']['sensitive_data'], False)
        self.assertEqual(tier['human_todo'], 'HUMAN_TODO.md')
        self.assertTrue((ROOT / tier['human_todo']).is_file())
        self.assertFalse((ROOT / '.claude/tier.json').exists(), 'legacy tier file must not coexist')
        self.assertFalse((ROOT / '.codex/hooks.json').exists(), 'floor_wiring none: no Codex hook adapter')

    def test_claude_md_tier_line_matches_declaration(self):
        head = (ROOT / 'CLAUDE.md').read_text(encoding='utf-8').splitlines()[:8]
        self.assertTrue(any(line.startswith('Tier: daily-driver (T2) — authority: push free / merge free') for line in head), head)


class BudgetTests(unittest.TestCase):
    def test_root_docs_within_budget(self):
        for name, cap in BUDGETS.items():
            lines = len((ROOT / name).read_text(encoding='utf-8').splitlines())
            self.assertLessEqual(lines, cap, f'{name}: {lines}>{cap} lines; rotate detail into linked docs')

    def test_skills_within_budget(self):
        for tree in (CLAUDE_SKILLS, CODEX_SKILLS):
            for name in SKILL_NAMES:
                lines = len((tree / name / 'SKILL.md').read_text(encoding='utf-8').splitlines())
                self.assertLessEqual(lines, SKILL_BUDGET, f'{tree.name}/{name}: {lines}>{SKILL_BUDGET} lines')


class SkillParityTests(unittest.TestCase):
    def test_every_named_skill_exists_in_both_trees_and_nothing_else(self):
        for tree in (CLAUDE_SKILLS, CODEX_SKILLS):
            found = sorted(p.name for p in tree.iterdir() if p.is_dir())
            self.assertEqual(found, sorted(SKILL_NAMES), tree)

    def test_frontmatter_shape(self):
        for tree in (CLAUDE_SKILLS, CODEX_SKILLS):
            for name in SKILL_NAMES:
                text = (tree / name / 'SKILL.md').read_text(encoding='utf-8')
                self.assertNotIn('\t', text, f'{tree.name}/{name}: tabs are rejected by the Codex loader')
                fields, body = split_frontmatter(text)
                self.assertEqual(fields.get('name'), name, f'{tree.name}/{name}: name must equal the directory')
                self.assertTrue(fields.get('description'), f'{tree.name}/{name}: empty description')
                for heading in ('## Use when / Do NOT use when', '## Guardrails', '## Workflow', '## Read first'):
                    self.assertIn(heading, body, f'{tree.name}/{name}: missing {heading}')

    def test_codex_bodies_and_descriptions_match_claude(self):
        for name in SKILL_NAMES:
            claude_fields, claude_body = split_frontmatter((CLAUDE_SKILLS / name / 'SKILL.md').read_text(encoding='utf-8'))
            codex_fields, codex_body = split_frontmatter((CODEX_SKILLS / name / 'SKILL.md').read_text(encoding='utf-8'))
            self.assertEqual(codex_body, claude_body, f'{name}: Codex body drifted from the canonical Claude skill')
            self.assertEqual(codex_fields['description'], claude_fields['description'], f'{name}: description drifted')

    def test_codex_openai_yaml_shape(self):
        for name in SKILL_NAMES:
            yaml_text = (CODEX_SKILLS / name / 'agents/openai.yaml').read_text(encoding='utf-8')
            self.assertNotIn('\t', yaml_text)
            for key in ('interface:', 'display_name:', 'short_description:', 'default_prompt:'):
                self.assertIn(key, yaml_text, f'{name}: openai.yaml missing {key}')
            self.assertIn(f'${name}', yaml_text, f'{name}: default_prompt must invoke ${name}')

    def test_routing_tables_name_every_skill(self):
        for doc in ('AGENTS.md', 'CLAUDE.md', '.claude/skills/README.md', '.codex/skills/README.md'):
            text = (ROOT / doc).read_text(encoding='utf-8')
            for name in SKILL_NAMES: self.assertIn(name, text, f'{doc} does not route to {name}')


if __name__ == '__main__': unittest.main()
