---
name: setup-snowplow-context
description: "Capture a project's Snowplow working context once — schema vendor, Iglu repositories, Console org and MCP availability, schema workflow, warehouse target, tracked platforms, and collaboration preferences — into .snowplow/agent-context.md so every other Snowplow skill reads it instead of re-asking. Use at project start, or whenever a Snowplow skill can't find the context file. Triggers: set up snowplow context, snowplow project context, snowplow preferences, agent context file."
---

# Setup Snowplow Context

Establish a project's Snowplow working context once and record it in `.snowplow/agent-context.md`, so every later Snowplow skill reads the answers instead of re-asking the user for them.

The file carries eight keys: `schema-vendor`, `iglu-repositories`, `console-org`, `mcp-available`, `schema-workflow`, `warehouse`, `tracked-platforms`, `collaboration-mode`.

## When To Use This Skill

Use this skill when:

- Snowplow work is starting in a project that has no `.snowplow/agent-context.md`.
- Another Snowplow skill reports the context file is missing.
- The project's Snowplow setup has shifted enough that most values need revisiting — a new warehouse, a move from Console-managed to git-backed schemas, a second platform now tracked.

Don't use this skill when:

- One value needs changing — edit `.snowplow/agent-context.md` directly. It is a flat list of keys, and a targeted edit beats a re-interview.
- The job is the actual Snowplow work — designing schemas (`design-tracking-plan`), installing a tracker (`install-snowplow-tracking`), or debugging events (`debug-failed-events`). This skill only records how the project works.

## Instructions

### 1. Read the existing context file first

If `.snowplow/agent-context.md` exists, show the user its current values and ask which ones to correct. Apply their corrections, carry every other key through unchanged, and go to step 4 — the detection and question steps are for a first run.

### 2. Detect before asking

Scan the project before asking anything. Each value found here is one question the user never has to answer.

| Key | Where to look |
|---|---|
| `tracked-platforms` | tracker dependencies: `@snowplow/browser-tracker` or `@snowplow/react-native-tracker` in `package.json`, `SnowplowTracker` in `Podfile`/SPM manifests, `snowplow-android-tracker` in `build.gradle`, tracker packages in `requirements.txt`/`go.mod`/`Gemfile` for server-side |
| `schema-vendor` | `iglu:<vendor>/…` URIs in source and test fixtures, vendor directories under `data-structures/`, `snowtype.config.json` |
| `iglu-repositories` | Iglu resolver config, `snowplow.yml`, a `data-structures/` tree and its git remote |
| `schema-workflow` | a `data-structures/` layout, `snowplow-cli` in CI workflows, or schema JSON under version control → `git-backed`; schemas only reachable through Console → `console-managed` |
| `mcp-available` | Snowplow MCP tools offered in this session (`list_schemas`, `create_schema_version`, and similar) → `yes`; none present → `no` |
| `warehouse` | dbt `profiles.yml` / `dbt_project.yml`, warehouse SDK dependencies, loader config in infrastructure code |
| `console-org` | organization id in `snowtype.config.json`, `snowplow.yml`, or Console URLs in project docs |

Report what was detected alongside the evidence for each, so the user can correct a wrong inference in the same breath as answering the rest.

### 3. Ask once, for the gaps only

Put every undetected key into a single compact numbered list in one message. For each, offer the allowed values from the template and mark your best guess as the default, so the user can reply "all defaults" or answer three of eight. Confirm the detected values in the same message rather than a second round trip.

`collaboration-mode` is never detectable — always ask it, phrased as the user's choice: co-design alongside them question-by-question, or prepare complete proposals for review.

### 4. Write the file

Write `.snowplow/agent-context.md` from `templates/agent-context.md`, keeping the template's key names, order, and header comment exactly. Replace every `{{ … }}` placeholder with the agreed value.

All eight keys are present in every file written. Where a value is genuinely unresolved, write `unknown` and keep the key — other skills branch on reading the key, so a dropped key reads as a broken file rather than an open question.

### 5. Point the project's agent instructions at the file

If `CLAUDE.md` or `AGENTS.md` exists at the repo root, append this line to it, skipping the append when the line is already there:

```
Snowplow project context lives in .snowplow/agent-context.md — read it before any Snowplow work.
```

If both files are absent, create nothing. Tell the user the context file was written and that adding that one line to a `CLAUDE.md` or `AGENTS.md` is what makes other agents find it.

## Templates

- `templates/agent-context.md` — the eight-key context file. Each `{{ … }}` placeholder names the allowed values for that key; replace the whole placeholder with the agreed value.

## Common Failure Modes

- **A skill still asks for the vendor**: the file was written somewhere other than `.snowplow/agent-context.md` at the repo root, or a key was renamed. The eight key names are a contract — match the template.
- **Detection reports the wrong platform**: a tracker package appears in a lockfile or an example directory rather than application code. Verify with a tracker initialisation call before recording the platform.
- **`mcp-available: yes` but Console calls fail**: the MCP is installed and unauthenticated, or is pointed at another organization. This file records availability, not credentials.

## Limits

- Every value is the user's declaration, not a verified fact. Nothing here proves a Console org exists, an MCP is authenticated, or a warehouse is reachable — skills acting on these values still handle failure.
- The file is plaintext in the repository and will usually be committed. It holds names and choices only: keep API keys, tokens, and credentials in the environment or a secret store, never in this file.
- Detection is a heuristic over repository files. A monorepo with several trackers, or a project whose schemas live in a separate repository, needs the user to confirm the values by hand.
