<!--
  SKILL.md TEMPLATE
  =================
  This template scaffolds a properly structured SKILL.md for a Snowplow agent skill.

  How to use:
  1. Copy this file to your new skill's directory as `SKILL.md`
  2. Replace each {{ PLACEHOLDER }} with content for your skill
  3. Delete the HTML comments (like this one) as you go - they're guidance for the author, not content for the agent
  4. Pair the SKILL.md with scripts, reference docs, examples, templates, and troubleshooting content as appropriate (see SKILL_DESIGN_GUIDE.md)
  5. Keep this file under 200-400 lines. If it grows beyond that, content has probably escaped from the other forms - move it back.

  See SKILL_DESIGN_GUIDE.md for the full framework on when to use scripts vs reference docs vs examples vs templates vs troubleshooting.
-->

---
name: {{ Skill Name }}
description: {{ One or two sentences stating the problem this skill solves and the audience it's for. Be concrete. Plain text only — no angle brackets. }}

<!--
  Good: "Helps engineers design and validate Iglu-compliant Snowplow schemas for self-describing events and context entities, with the conventions and trade-offs that Snowplow's own field engineering team applies."

  Bad: "A skill for working with schemas." (Too vague - doesn't help an agent decide whether to invoke it.)

  HARD CONSTRAINT — keep the description plain text, no angle brackets. The Claude Desktop skill
  validator parses the description for markup and REJECTS the upload with "SKILL.md description
  cannot contain XML tags" if it sees any `<...>`. This bites when you name types or placeholders:
  an ARRAY-of-STRUCT column, a `List<T>`, a vendor/event-name placeholder, an HTML tag. Reword them
  in prose — "ARRAY-of-STRUCT columns", "the vendor/name placeholders". The SKILL.md *body* can use
  angle brackets freely; only the description frontmatter is validated this way.
-->

---

# {{ Skill Name }}

<!--
  Use a clear, action-oriented name. "snowplow-schema-authoring" is good. "schemas" is not.
  Match the directory name. Use kebab-case.
-->


## When To Use This Skill

Use this skill when:

- {{ Specific situation 1 }}
- {{ Specific situation 2 }}
- {{ Specific situation 3 }}

Don't use this skill when:

- {{ Situation where a different skill or approach is better }}
- {{ Situation where this skill would produce mediocre results }}

<!--
  Be honest about the limits. A skill that acknowledges when it's not the right answer is more credible and more useful than one that assumes itself into every situation.

  This section is what the agent reads first to decide whether to invoke the skill at all. Make it concrete enough to support that decision.
-->

## Prerequisites

{{ What needs to be true before the agent invokes this skill. Tools installed, credentials available, files in expected locations, prior decisions made, etc. }}

<!--
  If there are no meaningful prerequisites, delete this section. Don't pad it with generic items like "have a Snowplow account" if those aren't actually preconditions for the skill working.
-->

## Instructions

{{ Workflow the agent follows: branch by scenario (what applies), then concrete steps, validation, and escalation to troubleshooting. This section is the index that ties scripts, reference docs, examples, and templates together. }}

<!--
  This is the heart of the SKILL.md. Combine branching with ordered steps so the agent always knows what to do next.

  Suggested shape:

  0. Dependencies or setup not already covered in Prerequisites.

  1. Identify which scenario applies — route to the right assets:
     - Scenario A → read `reference/scenario_a.md`, then run `scripts/handle_a.py`
     - Scenario B → read `reference/scenario_b.md`, then use `templates/b_template.json`
     - Scenario C → see `examples/scenario_c/` for a worked reference implementation

  2. Execute the path (numbered steps, commands, templates to fill).

  3. Validate when relevant (e.g. `scripts/validate.py` — see `--help` for options).

  4. On failure → `troubleshooting/` (mirror top issues in Common Failure Modes).

  Prefer bullets and short numbered lists; the agent uses this as a navigation aid, not long prose.
-->

## Scripts

{{ List each script with a one-line description and example invocation. }}

<!--
  Example:

  - `scripts/generate_schema.py` - Scaffolds an Iglu-compliant schema from a description.
    Usage: `python scripts/generate_schema.py --vendor com.example --name purchase_event --type event`

  - `scripts/validate.py` - Validates schemas against Iglu Central conventions.
    Usage: `python scripts/validate.py path/to/schema.json`

  Each script's --help should be the source of truth for full usage. This section just orients the agent.

  If your skill has no scripts, delete this section. Don't pad it with content that should be in reference docs.
-->

## Reference Documentation

{{ Pointer to each reference doc with a one-line description of when to consult it. }}

<!--
  Example:

  - `reference/what_to_track.md` - Decision framework for what events to capture and at what granularity. Read this before designing a tracking plan.
  - `reference/schema_versioning.md` - When to bump major vs minor versions. Read this when modifying an existing schema.
  - `reference/identity_modelling.md` - How to model user, session, and trace identity. Read this when the skill is being applied to multi-actor systems.

  If your skill has no reference docs, you probably need some. Skills with only scripts and no reference content tend to produce mediocre output for cases requiring judgment.
-->

## Examples

{{ Pointer to each example with a one-line description of what it demonstrates. }}

<!--
  Example:

  - `examples/ecommerce_purchase/` - Full schema for an e-commerce purchase event with realistic field complexity. Pattern-match against this when designing similar events.
  - `examples/multi_entity_context/` - Reference implementation showing how to combine multiple context entities cleanly.

  Examples should be complete and runnable, not fragments. If you're tempted to ship a fragment, make it a template instead.
-->

## Templates

{{ Pointer to each template with a one-line description and any variables to fill in. }}

<!--
  Example:

  - `templates/event_schema.json` - Skeleton for a self-describing event schema. Fill in {{ VENDOR }}, {{ NAME }}, {{ DESCRIPTION }}, and the properties block.

  If your skill has no templates, delete this section. Templates earn their place by saving meaningful work; a template for two lines of boilerplate isn't worth shipping.
-->

## Common Failure Modes

{{ Top 3-5 things that go wrong, with pointers to detailed diagnostic content. Surface these here so the agent finds them when failures occur, not after the fact. }}

<!--
  Example:

  - **Schema validation fails on free-form fields**: see `troubleshooting/free_form_validation.md`. Usually caused by missing `additionalProperties: false` declarations.
  - **Generated schemas don't load into Iglu**: see `troubleshooting/iglu_load_failures.md`. Usually a vendor namespace issue.
  - **Validation passes but events get rejected at enrichment**: see `troubleshooting/enrichment_rejection.md`. Schema is valid but doesn't match the expected event shape.

  These should be the failure modes you've actually seen, not the ones you imagine. If you don't have scars yet, ask people who do before publishing the skill.
-->

## Limits and Alternatives

{{ Honest acknowledgment of where this skill's approach is the right answer and where it isn't. Pointers to alternative approaches if relevant. }}

<!--
  Example:

  This skill encodes Snowplow's opinionated approach to schema authoring, which is the right answer when:
  - The team is already using Snowplow infrastructure
  - Strong governance and versioning matter
  - Schemas need to be shareable across multiple pipelines

  It's probably not the right approach when:
  - The team needs schema-on-read flexibility (consider a different data modelling pattern)
  - Schemas are throwaway / experimental (Snowplow's governance overhead is costly for short-lived data)

  This section is what makes the skill credible. Skipping it produces skills that feel like sales pitches.
-->

## Maintenance Notes

<!--
  Optional. Useful for skills that have known evolution paths or known gaps that future versions should address. Helps future contributors understand what state the skill is in.

  Example:

  - v1 supports event schemas and context entities. v2 will add support for self-describing JSON in entity fields.
  - The validation script currently uses igluctl 0.x syntax. Migration to 1.x is tracked in <issue link>.

  Delete this section if there's nothing meaningful to say.
-->

---

<!--
  END OF TEMPLATE

  Before publishing, run through the review checklist from SKILL_DESIGN_GUIDE.md:

  - [ ] Is each chunk of content in the form that makes it most directly usable?
  - [ ] Does this SKILL.md serve as an index and decision tree, or has it become a dumping ground?
  - [ ] Are scripts failing informatively, with errors that tell the agent what to do next?
  - [ ] Are reference docs explaining the why, not just the what?
  - [ ] Are examples complete, realistic, and accompanied by enough context to be applied to novel cases?
  - [ ] Is troubleshooting content discoverable from this SKILL.md, not buried at the end?
  - [ ] Does the skill acknowledge its limits and when alternatives might be better?
  - [ ] Is the file structure flat enough that an agent can navigate it without burning context on the layout itself?
-->
