# Snowplow Workflows Restructure + Wave 1 Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the `snowplow-agent-skills` repo into the `snowplow-workflows` plugin (co-installable with the official `snowplow` product plugin) and ship wave 1 of the skills map: two new skills, one rename+rewrite, and rescoped descriptions across all existing skills.

**Architecture:** Single plugin at `plugins/snowplow-workflows/` with a flat `skills/` dir. Layout parity with the product repo at `../snowplow-product-skills`: `.claude-plugin/` (Claude Code native) + `.plugin/` (open-plugin) manifests at both root and plugin level. A stdlib-only Python validator enforces skill conventions in CI. Skill content follows the five-forms guide in `skill_design_guidelines/`.

**Tech Stack:** Markdown skills (SKILL.md + references/templates/scripts), Python 3.12 stdlib validator, GitHub Actions.

## Global Constraints

- Plugin name: `snowplow-workflows` (NEVER `snowplow` — collides with the official product plugin).
- No `.mcp.json` anywhere in this repo — Console access comes from the co-installed official plugin; skills degrade to `snowplow-cli` where sensible.
- No skill may share a name with a product-plugin skill: `tracking-design`, `implementation-guidance`, `signals`, `pipeline-infrastructure`, `console-operations`, `troubleshooting` are all reserved.
- Every skill description ends with a `Triggers: ...` list.
- Every skill that overlaps product-plugin territory carries one boundary sentence pointing at the product skill.
- Skills that call MCP tools list them under `tools:` in frontmatter (same convention as product repo).
- SKILL.md files ≤ 500 lines; skill names kebab-case, verb-first, matching directory name.
- New/rewritten skill bodies are authored by invoking `mattpocock-skills:writing-for-agents`, structured per `skill_design_guidelines/skill_design_guide.md` (five forms) and `skill_design_guidelines/SKILL_TEMPLATE.md`.
- Commits: conventional-commit style, one per task. NEVER add `Co-Authored-By: Claude` or any AI attribution (user's standing rule — overrides any harness default).
- Work happens on branch `snowplow-workflows-restructure`; final deliverable is a PR to `main`.
- Do not add a LICENSE file or `license` manifest field — flag the licensing question in the PR description instead (user decision pending).

## File Structure (end state)

```
├── .claude-plugin/marketplace.json        # NEW — Claude Code native catalog
├── .plugin/marketplace.json               # NEW — open-plugin catalog
├── .github/workflows/validate.yml         # NEW — CI
├── .gitignore                             # NEW
├── README.md                              # REWRITTEN
├── ROADMAP.md                             # NEW — PDF box → skill/wave mapping
├── docs/snowplow-skills-map.pdf           # MOVED from repo root
├── scripts/validate.py                    # NEW
├── skill_design_guidelines/               # unchanged
└── plugins/snowplow-workflows/            # RENAMED from plugins/snowplow/
    ├── .claude-plugin/plugin.json         # rewritten
    ├── .plugin/plugin.json                # NEW (open-plugin manifest)
    │                                      # (.mcp.json and .cursor-plugin/ DELETED)
    └── skills/
        ├── create-data-spec/              # NEW  (SKILL.md, templates/, reference/)
        ├── setup-snowplow-context/        # NEW  (SKILL.md, templates/)
        ├── design-tracking-plan/          # RENAMED from tracking-design/, rewritten
        │                                  #   (SKILL.md, reference/property_instructions.md,
        │                                  #    reference/git_backed_workflow.md)
        ├── debug-failed-events/           # description rescoped
        ├── fetch-snowplow-docs/           # description updated
        ├── implement-custom-events/       # refs renamed, description updated
        ├── install-snowplow-tracking/     # description updated
        ├── setup-micro/                   # description updated
        └── validate-snowplow-implementation/  # description updated
```

---

### Task 1: Branch + repo restructure (rename plugin, manifests, cleanup)

**Files:**
- Rename: `plugins/snowplow/` → `plugins/snowplow-workflows/`
- Delete: `plugins/snowplow-workflows/.mcp.json`, `plugins/snowplow-workflows/.cursor-plugin/`
- Modify: `plugins/snowplow-workflows/.claude-plugin/plugin.json`
- Create: `plugins/snowplow-workflows/.plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.plugin/marketplace.json`, `.gitignore`
- Move: `snowplow-skills-map.pdf` → `docs/snowplow-skills-map.pdf`

**Interfaces:**
- Produces: plugin dir path `plugins/snowplow-workflows/` and plugin name `snowplow-workflows` — every later task and the validator depend on these exact values.

- [ ] **Step 1: Create branch**

```bash
git checkout -b snowplow-workflows-restructure
```

- [ ] **Step 2: Rename plugin dir, delete MCP config and cursor manifest, move PDF**

```bash
git mv plugins/snowplow plugins/snowplow-workflows
git rm plugins/snowplow-workflows/.mcp.json
git rm -r plugins/snowplow-workflows/.cursor-plugin
mkdir -p docs
git add docs
mv snowplow-skills-map.pdf docs/snowplow-skills-map.pdf
git add docs/snowplow-skills-map.pdf
```

(`.cursor-plugin/` is superseded by the open-plugin `.plugin/` format — the `plugins` CLI generates target-specific manifests at install time, matching the product repo's layout.)

- [ ] **Step 3: Write plugin manifests**

Overwrite `plugins/snowplow-workflows/.claude-plugin/plugin.json` with exactly:

```json
{
  "name": "snowplow-workflows",
  "displayName": "Snowplow Workflows",
  "description": "Deep, opinionated Snowplow field workflows — design tracking plans, create data specs, instrument and validate tracking locally with Micro, and run end-to-end custom event implementation. Install the official snowplow plugin alongside for Console access via MCP.",
  "version": "0.1.0",
  "author": {
    "name": "Snowplow",
    "email": "support@snowplow.io",
    "url": "https://snowplow.io"
  },
  "keywords": ["snowplow", "analytics", "tracking", "workflows", "micro", "snowtype"]
}
```

Create `plugins/snowplow-workflows/.plugin/plugin.json` with identical content (the two formats share fields today; keep them byte-identical and note "keep in sync by hand" in README Task 9).

- [ ] **Step 4: Write root marketplace catalogs**

Create `.claude-plugin/marketplace.json` AND `.plugin/marketplace.json`, both with exactly:

```json
{
  "name": "snowplow-workflows",
  "owner": {
    "name": "Snowplow",
    "url": "https://snowplow.io"
  },
  "description": "Snowplow-blessed field workflow skills for AI coding agents",
  "plugins": [
    {
      "name": "snowplow-workflows",
      "source": "./plugins/snowplow-workflows",
      "description": "Deep multi-step Snowplow workflows — tracking design, data specs, local testing with Micro, and end-to-end event implementation. Complements the official snowplow plugin (MCP + Console skills)."
    }
  ]
}
```

- [ ] **Step 5: Write .gitignore**

Create `.gitignore`:

```gitignore
.DS_Store
# Local agent-harness install artifacts (created by `npx skills add` runs)
.agents/
.augment/
.crush/
.kiro/
.qwen/
skills-lock.json
```

- [ ] **Step 6: Verify**

```bash
python3 -c "import json; [json.load(open(p)) for p in ['.claude-plugin/marketplace.json', '.plugin/marketplace.json', 'plugins/snowplow-workflows/.claude-plugin/plugin.json', 'plugins/snowplow-workflows/.plugin/plugin.json']]; print('JSON OK')"
test ! -e plugins/snowplow-workflows/.mcp.json && test ! -d plugins/snowplow-workflows/.cursor-plugin && test ! -d plugins/snowplow && echo "CLEANUP OK"
ls plugins/snowplow-workflows/skills   # expect the 7 existing skill dirs
git status --short                     # expect no untracked harness dirs listed (gitignore working)
```

Expected: `JSON OK`, `CLEANUP OK`, 7 skill dirs, clean status apart from staged changes.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: restructure as snowplow-workflows plugin with open-plugin layout parity"
```

---

### Task 2: Validator + CI

**Files:**
- Create: `scripts/validate.py`, `.github/workflows/validate.yml`

**Interfaces:**
- Produces: CLI `python3 scripts/validate.py --all` (exit 0 = pass, exit 1 = violations printed one per line as `<skill-or-file>: <problem>`). Also accepts a single skill dir path arg. Tasks 3–9 use `--all` as their test gate; Task 10 requires it green.

- [ ] **Step 1: Write the validator**

Create `scripts/validate.py`:

```python
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
```

- [ ] **Step 2: Run it — expect the KNOWN current violations (this is the failing-test phase)**

Run: `python3 scripts/validate.py --all`
Expected: exit 1, with exactly these classes of errors and no others:
- every one of the 7 skills flagged `description lacks a 'Triggers:' list`
- NO name/kebab-case errors, NO marketplace errors, NO line-cap errors

If other errors appear, the validator or Task 1 output is wrong — fix before continuing. Tasks 3–8 turn these red items green.

- [ ] **Step 3: Sanity-check the single-skill mode**

Run: `python3 scripts/validate.py plugins/snowplow-workflows/skills/setup-micro`
Expected: exit 1, only the Triggers error for setup-micro.

- [ ] **Step 4: Write the CI workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: validate
on:
  pull_request:
  push:
    branches: [main]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python3 scripts/validate.py --all
```

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.py .github/workflows/validate.yml
git commit -m "feat: add skill validator and CI workflow"
```

---

### Task 3: Rescope `debug-failed-events` to local-first + product boundary

**Files:**
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/SKILL.md` (frontmatter description only + one body paragraph)

**Interfaces:**
- Consumes: validator CLI from Task 2.
- Produces: nothing downstream.

- [ ] **Step 1: Replace the frontmatter `description` with exactly:**

```yaml
description: "Debug Snowplow events failing validation during local development — bad-row error messages, Snowplow Micro's /bad endpoint, schema resolution, schema validation, enrichment, and malformed-event errors — with categorized root causes and actionable fixes. For production pipeline-wide diagnosis (missing events, enrichment latency, loader health) use the official snowplow plugin's troubleshooting skill. Triggers: failed events, bad rows, validation error, Micro bad endpoint, schema resolution error, event failing validation."
```

- [ ] **Step 2: Add a boundary note to the body**

Immediately after the H1 heading line in SKILL.md, insert this paragraph:

```markdown
This skill is local-first: it assumes the failure is reproducible against Micro or that the user has pasted a bad-row payload. When the problem is production-pipeline-wide (events missing entirely, enrichment latency, loader failures) and the official `snowplow` plugin is installed, hand off to its `troubleshooting` skill instead of continuing here.
```

Do not otherwise change the body — the reference/ error-category docs and script stay as-is.

- [ ] **Step 3: Verify**

Run: `python3 scripts/validate.py plugins/snowplow-workflows/skills/debug-failed-events`
Expected: `OK — 0 problem(s)`.

- [ ] **Step 4: Commit**

```bash
git add plugins/snowplow-workflows/skills/debug-failed-events/SKILL.md
git commit -m "refactor: rescope debug-failed-events to local-first with product-plugin boundary"
```

---

### Task 4: Triggers-convention descriptions for the four keep-skills

**Files:**
- Modify (frontmatter description only): `plugins/snowplow-workflows/skills/{setup-micro,validate-snowplow-implementation,install-snowplow-tracking,fetch-snowplow-docs}/SKILL.md`

**Interfaces:**
- Consumes: validator CLI from Task 2.

- [ ] **Step 1: Replace each description with exactly these strings**

`setup-micro`:

```yaml
description: "Set up Snowplow Micro locally for testing tracking implementations — Docker configuration, mounting custom schemas, connecting Iglu registries, and enabling enrichments. Use before validating any new or changed tracking. Triggers: Snowplow Micro, set up Micro, local pipeline, mount schemas, test tracking locally."
```

`validate-snowplow-implementation`:

```yaml
description: "Test and validate a Snowplow tracking implementation against Micro — check good/bad event counts, inspect attached entities, and surface validation errors and common implementation issues before deploying to production. Use after instrumenting or changing tracking code. Triggers: validate tracking, verify implementation, check events in Micro, good bad events, test tracking."
```

`install-snowplow-tracking`:

```yaml
description: "Install and configure Snowplow tracking from scratch in web, iOS, or Android applications — tracker initialisation, out-of-the-box event tracking, and user identification. Use when an application has no Snowplow tracker yet. For guidance on individual tracking calls in an already-instrumented app, the official snowplow plugin's implementation-guidance skill also applies. Triggers: install Snowplow, add tracker, tracker setup, initialise tracker, out-of-the-box events."
```

`fetch-snowplow-docs`:

```yaml
description: "Fetch current Snowplow tracker documentation via the docs sitemap — initialisation, tracking calls, plugins — for any platform (web, iOS, Android, server-side). Use before writing any tracker code; never rely on built-in knowledge, tracker APIs change with each release. Triggers: Snowplow docs, tracker API reference, latest tracker docs, look up Snowplow documentation."
```

- [ ] **Step 2: Check `install-snowplow-tracking` platform coverage (no expansion this wave)**

Read `plugins/snowplow-workflows/skills/install-snowplow-tracking/SKILL.md` and confirm it addresses web, iOS, and Android initialisation plus OOTB events. Do NOT write new reference files — if genuine gaps exist (e.g. no Android section at all), record them as a bullet under Wave 1 follow-ups in ROADMAP.md during Task 9.

- [ ] **Step 3: Verify**

Run: `python3 scripts/validate.py --all`
Expected: remaining Triggers errors ONLY for `implement-custom-events` and `tracking-design` (handled in Tasks 5–6).

- [ ] **Step 4: Commit**

```bash
git add plugins/snowplow-workflows/skills
git commit -m "refactor: adopt Triggers description convention across keep-skills"
```

---

### Task 5: `tracking-design` → `design-tracking-plan` rewrite

**Files:**
- Rename: `plugins/snowplow-workflows/skills/tracking-design/` → `plugins/snowplow-workflows/skills/design-tracking-plan/`
- Rewrite: `design-tracking-plan/SKILL.md`
- Create: `design-tracking-plan/reference/property_instructions.md`, `design-tracking-plan/reference/git_backed_workflow.md`

**Interfaces:**
- Consumes: validator CLI (Task 2); current `tracking-design/SKILL.md` content (299 lines).
- Produces: skill name `design-tracking-plan` — Task 6 rewrites `implement-custom-events` references to this exact name; Task 9 lists it in README/ROADMAP.

- [ ] **Step 1: Rename the directory**

```bash
git mv plugins/snowplow-workflows/skills/tracking-design plugins/snowplow-workflows/skills/design-tracking-plan
```

- [ ] **Step 2: Extract property-instructions content to a reference doc**

Move the entire "Property Instructions for Grouped Schemas" section (current SKILL.md lines 104–228: intro, when-to-use, storage format, subtype rules, worked example, counter-example) verbatim into `reference/property_instructions.md` with an H1 of `# Property Instructions for Grouped Schemas`. In SKILL.md, replace it with a 4-line summary + pointer (exact text in Step 4 outline).

- [ ] **Step 3: Invoke `mattpocock-skills:writing-for-agents`, then rewrite SKILL.md**

Frontmatter — exactly:

```yaml
---
name: design-tracking-plan
description: "Design Snowplow tracking plans, schemas, entities, and event specifications — entity-first modelling, naming conventions, schema reuse, versioning, and property instructions — with a choice of git-backed (snowplow-cli) or Console-managed (MCP) workflows. Use when designing or evolving tracking from a data spec or feature requirements. For quick Console-side schema design without a local workflow, the official snowplow plugin's tracking-design skill also applies. Triggers: tracking plan, schema design, event spec, event specification, entities, Iglu, data structures, git-backed schemas."
tools:
  - list_schemas
  - get_schema_properties
  - get_data_structure_by_hash
  - create_schema_version
  - list_event_specifications
  - get_event_specification
---
```

Body requirements (structure per SKILL_TEMPLATE.md; keep ≤ 300 lines):

1. **Remove entirely** (console-agent artifacts): the "General Rules from your system instructions" paragraph (old line 8); the "Conversation Style" section (old 271–278); the "Image & Document Understanding" section (old 292–299).
2. **Keep, lightly edited**: warehouse representation notes (old 14–18); confirmation-before-creation rule (old 20); Workflow Phases 1–7 (old 28–102); Source Application Entity Inheritance (old 230–241); Best Practices (old 243–251); Event Granularity (old 253–261); Common Patterns (old 263–269); Terminology + Important Notes (old 280–290).
3. **New section — "Workflow Selection: Git-Backed vs Console-Managed"**, placed before the Workflow Phases, containing this decision framework verbatim:

```markdown
## Workflow Selection: Git-Backed vs Console-Managed

Decide with the user where schema definitions live before designing anything.

| Factor | Git-backed (snowplow-cli) | Console-managed (MCP) |
|---|---|---|
| Change review | PRs, code review, CI validation | Console UI history |
| Who edits | Engineers comfortable with git | PMs/analysts working in Console |
| Environments | Promote dev→prod via CI pipelines | Promote via Console/MCP publish |
| Existing state | Team already has a schemas repo | Schemas only exist in Console |
| Directly modifying Snowplow-managed schemas | Never — vendored copies only | Yes, via MCP with confirmation |

Default: if the organisation already keeps data structures in a git repository, or wants CI-gated schema changes, use the git-backed path (`reference/git_backed_workflow.md`). Otherwise use the Console-managed path via the Snowplow MCP. Never mix paths for the same schema — one source of truth per data structure.
```

4. **Tools paragraph** (replaces old "Tools" section): Console reads/writes go through the Snowplow MCP (installed with the official `snowplow` plugin). If the MCP is unavailable, do not call the Console API directly — fall back to the git-backed path with `snowplow-cli`, or stop and tell the user to install the official plugin.
5. **Property instructions summary** replacing the moved section:

```markdown
## Property Instructions

When multiple event specs share one data structure (Grouped Actions), property instructions narrow each spec to its subset of events — without them governance breaks down. They are draft-04 JSON Schema subtypes of the base schema: you may tighten constraints, never loosen or add. Read `reference/property_instructions.md` for the subtype rules and a worked example before creating any spec on a shared schema.
```

6. **Reference Documentation section** listing both reference files with one-line when-to-read descriptions.
7. Read the project's `.snowplow/agent-context.md` (if present, created by `setup-snowplow-context`) at Phase 1 for vendor, Iglu repos, and collaboration mode; honor a `collaboration-mode: review-only` preference by preparing complete proposals rather than co-designing interactively.

- [ ] **Step 4: Write `reference/git_backed_workflow.md`**

Before writing, invoke `fetch-snowplow-docs` for current `snowplow-cli` command syntax (data structures + data products commands) — do not trust remembered flags. The doc must cover, with real commands verified against fetched docs:

- Repo layout for data structures (`data-structures/<vendor>/<name>/...`) and data products, as generated by `snowplow-cli`.
- Downloading existing Console state into the repo (`snowplow-cli data-structures download`, `snowplow-cli data-products download` or current equivalents).
- Local validation before publish (`snowplow-cli data-structures validate`).
- Publishing dev → prod (`snowplow-cli data-structures publish dev`, `... publish prod` or current equivalents) and how this decouples publishing from design (the PDF's "Publishing (decoupled from design)" box).
- CI sketch: validate on PR, publish dev on merge, publish prod on tag/release approval.
- Auth prerequisites (API key env vars / `snowplow-cli` config file) — pointer only, no secrets handling advice beyond "use CI secrets".

- [ ] **Step 5: Verify**

```bash
python3 scripts/validate.py plugins/snowplow-workflows/skills/design-tracking-plan
grep -rn "tracking-design" plugins/snowplow-workflows/skills/design-tracking-plan/ ; true
```

Expected: `OK — 0 problem(s)`; the grep may match only the boundary sentence referencing the *product* plugin's `tracking-design` skill — no self-references to the old name.

- [ ] **Step 6: Commit**

```bash
git add -A plugins/snowplow-workflows/skills/design-tracking-plan
git commit -m "feat: rewrite tracking-design as field-native design-tracking-plan with git-backed workflow"
```

---

### Task 6: Refactor `implement-custom-events` to delegate to renamed skill

**Files:**
- Modify: `plugins/snowplow-workflows/skills/implement-custom-events/SKILL.md`

**Interfaces:**
- Consumes: skill name `design-tracking-plan` from Task 5.

- [ ] **Step 1: Replace the frontmatter description with exactly:**

```yaml
description: "End-to-end workflow for custom Snowplow event tracking — discover what to track, draft a tracking spec, design schemas and event specs via design-tracking-plan, create them in Console, instrument the code, and validate in Micro. Use when a customer wants custom event tracking added to an application from start to finish. Triggers: add custom events, implement tracking end to end, track new feature, instrument and validate events."
```

- [ ] **Step 2: Rename all delegation references**

Replace every occurrence of `` `tracking-design` `` in the body with `` `design-tracking-plan` `` (occurrences at old lines 21, 51–55 heading and text, 59, 70–72, 76, 153, 170). Update the step-3 heading to "Hand the spec to `design-tracking-plan`". In the phase cross-references, keep the phase numbers but verify they match the rewritten skill's phases from Task 5 (proposal presentation is Phase 5, confirmation Phase 6, execution Phase 7) — fix the two annotations that currently say "Executed inside `tracking-design` Phase 6" to reference Phase 7 (execution) where they describe creation calls.

- [ ] **Step 3: Add MCP-absence branch to Prerequisites**

Replace the Prerequisites bullet "The Snowplow MCP is available — the design and Console-write steps depend on it." with:

```markdown
- Console access for the design and Console-write steps: either the Snowplow MCP (from the official `snowplow` plugin) or `snowplow-cli` with the git-backed workflow. If neither is available, stop after the spec-drafting step and tell the user what to install.
```

- [ ] **Step 4: Add a pointer to project context**

In step 1 (Discover), add one line: "If `.snowplow/agent-context.md` exists (created by `setup-snowplow-context`), read it first for vendor, platforms, and collaboration mode."

- [ ] **Step 5: Verify**

```bash
python3 scripts/validate.py plugins/snowplow-workflows/skills/implement-custom-events
grep -c "design-tracking-plan" plugins/snowplow-workflows/skills/implement-custom-events/SKILL.md
grep -n "\`tracking-design\`" plugins/snowplow-workflows/skills/implement-custom-events/SKILL.md ; true
```

Expected: `OK — 0 problem(s)`; count ≥ 8; final grep matches nothing.

- [ ] **Step 6: Commit**

```bash
git add plugins/snowplow-workflows/skills/implement-custom-events/SKILL.md
git commit -m "refactor: delegate implement-custom-events to design-tracking-plan"
```

---

### Task 7: New skill `setup-snowplow-context`

**Files:**
- Create: `plugins/snowplow-workflows/skills/setup-snowplow-context/SKILL.md`, `.../templates/agent-context.md`

**Interfaces:**
- Produces: the file contract `.snowplow/agent-context.md` (template below) — `design-tracking-plan` (Task 5) and `implement-custom-events` (Task 6) already reference it by this exact path.

- [ ] **Step 1: Write the context-file template**

Create `templates/agent-context.md`:

```markdown
# Snowplow Agent Context

<!-- Written by the setup-snowplow-context skill. Other Snowplow skills read this
     file instead of re-asking. Edit values directly or re-run the skill. -->

- schema-vendor: {{ e.g. com.acme }}
- iglu-repositories: {{ e.g. Iglu Central + git repo URL or Console registry }}
- console-org: {{ Console organization name/id, or "none" }}
- mcp-available: {{ yes | no — is the official snowplow plugin / MCP installed? }}
- schema-workflow: {{ git-backed | console-managed }}
- warehouse: {{ snowflake | bigquery | databricks | redshift | none-yet }}
- tracked-platforms: {{ e.g. web, ios, android, server-side }}
- collaboration-mode: {{ co-design | review-only — should the agent design alongside the user or prepare complete proposals for review? }}
```

- [ ] **Step 2: Invoke `mattpocock-skills:writing-for-agents`, then author SKILL.md**

Frontmatter — exactly:

```yaml
---
name: setup-snowplow-context
description: "Capture a project's Snowplow working context once — schema vendor, Iglu repositories, Console org and MCP availability, schema workflow, warehouse target, tracked platforms, and collaboration preferences — into .snowplow/agent-context.md so every other Snowplow skill reads it instead of re-asking. Use at project start, or whenever a Snowplow skill can't find the context file. Triggers: set up snowplow context, snowplow project context, snowplow preferences, agent context file."
---
```

Body requirements (per SKILL_TEMPLATE.md, ≤ 120 lines):

- **When to use / not use**: use at project start or when context file missing; don't use to change a single value (edit the file directly).
- **Instructions**: (1) check for existing `.snowplow/agent-context.md` — if present, show it and ask only for corrections; (2) auto-detect before asking: scan the codebase for tracker packages (platforms), existing schema/vendor strings (`iglu:com.…` URIs), a data-structures git layout (schema-workflow), and whether Snowplow MCP tools are available in the session (mcp-available); (3) ask the user ONLY for values that couldn't be detected — one compact question set, not an interrogation; (4) write the file from `templates/agent-context.md` with all eight keys always present; (5) append a pointer to the project's agent instructions file — if `CLAUDE.md` or `AGENTS.md` exists at repo root, add the single line `Snowplow project context lives in .snowplow/agent-context.md — read it before any Snowplow work.` (skip if the line already exists; create nothing if neither file exists, just tell the user).
- **Templates section**: pointer to `templates/agent-context.md`.
- **Limits**: values are declarations, not verified credentials; the file is plaintext in the repo — never put API keys in it.

- [ ] **Step 3: Verify**

Run: `python3 scripts/validate.py plugins/snowplow-workflows/skills/setup-snowplow-context`
Expected: `OK — 0 problem(s)`.

- [ ] **Step 4: Commit**

```bash
git add plugins/snowplow-workflows/skills/setup-snowplow-context
git commit -m "feat: add setup-snowplow-context skill"
```

---

### Task 8: New skill `create-data-spec`

**Files:**
- Create: `plugins/snowplow-workflows/skills/create-data-spec/SKILL.md`, `.../templates/data-spec.md`, `.../reference/spec_translation_guide.md`

**Interfaces:**
- Consumes: `.snowplow/agent-context.md` contract (Task 7); hands its output to `design-tracking-plan` (Task 5).

- [ ] **Step 1: Write the data-spec template**

Create `templates/data-spec.md`:

```markdown
# Data Spec: {{ feature or initiative name }}

## Goal
{{ One or two sentences: the business questions this data must answer. }}

## KPIs / Success Metrics
| Metric | Definition | Computed from |
|---|---|---|
| {{ e.g. checkout conversion }} | {{ precise definition }} | {{ events below }} |

## Events
| Event | Trigger (user/system action) | Why it matters | Priority |
|---|---|---|---|
| {{ verb-noun, snake_case }} | {{ exact moment it fires }} | {{ KPI or question it feeds }} | {{ P0/P1/P2 }} |

## Entities
| Entity | Attached to (events) | Key fields | Source of truth |
|---|---|---|---|
| {{ e.g. product }} | {{ event list or "all" }} | {{ fields with types }} | {{ where values come from }} |

## Identity & Context
- User identification: {{ anonymous / logged-in id / both }}
- Platforms: {{ web / ios / android / server }}

## Open Questions
- {{ anything unresolved — must be empty before handing to design-tracking-plan }}
```

- [ ] **Step 2: Invoke `mattpocock-skills:writing-for-agents`, then author SKILL.md**

Frontmatter — exactly:

```yaml
---
name: create-data-spec
description: "Turn a product spec, PRD, or business goals into a data spec — KPIs, events, entities, identity — and then into Snowplow semantics ready for design-tracking-plan. Two entry points: from a product spec, or refining an existing data spec into Snowplow terms. Use when a product manager or analyst needs tracking requirements formalised before any schema design. Triggers: data spec, product spec to data spec, translate PRD to tracking, measurement plan, tracking requirements."
---
```

Body requirements (≤ 200 lines):

- **When to use / not use**: not for schema design itself (hand off to `design-tracking-plan`); not for instrumenting code (`implement-custom-events`).
- **Instructions — two entry points**:
  - *Entry A — from product spec/PRD/goals*: (1) read `.snowplow/agent-context.md` if present (platforms, collaboration mode); (2) extract goals and KPIs from the source document; (3) derive candidate events per KPI (every metric must be computable from listed events — state the computation); (4) derive entities entity-first (objects shared across events become entities, never repeated event properties); (5) fill `templates/data-spec.md`; (6) review with user, drive Open Questions to empty.
  - *Entry B — from an existing data spec*: validate it against the same rules (KPI-computability, entity-first, snake_case event names, priorities set), then translate to Snowplow semantics.
- **Snowplow semantics translation** (final section of output, appended to the data spec): each event → self-describing event candidate (name, vendor from context file, OOTB-schema-reuse note to be resolved during design); each entity → entity schema candidate; note which events group into one tracking plan; explicitly defer schema JSON, versions, and property instructions to `design-tracking-plan`.
- **Reference doc** `reference/spec_translation_guide.md`: judgment content — how to spot events hiding in PRD language (state changes, user decisions, system outcomes), granularity guidance (one event per decision point, not per click), the KPI-computability test with a worked example (e.g. "checkout conversion = complete_checkout / start_checkout, both events required"), and common PM-spec failure modes (vanity events with no KPI, missing failure-path events, entities modelled as event properties).
- **Handoff**: end by offering to invoke `design-tracking-plan` with the finished spec.

- [ ] **Step 3: Verify**

Run: `python3 scripts/validate.py plugins/snowplow-workflows/skills/create-data-spec`
Expected: `OK — 0 problem(s)`.

- [ ] **Step 4: Commit**

```bash
git add plugins/snowplow-workflows/skills/create-data-spec
git commit -m "feat: add create-data-spec skill"
```

---

### Task 9: README rewrite + ROADMAP.md

**Files:**
- Rewrite: `README.md`
- Create: `ROADMAP.md`

**Interfaces:**
- Consumes: final skill names + descriptions from Tasks 3–8.

- [ ] **Step 1: Rewrite README.md**

Required content (keep it tight; full skill descriptions live in frontmatter, README rows are one-liners):

1. Title `# Snowplow Workflows` + positioning paragraph: deep multi-step field workflows; complements — does not replace — the official `snowplow` plugin; install both.
2. **Install** section, mirroring the product repo's three paths:
   - `/plugin marketplace add <github-org>/snowplow-agent-skills` + `/plugin install snowplow-workflows@snowplow-workflows` (use the repo's actual GitHub org/name from `git remote get-url origin`)
   - `npx plugins add <org>/snowplow-agent-skills` (open-plugin, any agent)
   - `npx skills@latest add <repo-url>` (skills CLI)
3. **Console access** callout: no MCP bundled; install the official plugin (`/plugin marketplace add snowplow/skills`, `/plugin install snowplow@snowplow`) for Console operations; skills fall back to `snowplow-cli` where sensible.
4. **Skills tables** by the five README categories, now with real rows only (no `skill-name` placeholder rows): Tracking Design → create-data-spec, design-tracking-plan; Implementation & Testing → fetch-snowplow-docs, install-snowplow-tracking, setup-micro, validate-snowplow-implementation, debug-failed-events, implement-custom-events; Project Setup → setup-snowplow-context; Data Analytics & Modeling / Governance / Migration → "planned — see ROADMAP.md".
5. **Layout** section showing the dual-manifest structure and the "keep `.claude-plugin/` and `.plugin/` in sync by hand" note.
6. **Contributing**: run `python3 scripts/validate.py --all` before PR; skills follow `skill_design_guidelines/`.

- [ ] **Step 2: Create ROADMAP.md**

Full PDF-box → skill/wave mapping (source: `docs/snowplow-skills-map.pdf`). Exactly this table plus a follow-ups section:

```markdown
# Roadmap

Source: the field skills map (`docs/snowplow-skills-map.pdf`). Waves are indicative order, not commitments. Boxes marked *product* are served by the official `snowplow` plugin, not this repo.

| Skills-map box | Persona | Disposition | Skill | Wave |
|---|---|---|---|---|
| Setup working preferences | All | shipped | `setup-snowplow-context` | 1 |
| snowplow-cli / Authenticate with Console | All | shared reference, not a skill | `design-tracking-plan` references | 1 |
| Product Spec > Data Spec | PM/Analyst | shipped | `create-data-spec` (entry A) | 1 |
| Data Spec > Snowplow Semantics | PM/Analyst | shipped | `create-data-spec` (entry B) | 1 |
| Design Tracking Plans / Event Specs | PM/Analyst | shipped | `design-tracking-plan` | 1 |
| Create Git-backed Structures | PM/Analyst | shipped | `design-tracking-plan` (git-backed path) | 1 |
| Make changes directly to Snowplow-managed schemas | PM/Analyst | folded in | `design-tracking-plan` decision framework | 1 |
| Publishing (decoupled from design) | PM/Analyst | shipped | `design-tracking-plan` git-backed workflow | 1 |
| Discover tracking opportunities / product event surfaces | PM/Analyst | planned | discovery step of `implement-custom-events` today; dedicated skill later | 2 |
| Create tracking plans from uncategorised Data Structures | PM/Analyst | planned | — | 3 |
| Frontend / Mobile / Tracker init / OOTB | Developer | shipped | `install-snowplow-tracking` | 1 |
| Backend serverside | Developer | planned | extend `install-snowplow-tracking` | 2 |
| Plugin-specific instrumentation (media, ecom) | Developer | planned | — | 2 |
| Anonymous tracking implementation | Developer | planned | shared with governance anonymous-tracking skill | 3 |
| Writing a custom plugin | Developer | planned | — | 3 |
| Setup Snowtype | Developer | partial | inside `implement-custom-events` step 8; dedicated skill later | 2 |
| Check OOTB events against HTML markup | Developer | planned | — | 3 |
| Testing locally / Spin up Micro | Developer | shipped | `setup-micro`, `validate-snowplow-implementation` | 1 |
| Debugging failed events | Developer | shipped | `debug-failed-events` (local-first; production side is *product* `troubleshooting`) | 1 |
| Workflow: auto-implement events + monitor in Micro | Developer | shipped | `implement-custom-events` | 1 |
| Writing once-off queries | Analyst | planned | — | 2 |
| Debugging data quality issues | Analyst | planned | — | 2 |
| Event recovery (+ keyhole backfills) | Analyst | planned | — | 3 |
| New dbt project for Snowplow models | Analytics Eng | planned | — | 2 |
| Unified model setup | Analytics Eng | planned | — | 2 |
| Attribution model setup | Analytics Eng | planned | — | 2 |
| Autogenerate custom model | Analytics Eng | planned | — | 2 |
| Create semantic definitions from schema | Analytics Eng | planned | — | 2 |
| Audit / scoring of existing schemas | Governance | planned | — | 3 |
| Audits (spec-to-reality, anon tracking, missing events) | Governance | planned | — | 3 |
| Console configuration questions | Governance | *product* (`console-operations`) | — | — |
| Configure enrichments | Governance | *product* (`console-operations`); custom JS enrichment authoring stays here | 3 |
| Writing custom JS enrichment | Governance | planned | — | 3 |
| Anonymous tracking | Governance | planned | — | 3 |
| Schema discoverability tool | Governance | planned | — | 3 |
| Quick onboarding wizard | Migration | planned | — | 3 |
| GA4 > Snowplow | Migration | planned | — | 2 |
| Write a new Event Forwarding destination | Future | deferred | — | future |
| Signals | Future | *product* (`signals`) | — | — |
```

Add any Wave 1 follow-ups noted in Task 4 Step 2 under a `## Wave 1 follow-ups` heading (omit the heading if none).

- [ ] **Step 3: Verify**

```bash
python3 scripts/validate.py --all
grep -c "skill-name" README.md
```

Expected: `OK — 0 problem(s)`; grep count 0 (no placeholder rows left).

- [ ] **Step 4: Commit**

```bash
git add README.md ROADMAP.md
git commit -m "docs: rewrite README for snowplow-workflows and add roadmap"
```

---

### Task 10: Final verification + PR

**Files:** none new.

- [ ] **Step 1: Full validation sweep**

```bash
python3 scripts/validate.py --all
grep -rn "plugins/snowplow/" README.md ROADMAP.md docs/ scripts/ .github/ .claude-plugin/ .plugin/ ; true
grep -rln "General Rules from your system instructions" plugins/ ; true
```

Expected: `OK — 0 problem(s)`; both greps match nothing (no stale paths, no console-agent language).

- [ ] **Step 2: Optional local install smoke test**

```bash
npx plugins discover . 2>/dev/null || echo "plugins CLI discover unavailable — note in PR"
```

Expected: catalog lists `snowplow-workflows`. If the CLI errors for environmental reasons, note it in the PR body rather than blocking.

- [ ] **Step 3: Push and open PR**

```bash
git push -u origin snowplow-workflows-restructure
gh pr create --title "Restructure as snowplow-workflows plugin + wave 1 skills" --body "$(cat <<'EOF'
## Summary
- Renames the plugin to `snowplow-workflows`, co-installable with the official `snowplow` product plugin (no name/MCP collisions; bundled localhost `.mcp.json` removed)
- Adopts open-plugin layout parity with snowplow-product-skills (`.claude-plugin/` + `.plugin/` manifests, root marketplace catalogs)
- Adds `scripts/validate.py` + CI enforcing skill conventions (Triggers descriptions, name rules, 500-line cap, marketplace sync)
- Rewrites `tracking-design` as field-native `design-tracking-plan` with git-backed (snowplow-cli) vs Console-managed decision framework
- New skills: `setup-snowplow-context`, `create-data-spec`
- Rescopes `debug-failed-events` local-first with a boundary to the product plugin's `troubleshooting`
- README rewritten; ROADMAP.md maps every skills-map box to a wave

## Open question
- Should this repo carry an Apache-2.0 LICENSE like snowplow-product-skills? Manifests currently omit the `license` field pending that call.

## Testing
- `python3 scripts/validate.py --all` green
- CI workflow runs the same check on PRs
EOF
)"
```

(No AI attribution anywhere in commits or PR body.)

---

## Self-Review Notes

- **Spec coverage**: every confirmed decision from the grilling session maps to a task — rename/manifests/gitignore (T1), validator+CI (T2), debug-failed-events rescope (T3), Triggers convention (T3–T8), design-tracking-plan rewrite + schema-management fold-in + publishing (T5), orchestrator delegation (T6), setup-snowplow-context incl. collaboration-mode (T7), create-data-spec two entry points (T8), README + ROADMAP with full PDF mapping (T9), branch+PR (T10).
- **Deliberate deferrals**: `install-snowplow-tracking` reference expansion deferred to ROADMAP follow-ups (T4 Step 2) — no concrete gap identified yet. LICENSE decision escalated to PR body.
- **Type consistency**: skill name `design-tracking-plan`, context path `.snowplow/agent-context.md`, validator CLI `python3 scripts/validate.py --all`, and plugin name `snowplow-workflows` are used identically across all tasks.
- **Authoring-method note**: Tasks 5, 7, 8 intentionally specify structure + acceptance criteria rather than full prose bodies — the user mandated authoring skill bodies with `mattpocock-skills:writing-for-agents` at execution time. Frontmatter, templates, tables, and boundary sentences ARE verbatim in this plan.
