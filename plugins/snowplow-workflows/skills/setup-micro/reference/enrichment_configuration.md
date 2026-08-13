# Enrichment Configuration

How to configure enrichments locally in Snowplow Micro.

## When to Configure Enrichments

Configure enrichments when:

- Testing tracking that depends on enriched fields (e.g., user agent parsing, geo-location)
- Validating custom enrichment logic before deploying to production
- Understanding what data will be available downstream after enrichment
- Debugging enrichment issues in a controlled local environment

Skip enrichments if you're only testing basic event structure and schema validation.

## What Are Enrichments?

Enrichments augment raw Snowplow events with additional data. Common enrichments include:

- **UA Parser** - Extracts browser, OS, device info from user agent strings
- **IP Lookup** - Adds geographic data based on IP address
- **Campaign Attribution** - Parses UTM parameters and other campaign codes
- **Currency Conversion** - Converts transaction amounts to a base currency
- **Custom Enrichments** - Your own enrichment logic (JavaScript, API, SQL)

## Enrichment File Structure

Enrichments are configured as JSON files in a directory:

```
enrichments/
├── ua_parser_config.json
├── ip_lookups.json
└── campaign_attribution.json
```

Each file defines one enrichment configuration following the Iglu schema format.

## Common Enrichment Examples

### UA Parser Enrichment

Extracts browser/OS/device from user agent:

```json
{
  "schema": "iglu:com.snowplowanalytics.snowplow/ua_parser_config/jsonschema/1-0-1",
  "data": {
    "vendor": "com.snowplowanalytics.snowplow",
    "name": "ua_parser_config",
    "enabled": true,
    "parameters": {
      "database": "ua-parser.yaml"
    }
  }
}
```

### IP Lookup Enrichment

Adds geographic data (requires MaxMind GeoIP2 database):

```json
{
  "schema": "iglu:com.snowplowanalytics.snowplow/ip_lookups/jsonschema/2-0-0",
  "data": {
    "vendor": "com.snowplowanalytics.snowplow",
    "name": "ip_lookups",
    "enabled": true,
    "parameters": {
      "geo": {
        "database": "GeoLite2-City.mmdb",
        "uri": "http://download.maxmind.com/..."
      }
    }
  }
}
```

**Note:** IP lookup requires downloading the GeoIP2 database. See the example for full setup.

### Campaign Attribution

Parses marketing campaign parameters:

```json
{
  "schema": "iglu:com.snowplowanalytics.snowplow/campaign_attribution/jsonschema/1-0-1",
  "data": {
    "vendor": "com.snowplowanalytics.snowplow",
    "name": "campaign_attribution",
    "enabled": true,
    "parameters": {
      "mapping": "static",
      "fields": {
        "mktMedium": ["utm_medium"],
        "mktSource": ["utm_source"],
        "mktTerm": ["utm_term"],
        "mktContent": ["utm_content"],
        "mktCampaign": ["utm_campaign"]
      }
    }
  }
}
```

## Mounting Enrichments in Micro

The setup script handles this, but for reference:

```yaml
volumes:
  - /absolute/path/to/enrichments:/config/enrichments
environment:
  - MICRO_ENRICHMENTS_PATH=/config/enrichments
```

## Verifying Enrichments Are Applied

After starting Micro with enrichments:

1. Send a test event
2. Check `/micro/good` for the event
3. Look for enriched fields in the event JSON

For example, with UA parser enabled, you should see:

```json
{
  "event": { ... },
  "enriched": {
    "useragent_family": "Chrome",
    "useragent_major": "120",
    "os_family": "Mac OS X",
    "device_family": "Desktop"
  }
}
```

## Enrichment Dependencies

Some enrichments require external resources:

- **IP Lookup** - MaxMind GeoIP2 database file
- **Currency Conversion** - Exchange rate API access
- **API Enrichment** - Access to external API

For local testing, you can:
- Download required databases (GeoIP2)
- Mock API responses
- Disable enrichments that require external dependencies you don't have locally

## Disabling Enrichments

To temporarily disable an enrichment without removing its config:

```json
{
  "data": {
    "enabled": false,  // Set to false
    ...
  }
}
```

## Common Mistakes

### Wrong Schema Version

Enrichment schemas evolve. Make sure you're using the correct schema version for your Micro version.

Wrong (old version):
```json
"schema": "iglu:.../ua_parser_config/jsonschema/1-0-0"
```

Correct (current version):
```json
"schema": "iglu:.../ua_parser_config/jsonschema/1-0-1"
```

Check [Iglu Central](https://github.com/snowplow/iglu-central) for current versions.

### Missing Required Parameters

Each enrichment has required parameters. Missing them causes the enrichment to fail silently.

Refer to the enrichment's schema definition for required vs optional parameters.

### File Naming

Enrichment files can be named anything (e.g., `my-ua-config.json`), but:
- Use `.json` extension
- One enrichment per file
- Descriptive names help when debugging

## When Enrichments Fail

If enrichments aren't applying, check:

1. Micro logs: `docker logs snowplow-micro`
2. Enrichment files are valid JSON
3. Schema versions match what Micro expects
4. External dependencies (databases, APIs) are accessible

For deeper enrichment debugging, use the debug-failed-events skill.

## Enrichments in Micro vs Production

**Differences to be aware of:**

- Some enrichments available in production may not work in Micro (check Micro's documentation)
- Performance characteristics differ (Micro is single-threaded)
- Database versions (GeoIP, etc.) might differ from production

Micro is for **functional testing** of enrichment logic, not for performance or scale testing.
