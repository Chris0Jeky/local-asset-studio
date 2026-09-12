"""JSON types matter even when Python's numeric equality considers them equal."""
import copy
from pathlib import Path
import unittest
from scripts import character_study as c

DATA = Path(__file__).resolve().parents[1] / 'research/character-consistency'


class IntegrityTests(unittest.TestCase):
    def test_rehashed_or_equal_numeric_aliases_do_not_bypass_plan_identity(self):
        plan = c.make_plan(c.read_json(DATA / 'canon.example.json'), c.read_json(DATA / 'pilot.study.json'))
        for key, value in (('schema_version', True), ('schema_version', 1.0), ('submits_generation', 0)):
            changed = copy.deepcopy(plan); changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): c.check_plan(changed)


if __name__ == '__main__': unittest.main()
