# Schema Mounting Issues

## Symptom 1: Events Go to /bad with "Schema Not Found"

**What you see:**

```json
{
  "errors": [
    {
      "level": "error",
      "message": "Could not find schema with key iglu:com.example/my_event/jsonschema/1-0-0 in any repository"
    }
  ]
}
```

## Diagnosis

### Check Directory Structure

Verify your schemas follow Iglu conventions:

```bash
# Should look like this:
schemas/
└── com.example/
    └── my_event/
        └── jsonschema/
            └── 1-0-0
```

**Common mistake:**

```bash
# Wrong - missing vendor/name/format directories
schemas/
└── my_event.json
```

### Check self Descriptor Matches Path

The `self` section in the schema file must match the directory path:

```bash
# File path:
schemas/com.example/my_event/jsonschema/1-0-0

# Must match:
{
  "self": {
    "vendor": "com.example",
    "name": "my_event",
    "format": "jsonschema",
    "version": "1-0-0"
  }
}
```

### Check Volume Mount

Verify the schemas are actually mounted:

```bash
# Check what's inside the container
docker exec snowplow-micro ls -la /config/iglu-client-embedded/schemas
```

You should see your vendor directories. If empty, the mount isn't working.

### Check Micro Logs

```bash
docker logs snowplow-micro
```

Look for schema loading errors at startup.

## Solution 1: Fix Directory Structure

Restructure to match Iglu conventions:

```bash
mkdir -p schemas/com.example/my_event/jsonschema
mv my_event.json schemas/com.example/my_event/jsonschema/1-0-0
```

Then restart Micro:

```bash
docker compose restart
```

## Solution 2: Fix self Descriptor

Edit the schema file to match the path:

```json
{
  "self": {
    "vendor": "com.example",  // Must match directory
    "name": "my_event",        // Must match directory
    "format": "jsonschema",    // Always jsonschema
    "version": "1-0-0"         // Must match filename
  }
}
```

## Solution 3: Fix Volume Mount Path

Check `docker-compose.yml`:

```yaml
volumes:
  # Must be absolute path or relative to docker-compose.yml location
  - /absolute/path/to/schemas:/config/iglu-client-embedded/schemas
```

**On Windows**, use forward slashes or escape backslashes:

```yaml
volumes:
  - C:/Users/YourName/schemas:/config/iglu-client-embedded/schemas
```

## Symptom 2: Permission Denied Errors

**What you see in logs:**

```
Error reading schema file: Permission denied
```

## Diagnosis

Check file permissions:

```bash
ls -la schemas/com.example/my_event/jsonschema/
```

## Solution

Make sure schema files are readable:

```bash
chmod -R +r schemas/
```

On macOS, ensure Docker has file access permissions in System Preferences → Privacy & Security → Files and Folders.

## Symptom 3: Schemas Work Locally But Not in CI

**What happens:**

Schemas validate locally but fail in CI/CD with "schema not found".

## Diagnosis

CI environments may have different:
- Working directory
- File paths
- Docker volume mount behavior

## Solution

Use absolute paths in CI or make paths relative to a known location:

```yaml
# GitHub Actions example
- name: Setup Micro
  run: |
    python scripts/setup_micro.py \
      --schemas-path ${{ github.workspace }}/schemas
```

## Symptom 4: Schema Changes Not Taking Effect

**What happens:**

You edit a schema file but Micro still uses the old version.

## Cause

Micro loads schemas at startup and caches them.

## Solution

Restart Micro after schema changes:

```bash
docker compose restart

# Also clear cached events
curl -X POST http://localhost:9090/micro/reset
```

## Verification

After fixing schema issues:

```bash
# 1. Check schemas are mounted
docker exec snowplow-micro ls -la /config/iglu-client-embedded/schemas/com.example

# 2. Restart Micro
docker compose restart

# 3. Clear events
curl -X POST http://localhost:9090/micro/reset

# 4. Send test event
python scripts/send_test_event.py --port 9090

# 5. Check it went to /good
curl http://localhost:9090/micro/good | jq
```

## Prevention Checklist

Before setting up schemas:

- [ ] Use correct Iglu directory structure (vendor/name/format/version)
- [ ] `self` descriptor matches file path exactly
- [ ] Schema files are valid JSON (use `jq . < schema-file` to validate)
- [ ] Use absolute paths in docker-compose.yml
- [ ] Files are readable (check permissions)
- [ ] Restart Micro after schema changes
