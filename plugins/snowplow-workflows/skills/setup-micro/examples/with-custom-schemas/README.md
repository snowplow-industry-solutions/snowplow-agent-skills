# Snowplow Micro with Custom Schemas

Example showing how to mount and test custom schemas.

## What This Example Shows

- Proper Iglu directory structure for schemas
- Mounting local schemas in Micro
- Testing custom self-describing events
- Schema validation workflow

## Directory Structure

```
with-custom-schemas/
├── README.md
└── schemas/
    └── com.example/
        ├── purchase_event/
        │   └── jsonschema/
        │       └── 1-0-0
        └── user_context/
            └── jsonschema/
                └── 1-0-0
```

## Schema Files

### Purchase Event (schemas/com.example/purchase_event/jsonschema/1-0-0)

```json
{
  "$schema": "http://iglucentral.com/schemas/com.snowplowanalytics.self-desc/schema/jsonschema/1-0-0#",
  "description": "Schema for tracking purchase events",
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
      "description": "Unique product identifier",
      "maxLength": 255
    },
    "product_name": {
      "type": "string",
      "description": "Product name",
      "maxLength": 500
    },
    "amount": {
      "type": "number",
      "description": "Purchase amount",
      "minimum": 0
    },
    "currency": {
      "type": "string",
      "description": "Currency code (ISO 4217)",
      "pattern": "^[A-Z]{3}$"
    },
    "quantity": {
      "type": "integer",
      "description": "Number of items purchased",
      "minimum": 1
    }
  },
  "required": ["product_id", "amount", "currency"],
  "additionalProperties": false
}
```

### User Context (schemas/com.example/user_context/jsonschema/1-0-0)

```json
{
  "$schema": "http://iglucentral.com/schemas/com.snowplowanalytics.self-desc/schema/jsonschema/1-0-0#",
  "description": "Context entity for user information",
  "self": {
    "vendor": "com.example",
    "name": "user_context",
    "format": "jsonschema",
    "version": "1-0-0"
  },
  "type": "object",
  "properties": {
    "user_id": {
      "type": "string",
      "description": "Internal user ID",
      "maxLength": 128
    },
    "user_type": {
      "type": "string",
      "description": "User type classification",
      "enum": ["free", "premium", "enterprise"]
    },
    "account_created_at": {
      "type": "string",
      "description": "ISO 8601 timestamp of account creation",
      "format": "date-time"
    }
  },
  "required": ["user_id", "user_type"],
  "additionalProperties": false
}
```

## Setup

```bash
# From this example directory
cd examples/with-custom-schemas

# Generate config pointing to local schemas
python ../../scripts/setup_micro.py \
  --port 9090 \
  --schemas-path ./schemas
```

## Start Micro

```bash
docker compose up -d
```

## Test Custom Event

Send a purchase event using curl:

```bash
curl -X POST http://localhost:9090/com.snowplowanalytics.snowplow/tp2 \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "iglu:com.snowplowanalytics.snowplow/payload_data/jsonschema/1-0-4",
    "data": [{
      "e": "ue",
      "ue_pr": "{\"schema\":\"iglu:com.snowplowanalytics.snowplow/unstruct_event/jsonschema/1-0-0\",\"data\":{\"schema\":\"iglu:com.example/purchase_event/jsonschema/1-0-0\",\"data\":{\"product_id\":\"prod-123\",\"product_name\":\"Test Product\",\"amount\":29.99,\"currency\":\"USD\",\"quantity\":2}}}",
      "tv": "test-0.1",
      "p": "web",
      "aid": "example-app"
    }]
  }'
```

## Verify

```bash
# Check good events
python ../../scripts/check_good_bad.py --port 9090 --filter-vendor com.example
```

Expected: The purchase event should appear in the good events list.

## Testing Schema Validation

Try sending an invalid event (missing required field):

```bash
curl -X POST http://localhost:9090/com.snowplowanalytics.snowplow/tp2 \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "iglu:com.snowplowanalytics.snowplow/payload_data/jsonschema/1-0-4",
    "data": [{
      "e": "ue",
      "ue_pr": "{\"schema\":\"iglu:com.snowplowanalytics.snowplow/unstruct_event/jsonschema/1-0-0\",\"data\":{\"schema\":\"iglu:com.example/purchase_event/jsonschema/1-0-0\",\"data\":{\"product_id\":\"prod-123\"}}}",
      "tv": "test-0.1",
      "p": "web",
      "aid": "example-app"
    }]
  }'
```

Check bad events:

```bash
curl http://localhost:9090/micro/bad | jq
```

This should show a validation error about missing `amount` and `currency` fields.

## Iterating on Schemas

1. Edit schema file (e.g., add a new optional field)
2. Restart Micro: `docker compose restart`
3. Clear cached events: `curl -X POST http://localhost:9090/micro/reset`
4. Re-test your events

## Integration with Your Tracker

Once schemas are validated in Micro, use them in your tracker:

**JavaScript (browser tracker):**

```javascript
snowplow('trackSelfDescribingEvent', {
  schema: 'iglu:com.example/purchase_event/jsonschema/1-0-0',
  data: {
    product_id: 'prod-123',
    product_name: 'Test Product',
    amount: 29.99,
    currency: 'USD',
    quantity: 2
  }
});
```

**Python (tracker):**

```python
from snowplow_tracker import SelfDescribingJson

tracker.track_self_describing_event(
    SelfDescribingJson(
        'iglu:com.example/purchase_event/jsonschema/1-0-0',
        {
            'product_id': 'prod-123',
            'product_name': 'Test Product',
            'amount': 29.99,
            'currency': 'USD',
            'quantity': 2
        }
    )
)
```

## Common Issues

See `../../troubleshooting/schema_mounting_issues.md` if:
- Schemas aren't being recognized
- Events go to `/bad` with "schema not found"
- Volume mount errors
