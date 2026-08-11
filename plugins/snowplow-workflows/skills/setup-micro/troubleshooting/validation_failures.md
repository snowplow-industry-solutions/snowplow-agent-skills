# Validation Failures (Events in /bad)

When events appear in `/micro/bad` instead of `/micro/good`, it means they failed validation.

## Understanding Bad Events

Check the bad endpoint:

```bash
curl http://localhost:9090/micro/bad | jq
```

Each bad event includes an `errors` array with failure reasons.

## Common Validation Failures

### 1. Schema Not Found

**Error message:**

```json
{
  "level": "error",
  "message": "Could not find schema with key iglu:com.example/my_event/jsonschema/1-0-0 in any repository"
}
```

**Causes:**
- Schema not mounted in Micro
- Schema directory structure incorrect
- Schema file `self` descriptor doesn't match path
- Typo in schema reference

**Solution:**

See `schema_mounting_issues.md` for detailed diagnosis.

Quick checks:
```bash
# Verify schema is mounted
docker exec snowplow-micro ls -la /config/iglu-client-embedded/schemas/com.example

# Check schema self descriptor matches path
jq '.self' path/to/schema/file
```

### 2. Missing Required Field

**Error message:**

```json
{
  "level": "error",
  "message": "$.product_id: is missing but it is required"
}
```

**Cause:**

Event data is missing a field that the schema marks as `required`.

**Solution:**

Either:
- Add the field to your tracking code
- Make the field optional in the schema (if appropriate)

Example fix in tracking code:

```javascript
// Before (missing product_id)
snowplow('trackSelfDescribingEvent', {
  schema: 'iglu:com.example/purchase/jsonschema/1-0-0',
  data: {
    amount: 29.99
    // product_id is missing!
  }
});

// After
snowplow('trackSelfDescribingEvent', {
  schema: 'iglu:com.example/purchase/jsonschema/1-0-0',
  data: {
    product_id: 'prod-123',  // Added
    amount: 29.99
  }
});
```

### 3. Type Mismatch

**Error message:**

```json
{
  "level": "error",
  "message": "$.amount: string found, number expected"
}
```

**Cause:**

Field has wrong data type. Common examples:
- Sending string when number expected: `"123"` vs `123`
- Sending number when string expected: `123` vs `"123"`
- Sending array when object expected

**Solution:**

Fix the data type in your tracking code:

```javascript
// Wrong
data: {
  amount: "29.99"  // String
}

// Correct
data: {
  amount: 29.99  // Number
}
```

### 4. Additional Properties Not Allowed

**Error message:**

```json
{
  "level": "error",
  "message": "$.extra_field: is not defined in the schema and the schema does not allow additional properties"
}
```

**Cause:**

Sending a field that's not defined in the schema, and schema has `"additionalProperties": false`.

**Solution:**

Either:
- Remove the extra field from tracking code
- Add the field to the schema (with proper schema versioning)

### 5. Pattern Mismatch

**Error message:**

```json
{
  "level": "error",
  "message": "$.currency: does not match the regex pattern ^[A-Z]{3}$"
}
```

**Cause:**

Field value doesn't match schema's `pattern` constraint.

**Solution:**

Fix the data to match the pattern:

```javascript
// Wrong
data: {
  currency: "usd"  // Lowercase, fails ^[A-Z]{3}$
}

// Correct
data: {
  currency: "USD"  // Uppercase, matches pattern
}
```

### 6. Value Out of Range

**Error message:**

```json
{
  "level": "error",
  "message": "$.quantity: must have a minimum value of 1"
}
```

**Cause:**

Numeric value violates `minimum`, `maximum`, `minLength`, or `maxLength` constraints.

**Solution:**

Ensure values are within schema constraints:

```javascript
// Wrong
data: {
  quantity: 0  // Below minimum of 1
}

// Correct
data: {
  quantity: 1
}
```

### 7. Enum Value Not Recognized

**Error message:**

```json
{
  "level": "error",
  "message": "$.user_type: does not have a value in the enumeration [free, premium, enterprise]"
}
```

**Cause:**

Field uses a value not listed in schema's `enum`.

**Solution:**

Use one of the allowed values:

```javascript
// Wrong
data: {
  user_type: "trial"  // Not in enum
}

// Correct
data: {
  user_type: "free"  // Valid enum value
}
```

### 8. Invalid Tracker Protocol

**Error message:**

```json
{
  "level": "error",
  "message": "Request body is not a valid Snowplow event payload"
}
```

**Cause:**

Malformed event payload - doesn't match Snowplow's protocol.

**Solution:**

Ensure you're using a valid Snowplow tracker or correctly formatting raw HTTP requests.

For raw requests, use the correct endpoint:
- Page views, structured events: `/i` (GET or POST)
- Self-describing events: `/com.snowplowanalytics.snowplow/tp2` (POST)

## Debugging Workflow

1. **Get the full error:**
   ```bash
   curl http://localhost:9090/micro/bad | jq '.[] | .errors'
   ```

2. **Identify the schema:**
   ```bash
   curl http://localhost:9090/micro/bad | jq '.[] | .schema'
   ```

3. **Compare event data with schema:**
   - Find the schema file
   - Check required fields
   - Check data types
   - Check constraints (min/max, pattern, enum)

4. **Fix the issue** in tracker code or schema

5. **Clear events and re-test:**
   ```bash
   curl -X POST http://localhost:9090/micro/reset
   # Send event again
   curl http://localhost:9090/micro/good | jq
   ```

## Validation Tips

### Test Early

Send test events as soon as you write tracking code:

```bash
python scripts/send_test_event.py --port 9090
python scripts/check_good_bad.py --port 9090
```

### Use Schema Defaults Wisely

Optional fields with defaults can help prevent validation failures:

```json
{
  "properties": {
    "quantity": {
      "type": "integer",
      "default": 1  // Falls back if not provided
    }
  }
}
```

### Validate Schema Before Using

Use `igluctl` to validate schemas before mounting:

```bash
igluctl lint path/to/schemas
```

### Add Unit Tests

Test your tracking code with Micro in CI:

```python
def test_purchase_event_valid():
    # Send event
    send_purchase_event(product_id="123", amount=29.99, currency="USD")

    # Check it's good
    good_events = get_micro_good_events()
    assert len(good_events) == 1
    assert good_events[0]["schema"] == "iglu:com.example/purchase/jsonschema/1-0-0"

    # Check nothing bad
    bad_events = get_micro_bad_events()
    assert len(bad_events) == 0
```

## When Validation Seems Wrong

If you believe an event should validate but Micro rejects it:

1. Check Micro version matches your production Snowplow version
2. Verify schema file syntax with `jq . < schema-file`
3. Test with a minimal event (just required fields)
4. Check for invisible characters (copy/paste issues)
5. Compare with working examples

If issues persist, the schema or event format may need adjustment.
