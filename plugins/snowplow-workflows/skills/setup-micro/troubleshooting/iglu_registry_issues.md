# Iglu Registry Connection Issues

Troubleshooting problems when connecting Snowplow Micro to Snowplow Console Iglu registries.

## Symptom 1: Schema Not Found (Despite Being in Console)

**What you see in /bad:**

```json
{
  "errors": [{
    "message": "Could not find schema with key iglu:com.example/my_event/jsonschema/1-0-0 in any repository"
  }]
}
```

### Diagnosis

Check if the schema exists in Console and Micro can access it.

### Verify Schema Exists

**In Snowplow Console:**
1. Log into console
2. Navigate to Data Structures
3. Search for the schema by vendor and name
4. Confirm version exists and is published

**Using API:**
```bash
curl -H "apikey: YOUR_API_KEY" \
  https://com-example.iglu.snplow.net/api/schemas/com.example/my_event/jsonschema/1-0-0
```

Should return the schema JSON if it exists.

### Check Micro Logs

```bash
docker logs snowplow-micro | grep -i iglu
```

Look for:
- Registry loading messages
- Connection errors
- Authentication failures

### Solutions

**If schema doesn't exist in Console:**
- Publish the schema to Console first
- Or mount it locally with `--schemas-path`

**If schema exists but Micro can't find it:**
- Verify URL ends with `/api`
- Check API key has read permissions in Console
- Restart Micro: `docker compose restart`

## Symptom 2: Connection Refused / Network Error

**Logs show:**

```
Connection refused
Unable to connect to Iglu registry
Network unreachable
```

### Diagnosis

Network connectivity or Console URL issues.

### Check URL Format

**Wrong URL (missing protocol):**
```
com-example.iglu.snplow.net/api
```

**Correct:**
```
https://com-example.iglu.snplow.net/api
```

### Test Connection

```bash
curl https://com-example.iglu.snplow.net/api/health
```

Should return a response if Console registry is reachable.

### Solutions

**Fix URL format:**
- Re-run setup script with corrected URL
- Ensure `https://` prefix

**Check network:**
- Verify internet connection
- Check if firewall blocks Docker container
- Try from host: `curl https://registry-url/api/health`

**Restart Docker networking:**
```bash
docker compose down
docker compose up -d
```

## Symptom 3: Authentication Failed

**Logs show:**

```
401 Unauthorized
403 Forbidden
Invalid API key
```

### Diagnosis

API key is missing, expired, or lacks permissions.

### Verify API Key

**Check key is set:**
```bash
docker exec snowplow-micro env | grep MICRO_IGLU_API_KEY
```

Should show the API key (masked).

**Test key manually:**
```bash
curl -H "apikey: YOUR_KEY" \
  https://com-example.iglu.snplow.net/api/schemas
```

Should return schema list if key is valid.

### Solutions

**If key is invalid/expired:**
1. Generate new API key in Snowplow Console: https://console.snowplowanalytics.com/iglu-keys
2. Re-run setup script with new key
3. Restart Micro

**If key is missing:**
- Ensure you passed `--iglu-api-key` to setup script
- Check docker-compose.yml has `MICRO_IGLU_API_KEY` environment variable

**If permissions insufficient:**
- API key needs read access to schemas
- Generate a new key with appropriate permissions in console

## Symptom 4: Wrong Registry URL (404 Not Found)

**Logs show:**

```
404 Not Found
Registry endpoint not found
```

### Common Mistakes

**Missing /api suffix:**
```
Wrong:  https://com-example.iglu.snplow.net
Correct: https://com-example.iglu.snplow.net/api
```

**Typo in URL:**
```
Wrong:  https://com-example.iglu.snowplow.net/api
Correct: https://com-example.iglu.snplow.net/api
```

### Solution

Fix URL and regenerate config:

```bash
python scripts/setup_micro.py --port 9090 \
  --iglu-registry-url https://com-example.iglu.snplow.net/api \
  --iglu-api-key your-key

docker compose restart
```

## Symptom 5: SSL/TLS Certificate Errors

**Logs show:**

```
SSL certificate verification failed
Unable to verify certificate
```

### Cause

Certificate chain issues connecting to Console.

### Solution

This usually indicates a network or configuration issue. Contact Snowplow support for assistance.

## Symptom 6: Slow Schema Resolution

**What happens:**

Events take long time to validate, Micro feels slow.

### Cause

Network latency to Console.

### Solution

**Cache schemas locally:**

After testing, export frequently-used schemas from Console:
```bash
curl -H "apikey: YOUR_KEY" \
  https://registry-url/api/schemas/com.example/my_event/jsonschema/1-0-0 \
  > local-schemas/com.example/my_event/jsonschema/1-0-0
```

Then use `--schemas-path` to load them locally on subsequent runs.

## Debugging Workflow

1. **Verify Console URL and key:**
   ```bash
   curl -H "apikey: YOUR_KEY" https://registry-url/api/schemas
   ```

2. **Check Micro environment:**
   ```bash
   docker exec snowplow-micro env | grep MICRO_IGLU
   ```

3. **Restart with logs:**
   ```bash
   docker compose down
   docker compose up
   # Watch logs for Console connection messages
   ```

4. **Test with simple event:**
   ```bash
   python scripts/send_test_event.py --port 9090
   python scripts/check_good_bad.py --port 9090
   ```

5. **If still failing:**
   - Check Snowplow Console status page
   - Contact Snowplow support

## Console Connection Checklist

When setting up Console connection, verify:

- [ ] URL includes protocol (`https://`)
- [ ] URL ends with `/api`
- [ ] API key created in Console with read permissions
- [ ] Network allows connection from Docker container
- [ ] Schema exists in Console and is published
- [ ] Using latest Micro version

## Getting Help

If issues persist:

1. Gather diagnostics:
   ```bash
   docker logs snowplow-micro > micro-logs.txt
   curl -I https://registry-url/api
   ```

2. Check Snowplow Console status page

3. Contact Snowplow support with:
   - Console registry URL (masked)
   - Micro version
   - Log output
   - Schema URI you're trying to resolve
