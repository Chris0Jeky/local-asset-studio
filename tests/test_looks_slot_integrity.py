"""Optional-line replacements must preserve the single scene slot (#1237)."""
import unittest

from test_looks import BODY, OPTIONAL, TEXT, WALL, WorkspaceError, looks


class LookSlotIntegrityTests(unittest.TestCase):
    def test_optional_lines_cannot_materialize_an_extra_scene_slot(self):
        split = "{scene} beside {sce{quiet_wall}ne}"
        # Reject unsafe stored looks even if their default would leave the split slot hidden.
        for default in (False, True):
            with self.subTest(default=default), self.assertRaisesRegex(WorkspaceError, "slot"):
                looks.validate_body(dict(OPTIONAL, template=split, options=[dict(WALL, default=default)]), TEXT)
        # The composition boundary also defends callers holding already-saved look bodies.
        with self.assertRaisesRegex(WorkspaceError, "slot"):
            looks.compose(split, "a hall", [WALL], {"quiet_wall": False})

    def test_optional_lines_cannot_jointly_materialize_an_extra_scene_slot(self):
        other = dict(WALL, id="empty_line", label="Another line")
        split = "{scene} beside {sc{quiet_wall}e{empty_line}ne}"
        with self.assertRaisesRegex(WorkspaceError, "slot"):
            looks.validate_body(dict(OPTIONAL, template=split, options=[WALL, other]), TEXT)
        with self.assertRaisesRegex(WorkspaceError, "slot"):
            looks.compose(split, "a hall", [WALL, other])

    def test_composition_rechecks_slots_after_enabled_line_insertion(self):
        # Even a caller bypassing body validation must not insert the scene twice.
        with self.assertRaisesRegex(WorkspaceError, "slot"):
            looks.compose(OPTIONAL["template"], "a hall", [dict(WALL, text="{scene}", default=True)])

    def test_all_safe_line_choices_keep_scene_words_literal(self):
        options = [WALL, dict(WALL, id="empty_line", label="Another line")]
        template = "{scene}. {quiet_wall} {empty_line}"
        body = looks.validate_body(dict(BODY, template=template, options=options), TEXT)
        for mask in range(4):
            chosen = {option["id"]: bool(mask & (1 << index)) for index, option in enumerate(options)}
            with self.subTest(chosen=chosen):
                result = looks.compose(body["template"], "a {quiet_wall} sign", body["options"], chosen)
                self.assertEqual(result.count("a {quiet_wall} sign"), 1)
                self.assertEqual(result.count(WALL["text"]), mask.bit_count())


if __name__ == "__main__":
    unittest.main()
