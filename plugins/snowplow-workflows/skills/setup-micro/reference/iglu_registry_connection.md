# Iglu Registry Connection

How to connect Snowplow Micro to an Iglu registry, including Snowplow Console registries.

## What is an Iglu Registry?

An Iglu registry in Snowplow Console hosts your data structure schemas. Instead of mounting schemas locally, you can point Micro to your Console registry where schemas are centrally managed.

## When to Use Registry Connection

Connect to your Snowplow Console registry when:

- Using schemas managed in Snowplow Console
- Working with a team sharing schemas in Console
- Testing against production or staging schemas without duplicating files locally
- Validating that schemas published to Console are correct

Use local schema mounting when:

- Developing new schemas that aren't published yet
- Testing schema changes before publishing
- Working offline

## Getting Registry Credentials

### From Snowplow Console

1. Log into Snowplow Console
2. Navigate to **Iglu API Keys**: https://console.snowplowanalytics.com/iglu-keys
3. Click **Create API Key** and give it read permissions
4. Copy the generated API key
5. Find your Iglu registry URL in the console (format: `https://com-example.iglu.snplow.net/api`)

## Configuration

### Required Information

- **Registry URL**: Full URL including protocol and `/api` suffix
  - Format: `https://com-example.iglu.snplow.net/api`
  - Note: Static registries like Iglu Central don't need `/api`: `https://iglucentral.com`

- **API Key**: Authentication token from Snowplow Console

### Setup Command

```bash
python scripts/setup_micro.py --port 9090 \
  --iglu-registry-url https://com-example.iglu.snplow.net/api \
  --create-env-file
```

The script will:
- Validate the URL format
- Warn if `/api` suffix is missing (for non-static registries)
- Generate `docker-compose.yml` with secure environment configuration
- Create a `.env` template file for your API key

**After running the script, edit `.env` and add your API key:**

```bash
# .env file
SNOWPLOW_IGLU_API_KEY=your-actual-api-key-here
```

**Important:** Add `.env` to your `.gitignore` to avoid committing secrets!

## URL Format Rules

### Include Full Protocol

**Wrong:**
```
com-example.iglu.snplow.net/api
```

**Correct:**
```
https://com-example.iglu.snplow.net/api
```

### Include /api Suffix

**Correct for Snowplow Console:**
```
https://com-example.iglu.snplow.net/api
```

**Exception - Iglu Central (public schemas):**
```
https://iglucentral.com
```

## Combining with Local Schemas

You can use both a registry connection and local schemas:

```bash
python scripts/setup_micro.py --port 9090 \
  --iglu-registry-url https://com-example.iglu.snplow.net/api \
  --schemas-path ./local-schemas \
  --create-env-file

# Then add your API key to .env
```

Micro will:
1. Check local schemas first
2. Fall back to the remote registry if schema not found locally

This is useful for:
- Testing new schemas locally while using published schemas from Console
- Overriding Console schemas temporarily for testing

## Schema Resolution Order

When Micro receives an event referencing a schema:

1. **Embedded schemas** (Snowplow built-in schemas)
2. **Local schemas** (if `--schemas-path` is provided)
3. **Console registry** (if `--iglu-registry-url` is provided)
4. **Iglu Central** (public Snowplow schemas)

## Verifying Connection

After starting Micro with Console registry connection:

1. Check Micro logs for registry loading:
   ```bash
   docker logs snowplow-micro | grep -i iglu
   ```

2. Send an event using a schema from Console
3. Check if event validates:
   ```bash
   python scripts/check_good_bad.py --port 9090
   ```

If the schema is found and event validates, Console connection is working.

## Security Best Practices

### Why .env File Approach?

The setup script uses a `.env` file for API keys to prevent:

1. **Shell history exposure** - API keys don't appear in command history
2. **Process listing exposure** - API keys aren't visible in `ps` output
3. **Version control leaks** - `.env` stays local when in `.gitignore`

### API Key Storage

The `.env` file keeps credentials secure and local:

```bash
# .env file (add to .gitignore)
SNOWPLOW_IGLU_API_KEY=your-api-key-here
```

Docker Compose automatically loads this file and makes variables available to the container.

### Best Practices

- ✅ **DO**: Store API keys in `.env` file
- ✅ **DO**: Add `.env` to `.gitignore`
- ✅ **DO**: Rotate API keys regularly
- ✅ **DO**: Use read-only API keys for Micro
- ❌ **DON'T**: Pass API keys as command-line arguments
- ❌ **DON'T**: Commit `.env` to version control
- ❌ **DON'T**: Share API keys in chat or documentation

## Common Use Cases

### Testing Production Schemas Locally

```bash
python scripts/setup_micro.py --port 9090 \
  --iglu-registry-url https://prod.iglu.snplow.net/api \
  --create-env-file

# Then edit .env and add:
# SNOWPLOW_IGLU_API_KEY=your-prod-read-only-key
```

Now local tracking sends events validated against production schemas in Console.

### Developing New Schema + Using Published Schemas

```bash
python scripts/setup_micro.py --port 9090 \
  --schemas-path ./new-schemas \
  --iglu-registry-url https://com-example.iglu.snplow.net/api \
  --create-env-file

# Edit .env with your API key
```

New schemas in `./new-schemas` are tested locally, while existing schemas come from Console.

### Team Development

All team members point to the same Console registry:

```bash
python scripts/setup_micro.py --port 9090 \
  --iglu-registry-url https://team.iglu.snplow.net/api \
  --create-env-file

# Each team member adds their own API key to .env (not shared)
```

Everyone tests against the same schemas managed in Console, with individual API keys.

## Limitations

- Micro only reads from Console (doesn't publish schemas)
- Changes to Console schemas require restarting Micro to refresh
- Network connectivity required (use local schemas for offline work)

## Troubleshooting

See `troubleshooting/iglu_registry_issues.md` for:
- Connection failures
- Authentication errors
- Schema not found despite being in registry
