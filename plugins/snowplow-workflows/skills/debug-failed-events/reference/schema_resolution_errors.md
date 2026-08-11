# Schema Resolution Errors

Diagnosing and fixing "schema not found" and other schema lookup failures.

## Error: Schema Not Found

**Symptom:**
```json
{
  "error": "ResolutionError",
  "message": "Schema iglu:com.example/event_name/jsonschema/1-0-0 not found"
}
```

**Diagnosis Steps:**

### 1. Verify Schema URI

Check for typos or incorrect formatting in the Iglu URI:
- Vendor: `com.example`
- Name: `event_name`
- Format: `jsonschema`
- Version: `1-0-0` (note: hyphens, not dots)

Common mistakes:
- Using dots in version: `1.0.0` instead of `1-0-0`
- Wrong vendor namespace
- Typo in schema name
- Missing or wrong format specification

### 2. Check Schema Exists in Registry

**For Micro testing:**
- Micro uses schemas from DEV environment by default
- Check if schema is deployed to DEV in Snowplow Console

**For pipeline:**
- Check if schema is deployed to the environment your pipeline uses (DEV/PROD)

**To verify:**
```bash
python scripts/check_schema_deployment.py --schema "iglu:com.example/event_name/jsonschema/1-0-0" --environment DEV
```

### 3. Verify Registry Configuration

**For Micro:**
Check Micro's Iglu registry configuration in `docker-compose.yml`:
```yaml
MICRO_IGLU_REGISTRY_URL: https://your-org.iglu.snplow.net/api
MICRO_IGLU_API_KEY: ${SNOWPLOW_IGLU_API_KEY}
```

Ensure:
- Registry URL is correct
- API key is valid and in `.env` file
- Micro can reach the registry (not blocked by firewall)

**For pipeline:**
Check pipeline's Iglu resolver configuration. This varies by deployment.

### 4. Test Registry Connectivity

```bash
# Test if registry is accessible
curl -H "apikey: YOUR_API_KEY" https://your-org.iglu.snplow.net/api/schemas/iglu:com.example/event_name/jsonschema/1-0-0
```

Should return the schema JSON if it exists and is accessible.

## Error: Schema Version Not Found

**Symptom:**
```json
{
  "error": "ResolutionError",
  "message": "Schema iglu:com.example/event/jsonschema/1-0-1 not found. Found versions: 1-0-0"
}
```

**Cause:**
Tracking code references version `1-0-1` but only version `1-0-0` exists in the registry.

**Fix:**

**Option 1: Use existing version (recommended for testing)**
```javascript
// Change tracking code to use correct version
trackSelfDescribingEvent({
  schema: 'iglu:com.example/event/jsonschema/1-0-0',  // Use 1-0-0
  data: { ... }
});
```

**Option 2: Deploy new version**
1. Create schema version `1-0-1` in Snowplow Console
2. Deploy to DEV (for Micro testing) or PROD (for production)
3. Wait for deployment to complete
4. Retry tracking

## Error: Registry Timeout

**Symptom:**
```json
{
  "error": "ResolutionError",
  "message": "Timeout resolving schema from registry"
}
```

**Causes:**
- Registry is down or unreachable
- Network connectivity issues
- API key expired or invalid
- Firewall blocking requests

**Diagnosis:**

1. **Check registry health:**
   ```bash
   curl -I https://your-org.iglu.snplow.net/api/health
   ```

2. **Verify API key:**
   ```bash
   # Test authentication
   curl -H "apikey: YOUR_API_KEY" https://your-org.iglu.snplow.net/api/schemas
   ```

3. **Check network:**
   - Can Micro/pipeline reach the registry?
   - Is a firewall blocking requests?
   - Are there DNS resolution issues?

**Fixes:**

- **Registry down**: Wait for registry to come back online or contact support
- **Network issue**: Fix network connectivity or firewall rules
- **Invalid API key**: Generate new API key in Console and update configuration
- **Timeout too short**: Increase timeout in Micro/pipeline configuration (if applicable)

## Error: Multiple Schema Registries

**Symptom:**
Schema exists in registry A but Micro/pipeline is configured to use registry B.

**Diagnosis:**

Check which registries are configured:
- **Micro**: Check `MICRO_IGLU_REGISTRY_URL` in `docker-compose.yml`
- **Pipeline**: Check Iglu resolver configuration

**Fix:**

Ensure schema is deployed to the registry that Micro/pipeline is using:
1. Identify which registry is configured
2. Deploy schema to that registry
3. Alternatively, update configuration to use the correct registry

## Schema Caching Issues

**Symptom:**
Schema was just deployed but still shows "not found" error.

**Causes:**
- Registry cache not yet refreshed
- Micro/pipeline cache not yet updated
- Schema deployment still in progress

**Fixes:**

1. **Wait for deployment**: Schema deployments can take 1-2 minutes to propagate

2. **Clear Micro cache** (if using Micro):
   ```bash
   # Restart Micro to clear cache
   docker compose restart micro
   ```

3. **Check deployment status**:
   Verify schema deployment completed in Console before testing

4. **Force refresh** (if applicable):
   Some pipeline configurations allow forcing cache refresh

## Prevention

To avoid schema resolution errors:

1. **Deploy schemas before testing**
   - Deploy to DEV before testing with Micro
   - Deploy to PROD before production deployment

2. **Verify Iglu URIs**
   - Use exact URI from Console when implementing tracking
   - Copy-paste to avoid typos

3. **Test schema accessibility**
   ```bash
   # After deployment, verify schema is accessible
   python scripts/check_schema_deployment.py --schema "iglu:com.example/event/jsonschema/1-0-0"
   ```

4. **Document schema versions**
   - Track which version is deployed to which environment
   - Update tracking code when deploying new versions

5. **Use consistent registries**
   - Configure all environments (local, DEV, PROD) to use appropriate registries
   - Document registry URLs for team reference

## Quick Reference

| Error | Most Common Cause | First Step |
|-------|------------------|------------|
| Schema not found | Schema not deployed to environment | Check deployment status in Console |
| Version not found | Wrong version in tracking code | Verify available versions |
| Registry timeout | Network/connectivity issue | Test registry accessibility |
| Multiple registries | Configuration mismatch | Check registry configuration |
| Cache issue | Recent deployment | Wait 1-2 minutes, then retry |
