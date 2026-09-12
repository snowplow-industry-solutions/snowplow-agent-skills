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


def make_marketplace(root: Path, plugins: list, plugin_dirs: dict | None = None):
    """Write both marketplace.json copies + optional plugin dirs.

    plugins: the entry list for both catalogs.
    plugin_dirs: {source_rel: manifest_dict_or_raw_str} — creates
    <source_rel>/.claude-plugin/plugin.json and .plugin/plugin.json.
    """
    cat = {"name": "test-marketplace", "plugins": plugins}
    for sub in (".claude-plugin", ".plugin"):
        d = root / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / "marketplace.json").write_text(json.dumps(cat), encoding="utf-8")
    for src_rel, manifest in (plugin_dirs or {}).items():
        for sub in (".claude-plugin", ".plugin"):
            d = root / src_rel / sub
            d.mkdir(parents=True, exist_ok=True)
            body = manifest if isinstance(manifest, str) else json.dumps(manifest)
            (d / "plugin.json").write_text(body, encoding="utf-8")


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
        # foo.html HAS an extension — only the URL-context guard keeps this
        # from being flagged, so this test fails if that guard is removed.
        skill = make_skill(
            self.root, "my-skill",
            body="See https://docs.snowplow.io/docs/reference/foo.html for docs.")
        self.assertEqual(validate.check_skill(skill), [])

    def test_url_query_value_not_flagged(self):
        # '=' before the ref marks a URL query value, not an intra-skill path.
        skill = make_skill(
            self.root, "my-skill",
            body="See https://x.io/d?f=reference/a.md for the doc.")
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

    def test_relative_reference_resolved_from_md_dir_fails(self):
        skill = make_skill(
            self.root, "my-skill",
            files={"examples/demo/README.md":
                   "Run `python ../../scripts/setup.py` first.\n"})
        errors = validate.check_skill(skill)
        self.assertTrue(any("missing path" in e and "../../scripts/setup.py" in e
                            for e in errors), errors)

    def test_relative_reference_resolved_from_md_dir_passes(self):
        skill = make_skill(
            self.root, "my-skill",
            files={"examples/demo/README.md":
                   "Run `python ../../scripts/setup.py` first.\n",
                   "scripts/setup.py": "print('hi')\n"})
        self.assertEqual(validate.check_skill(skill), [])

    def test_backtick_extensionless_reference_fails(self):
        skill = make_skill(self.root, "my-skill",
                           body="See `examples/schema_not_found` for a sample.")
        errors = validate.check_skill(skill)
        self.assertTrue(any("missing path" in e for e in errors), errors)

    def test_backtick_extensionless_reference_passes(self):
        skill = make_skill(self.root, "my-skill",
                           body="See `examples/sample` for a sample.",
                           files={"examples/sample/event.json": "{}\n"})
        self.assertEqual(validate.check_skill(skill), [])

    def test_hyphen_suffixed_prose_not_flagged(self):
        # 'scripts/foo.py-based' is prose about a file, not a path ref.
        skill = make_skill(self.root, "my-skill",
                           body="Use the scripts/foo.py-based workflow.")
        self.assertEqual(validate.check_skill(skill), [])

    def test_sentence_final_bare_dir_not_flagged(self):
        skill = make_skill(self.root, "my-skill",
                           body="Put shared helpers in scripts/.")
        self.assertEqual(validate.check_skill(skill), [])

    def test_glob_reference_passes_when_matches(self):
        skill = make_skill(self.root, "my-skill",
                           body="Run the `scripts/*.py` helpers.",
                           files={"scripts/a.py": "print('hi')\n"})
        self.assertEqual(validate.check_skill(skill), [])

    def test_glob_reference_fails_when_no_match(self):
        skill = make_skill(self.root, "my-skill",
                           body="Run the `scripts/*.py` helpers.")
        errors = validate.check_skill(skill)
        self.assertTrue(any("missing path" in e for e in errors), errors)


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

    def test_non_dict_manifest_fails(self):
        plugin = make_plugin(self.root, self.MANIFEST, dict(self.MANIFEST))
        (plugin / ".plugin" / "plugin.json").write_text('["a"]', encoding="utf-8")
        errors = validate.check_plugin_manifest_pair(plugin)
        self.assertTrue(any("JSON object" in e for e in errors), errors)

    def test_bool_int_drift_detected(self):
        a = dict(self.MANIFEST, flag=True)
        b = dict(self.MANIFEST, flag=1)
        plugin = make_plugin(self.root, a, b)
        errors = validate.check_plugin_manifest_pair(plugin)
        self.assertTrue(any("differ" in e for e in errors), errors)


class TestCheckAll(TempDirTest):
    def _registered_plugin(self):
        make_marketplace(
            self.root,
            [{"name": "p1", "source": "plugins/p1"}],
            {"plugins/p1": {"name": "p1", "version": "1.0.0"}})

    def test_unregistered_plugin_pair_checked(self):
        self._registered_plugin()
        extra = self.root / "plugins" / "extra"
        (extra / ".claude-plugin").mkdir(parents=True)
        (extra / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "extra", "version": "2.0.0"}), encoding="utf-8")
        (extra / ".plugin").mkdir()
        (extra / ".plugin" / "plugin.json").write_text(
            json.dumps({"name": "extra", "version": "1.0.0"}), encoding="utf-8")
        errors = validate.check_all(self.root)
        self.assertTrue(any("extra" in e and "differ" in e for e in errors), errors)

    def test_second_plugin_skills_validated(self):
        self._registered_plugin()
        skills = self.root / "plugins" / "p1" / "skills"
        make_skill(skills, "broken-skill",
                   description="No trigger list here at all.")
        errors = validate.check_all(self.root)
        self.assertTrue(any("broken-skill" in e and "Triggers:" in e
                            for e in errors), errors)

    def test_clean_tree_passes(self):
        self._registered_plugin()
        skills = self.root / "plugins" / "p1" / "skills"
        make_skill(skills, "good-skill")
        self.assertEqual(validate.check_all(self.root), [])


class TestReadmeSkillGraph(TempDirTest):
    HEADING = validate.README_SECTION_HEADING

    def _tree(self, skill_names: list, readme: str | None):
        make_marketplace(
            self.root,
            [{"name": "p1", "source": "plugins/p1"}],
            {"plugins/p1": {"name": "p1", "version": "1.0.0"}})
        for name in skill_names:
            make_skill(self.root / "plugins" / "p1" / "skills", name)
        if readme is not None:
            (self.root / "README.md").write_text(readme, encoding="utf-8")

    def test_no_readme_skips(self):
        self._tree(["good-skill"], None)
        self.assertEqual(validate.check_readme_skill_graph(self.root), [])

    def test_all_skills_mentioned_passes(self):
        self._tree(["good-skill", "other-skill"],
                   f"# T\n\n{self.HEADING}\n\ngood-skill then `other-skill`.\n\n## Next\n")
        self.assertEqual(validate.check_readme_skill_graph(self.root), [])

    def test_missing_skill_fails(self):
        self._tree(["good-skill", "other-skill"],
                   f"# T\n\n{self.HEADING}\n\nOnly `good-skill` here.\n")
        errors = validate.check_readme_skill_graph(self.root)
        self.assertTrue(any("other-skill" in e and "missing" in e
                            for e in errors), errors)

    def test_missing_section_fails(self):
        self._tree(["good-skill"], "# T\n\n## Something else\n\ngood-skill\n")
        errors = validate.check_readme_skill_graph(self.root)
        self.assertTrue(any("missing required section" in e for e in errors), errors)

    def test_mention_outside_section_does_not_count(self):
        self._tree(["good-skill"],
                   f"# T\n\ngood-skill up front.\n\n{self.HEADING}\n\nNothing.\n")
        errors = validate.check_readme_skill_graph(self.root)
        self.assertTrue(any("good-skill" in e and "missing" in e
                            for e in errors), errors)

    def test_longer_token_containing_name_does_not_count(self):
        self._tree(["good-skill"],
                   f"# T\n\n{self.HEADING}\n\nSee good-skill-extras.\n")
        errors = validate.check_readme_skill_graph(self.root)
        self.assertTrue(any("good-skill" in e and "missing" in e
                            for e in errors), errors)

    def test_dangling_backtick_token_fails(self):
        self._tree(["good-skill"],
                   f"# T\n\n{self.HEADING}\n\n`good-skill` and `gone-skill`.\n")
        errors = validate.check_readme_skill_graph(self.root)
        self.assertTrue(any("gone-skill" in e and "not a" in e
                            for e in errors), errors)

    def test_allowlisted_token_passes(self):
        self._tree(["good-skill"],
                   f"# T\n\n{self.HEADING}\n\n`good-skill` via `snowplow-cli`.\n")
        self.assertEqual(validate.check_readme_skill_graph(self.root), [])

    def test_check_all_includes_readme_errors(self):
        self._tree(["good-skill"], f"# T\n\n{self.HEADING}\n\nNothing here.\n")
        errors = validate.check_all(self.root)
        self.assertTrue(any("good-skill" in e and "missing" in e
                            for e in errors), errors)


class TestMarketplaces(TempDirTest):
    def test_valid_marketplace_passes(self):
        make_marketplace(
            self.root,
            [{"name": "p1", "source": "plugins/p1"}],
            {"plugins/p1": {"name": "p1", "version": "1.0.0"}})
        self.assertEqual(validate.check_marketplaces(self.root), [])

    def test_entry_missing_source_reported_by_name(self):
        make_marketplace(self.root, [{"name": "p1"}])
        errors = validate.check_marketplaces(self.root)
        self.assertTrue(any("p1" in e and "source" in e for e in errors), errors)

    def test_source_dir_absent_fails(self):
        make_marketplace(self.root, [{"name": "p1", "source": "plugins/gone"}])
        errors = validate.check_marketplaces(self.root)
        self.assertTrue(any("does not exist" in e for e in errors), errors)

    def test_entry_name_mismatch_fails(self):
        make_marketplace(
            self.root,
            [{"name": "wrong", "source": "plugins/p1"}],
            {"plugins/p1": {"name": "p1", "version": "1.0.0"}})
        errors = validate.check_marketplaces(self.root)
        self.assertTrue(any("wrong" in e and "p1" in e for e in errors), errors)

    def test_non_dict_manifest_does_not_crash(self):
        # The error itself is reported by the manifest pair check (see
        # TestManifestPairSync.test_non_dict_manifest_fails); here we pin
        # that the name check no longer dies with AttributeError.
        make_marketplace(
            self.root,
            [{"name": "p1", "source": "plugins/p1"}],
            {"plugins/p1": '["not", "a", "dict"]'})
        errors = validate.check_marketplaces(self.root)  # must not raise
        self.assertIsInstance(errors, list)

    def test_non_dict_catalog_reported_and_no_crash(self):
        # make_marketplace always writes a dict catalog, so write the
        # non-dict catalog file directly.
        d = self.root / ".claude-plugin"
        d.mkdir(parents=True)
        (d / "marketplace.json").write_text(
            json.dumps(["not", "a", "dict"]), encoding="utf-8")
        errors = validate.check_marketplaces(self.root)  # must not raise
        self.assertTrue(any("JSON object" in e for e in errors), errors)

    def test_non_dict_plugin_entry_reported_and_no_crash(self):
        make_marketplace(self.root, ["just-a-string"])
        errors = validate.check_marketplaces(self.root)  # must not raise
        self.assertTrue(any("is not an object" in e for e in errors), errors)


class TestCrossSkillPaths(TempDirTest):
    """Cross-skill refs (../<skill>/<asset-dir>/...) must be resolved and
    existence-checked — the mechanism debug-data-quality uses to consume
    query-snowplow-data's reference files."""

    def test_cross_skill_ref_to_existing_file_passes(self):
        make_skill(self.root, "provider-skill",
                   files={"reference/patterns.md": "# patterns\n"})
        consumer = make_skill(
            self.root, "consumer-skill",
            body="Read `../provider-skill/reference/patterns.md` first.")
        self.assertEqual(validate.check_skill(consumer), [])

    def test_cross_skill_ref_to_missing_file_fails(self):
        make_skill(self.root, "provider-skill",
                   files={"reference/patterns.md": "# patterns\n"})
        consumer = make_skill(
            self.root, "consumer-skill",
            body="Read `../provider-skill/reference/gone.md` first.")
        errors = validate.check_skill(consumer)
        self.assertTrue(any("missing path" in e for e in errors), errors)

    def test_cross_skill_ref_to_missing_skill_fails(self):
        consumer = make_skill(
            self.root, "consumer-skill",
            body="Read `../no-such-skill/reference/patterns.md` first.")
        errors = validate.check_skill(consumer)
        self.assertTrue(any("missing path" in e for e in errors), errors)

    def test_unbackticked_cross_skill_file_ref_checked(self):
        consumer = make_skill(
            self.root, "consumer-skill",
            body="See ../provider-skill/reference/patterns.md for details.")
        errors = validate.check_skill(consumer)
        self.assertTrue(any("missing path" in e for e in errors), errors)

    def test_deep_relative_prefix_resolves_from_nested_md(self):
        make_skill(self.root, "provider-skill",
                   files={"reference/patterns.md": "# patterns\n"})
        consumer = make_skill(
            self.root, "consumer-skill",
            files={"reference/notes.md":
                   "See `../../provider-skill/reference/patterns.md`.\n"})
        self.assertEqual(validate.check_skill(consumer), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
