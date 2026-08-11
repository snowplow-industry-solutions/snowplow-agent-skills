# Schema Mounting

How to structure and mount local schema files so Snowplow Micro recognizes them.

## When to Mount Custom Schemas

Mount local schemas when:

- Testing tracking implementations that use custom self-describing events or entities
- Iterating on schema design before publishing to a production Iglu registry
- Working with proprietary schemas that aren't in Iglu Central
- Testing schema changes locally before deploying to production

You don't need custom schemas if you're only testing Snowplow's standard events (page views, structured events with no custom schemas).

## Directory Structure

Snowplow Micro expects schemas to follow Iglu's directory structure:

```
schemas/
└── com.example/          # Vendor namespace
    └── event_name/       # Schema name
        └── jsonschema/   # Format (always jsonschema for Snowplow)
            └── 1-0-0     # Version (MAJOR-MINOR-PATCH)
```

Example with multiple schemas:

```
my-schemas/
├── com.example/
│   ├── purchase_event/
│   │   └── jsonschema/
│   │       ├── 1-0-0
│   │       └── 1-0-1
│   └── user_context/
│       └── jsonschema/
│           └── 1-0-0
└── com.mycompany/
    └── page_metadata/
        └── jsonschema/
            └── 1-0-0
```

## Schema File Format

Each schema file must be valid Iglu-compliant JSON. Minimal example:

```json
{
  "$schema": "http://iglucentral.com/schemas/com.snowplowanalytics.self-desc/schema/jsonschema/1-0-0#",
  "description": "Schema for purchase events",
  "self": {
    "vendor": "com.example",
    "name": "purchase_event",
    "format": "jsonschema",
    "version": "1-0-0"
  },
  "type": "object",
  "properties": {
    "product_id": {
      "type": "string",
      "description": "Unique product identifier"
    },
    "amount": {
      "type": "number",
      "description": "Purchase amount"
    }
  },
  "required": ["product_id", "amount"],
  "additionalProperties": false
}
```

## Common Mistakes

### Wrong Directory Structure

**Wrong:**
```
schemas/
└── purchase_event.json  # Missing vendor and version directories
```

**Correct:**
```
schemas/
└── com.example/
    └── purchase_event/
        └── jsonschema/
            └── 1-0-0
```

### Mismatched self Descriptor

The `self` section in the schema file **must** match the directory path:

**Wrong:**
```
Path: schemas/com.example/purchase/jsonschema/1-0-0
self.vendor: com.mycompany  # Doesn't match!
```

**Correct:**
```
Path: schemas/com.example/purchase/jsonschema/1-0-0
self.vendor: com.example
self.name: purchase
self.version: 1-0-0
```

### Missing additionalProperties

Always explicitly set `additionalProperties: false` to prevent unexpected fields:

**Risky:**
```json
{
  "type": "object",
  "properties": { ... }
  // additionalProperties defaults to true!
}
```

**Better:**
```json
{
  "type": "object",
  "properties": { ... },
  "additionalProperties": false
}
```

## Mounting in Docker

The setup script handles this automatically, but for reference:

```yaml
volumes:
  - /absolute/path/to/schemas:/config/iglu-client-embedded/schemas
```

**Important:** Use absolute paths. Relative paths can cause issues depending on where Docker Compose is run.

## Verifying Schemas Are Loaded

After starting Micro with custom schemas:

1. Send a test event using one of your custom schemas
2. Check the `/micro/good` endpoint - if your schema is recognized, the event appears there
3. If the event goes to `/micro/bad`, check the error message - it usually indicates schema not found or validation failure

## Iterating on Schemas

When modifying schemas locally:

1. Edit the schema file
2. Restart Micro to pick up changes: `docker compose restart`
3. Clear cached events: `curl -X POST http://localhost:9090/micro/reset`
4. Re-test your events

**Note:** Micro loads schemas at startup. Changes to schema files won't be picked up without a restart.

## When Schemas Fail to Load

See `troubleshooting/schema_mounting_issues.md` for:
- Schema validation errors
- Directory permission issues
- Volume mount problems on different operating systems
