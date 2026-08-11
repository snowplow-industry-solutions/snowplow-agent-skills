#!/usr/bin/env python3
"""Validate snowplow-workflows skills and manifests.

Usage:
    python3 scripts/validate.py --all
    python3 scripts/validate.py plugins/snowplow-workflows/skills/<skill-name>

Checks per skill:
  - SKILL.md exists
  - frontmatter parses and contains single-line `name:` and `description:`
  - name is kebab-case and matches the directory name
  - description ends with a `Triggers: ...` list
  - SKILL.md is <= 500 lines
  - no forbidden files (README.md, CHANGELOG.md, .env) inside the skill dir
Repo-level:
  - root marketplace.json files parse, agree with each other, and every
    plugin `source` dir exists and contains .claude-plugin/plugin.json
    whose `name` matches the marketplace entry
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "plugins" / "snowplow-workflows" / "skills"
MAX_LINES = 500
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FORBIDDEN = {"README.md", "CHANGELOG.md", ".env"}


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
    if not isinstance(desc, str) or not desc:
        errors.append(f"{label}: frontmatter missing `description`")
    elif "Triggers:" not in desc:
        errors.append(f"{label}: description lacks a 'Triggers:' list")
    for f in skill_dir.iterdir():
        if f.name in FORBIDDEN:
            errors.append(f"{label}: forbidden file {f.name}")
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
    for rel, cat in catalogs.items():
        for entry in cat.get("plugins", []):
            src = ROOT / entry.get("source", "")
            manifest = src / ".claude-plugin" / "plugin.json"
            if not src.is_dir():
                errors.append(f"{rel}: plugin source {entry.get('source')} does not exist")
            elif not manifest.is_file():
                errors.append(f"{rel}: {entry.get('source')} lacks .claude-plugin/plugin.json")
            else:
                declared = json.loads(manifest.read_text(encoding="utf-8")).get("name")
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
