# Review Findings Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 15 confirmed code-review findings on the `validator-hardening` branch — broken diagnostic commands in the debug-failed-events docs, coverage holes and false positives in scripts/validate.py, and vacuous tests.

**Architecture:** Two independent workstreams. (1) Doc fixes in `plugins/snowplow-workflows/skills/debug-failed-events/` replace wrong curl/jq commands with correct, honest ones. (2) Validator fixes rewrite the path-reference engine, harden marketplace checks, make functions root-injectable for testing, and widen `--all` discovery to every plugin. Code changes are TDD; doc changes are verified by running the validator.

**Tech Stack:** Python 3 stdlib only (json, re, pathlib, glob, os, unittest). No new dependencies.

**Spec:** docs/superpowers/plans/2026-08-13-review-findings-spec.md

## Global Constraints

- Work happens on the existing `validator-hardening` branch in the primary working directory (user directed "in this branch" — no new worktree, no new branch).
- `python3 scripts/test_validate.py` must pass after every task.
- `python3 scripts/validate.py --all` must print `OK — 0 problem(s)` after every task.
- Commit messages must NOT contain any `Co-Authored-By: Claude` line or other AI attribution.
- SKILL.md files must stay ≤ 500 lines (the validator enforces this).
- Registry hostname placeholder in docs is `your-org.iglu.snplow.net`; API key placeholder is `YOUR_API_KEY` — keep both verbatim.
- Correct Iglu Server schema route is `/api/schemas/{vendor}/{name}/{format}/{version}` — vendor WITHOUT the `iglu:` prefix (reference form: `plugins/snowplow-workflows/skills/setup-micro/troubleshooting/iglu_registry_issues.md:31-32`).
- Do not add new helper scripts to the skills; fixes stay in docs / validate.py / test_validate.py.

---

### Task 1: Fix Iglu Server URLs in debug-failed-events docs (F1, curl flags from F9)

**Files:**
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/SKILL.md:136-144`
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/schema_resolution_errors.md:40-44`
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/schema_resolution_errors.md:199-206`

(The two remaining `iglu:`-in-URL sites — SKILL.md:149-155 and schema_validation_errors.md:398-416 — are rewritten wholesale by Task 2; do not touch them here.)

**Interfaces:**
- Produces: canonical curl form `curl -fsS -H "apikey: YOUR_API_KEY" "https://your-org.iglu.snplow.net/api/schemas/com.example/event/jsonschema/1-0-0"` that Task 2 reuses.

- [ ] **Step 1: Fix SKILL.md schema-resolution fix pattern**

In `SKILL.md`, replace the block at lines 136-144:

```markdown
**Fix Pattern:**
```bash
# Check schema deployment — returns the schema JSON if deployed.
# -f makes a missing schema fail loudly (curl: (22) ... 404) instead of
# printing an error body that looks like a result.
curl -fsS -H "apikey: YOUR_API_KEY" \
  "https://your-org.iglu.snplow.net/api/schemas/com.example/event/jsonschema/1-0-0"

# If not deployed, deploy to appropriate environment
# Then retry event
```
```

(The change: `iglu:com.example` → `com.example` in the URL path, add `-fsS`, add the comment explaining `-f`.)

- [ ] **Step 2: Fix schema_resolution_errors.md verify block (line ~41)**

Replace:

```bash
python scripts/check_schema_deployment.py ...   # <- already replaced on branch with:
curl -H "apikey: YOUR_API_KEY" \
  "https://your-org.iglu.snplow.net/api/schemas/iglu:com.example/event_name/jsonschema/1-0-0"
```

with:

```bash
curl -fsS -H "apikey: YOUR_API_KEY" \
  "https://your-org.iglu.snplow.net/api/schemas/com.example/event_name/jsonschema/1-0-0"
```

- [ ] **Step 3: Fix schema_resolution_errors.md test-accessibility block (line ~201)**

Replace:

```bash
   curl -H "apikey: YOUR_API_KEY" \
     "https://your-org.iglu.snplow.net/api/schemas/iglu:com.example/event/jsonschema/1-0-0"
```

with:

```bash
   curl -fsS -H "apikey: YOUR_API_KEY" \
     "https://your-org.iglu.snplow.net/api/schemas/com.example/event/jsonschema/1-0-0"
```

(Keep the 3-space indentation — the block sits inside a numbered list.)

- [ ] **Step 4: Verify no `iglu:` remains inside any API URL in this skill**

Run: `grep -rn "api/schemas/iglu:" plugins/snowplow-workflows/skills/debug-failed-events/`
Expected: only the two Task-2 sites remain (SKILL.md comparison block, schema_validation_errors.md Diagnostic Approach). If any OTHER site matches, fix it the same way.

- [ ] **Step 5: Run validator and commit**

Run: `python3 scripts/validate.py --all` → expect `OK — 0 problem(s)`

```bash
git add plugins/snowplow-workflows/skills/debug-failed-events/
git commit -m "fix(debug-failed-events): drop iglu: prefix from Iglu Server API URLs"
```

---

### Task 2: Rework schema-vs-event comparison guidance (F3, F9, remaining F1 sites)

**Files:**
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/SKILL.md:146-155`
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/schema_validation_errors.md:399-416`

**Interfaces:**
- Consumes: canonical curl form from Task 1.

- [ ] **Step 1: Replace the SKILL.md comparison block (lines 146-155)**

Replace:

````markdown
1. **Compare event data with schema**
   ```bash
   # Fetch the schema, then compare field-by-field against the failing event
   curl -H "apikey: YOUR_API_KEY" \
     "https://your-org.iglu.snplow.net/api/schemas/iglu:com.example/event/jsonschema/1-0-0" > schema.json
   jq '{required, properties: (.properties | map_values(.type))}' schema.json
   jq 'keys' failed_event.json
   ```
````

with:

````markdown
1. **Compare event data with schema**
   ```bash
   # Fetch the schema (-f fails loudly on 404 instead of saving the error body)
   curl -fsS -H "apikey: YOUR_API_KEY" \
     "https://your-org.iglu.snplow.net/api/schemas/com.example/event/jsonschema/1-0-0" > schema.json

   # Required fields plus FULL property definitions — keep enum/pattern/format
   # constraints visible; they fail validation as often as wrong types
   jq '{required, properties}' schema.json

   # Extract the entity data that failed validation into entity.json first.
   # The fields to compare are nested in the unstruct_event / context entity
   # payload — NOT at the top level of the bad-row wrapper, where jq would
   # only show wrapper keys like ["collectorPayload","errors","timestamp"].
   jq 'keys' entity.json
   ```
````

- [ ] **Step 2: Replace the schema_validation_errors.md "Diagnostic Approach" section (lines ~399-416)**

Replace everything from the ` ```bash ` fence after "Fetch the schema and compare the failing event field-by-field:" through the closing paragraph "Missing required fields, extra fields not in `properties`, and type mismatches account for nearly all validation errors." with:

````markdown
```bash
# Fetch the schema from your registry (-f fails loudly if the schema is missing)
curl -fsS -H "apikey: YOUR_API_KEY" \
  "https://your-org.iglu.snplow.net/api/schemas/com.example/event/jsonschema/1-0-0" > schema.json

# List the schema's required fields and full property definitions
jq '{required, properties}' schema.json

# Extract the entity data that failed validation into entity.json first —
# the fields to compare live in the unstruct_event / context entity payload,
# not at the top level of the bad-row wrapper. Then list its fields:
jq 'keys' entity.json
```

Compare the entity's fields against `required` and `properties`. Check for
missing required fields and unexpected extra fields first, then check each
value against its full property definition — `type`, and equally the
constraint keywords (`enum`, `pattern`, `format`, `minimum`/`maximum`,
array `items`) that the error catalogue above documents.
````

- [ ] **Step 3: Run validator and commit**

Run: `python3 scripts/validate.py --all` → expect `OK — 0 problem(s)`
Run: `grep -rn "api/schemas/iglu:" plugins/` → expect no matches at all now.

```bash
git add plugins/snowplow-workflows/skills/debug-failed-events/
git commit -m "fix(debug-failed-events): make schema-vs-event comparison target the failing entity and keep constraints visible"
```

---

### Task 3: Fix malformed-event diagnostics (F2, F10, F11)

**Files:**
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/SKILL.md:198-217`
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/malformed_events.md:59-62`
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/malformed_events.md:83-87`
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/malformed_events.md:334-345`

**Interfaces:** none.

- [ ] **Step 1: Fix SKILL.md Malformed Events step 1 (lines ~200-203)**

Replace:

````markdown
1. **Validate JSON structure**
   ```bash
   python3 -m json.tool failed_event.json
   ```
````

with:

````markdown
1. **Validate JSON structure of the raw payload**
   ```bash
   # A bad-row record is itself valid JSON wrapping the broken payload —
   # extract the original tracker payload (the collector payload body /
   # parameters inside the bad row) into payload.json first, or this
   # check always passes.
   python3 -m json.tool payload.json
   ```
````

- [ ] **Step 2: Fix malformed_events.md Invalid-JSON diagnosis (lines ~59-62)**

Replace:

````markdown
**Diagnosis:**
```bash
python3 -m json.tool event.json
```
````

with:

````markdown
**Diagnosis:**
```bash
# Run against the raw tracker payload itself. A bad-row record from
# /micro/bad or the warehouse is valid JSON wrapping the broken payload —
# extract the inner payload first, or this check always passes.
python3 -m json.tool payload.json
```
````

- [ ] **Step 3: Fix malformed_events.md required-fields diagnosis (lines ~83-87)**

Replace:

````markdown
**Diagnosis:**
Check event payload for these fields (`null` in the output = missing):
```bash
jq '{e, tv, p, aid, dtm, ttm}' event.json
```
````

with:

````markdown
**Diagnosis:**
Check each event in the payload for these fields (`null` in the output =
missing). The params are nested, not top-level — pick the form matching
what you captured:
```bash
# Captured POST body (payload_data envelope) — one line per event:
jq '.data[] | {e, tv, p, aid, dtm, ttm}' post_body.json

# Bad row: the tracker params live under the raw payload instead —
# inspect them there (adjust the path to your bad-row format):
jq '.payload.raw.parameters' bad_row.json
```
````

- [ ] **Step 4: Fix malformed_events.md Diagnostic Tools (lines ~334-345)**

Replace:

````markdown
## Diagnostic Tools

```bash
# Validate JSON structure
python3 -m json.tool event.json

# Check event size in bytes
wc -c < event.json

# Check required Snowplow fields (null in the output = missing)
jq '{e, tv, p, aid, dtm, ttm}' event.json
```
````

with:

````markdown
## Diagnostic Tools

```bash
# Validate JSON structure of the raw payload (extract it from the bad-row
# wrapper first — the wrapper is valid JSON even when the payload is not)
python3 -m json.tool payload.json

# Check compact serialized size against the 10000-byte limit above —
# measure compact form, pretty-printed files overcount
jq -c . payload.json | wc -c

# Check required Snowplow fields per event in a POST body
# (null in the output = missing)
jq '.data[] | {e, tv, p, aid, dtm, ttm}' post_body.json
```
````

- [ ] **Step 5: Run validator and commit**

Run: `python3 scripts/validate.py --all` → expect `OK — 0 problem(s)`

```bash
git add plugins/snowplow-workflows/skills/debug-failed-events/
git commit -m "fix(debug-failed-events): target the right payload layer in malformed-event diagnostics"
```

---

### Task 4: Fix enrichment required-fields check (F12)

**Files:**
- Modify: `plugins/snowplow-workflows/skills/debug-failed-events/reference/enrichment_errors.md:134-140`

**Interfaces:** none.

- [ ] **Step 1: Replace the identity jq with a real field check**

Replace:

````markdown
Check if event has required fields for enrichment:
```bash
jq . failed_event.json
```
````

with:

````markdown
Check that the fields the enrichment reads are present and non-null —
substitute the input fields for your enrichment (e.g. `useragent` for the
UA parser, `user_ipaddress` for the IP lookup), and adjust the jq path to
where the event payload sits in your bad-row wrapper:
```bash
jq '{useragent, user_ipaddress}' failed_event.json
```
`null` in the output means the field is missing — the enrichment has no
input to work with, which is the failure cause to fix in the tracker.
````

- [ ] **Step 2: Run validator and commit**

Run: `python3 scripts/validate.py --all` → expect `OK — 0 problem(s)`

```bash
git add plugins/snowplow-workflows/skills/debug-failed-events/reference/enrichment_errors.md
git commit -m "fix(debug-failed-events): make enrichment field check actually check fields"
```

---

### Task 5: Harden the Triggers-suffix check (F4)

**Files:**
- Modify: `scripts/validate.py:116-119` (inside `check_skill`)
- Test: `scripts/test_validate.py` (class `TestTriggersSuffix`)

**Interfaces:**
- Produces: module-level `TRIGGERS_RE` in validate.py; `check_skill` behavior change only.

Design ruling (recorded here so the implementer doesn't re-derive it): trailing-prose detection is a heuristic. New rule — the tail after the LAST word-boundary `Triggers:` fails if it is empty, contains a semicolon followed by more text (semicolons don't belong in a trigger list), or contains `. ` followed by an uppercase letter (a new sentence). `e.g.`/`vs.` followed by lowercase now pass. Known accepted limitation: prose glued on with `.NoSpace` followed by uppercase is only caught when preceded by a space.

- [ ] **Step 1: Write the failing tests**

In `scripts/test_validate.py`, add to `TestTriggersSuffix`:

```python
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
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 scripts/test_validate.py`
Expected: `test_abbreviation_in_triggers_passes` and `test_glued_triggers_token_fails` FAIL (abbreviation currently flagged; glued token currently accepted). `test_semicolon_prose_after_triggers_fails` currently FAILS too (semicolon prose passes today).

- [ ] **Step 3: Implement**

In `scripts/validate.py`, add near the other module regexes:

```python
# 'Triggers:' must start at a word boundary — 'FooTriggers:' is not a
# trigger list.
TRIGGERS_RE = re.compile(r"(?<![A-Za-z0-9])Triggers:")
```

Replace the description check in `check_skill`:

```python
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
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `python3 scripts/test_validate.py`
Expected: PASS (all, including the four pre-existing TestTriggersSuffix tests).

Run: `python3 scripts/validate.py --all`
Expected: `OK — 0 problem(s)` (if any real skill description now fails, fix that description in the same commit — the check is the spec).

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.py scripts/test_validate.py
git commit -m "fix(validate): word-boundary Triggers match, tolerate abbreviations, catch semicolon prose"
```

---

### Task 6: Rewrite the intra-skill path-reference engine (F5, F7, F8, URL-test part of F15)

**Files:**
- Modify: `scripts/validate.py:47-54` (regex block) and `scripts/validate.py:127-150` (`check_intra_skill_paths`)
- Test: `scripts/test_validate.py` (class `TestDanglingPaths`)

**Interfaces:**
- Produces: module-level `FILE_REF_RE`, `DIR_REF_RE`, `BACKTICK_REF_RE` (replacing `INTRA_PATH_RE`); `check_intra_skill_paths(skill_dir)` signature unchanged.

Design rulings (recorded for the implementer):
- Three reference classes are checked: (a) refs whose final segment has an extension, anywhere in prose; (b) refs with a trailing `/` and at least one named segment after the asset dir (`scripts/` alone is prose); (c) backtick-wrapped refs where the backtick span IS the path — these are checked even without extension or slash (catches `` `examples/schema_not_found` ``).
- Relative refs (`./x`, `../x`) are now matched and resolve against the referencing .md file's directory; bare refs resolve against the skill root.
- Refs containing `*` are checked with glob: pass if the glob matches anything.
- A trailing guard stops `scripts/foo.py-based` prose from matching as a path.
- Accepted limitation: extensionless, slash-less, non-backticked prose (`examples/schema_not_found` bare in a sentence) remains unchecked — indistinguishable from prose like `troubleshooting/debugging tips`.

- [ ] **Step 1: Write the failing tests**

In `scripts/test_validate.py`, REPLACE `test_url_path_not_flagged` (currently vacuous — its `reference/foo` has no extension so the extension filter skips it regardless of the lookbehind) with:

```python
    def test_url_path_not_flagged(self):
        # foo.html HAS an extension — only the URL-context guard keeps this
        # from being flagged, so this test fails if that guard is removed.
        skill = make_skill(
            self.root, "my-skill",
            body="See https://docs.snowplow.io/docs/reference/foo.html for docs.")
        self.assertEqual(validate.check_skill(skill), [])
```

Add to `TestDanglingPaths`:

```python
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
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 scripts/test_validate.py`
Expected: the relative-ref, backtick-extensionless, hyphen-prose, glob tests FAIL against current code (relative/backtick/glob refs unchecked → the `_fails` variants fail; hyphen prose currently flagged → that test fails). `test_sentence_final_bare_dir_not_flagged` FAILS (currently flags `scripts/`).

- [ ] **Step 3: Implement**

In `scripts/validate.py`, add `import glob` and `import os` to the imports. Replace the `INTRA_PATH_RE` block (keep `SKILL_ASSET_DIRS`) with:

```python
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
```

Replace `check_intra_skill_paths` with:

```python
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
```

- [ ] **Step 4: Run tests, then the validator on the real repo**

Run: `python3 scripts/test_validate.py`
Expected: PASS (all — including the pre-existing prose/period/dir tests).

Run: `python3 scripts/validate.py --all`
Expected: `OK — 0 problem(s)`. The new engine now checks previously-invisible refs across ALL skills (relative refs in setup-micro examples, backticked extensionless refs everywhere). If real dangling refs surface, they are real findings: fix each doc to point at an existing path (mirror what commit db9342f did) in the same commit, and list every such fix in your report.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.py scripts/test_validate.py plugins/
git commit -m "fix(validate): check relative, backticked, and glob refs; stop flagging prose"
```

---

### Task 7: Harden marketplace/manifest checks and make them testable (F6, F13, test half of F15)

**Files:**
- Modify: `scripts/validate.py:153-172` (`check_plugin_manifest_pair`), `scripts/validate.py:175-211` (`check_marketplaces`)
- Test: `scripts/test_validate.py` (extend `TestManifestPairSync`, delete `test_all_official_names_reserved`, new `TestMarketplaces`)

**Interfaces:**
- Produces: `check_marketplaces(root: Path = validate.ROOT)` — now takes an injectable root (default preserves CLI behavior). Task 8 relies on this signature and on pair-checking having MOVED OUT of `check_marketplaces` (see ruling below).

Design rulings:
- `check_marketplaces` becomes catalog-only: parse both catalogs, catalog sync, source-exists, entry-name-vs-manifest. Manifest pair checks move to `--all` discovery (Task 8) so unregistered plugins get them too. To keep `--all` green between Tasks 7 and 8, Task 7 temporarily calls `check_plugin_manifest_pair` from `main()` for marketplace sources; Task 8 replaces that with full discovery.
- Manifest pair equality compares `json.dumps(..., sort_keys=True)` serializations so `{"a": true}` vs `{"a": 1}` counts as a difference.
- `test_all_official_names_reserved` is deleted: it asserts a hand-copied literal against itself and cannot detect drift from the official plugin. No replacement test — the RESERVED_SKILL_NAMES comment in validate.py already records provenance; drift detection needs the official plugin at test time, which unit tests don't have.

- [ ] **Step 1: Write the failing tests**

In `scripts/test_validate.py`, add a marketplace helper next to `make_plugin`:

```python
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
```

Add the test class:

```python
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
```

Extend `TestManifestPairSync`:

```python
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
```

Delete `test_all_official_names_reserved` from `TestReservedNames`.

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 scripts/test_validate.py`
Expected: `test_entry_missing_source_reported_by_name` FAILS (no error emitted today), `test_non_dict_manifest_does_not_crash` ERRORS (AttributeError today), `test_non_dict_manifest_fails` FAILS, `test_bool_int_drift_detected` FAILS (True == 1). `check_marketplaces(self.root)` calls also fail with TypeError until the signature lands.

- [ ] **Step 3: Implement**

In `check_plugin_manifest_pair`, replace the parse/compare body:

```python
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{plugin_dir.name}: {rel} invalid JSON ({e})")
            continue
        if not isinstance(data, dict):
            errors.append(f"{plugin_dir.name}: {rel} must be a JSON object")
            continue
        manifests[rel] = data
    if len(manifests) == 2:
        a, b = (json.dumps(manifests[k], sort_keys=True)
                for k in (".claude-plugin/plugin.json", ".plugin/plugin.json"))
        if a != b:
            errors.append(
                f"{plugin_dir.name}: .claude-plugin/plugin.json and .plugin/plugin.json differ — keep in sync"
            )
    return errors
```

Rewrite `check_marketplaces` (catalog-only, root-injectable):

```python
def check_marketplaces(root: Path = ROOT):
    errors = []
    catalogs = {}
    for rel in (".claude-plugin/marketplace.json", ".plugin/marketplace.json"):
        p = root / rel
        if not p.is_file():
            errors.append(f"{rel}: missing")
            continue
        try:
            catalogs[rel] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: invalid JSON ({e})")
    if len(catalogs) == 2:
        vals = list(catalogs.values())
        if json.dumps(vals[0], sort_keys=True) != json.dumps(vals[1], sort_keys=True):
            errors.append(".claude-plugin/ and .plugin/ marketplace.json differ — keep in sync")
    for rel, cat in catalogs.items():
        for entry in cat.get("plugins", []):
            src_rel = entry.get("source")
            if not src_rel:
                errors.append(f"{rel}: entry {entry.get('name')!r} has no source")
                continue
            src = root / src_rel
            if not src.is_dir():
                errors.append(f"{rel}: plugin source {src_rel!r} does not exist")
                continue
            manifest = src / ".claude-plugin" / "plugin.json"
            if manifest.is_file():
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue  # reported by the manifest pair check
                if not isinstance(data, dict):
                    continue  # reported by the manifest pair check
                if data.get("name") != entry.get("name"):
                    errors.append(
                        f"{rel}: entry name {entry.get('name')!r} != plugin.json name {data.get('name')!r}"
                    )
    return errors
```

In `main()`, keep `--all` green until Task 8 by pair-checking marketplace sources there (temporary — Task 8 replaces this block with full discovery):

```python
    if args == ["--all"]:
        errors += check_marketplaces()
        errors += check_plugin_manifest_pair(ROOT / "plugins" / "snowplow-workflows")
        for d in sorted(SKILLS_DIR.iterdir()):
            if d.is_dir():
                errors += check_skill(d)
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `python3 scripts/test_validate.py` → PASS
Run: `python3 scripts/validate.py --all` → `OK — 0 problem(s)`

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.py scripts/test_validate.py
git commit -m "fix(validate): catalog checks name malformed entries, survive non-dict manifests, detect bool/int drift"
```

---

### Task 8: Widen --all discovery to every plugin (F14)

**Files:**
- Modify: `scripts/validate.py` (`main`, new `check_all`, module docstring, remove `SKILLS_DIR`)
- Test: `scripts/test_validate.py` (new `TestCheckAll`)

**Interfaces:**
- Consumes: `check_marketplaces(root)` from Task 7 (catalog-only), `check_plugin_manifest_pair`, `check_skill`.
- Produces: `check_all(root: Path = validate.ROOT) -> list[str]`; `main()` delegates to it.

- [ ] **Step 1: Write the failing tests**

Add to `scripts/test_validate.py` (uses `make_marketplace`, `make_skill` from earlier tasks):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 scripts/test_validate.py`
Expected: all three FAIL/ERROR (`check_all` does not exist).

- [ ] **Step 3: Implement**

In `scripts/validate.py`, delete the `SKILLS_DIR` global. Add `check_all` above `main`, and shrink `main`:

```python
def check_all(root: Path = ROOT):
    """Repo-wide validation: catalogs, every plugin's manifest pair, every
    plugin's skills — discovered from plugins/* AND marketplace sources, so
    an unregistered plugin dir is still validated."""
    errors = list(check_marketplaces(root))
    plugin_dirs = set()
    plugins_root = root / "plugins"
    if plugins_root.is_dir():
        plugin_dirs.update(p.resolve() for p in plugins_root.iterdir() if p.is_dir())
    for rel in (".claude-plugin/marketplace.json", ".plugin/marketplace.json"):
        p = root / rel
        if not p.is_file():
            continue
        try:
            cat = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue  # reported by check_marketplaces
        for entry in cat.get("plugins", []):
            src = entry.get("source")
            if src and (root / src).is_dir():
                plugin_dirs.add((root / src).resolve())
    for plugin in sorted(plugin_dirs):
        errors += check_plugin_manifest_pair(plugin)
        skills_dir = plugin / "skills"
        if skills_dir.is_dir():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir():
                    errors += check_skill(d)
    return errors


def main():
    args = sys.argv[1:]
    if args == ["--all"]:
        errors = check_all()
    elif len(args) == 1:
        errors = check_skill(Path(args[0]).resolve())
    else:
        print(__doc__)
        return 2
    for e in errors:
        print(e)
    print(f"{'FAIL' if errors else 'OK'} — {len(errors)} problem(s)")
    return 1 if errors else 0
```

Update the module docstring's Repo-level section to:

```
Repo-level (--all):
  - root marketplace.json files parse, agree with each other, and every
    plugin `source` names an existing dir whose plugin.json `name` matches
    the marketplace entry
  - every plugin dir (under plugins/ or named as a marketplace source) has
    .claude-plugin/plugin.json and .plugin/plugin.json present, parsed,
    and identical
  - every skill under every plugin's skills/ dir passes the per-skill checks
```

- [ ] **Step 4: Run tests, then the validator on the real repo**

Run: `python3 scripts/test_validate.py` → PASS
Run: `python3 scripts/validate.py --all` → `OK — 0 problem(s)`. Discovery now covers every skill in every plugin (previously only snowplow-workflows) — if newly-discovered skills fail, fix the docs/frontmatter in the same commit and list every such fix in your report.
Run: `python3 scripts/validate.py plugins/snowplow-workflows/skills/debug-failed-events` → `OK — 0 problem(s)` (single-skill mode unchanged).

- [ ] **Step 5: Commit**

```bash
git add scripts/validate.py scripts/test_validate.py plugins/
git commit -m "feat(validate): discover and validate every plugin, registered or not"
```
