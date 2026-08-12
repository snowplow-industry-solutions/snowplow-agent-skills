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
