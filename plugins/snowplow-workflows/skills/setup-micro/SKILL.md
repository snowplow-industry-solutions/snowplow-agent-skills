---
name: setup-micro
description: "Set up Snowplow Micro locally for testing tracking implementations — Docker configuration, mounting custom schemas, connecting Iglu registries, and enabling enrichments. Use before validating any new or changed tracking. Triggers: Snowplow Micro, set up Micro, local pipeline, mount schemas, test tracking locally."
---

# Setup Micro

## When To Use This Skill

Use this skill when:

- Setting up a local Snowplow testing environment
- Testing schema changes locally before deploying to production
- Validating tracking implementations without sending data to production
- Debugging enrichment configurations locally

Don't use this skill when:

- Testing at scale (Micro is for functional testing, not load testing)
- The team needs a persistent shared testing environment (use hosted Snowplow Micro in Snowplow Console)

## Prerequisites

- Docker installed and running
- Docker Compose v2+ installed
- (Optional) Local schema files in Iglu-compatible structure
- (Optional) Enrichment configuration files

## Instructions

### 1. Determine requirements

Ask the user:
- Need to mount local schemas? Get the path.
- Need custom enrichments? Get the path.
- Need to connect to an Iglu registry (e.g., Snowplow Console)?
  - **IMPORTANT:** Ask the user directly to provide their Iglu registry URL in the conversation. Do NOT attempt to read it from files or use tools to find it.
  - Format example: `https://com-example.iglu.snplow.net/api`
  - Get the registry URL (NOT the API key - that will be stored securely in `.env`).
- What port? (Default: 9090)

**Security Note:** NEVER ask the user to paste API keys directly. The setup script provides instructions for users to manually create a `.env` file where they can securely store credentials locally.

### 2. Generate configuration

Run the setup script:

```bash
python scripts/setup_micro.py --port 9090 \
  [--schemas-path PATH] \
  [--enrichments-path PATH] \
  [--iglu-registry-url URL] \
  [--create-env-file]
```

The script generates:
- `docker-compose.yml` - Docker configuration
- Instructions for manually creating a `.env` file (if using Iglu registry)

**Important:** If using an Iglu registry, the user must manually create a `.env` file with their API key:
```
SNOWPLOW_IGLU_API_KEY=their-actual-api-key
```

This approach keeps credentials out of:
- Command-line history
- Process listings
- Version control (when `.env` is in `.gitignore`)

**Configuration guides:**
- Local schemas: `reference/schema_mounting.md` - directory structure requirements
- Enrichments: `reference/enrichment_configuration.md` - configuration format
- Iglu registry: `reference/iglu_registry_connection.md` - connecting to Snowplow Console or custom registries

### 3. Start Micro

```bash
docker compose up -d
```

### 4. Validate

```bash
python scripts/validate_micro.py --port 9090
```

### 5. Test

Send a test page_view event:

```bash
python scripts/send_test_event.py --port 9090
```

Check that the event was received:

```bash
python scripts/check_good_bad.py --port 9090
```

To manually inspect events in a browser, open `http://localhost:9090/micro/ui`.

### 6. Troubleshoot failures

If issues occur:
- Schema not found → `troubleshooting/schema_mounting_issues.md`
- Events going to /bad → `troubleshooting/validation_failures.md`
- Iglu registry connection issues → `troubleshooting/iglu_registry_issues.md`
- Docker problems → `troubleshooting/docker_issues.md`

## Scripts

- `scripts/setup_micro.py` - Generate docker-compose.yml with optional schema/enrichment mounting
- `scripts/validate_micro.py` - Verify Micro is running correctly
- `scripts/send_test_event.py` - Send a test page_view event
- `scripts/check_good_bad.py` - Query /good endpoint to see received events

Run any script with `--help` for usage details.

## Reference Documentation

- `reference/schema_mounting.md` - How to structure and mount local schemas (Iglu conventions, common mistakes)
- `reference/enrichment_configuration.md` - How to configure enrichments (common enrichments, dependencies)
- `reference/iglu_registry_connection.md` - How to connect to Iglu registries including Snowplow Console

## Example

- `examples/with-custom-schemas/` - Complete example with realistic schema structure and usage instructions

## Common Failures

- **Schemas not recognized** → Check Iglu directory structure in `troubleshooting/schema_mounting_issues.md`
- **Events in /bad** → Validation errors, see `troubleshooting/validation_failures.md`
- **Registry connection fails** → See `troubleshooting/iglu_registry_issues.md`
- **Docker issues** → Container won't start, see `troubleshooting/docker_issues.md`

## Limits

Micro is for local functional testing, not:
- Load/performance testing
- Persistent event storage
- Production use

For shared/staging environments, deploy a full Snowplow pipeline instead.
