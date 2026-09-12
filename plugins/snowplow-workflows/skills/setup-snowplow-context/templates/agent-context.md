# Snowplow Agent Context

<!-- Written by the setup-snowplow-context skill. Other Snowplow skills read this
     file instead of re-asking, and leave it byte-for-byte unchanged — values are
     used as written, whatever their formatting. Edit values directly or re-run
     the skill. -->

- schema-vendor: {{ e.g. com.acme }}
- iglu-repositories: {{ e.g. Iglu Central + git repo URL or Console registry }}
- console-org: {{ org-name (org-id) — e.g. Acme Corp (b2f4c8d0-1234-…) — or "none" }}
- mcp-available: {{ yes | no — is the official snowplow plugin / MCP installed? }}
- schema-workflow: {{ git-backed | console-managed }}
- warehouse: {{ snowflake | bigquery | databricks | redshift | athena | none-yet }}
- tracked-platforms: {{ e.g. web, ios, android, server-side }}
- collaboration-mode: {{ co-design | review-only — should the agent design alongside the user or prepare complete proposals for review? }}
