#!/usr/bin/env python3
"""Tests for scripts/validate.py.

Usage:
    python3 scripts/test_validate.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate

GOOD_DESC = (
    "Do a thing for testing purposes. Use when testing. "
    "Triggers: test thing, do thing."
)


def make_skill(root: Path, name: str, description: str = GOOD_DESC,
               body: str = "", files: dict | None = None) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\n# {name}\n\n{body}\n',
        encoding="utf-8",
    )
    for rel, content in (files or {}).items():
        p = skill_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return skill_dir


def make_plugin(root: Path, claude: dict | None, dot: dict | None) -> Path:
    plugin = root / "plugins" / "test-plugin"
    plugin.mkdir(parents=True)
    for sub, data in ((".claude-plugin", claude), (".plugin", dot)):
        if data is not None:
            d = plugin / sub
            d.mkdir()
            (d / "plugin.json").write_text(json.dumps(data), encoding="utf-8")
    return plugin


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


class TestExistingChecks(TempDirTest):
    def test_good_skill_passes(self):
        skill = make_skill(self.root, "my-skill")
        self.assertEqual(validate.check_skill(skill), [])

    def test_name_directory_mismatch_fails(self):
        skill = make_skill(self.root, "my-skill")
        (skill / "SKILL.md").write_text(
            f'---\nname: other-name\ndescription: "{GOOD_DESC}"\n---\n',
            encoding="utf-8",
        )
        errors = validate.check_skill(skill)
        self.assertTrue(any("directory name" in e for e in errors), errors)


class TestTriggersSuffix(TempDirTest):
    def test_description_ending_with_triggers_passes(self):
        skill = make_skill(self.root, "my-skill")
        self.assertEqual(validate.check_skill(skill), [])

    def test_missing_triggers_fails(self):
        skill = make_skill(self.root, "my-skill",
                           description="Does a thing. Use when testing.")
        errors = validate.check_skill(skill)
        self.assertTrue(any("Triggers:" in e for e in errors), errors)

    def test_triggers_mid_description_fails(self):
        skill = make_skill(
            self.root, "my-skill",
            description="Does a thing. Triggers: foo, bar. Also does other "
                        "stuff described after the trigger list.",
        )
        errors = validate.check_skill(skill)
        self.assertTrue(any("Triggers:" in e for e in errors), errors)

    def test_empty_triggers_list_fails(self):
        skill = make_skill(self.root, "my-skill",
                           description="Does a thing. Triggers:")
        errors = validate.check_skill(skill)
        self.assertTrue(any("Triggers:" in e for e in errors), errors)

    def test_abbreviation_in_triggers_passes(self):
        skill = make_skill(
            self.root, "my-skill",
            description="Does a thing. Use when testing. "
                        "Triggers: install foo, e.g. setup, run bar.",
        )
        self.assertEqual(validate.check_skill(skill), [])

    def test_semicolon_prose_after_triggers_fails(self):
        skill = make_skill(
            self.root, "my-skill",
            description="Does a thing. Triggers: foo, bar; do not use for "
                        "pipeline setup.",
        )
        errors = validate.check_skill(skill)
        self.assertTrue(any("Triggers:" in e for e in errors), errors)

    def test_glued_triggers_token_fails(self):
        skill = make_skill(
            self.root, "my-skill",
            description="Does a thing that sets up FooTriggers: blah blah.",
        )
        errors = validate.check_skill(skill)
        self.assertTrue(any("Triggers:" in e for e in errors), errors)


class TestReservedNames(TempDirTest):
    def test_reserved_skill_name_fails(self):
        skill = make_skill(self.root, "tracking-design")
        errors = validate.check_skill(skill)
        self.assertTrue(any("collides" in e for e in errors), errors)

    def test_all_official_names_reserved(self):
        for name in ("console-operations", "implementation-guidance",
                     "pipeline-infrastructure", "signals", "tracking-design",
                     "troubleshooting"):
            self.assertIn(name, validate.RESERVED_SKILL_NAMES)

    def test_unreserved_name_passes(self):
        skill = make_skill(self.root, "my-skill")
        self.assertEqual(validate.check_skill(skill), [])


class TestDanglingPaths(TempDirTest):
    def test_dangling_script_reference_fails(self):
        skill = make_skill(self.root, "my-skill",
                           body="Run `scripts/missing.py` to analyze.")
        errors = validate.check_skill(skill)
        self.assertTrue(any("missing path" in e for e in errors), errors)

    def test_existing_script_reference_passes(self):
        skill = make_skill(self.root, "my-skill",
                           body="Run `scripts/present.py` to analyze.",
                           files={"scripts/present.py": "print('hi')\n"})
        self.assertEqual(validate.check_skill(skill), [])

    def test_dangling_reference_in_reference_md_fails(self):
        skill = make_skill(self.root, "my-skill",
                           files={"reference/notes.md": "Run scripts/gone.py first.\n"})
        errors = validate.check_skill(skill)
        self.assertTrue(any("missing path" in e and "reference/notes.md" in e
                            for e in errors), errors)

    def test_dangling_directory_reference_fails(self):
        skill = make_skill(self.root, "my-skill",
                           body="See `examples/schema_not_found/` for a sample.")
        errors = validate.check_skill(skill)
        self.assertTrue(any("missing path" in e for e in errors), errors)

    def test_existing_directory_reference_passes(self):
        skill = make_skill(self.root, "my-skill",
                           body="See `examples/sample/` for a sample.",
                           files={"examples/sample/event.json": "{}\n"})
        self.assertEqual(validate.check_skill(skill), [])

    def test_url_path_not_flagged(self):
        skill = make_skill(
            self.root, "my-skill",
            body="See https://docs.snowplow.io/docs/reference/foo for docs.")
        self.assertEqual(validate.check_skill(skill), [])

    def test_prose_slash_without_extension_not_flagged(self):
        skill = make_skill(self.root, "my-skill",
                           body="General troubleshooting/debugging tips follow.")
        self.assertEqual(validate.check_skill(skill), [])

    def test_sentence_final_period_stripped(self):
        skill = make_skill(self.root, "my-skill",
                           body="Then run scripts/present.py.",
                           files={"scripts/present.py": "print('hi')\n"})
        self.assertEqual(validate.check_skill(skill), [])


class TestManifestPairSync(TempDirTest):
    MANIFEST = {"name": "test-plugin", "version": "1.0.0", "description": "A test plugin."}

    def test_pair_in_sync_passes(self):
        plugin = make_plugin(self.root, self.MANIFEST, dict(self.MANIFEST))
        self.assertEqual(validate.check_plugin_manifest_pair(plugin), [])

    def test_pair_out_of_sync_fails(self):
        other = dict(self.MANIFEST, version="2.0.0")
        plugin = make_plugin(self.root, self.MANIFEST, other)
        errors = validate.check_plugin_manifest_pair(plugin)
        self.assertTrue(any("differ" in e for e in errors), errors)

    def test_missing_dot_plugin_manifest_fails(self):
        plugin = make_plugin(self.root, self.MANIFEST, None)
        errors = validate.check_plugin_manifest_pair(plugin)
        self.assertTrue(any(".plugin/plugin.json" in e for e in errors), errors)

    def test_invalid_json_fails(self):
        plugin = make_plugin(self.root, self.MANIFEST, dict(self.MANIFEST))
        (plugin / ".plugin" / "plugin.json").write_text("{not json", encoding="utf-8")
        errors = validate.check_plugin_manifest_pair(plugin)
        self.assertTrue(any("invalid JSON" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
