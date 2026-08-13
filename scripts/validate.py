#!/usr/bin/env python3
"""Validate snowplow-workflows skills and manifests.

Usage:
    python3 scripts/validate.py --all
    python3 scripts/validate.py plugins/snowplow-workflows/skills/<skill-name>

Checks per skill:
  - SKILL.md exists
  - frontmatter parses and contains single-line `name:` and `description:`
  - name is kebab-case and matches the directory name
  - name does not collide with a skill in the official `snowplow` plugin
  - description ends with a `Triggers: ...` list (list is the final content)
  - SKILL.md is <= 500 lines
  - no forbidden files (README.md, CHANGELOG.md, .env) inside the skill dir
  - intra-skill paths referenced in .md files (scripts/, reference/, ...) exist
Repo-level:
  - root marketplace.json files parse, agree with each other, and every
    plugin `source` dir exists and contains .claude-plugin/plugin.json
    whose `name` matches the marketplace entry
  - each plugin's .claude-plugin/plugin.json and .plugin/plugin.json are
    both present, parse, and are identical
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "plugins" / "snowplow-workflows" / "skills"
MAX_LINES = 500
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FORBIDDEN = {"README.md", "CHANGELOG.md", ".env"}

# 'Triggers:' must start at a word boundary — 'FooTriggers:' is not a
# trigger list.
TRIGGERS_RE = re.compile(r"(?<![A-Za-z0-9])Triggers:")

# Skill names in the official `snowplow` product plugin. A skill here with
# the same name collides when both plugins are installed (the tracking-design
# -> design-tracking-plan rename happened for exactly this reason).
RESERVED_SKILL_NAMES = {
    "console-operations",
    "implementation-guidance",
    "pipeline-infrastructure",
    "signals",
    "tracking-design",
    "troubleshooting",
}

# Path-like references to a skill's own asset directories, e.g.
# `scripts/analyze.py` or `examples/foo/`. The lookbehind keeps this from
# matching inside URLs or longer paths.
SKILL_ASSET_DIRS = ("scripts", "reference", "references", "examples",
                    "assets", "templates", "troubleshooting")
_DIRS = "(?:" + "|".join(SKILL_ASSET_DIRS) + ")"
_REL = r"(?:\.\./|\./)*"
# (a) File refs: final segment has an extension. The trailing (?![\w-])
# guard stops prose like 'scripts/foo.py-based' matching as a path; the
# lookbehind keeps this from firing inside URLs or longer paths.
FILE_REF_RE = re.compile(
    r"(?<![\w/.-])(" + _REL + _DIRS + r"/[A-Za-z0-9_*./-]*\.[A-Za-z0-9]+)(?![\w-])"
)
# (b) Directory refs: trailing '/' with at least one named segment after
# the asset dir — 'scripts/' alone is prose, not a reference.
DIR_REF_RE = re.compile(
    r"(?<![\w/.-])(" + _REL + _DIRS + r"/[A-Za-z0-9_*-][A-Za-z0-9_*/-]*/)(?![\w.-])"
)
# (c) Backtick-wrapped refs where the whole span is the path: explicit
# references, checked even without an extension or trailing slash.
BACKTICK_REF_RE = re.compile(
    r"`(" + _REL + _DIRS + r"/[A-Za-z0-9_*./-]+)`"
)


def parse_frontmatter(text: str):
    """Return (dict, error). Frontmatter = block between the first two '---' lines.
    Values: single-line `key: value` pairs; a `tools:` key collects following `- item` lines."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "SKILL.md does not start with '---' frontmatter"
    fm, i = {}, 1
    current_list_key = None
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            return fm, None
        stripped = line.strip()
        if current_list_key and stripped.startswith("- "):
            fm[current_list_key].append(stripped[2:].strip())
        elif stripped and not stripped.startswith("#"):
            m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", stripped)
            if not m:
                return None, f"unparseable frontmatter line: {stripped!r}"
            key, value = m.group(1), m.group(2).strip().strip('"')
            if value == "":
                fm[key] = []
                current_list_key = key
            else:
                fm[key] = value
                current_list_key = None
        i += 1
    return None, "frontmatter never closed with '---'"


def check_skill(skill_dir: Path):
    errors = []
    label = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return [f"{label}: missing SKILL.md"]
    text = skill_md.read_text(encoding="utf-8")
    n_lines = len(text.splitlines())
    if n_lines > MAX_LINES:
        errors.append(f"{label}: SKILL.md is {n_lines} lines (max {MAX_LINES})")
    fm, err = parse_frontmatter(text)
    if err:
        return errors + [f"{label}: {err}"]
    name = fm.get("name")
    desc = fm.get("description")
    if not isinstance(name, str) or not name:
        errors.append(f"{label}: frontmatter missing `name`")
    else:
        if not NAME_RE.match(name):
            errors.append(f"{label}: name {name!r} is not kebab-case")
        if name != skill_dir.name:
            errors.append(f"{label}: name {name!r} != directory name {skill_dir.name!r}")
        if name in RESERVED_SKILL_NAMES:
            errors.append(
                f"{label}: name {name!r} collides with an official snowplow plugin skill"
            )
    if not isinstance(desc, str) or not desc:
        errors.append(f"{label}: frontmatter missing `description`")
    else:
        matches = list(TRIGGERS_RE.finditer(desc))
        tail = desc[matches[-1].end():].strip().rstrip(".") if matches else ""
        # Heuristic for prose after the trigger list: a semicolon clause, or
        # '. ' starting a new capitalized sentence. Lowercase after '. '
        # (e.g., vs.) is treated as part of the list.
        if not tail or re.search(r";\s*\S|\.\s+[A-Z]", tail):
            errors.append(f"{label}: description must end with a 'Triggers:' list")
    for f in skill_dir.iterdir():
        if f.name in FORBIDDEN:
            errors.append(f"{label}: forbidden file {f.name}")
    errors += check_intra_skill_paths(skill_dir)
    return errors


def check_intra_skill_paths(skill_dir: Path):
    """Flag references in the skill's .md files to asset paths that don't exist.

    Checked: refs whose final segment has an extension, refs with a
    trailing '/' and a named segment, and backtick-wrapped path refs
    (extension or not). Relative refs (./x, ../x) resolve against the
    referencing .md file's directory; bare refs resolve against the skill
    root. Refs containing '*' pass if the glob matches anything. Bare
    prose like "troubleshooting/debugging tips" is ignored.
    """
    errors = []
    seen = set()
    for md in sorted(skill_dir.rglob("*.md")):
        rel_md = md.relative_to(skill_dir)
        text = md.read_text(encoding="utf-8")
        refs = set()
        for regex in (FILE_REF_RE, DIR_REF_RE, BACKTICK_REF_RE):
            refs.update(m.group(1) for m in regex.finditer(text))
        for ref in sorted(refs):
            if (rel_md, ref) in seen:
                continue
            seen.add((rel_md, ref))
            base = md.parent if ref.startswith(("./", "../")) else skill_dir
            target = os.path.normpath(base / ref)
            missing = (not glob.glob(target)) if "*" in ref \
                else (not Path(target).exists())
            if missing:
                errors.append(
                    f"{skill_dir.name}: {rel_md} references missing path {ref!r}"
                )
    return errors


def check_plugin_manifest_pair(plugin_dir: Path):
    """The plugin manifest is duplicated for two loaders; both copies must
    exist, parse, and be identical."""
    errors = []
    manifests = {}
    for sub in (".claude-plugin", ".plugin"):
        p = plugin_dir / sub / "plugin.json"
        rel = f"{sub}/plugin.json"
        if not p.is_file():
            errors.append(f"{plugin_dir.name}: missing {rel}")
            continue
        try:
            manifests[rel] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{plugin_dir.name}: {rel} invalid JSON ({e})")
    if len(manifests) == 2 and manifests[".claude-plugin/plugin.json"] != manifests[".plugin/plugin.json"]:
        errors.append(
            f"{plugin_dir.name}: .claude-plugin/plugin.json and .plugin/plugin.json differ — keep in sync"
        )
    return errors


def check_marketplaces():
    errors = []
    catalogs = {}
    for rel in (".claude-plugin/marketplace.json", ".plugin/marketplace.json"):
        p = ROOT / rel
        if not p.is_file():
            errors.append(f"{rel}: missing")
            continue
        try:
            catalogs[rel] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: invalid JSON ({e})")
    if len(catalogs) == 2:
        vals = list(catalogs.values())
        if vals[0] != vals[1]:
            errors.append(".claude-plugin/ and .plugin/ marketplace.json differ — keep in sync")
    seen_sources = set()
    for rel, cat in catalogs.items():
        for entry in cat.get("plugins", []):
            src = ROOT / entry.get("source", "")
            manifest = src / ".claude-plugin" / "plugin.json"
            if not src.is_dir():
                errors.append(f"{rel}: plugin source {entry.get('source')} does not exist")
                continue
            if src not in seen_sources:
                seen_sources.add(src)
                errors += check_plugin_manifest_pair(src)
            if manifest.is_file():
                try:
                    declared = json.loads(manifest.read_text(encoding="utf-8")).get("name")
                except json.JSONDecodeError:
                    continue  # already reported by check_plugin_manifest_pair
                if declared != entry.get("name"):
                    errors.append(
                        f"{rel}: entry name {entry.get('name')!r} != plugin.json name {declared!r}"
                    )
    return errors


def main():
    args = sys.argv[1:]
    errors = []
    if args == ["--all"]:
        errors += check_marketplaces()
        for d in sorted(SKILLS_DIR.iterdir()):
            if d.is_dir():
                errors += check_skill(d)
    elif len(args) == 1:
        errors += check_skill(Path(args[0]).resolve())
    else:
        print(__doc__)
        return 2
    for e in errors:
        print(e)
    print(f"{'FAIL' if errors else 'OK'} — {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
