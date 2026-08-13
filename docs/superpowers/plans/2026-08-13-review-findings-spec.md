# Spec: validator-hardening review findings (2026-08-13)

Code review of branch `validator-hardening` (PR: validator hardening + dangling-reference repointing) produced 15 confirmed findings. Every finding was verified with an executed reproduction or repo evidence. This spec is the authority for the fix plan.

## Context

The branch did two things:

1. `db9342f` repointed dangling intra-skill references in `debug-failed-events` to real commands (curl/jq replacing deleted helper scripts).
2. `6a67ce3` hardened `scripts/validate.py` (Triggers suffix, manifest pair sync, reserved names, dangling paths) and added `scripts/test_validate.py`.

The review found the replacement commands in (1) frequently give wrong diagnostic answers, and the hardening in (2) has coverage holes, false positives, and crash paths.

## Findings

### Docs — debug-failed-events skill

**F1 (SKILL.md:140 + 4 more sites).** All five new Iglu curl commands embed the `iglu:` URI scheme inside the REST path (`/api/schemas/iglu:com.example/...`). Iglu Server's route is `/api/schemas/{vendor}/{name}/{format}/{version}` — the vendor segment becomes the literal `iglu:com.example`, always 404, teaching the exact wrong diagnosis ("schema not deployed"). Correct prefix-free form exists at `plugins/snowplow-workflows/skills/setup-micro/troubleshooting/iglu_registry_issues.md:31-32`. Sites: SKILL.md:140, SKILL.md:152, reference/schema_resolution_errors.md:43, :203, reference/schema_validation_errors.md:406. At SKILL.md:152 and schema_validation_errors.md:405 the un-flagged curl redirects a 404 body into schema.json.

**F2 (reference/malformed_events.md:86, :344).** `jq '{e, tv, p, aid, dtm, ttm}' event.json` reads the top level, but tracker params sit under `.data[]` of a `payload_data` POST body (or under the raw payload's parameters in a bad row). With the new gloss "(null in the output = missing)" a real POST body reports all six fields missing; the JSON array `/micro/bad` returns hard-errors (`Cannot index array with string "e"`, exit 5).

**F3 (SKILL.md:154; reference/schema_validation_errors.md:412).** `jq 'keys' failed_event.json` lists wrapper keys (`["collectorPayload","errors","timestamp"]`) or array indices (`[0,1]`) — never the failing entity's fields. The field-by-field comparison against the schema's `properties` yields zero overlap and a false "every required property missing" diagnosis. The entity's real fields are nested in the unstruct_event/context data.

**F9 (reference/schema_validation_errors.md:409; SKILL.md:153).** `jq '{required, properties: (.properties | map_values(.type))}'` projects away enum/pattern/format/array constraints (enum/$ref properties render as `null` type), and hard-errors when `properties` is absent or schema.json holds a 404 error body. The closing claim that missing/extra/type checks cover "nearly all validation errors" is wrong for every constraint-based error this same file documents.

**F10 (SKILL.md:202; reference/malformed_events.md:61, :338).** `python3 -m json.tool failed_event.json` validates the wrong layer: a bad-row record is well-formed JSON wrapping the actually-malformed payload, so step 1 of the Malformed Events workflow passes for exactly the error category it exists to detect. The inner payload must be extracted first.

**F11 (reference/malformed_events.md:341).** `wc -c < event.json` measures the on-disk (typically pretty-printed) file and states no threshold. The real constraint defined ~20 lines earlier is compact-serialized size vs a 10000-byte limit. Pretty-printed ~9KB payloads measure >10KB → false "truncate" advice.

**F12 (reference/enrichment_errors.md:139).** `jq . failed_event.json` under "Check if event has required fields for enrichment" is an identity pretty-print — no field check happens; agent marks verification complete without checking the enrichment's inputs (e.g. `useragent` for UA parser, `user_ipaddress` for IP lookup).

### Validator — scripts/validate.py

**F4 (validate.py:118).** Triggers-suffix check: `". " in tail` rejects trigger lists containing abbreviations (`e.g.`, `vs.`) — verified false CI failure; misses trailing prose delimited otherwise (`; do not use...`, `.Second` without space); `rfind("Triggers:")` has no word boundary so `FooTriggers:` passes.

**F5 (validate.py:53).** INTRA_PATH_RE's lookbehind `(?<![\w/.-])` excludes `.` and `/`, so `./scripts/x.py` and `../../scripts/x.py` refs are never validated. Three live refs escape today: setup-micro/examples/with-custom-schemas/README.md:116 (`../../scripts/setup_micro.py`), :150 (`../../scripts/check_good_bad.py`), :229 (`../../troubleshooting/schema_mounting_issues.md`). Deleting those targets keeps `--all` green. Relative refs must resolve against the referencing .md file's directory.

**F6 (validate.py:194).** Marketplace entry with missing/empty `source`: `ROOT / ""` collapses to the repo root (a directory) → "does not exist" error skipped, pair check runs against repo root emitting two nonsense errors, entry-name check never runs, nothing names the malformed entry.

**F7 (validate.py:141).** Concrete-reference filter skips dangling directory refs written without a trailing slash (`` `examples/schema_not_found` `` — the exact bug class this PR fixed — passes silently), extensionless script refs, and globs (`scripts/*.py`; `*` not in char class).

**F8 (validate.py:139).** INTRA_PATH_RE over-matches prose into false errors: sentence-final bare-dir mentions ("in scripts/." → flags `scripts/`), hyphenated prose (`scripts/foo.py-based` checked as a path, reported missing even when scripts/foo.py exists), URL query values (`?f=reference/a.md`; `=` not in lookbehind class).

**F13 (validate.py:204).** `json.loads(...).get("name")` catches only JSONDecodeError; valid-but-non-dict JSON (array/string/number) crashes `--all` with AttributeError instead of a validation error. Also `check_plugin_manifest_pair` passes two equal non-dict manifests, and Python dict equality treats `{"a": true}` and `{"a": 1}` as identical (True == 1) — pair-sync blind spot.

**F14 (validate.py:199, :219).** Coverage keys off the wrong discovery source: pair checks only run for marketplace-registered plugin dirs (an unregistered `plugins/*` dir with drifting manifests passes `--all`), while skill checks only walk hardcoded `SKILLS_DIR` (a properly registered second plugin gets manifest checks but zero skill checks).

### Tests — scripts/test_validate.py

**F15 (test_validate.py:146, :103).** `test_url_path_not_flagged` passes vacuously (extension filter skips `reference/foo` regardless — delete the lookbehind and it stays green). `test_all_official_names_reserved` asserts a hand-copied literal against itself — cannot detect drift. `check_marketplaces` — the function whose control flow the diff rewrote — has zero tests because it reads module-global ROOT.

## Out of scope (parked by review)

- Uncaught decode/IO errors in the `rglob` loop (low severity, didn't make the cut).
- Triple-parse of plugin.json / SKILL.md double-read / docstring drift cleanups (cut by cap).
