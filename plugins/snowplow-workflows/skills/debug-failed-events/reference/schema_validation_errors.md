# Schema Validation Errors

Complete guide to diagnosing and fixing JSON Schema validation errors in Snowplow events.

## Understanding Validation Errors

Schema validation errors occur when an event's data doesn't match the constraints defined in its JSON Schema. The error message indicates what constraint was violated.

## Error: Missing Required Property

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "object has missing required properties: [\"field_name\"]"
}
```

**Diagnosis:**

1. **Check which field is missing** from the error message
2. **Review schema** to confirm field is marked as required
3. **Check tracking code** to see if field is being sent

**Common Causes:**

- Field not included in tracking call
- Field name typo (sent as different name)
- Conditional logic omits field in some cases
- Field is null/undefined (not sent)

**Fixes:**

**Fix 1: Add missing field to tracking code**
```javascript
// Before (missing 'action' field)
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: {
    label: 'Sign Up'
  }
});

// After (added required field)
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: {
    label: 'Sign Up',
    action: 'click'  // Added required field
  }
});
```

**Fix 2: Make field optional in schema** (if field shouldn't be required)
```json
// In schema definition, remove field from "required" array
{
  "required": ["label", "action"]  // Remove "action" if it's optional
}
```

**Fix 3: Provide default value**
```javascript
// Ensure field always has a value
const action = buttonAction || 'unknown';  // Default value
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: {
    label: 'Sign Up',
    action: action
  }
});
```

## Error: Additional Properties Not Allowed

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "object instance has properties which are not allowed by the schema: [\"extra_field\"]"
}
```

**Diagnosis:**

1. **Identify the extra field** from error message
2. **Check if field is defined in schema**
3. **Check if it's a typo** (wrong field name)

**Common Causes:**

- Field sent but not defined in schema
- Typo in field name (e.g., `user_id` vs `userId`)
- Debug fields accidentally included
- Old field from previous schema version

**Fixes:**

**Fix 1: Remove extra field from tracking code**
```javascript
// Before (has extra field 'debug_mode')
trackSelfDescribingEvent({
  schema: 'iglu:com.example/event/jsonschema/1-0-0',
  data: {
    label: 'Sign Up',
    debug_mode: true  // Not in schema
  }
});

// After (removed extra field)
trackSelfDescribingEvent({
  schema: 'iglu:com.example/event/jsonschema/1-0-0',
  data: {
    label: 'Sign Up'
  }
});
```

**Fix 2: Fix field name typo**
```javascript
// Before (wrong field name)
data: {
  userId: '12345'  // Wrong: camelCase
}

// After (corrected to match schema)
data: {
  user_id: '12345'  // Correct: snake_case as defined in schema
}
```

**Fix 3: Add field to schema** (if field should be tracked)
1. Update schema in Console to include the new field
2. Deploy new schema version
3. Update tracking code to use new version

## Error: Type Mismatch

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "instance type (string) does not match any allowed primitive type (number)"
}
```

**Diagnosis:**

1. **Identify field** with type mismatch
2. **Check expected type** in schema (string, number, boolean, etc.)
3. **Check actual value** being sent

**Common Causes:**

- Sending string when schema expects number: `"29.99"` vs `29.99`
- Sending number when schema expects string: `12345` vs `"12345"`
- Sending boolean as string: `"true"` vs `true`
- Null sent when type doesn't allow null

**Fixes:**

**Fix 1: Convert to correct type**
```javascript
// String to number
amount: parseFloat(amountString)  // "29.99" → 29.99
count: parseInt(countString)       // "5" → 5

// Number to string
id: userId.toString()              // 12345 → "12345"

// String to boolean
active: activeString === 'true'    // "true" → true
```

**Fix 2: Allow multiple types in schema** (if appropriate)
```json
// In schema, allow both string and number
{
  "properties": {
    "amount": {
      "type": ["string", "number"]  // Accept both types
    }
  }
}
```

**Fix 3: Allow null** (if field can be null)
```json
{
  "properties": {
    "optional_field": {
      "type": ["string", "null"]  // Can be string or null
    }
  }
}
```

## Error: Enum Violation

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "instance value (\"unknown\") not found in enum (possible values: [\"click\",\"hover\",\"focus\"])"
}
```

**Diagnosis:**

Field value not in allowed enum values list.

**Fixes:**

**Fix 1: Use valid enum value**
```javascript
// Before (invalid value)
data: {
  action: 'unknown'  // Not in enum
}

// After (valid value from enum)
data: {
  action: 'click'  // Valid enum value
}
```

**Fix 2: Add value to enum** (if new value is valid)
Update schema to include new enum value:
```json
{
  "properties": {
    "action": {
      "enum": ["click", "hover", "focus", "unknown"]  // Added "unknown"
    }
  }
}
```

**Fix 3: Map to valid values**
```javascript
// Map any value to valid enum values
const validActions = ['click', 'hover', 'focus'];
const action = validActions.includes(userAction) ? userAction : 'click';  // Default to 'click'
```

## Error: Pattern Validation Failed

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "string does not match pattern \"^[A-Z]{2}$\""
}
```

**Diagnosis:**

Field value doesn't match regex pattern defined in schema.

**Common Patterns:**
- Email: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$`
- URL: `^https?://.*`
- Country code: `^[A-Z]{2}$`
- Date: `^\\d{4}-\\d{2}-\\d{2}$`

**Fixes:**

**Fix 1: Format value correctly**
```javascript
// Before (wrong format)
data: {
  country_code: 'usa'  // Pattern expects 2 uppercase letters
}

// After (correct format)
data: {
  country_code: 'US'   // Matches pattern ^[A-Z]{2}$
}
```

**Fix 2: Validate before sending**
```javascript
// Validate against pattern before tracking
const countryCodePattern = /^[A-Z]{2}$/;
if (!countryCodePattern.test(countryCode)) {
  console.error('Invalid country code:', countryCode);
  return;  // Don't send event with invalid data
}
```

**Fix 3: Update pattern in schema** (if pattern is too restrictive)

## Error: String Length Violation

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "string is too long (length: 150, maximum allowed: 100)"
}
```

**Diagnosis:**

String value exceeds maxLength constraint or is shorter than minLength.

**Fixes:**

**Fix 1: Truncate string**
```javascript
// Truncate to max length
const maxLength = 100;
const description = longDescription.substring(0, maxLength);
```

**Fix 2: Update schema constraints** (if limit is too restrictive)
```json
{
  "properties": {
    "description": {
      "type": "string",
      "maxLength": 200  // Increase limit
    }
  }
}
```

## Error: Number Range Violation

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "numeric instance is lower than the required minimum (minimum: 0, found: -1)"
}
```

**Diagnosis:**

Number value outside allowed range (minimum/maximum constraints).

**Fixes:**

**Fix 1: Clamp value to range**
```javascript
// Ensure value is within range
const amount = Math.max(0, Math.min(1000, userAmount));  // Clamp to 0-1000
```

**Fix 2: Validate before sending**
```javascript
if (amount < 0 || amount > 1000) {
  console.error('Amount out of range:', amount);
  return;  // Don't send invalid event
}
```

## Error: Array Constraints

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "array is too short: must have at least 1 elements but instance has 0 elements"
}
```

**Diagnosis:**

Array doesn't meet minItems/maxItems or uniqueItems constraints.

**Fixes:**

**Fix 1: Ensure array has required elements**
```javascript
// Before (empty array)
data: {
  items: []  // Violates minItems: 1
}

// After (has elements)
data: {
  items: ['item1']  // Meets requirement
}

// Or don't send field if empty and optional
if (items.length > 0) {
  data.items = items;
}
```

**Fix 2: Ensure unique elements** (if uniqueItems: true)
```javascript
// Remove duplicates
const uniqueItems = [...new Set(items)];
```

## Diagnostic Approach

Fetch the schema and compare the failing event field-by-field:

```bash
# Fetch the schema from your registry (-f fails loudly if the schema is missing)
curl -fsS -H "apikey: YOUR_API_KEY" \
  "https://your-org.iglu.snplow.net/api/schemas/com.example/event/jsonschema/1-0-0" > schema.json

# List the schema's required fields and full property definitions
jq '{required, properties}' schema.json

# Extract the entity data that failed validation into entity.json first —
# the fields to compare live in the unstruct_event / context entity payload,
# not at the top level of the bad-row wrapper.
# e.g. for an enriched/pipeline bad row (adjust the path for your format;
# a Micro bad row has no `event` key — its entity sits in the collector
# payload's ue_pr/ue_px tracker parameter, base64-decode ue_px):
jq '.event.unstruct_event.data.data' bad_row.json > entity.json

# Then list its fields:
jq 'keys' entity.json
```

Compare the entity's fields against `required` and `properties`. Check for
missing required fields and unexpected extra fields first, then check each
value against its full property definition — `type`, and equally the
constraint keywords (`enum`, `pattern`, `format`, `minimum`/`maximum`,
array `items`) that the error catalogue above documents.

## Quick Reference

| Error Type | Common Cause | Quick Fix |
|------------|--------------|-----------|
| Missing required property | Field not sent | Add field to tracking code |
| Additional property | Extra field sent | Remove field or add to schema |
| Type mismatch | Wrong data type | Convert to correct type |
| Enum violation | Invalid value | Use value from enum list |
| Pattern mismatch | Wrong format | Format correctly or fix pattern |
| String too long | Exceeds maxLength | Truncate string |
| Number out of range | Violates min/max | Clamp to range |
| Array constraints | Wrong size/duplicates | Add elements or deduplicate |
