# Enrichment Errors

Diagnosing and fixing Snowplow enrichment failures.

## Overview

Enrichment errors occur when an enrichment process fails to execute successfully. Unlike schema validation errors (which happen before enrichments), enrichment errors occur after events pass schema validation.

## Common Enrichment Error Patterns

### API Enrichment Timeout

**Symptom:**
```
Enrichment 'api_enrichment_name' timed out after 5000ms
```

**Causes:**
- External API is slow or unresponsive
- Network latency
- API rate limiting
- Timeout configured too short

**Fixes:**
1. Check external API availability and response times
2. Increase timeout in enrichment configuration
3. Implement retry logic in API
4. Consider caching for frequently accessed data

### API Enrichment Authentication

**Symptom:**
```
API enrichment failed: 401 Unauthorized
```

**Causes:**
- Invalid API credentials
- Expired authentication token
- Missing authentication header

**Fixes:**
1. Verify API credentials are current
2. Refresh authentication tokens
3. Check API key permissions
4. Ensure credentials are properly configured in enrichment

### Lookup Table Missing

**Symptom:**
```
SQL enrichment failed: Table 'lookup_table' does not exist
```

**Causes:**
- Lookup table not created or populated
- Wrong table name in enrichment configuration
- Database connection issue

**Fixes:**
1. Verify lookup table exists in database
2. Check table name in enrichment configuration
3. Ensure database is accessible
4. Populate table with required data

### Invalid Enrichment Configuration

**Symptom:**
```
Enrichment configuration error: Invalid JSON
```

**Causes:**
- Malformed enrichment JSON configuration
- Missing required configuration fields
- Invalid parameter values

**Fixes:**
1. Validate enrichment JSON against schema
2. Check for syntax errors (missing commas, quotes, etc.)
3. Verify all required fields are present
4. Ensure parameter values are valid types

### Field Not Found in Event

**Symptom:**
```
Enrichment failed: Field 'user_id' not found in event
```

**Causes:**
- Enrichment expects field that doesn't exist in event
- Field name typo in enrichment configuration
- Event variation without required field

**Fixes:**
1. Verify field exists in event payload
2. Check field name spelling in enrichment config
3. Make enrichment conditional on field presence
4. Add field to tracking code if missing

## Diagnosis Workflow

### 1. Identify Failing Enrichment

Check error message for enrichment name:
```
Error in enrichment 'ip_lookups': ...
```

### 2. Review Enrichment Configuration

Check enrichment configuration in your pipeline:
- Verify parameters are correct
- Ensure external dependencies are configured
- Check for recent changes

### 3. Test Enrichment Isolation

If possible, test the enrichment with sample data:
```bash
# Example: Test API enrichment endpoint directly
curl -X POST https://api.example.com/enrich \
  -H "Authorization: Bearer TOKEN" \
  -d '{"field": "value"}'
```

### 4. Check External Dependencies

For enrichments with external dependencies:
- **API enrichments**: Verify API is accessible and responding
- **Database enrichments**: Check database connectivity
- **File-based enrichments**: Ensure files are accessible

### 5. Review Event Data

Check if event has required fields for enrichment:
```bash
jq . failed_event.json
```

## Platform-Specific Enrichments

### IP Lookup Enrichments

**Common Issues:**
- MaxMind database not updated
- Invalid IP address format
- Database file not accessible

**Fixes:**
- Update MaxMind database file
- Validate IP address before enrichment
- Ensure database path is correct

### UA Parser Enrichment

**Common Issues:**
- User agent string malformed
- Parser database outdated

**Fixes:**
- Validate user agent string format
- Update UA parser database
- Handle edge cases with unknown UAs

### Campaign Attribution

**Common Issues:**
- UTM parameters missing or malformed
- Invalid URL encoding

**Fixes:**
- Validate UTM parameters before tracking
- Properly URL-encode parameters
- Set defaults for missing parameters

## Prevention

### 1. Test Enrichments Before Deployment

Test enrichments with sample events: run them in Snowplow Micro with the
enrichment configuration mounted (see the setup-micro skill), send a sample
event, and confirm it lands in `/micro/good` with the expected derived
context attached.

### 2. Monitor External Dependencies

- Set up health checks for API endpoints
- Monitor database availability
- Track enrichment success rates

### 3. Implement Graceful Failures

Configure enrichments to:
- Continue processing on non-critical enrichment failures
- Log failures for investigation
- Provide default values when enrichment fails

### 4. Document Dependencies

Document all enrichment dependencies:
- Required external APIs
- Database tables and schemas
- File paths and formats
- Credentials and authentication

## Quick Reference

| Enrichment Type | Common Failure | First Check |
|-----------------|----------------|-------------|
| API Enrichment | Timeout/Auth | API accessibility and credentials |
| SQL Enrichment | Table not found | Database connection and table existence |
| IP Lookup | Database missing | MaxMind database file location |
| UA Parser | Parse failure | User agent string format |
| Custom Enrichment | Configuration | JSON configuration syntax |

## Debugging Tools

```bash
# Test API enrichment endpoint
curl -v https://api.example.com/endpoint

# Check database connectivity
psql -h hostname -U username -d database

# Validate enrichment configuration JSON syntax
python3 -m json.tool enrichment.json
```

To test an enrichment end to end, run it in Micro with the configuration
mounted (see the setup-micro skill) and send a sample event through.

## Further Reading

For enrichment-specific documentation, fetch from Snowplow docs:
```
fetch_documentation_page('/docs/enriching-your-data/available-enrichments/')
```
