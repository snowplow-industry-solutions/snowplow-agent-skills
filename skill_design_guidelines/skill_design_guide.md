# Skill Design Guide

A framework for structuring public Snowplow agent skills so that each kind of knowledge lives in the form that makes it most directly usable.

## Why This Guide Exists

A skill's value is in how directly it gives an agent leverage. The failure mode we're trying to avoid is undifferentiated skills: long SKILL.md files that try to do everything through prose, mixing procedural instructions with judgment frameworks with examples with troubleshooting, all in the same medium. The result is content the agent has to laboriously parse and apply, when it could have been content the agent simply *uses*.

This guide lays out the five forms a skill's content can take, when each is the right choice, and how to combine them. Use it when authoring new skills or reviewing PRs against existing ones.

## The Core Principle

> Every chunk of a skill should answer one question: what form makes this knowledge most directly usable by the agent?

Knowledge has different shapes. Procedures want to be executable. Judgment wants to be explained. Patterns want to be shown. Decisions want to be structured. Failures want to be diagnosed. A well-architected skill recognises these differences and uses the right form for each.

A skill is **deep** in Ousterhout's sense when it hides real complexity behind a simple interface. For skills, "the interface" is what the agent has to read and reason about to use the skill. "The implementation" is the encoded expertise the skill provides. The forms below are the different ways to encode that expertise so the agent can use it without having to reconstruct it.

## The Five Forms

### 1. Scripts

Use scripts when you have a deterministic procedure that should be done the same way every time, regardless of which agent or model is invoking the skill.

**Right for:**
- Mechanical procedures with clear inputs and outputs (validation, code generation, API calls, file transformations)
- Anything correctness-sensitive where you don't want the agent reasoning from first principles each time
- Procedures involving parsing, formatting, or transformations the agent would do worse than purpose-built code
- Operations that should produce structured output the agent then reasons about

**Wrong for:**
- Decisions that depend on context the script can't see
- Anything where the "right answer" varies based on judgment
- Content that needs to teach the agent *why*, not just *how*

**Quality bar:**
- Scripts must fail informatively. An error message should tell the agent what to do next, not just what went wrong. "Schema validation failed: field X has type Y but Iglu expects Z. Try changing the type to Z, or add a custom validator if Y is intentional" is useful. "ValidationError: type mismatch" is not.
- Scripts should have a stable CLI interface documented in the SKILL.md.
- Scripts should be runnable in isolation for debugging. Avoid hidden dependencies on global state.
- Include `--help` output and example invocations.

**Examples in practice:**
- A schema generation script that scaffolds Iglu-compliant JSON schemas from a description
- A validation script that runs `igluctl` and parses output into actionable feedback
- A scaffolding script that generates tracker initialisation code for a chosen framework

### 2. Reference Documentation

Use reference docs when the agent needs to make judgment calls based on context, and you want to encode the *reasoning* a domain expert would apply.

**Right for:**
- Decision frameworks (when to use entity X vs entity Y, when to choose approach A over B)
- Conceptual content that the agent needs to understand to apply correctly to novel cases
- Domain knowledge that's declarative rather than procedural
- Trade-off analysis where there's no universally right answer

**Wrong for:**
- Anything that should be a script (procedural content trapped in prose)
- Step-by-step instructions for mechanical work
- Content the agent has to execute rather than understand

**Quality bar:**
- Each reference doc should have a focused scope. One concept or framework per file.
- Lead with the decision the doc helps the agent make, not the background.
- Include the *why* behind recommendations, not just the *what*. The agent needs reasoning to apply guidance to cases the doc didn't anticipate.
- Acknowledge when the recommendation has limits. "This works well when X, but if Y is true, consider Z instead."

**Examples in practice:**
- A doc on what to track in agent observability (judgment framework, not procedure)
- A doc on schema versioning strategy (when to bump major vs minor)
- A doc on modelling identity across agent traces (conceptual, with worked reasoning)

### 3. Examples

Use examples when you want to anchor the agent's output to known-good shapes, especially for content where conventions are easier to demonstrate than to specify.

**Right for:**
- Reference implementations the agent can pattern-match against
- Canonical examples of well-designed artefacts (schemas, models, configs)
- Cases where "good" is recognisable but hard to articulate as rules
- Showing how multiple pieces fit together end-to-end

**Wrong for:**
- Replacing reference docs. Examples without explanation teach the wrong lesson when the agent's situation differs.
- Examples that are actually templates in disguise (see below)
- Cherry-picked best cases that don't represent realistic complexity

**Quality bar:**
- Examples should be complete and runnable, not fragments.
- Include a README or comment block explaining why this example is shaped the way it is.
- Show realistic complexity, not toy cases. If real schemas have 15 fields, the example should too.
- Where multiple valid approaches exist, show more than one and explain the trade-offs.

**Examples in practice:**
- A full reference implementation of an instrumented LangGraph agent
- A canonical schema for a common event type, with comments explaining each field choice
- An example dbt model showing how to derive a useful table from raw events

### 4. Templates

Use templates when you want the agent to produce something with a known structure but variable content.

**Right for:**
- Boilerplate the agent shouldn't have to reconstruct
- Configuration files with required sections and team conventions baked in
- Skeleton code where the shape is fixed but the logic is filled in per case

**Wrong for:**
- Replacing examples. A template shows the shape; an example shows the shape filled in well.
- Anything where the structure itself is a judgment call. Don't template what should be reasoned about.

**Quality bar:**
- Templates should have clear placeholder markers (`{{ PROJECT_NAME }}`, `<!-- DESCRIBE_EVENT_HERE -->`).
- Include comments explaining what each section is for and what to put there.
- Pair every non-trivial template with at least one example showing it filled in.

**Examples in practice:**
- A SKILL.md template for new skills (this guide could ship one)
- A schema template with required Iglu fields pre-filled and placeholder slots for the rest
- A dbt config template with Snowplow conventions baked in

### 5. Diagnostic / Troubleshooting Content

Use diagnostic content for the unhappy path. This is the form most often missing from skills, and the one that most distinguishes a skill written by someone with scars from one written by someone who only knows the happy path.

**Right for:**
- Common failure modes and their fixes
- "If you see X, check Y, the usual cause is Z" patterns
- Edge cases that catch people out
- Recovery procedures for partial failures

**Wrong for:**
- Bolting onto the end of a skill as an afterthought. Diagnostics should be discoverable from the SKILL.md, not buried.
- Generic "check your config" advice. Diagnostics should be specific to the actual failure modes of the domain.

**Quality bar:**
- Each diagnostic entry should follow the pattern: symptom -> likely cause(s) -> verification step -> fix.
- Cover the failure modes you've actually seen, not the ones you imagine. If you don't have scars yet, ask people who do.
- Cross-reference from the SKILL.md so the agent finds the right diagnostic when something fails, not after the fact.

**Examples in practice:**
- "Events not appearing in the warehouse" with a structured diagnosis path
- "Schema validation failing on free-form fields" with concrete fixes
- "Trace IDs not propagating across async boundaries" with framework-specific guidance

## How to Combine Them

Most non-trivial skills need three or four of these forms. The SKILL.md itself becomes the *index and reasoning layer* that ties them together, not the place where all the knowledge lives.

A typical structure:

```
skill-name/
├── SKILL.md                # Short. Index, decision tree, pointers to the right content.
├── scripts/                # Mechanical procedures
├── reference/              # Judgment frameworks
├── examples/               # Pattern-matching anchors
├── templates/              # Boilerplate scaffolds (if needed)
└── troubleshooting/        # Diagnostic content
```

The SKILL.md should:
1. State what the skill is for and when to use it
2. Walk through the high-level decision tree the agent follows when invoking the skill
3. Point to the right script, doc, example, or template for each branch
4. Surface the most common failure modes with pointers to the relevant troubleshooting

A SKILL.md that's longer than 200-400 lines is almost certainly trying to do too much. If it's that long, content has probably escaped from one of the other forms into the index.

## Setup-Skill Pointers: Hard vs. Soft Dependency

Some skills read per-project config seeded by a setup skill (e.g. `setup-snowplow-context`'s `.snowplow/agent-context.md`). Classify the dependency before deciding whether the SKILL.md points to the setup skill:

- **Hard dependency** — without the config, the skill's output is *wrong*, not just fuzzy. Example: `design-tracking-plan` — a wrong `schema-vendor` produces wrong Iglu URIs, a wrong `schema-workflow` mutates the wrong source of truth.
- **Soft dependency** — the config only sharpens output; the skill degrades gracefully without it. Example: `implement-custom-events`, which delegates its design work to `design-tracking-plan` and relies on that skill's own hard-dependency check rather than repeating it.

Pointer rule: hard-dependency skills carry one explicit pointer line in their context-loading step, offering once to run the setup skill before continuing. Soft-dependency skills carry none — don't cargo-cult the pointer into places where it isn't load-bearing.

Ownership rule: the setup skill is the config file's only writer. Consuming skills use values as written — a formatting difference is never a reason to rewrite the file, since a cosmetic rewrite churns the user's working tree for zero information gain.

## Gotchas, Not Docs Duplication

This repo will eventually cover many Snowplow SDKs, and tracker APIs move with every release. A skill that restates tracker or API mechanics becomes a large, stale duplicate of the official docs. Draw the line by source of truth:

- **Mechanics live in the docs.** Initialisation, method signatures, and config options are fetched at run time via the `fetch-snowplow-docs` skill. A skill body carries none of them — it points the agent at `fetch-snowplow-docs` and lets the live docs answer.
- **The skill body carries what the docs undercover.** Failure modes, the defaults people frequently get wrong, and the mistakes that break downstream models. For example: setting the media player session ID to a static value or to `domain_sessionid` breaks the dbt media model — a gotcha no API reference will tell you.
- **Source gotchas, don't invent them.** The gotchas for a given area live in the relevant skill and are read in at query time. Add only failure modes you can source; an unsourced, imagined one is worse than none — it sends the agent chasing problems that don't exist.

This is the diagnostic form (see form 5) applied at authoring time: the value a skill adds over the docs is the scar tissue, not the happy-path mechanics.

## Choosing the Right Form: A Decision Procedure

When you have a chunk of knowledge to encode, ask in order:

1. **Is this a deterministic procedure with clear inputs and outputs?** -> Script.
2. **Does this teach the agent how to reason about a decision?** -> Reference doc.
3. **Is this a known-good shape the agent should pattern-match against?** -> Example.
4. **Is this boilerplate the agent shouldn't reconstruct?** -> Template.
5. **Is this guidance for when something has gone wrong?** -> Troubleshooting.
6. **Does this belong in the SKILL.md itself as part of the decision tree?** -> Only if it doesn't fit the above. Most content does fit.

## Common Anti-Patterns

**The procedural prose dump.** Step-by-step instructions written as paragraphs in SKILL.md. Almost always wants to be a script, with the SKILL.md just naming the script and explaining when to use it.

**The judgment-free skill.** All scripts and templates, no reference content. Works for the happy path, produces mediocre output for any case requiring judgment. The agent has nothing to reason from when the situation is novel.

**The undifferentiated skill.** Long SKILL.md mixing procedure, reasoning, examples, and troubleshooting all in the same prose. Hard to navigate, hard to maintain, hard for the agent to extract specific guidance from.

**The example-as-template confusion.** A worked example presented as something to copy verbatim, when it should be either a template (with marked placeholders) or an example (illustrating principles to be applied, not copied). Each is fine; conflating them produces output that's a bad copy of the example.

**The afterthought diagnostics.** Troubleshooting content tacked onto the end of a SKILL.md, not discoverable when the agent actually needs it. Diagnostics should be cross-referenced from the SKILL.md and surfaced when failures occur, not buried.

**The over-deep skill.** Skill nested four levels deep with elaborate internal hierarchy. Skills should be flat where possible. Depth lives in the *quality* of the encoded knowledge, not in the layering of files.

## When Skills Are Honest About Their Limits

A skill should acknowledge when it's not the right answer. This is especially important for opinionated skills (like a Snowplow approach to a problem also served by other tools).

A skill that says "use this approach when X, Y, Z; if you're in situation W, consider these alternatives" is more useful and more credible than one that assumes itself into every situation. It also helps the agent make sensible build/buy recommendations rather than railroading the engineer.

## Frontmatter and Packaging Constraints

Separate from the five forms, a few mechanical rules govern whether a skill will actually load once packaged (e.g. zipped and imported into Claude Desktop):

- **Keep the `description` plain text with no angle brackets.** The Claude Desktop skill validator parses the `description` frontmatter for markup and rejects the import with *"SKILL.md description cannot contain XML tags"* if it finds any `<...>`. This bites when a description names a type or a placeholder — an ARRAY-of-STRUCT column, a `List<T>`, a vendor/name placeholder. Reword them in prose ("ARRAY-of-STRUCT columns", "the vendor placeholder"). The SKILL.md **body** may use angle brackets freely; only the `description` is validated this way.
- **Keep the `description` a single concrete line (or two).** It's what the agent reads to decide whether to invoke the skill; a vague description hurts triggering.
- **`name` is kebab-case and matches the skill's directory.**
- **Package as a single top-level folder** containing `SKILL.md` at its root, with `reference/`, `scripts/`, etc. beneath it. Exclude `.DS_Store` and other OS cruft from the zip.

## Review Checklist

When reviewing a new skill or major change:

- [ ] Does the skill fetch tracker/API mechanics via `fetch-snowplow-docs` rather than restating them, carrying only sourced gotchas the docs undercover?
- [ ] Is the `description` plain text with no angle brackets / XML tags, so it passes the Desktop import validator?
- [ ] Is each chunk of content in the form that makes it most directly usable?
- [ ] Does the SKILL.md serve as an index and decision tree, or has it become a dumping ground?
- [ ] Are scripts failing informatively, with errors that tell the agent what to do next?
- [ ] Are reference docs explaining the *why*, not just the *what*?
- [ ] Are examples complete, realistic, and accompanied by enough context to be applied to novel cases?
- [ ] Is troubleshooting content discoverable from the SKILL.md, not buried at the end?
- [ ] Does the skill acknowledge its limits and when alternatives might be better?
- [ ] Is the file structure flat enough that an agent can navigate it without burning context on the layout itself?

## Notes on Maintenance

Skills evolve. As you learn more about how a skill is used in practice, expect to:

- Move content between forms as you understand the shape of the knowledge better
- Add troubleshooting entries as new failure modes surface
- Replace examples with better ones as you see real-world usage
- Tighten the SKILL.md as content escapes into more appropriate forms

A skill that hasn't changed since v1 is probably either perfect (rare) or stale (common). Treat skill maintenance as part of the contract of publishing one.
