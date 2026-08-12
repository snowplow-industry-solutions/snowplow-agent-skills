# Malformed Events

Handling corrupt, incomplete, or improperly formatted event payloads.

## Overview

Malformed events fail before schema validation because the event structure itself is invalid. These are fundamental formatting issues, not schema violations.

## Invalid JSON Structure

**Symptom:**
```
Parse error: Invalid JSON at line 12, column 5
```

**Common Causes:**

1. **Missing or extra commas**
```javascript
// Wrong: trailing comma
{
  "field1": "value",
  "field2": "value",  // Trailing comma not allowed in JSON
}

// Correct
{
  "field1": "value",
  "field2": "value"
}
```

2. **Unquoted field names**
```javascript
// Wrong: unquoted
{
  fieldName: "value"
}

// Correct
{
  "fieldName": "value"
}
```

3. **Single quotes instead of double quotes**
```javascript
// Wrong: single quotes
{
  'field': 'value'
}

// Correct: double quotes
{
  "field": "value"
}
```

**Diagnosis:**
```bash
python scripts/validate_event_json.py --event-file event.json
```

**Fixes:**
1. Use `JSON.stringify()` to ensure valid JSON
2. Validate JSON before sending
3. Use a JSON linter in development

## Missing Required Snowplow Fields

**Symptom:**
```
Error: Missing required platform field 'e' (event type)
```

**Required Snowplow Fields:**
- `e`: Event type (pv, se, ue, etc.)
- `tv`: Tracker version
- `p`: Platform (web, mob, srv, etc.)
- `aid`: Application ID
- `dtm` or `ttm`: Timestamp

**Diagnosis:**
Check event payload for these fields:
```bash
python scripts/validate_event_json.py --event-file event.json --check-snowplow-fields
```

**Fixes:**

Ensure tracker is properly initialized:
```javascript
// Proper initialization sets required fields automatically
newTracker('sp', collectorEndpoint, {
  appId: 'my-app',         // Sets 'aid'
  platform: 'web'          // Sets 'p'
});

// Tracker automatically adds:
// - 'tv' (tracker version)
// - 'e' (event type based on tracking method)
// - 'dtm' (timestamp)
```

## Character Encoding Issues

**Symptom:**
```
Parse error: Invalid UTF-8 sequence
```

**Common Causes:**
- Non-UTF-8 characters in event data
- Improperly escaped special characters
- Emoji or unicode without proper encoding

**Fixes:**

1. **Ensure UTF-8 encoding**
```javascript
// Properly encode special characters
const description = encodeURIComponent(userInput);
```

2. **Escape special characters**
```javascript
// Escape quotes, backslashes, etc.
const sanitized = rawString
  .replace(/\\/g, '\\\\')
  .replace(/"/g, '\\"')
  .replace(/\n/g, '\\n');
```

3. **Handle emoji properly**
```javascript
// Emoji are valid UTF-8, but ensure proper encoding
const text = "Product review: 👍";  // Valid if properly encoded as UTF-8
```

## Oversized Events

**Symptom:**
```
Error: Event payload exceeds maximum size (10KB)
```

**Causes:**
- Very long strings in event data
- Large arrays or nested objects
- Binary data incorrectly included

**Fixes:**

1. **Truncate long strings**
```javascript
const maxLength = 1000;
const description = longText.substring(0, maxLength);
```

2. **Paginate large arrays**
```javascript
// Don't send entire large array in one event
// Instead, send multiple events or summary statistics
if (items.length > 100) {
  // Send summary instead
  data.itemCount = items.length;
  data.itemSample = items.slice(0, 10);
} else {
  data.items = items;
}
```

3. **Use references for large data**
```javascript
// Instead of including large data, reference it
data.dataUrl = "https://example.com/data/123";
// Rather than:
// data.largePayload = { ... }  // Avoid
```

## Circular References

**Symptom:**
```
TypeError: Converting circular structure to JSON
```

**Cause:**
Object contains circular reference that can't be serialized to JSON.

**Example:**
```javascript
const obj = {};
obj.self = obj;  // Circular reference
JSON.stringify(obj);  // Error!
```

**Fixes:**

1. **Remove circular references**
```javascript
// Don't include parent references
const cleanData = {
  id: object.id,
  name: object.name
  // Don't include: parent: object.parent
};
```

2. **Use a circular reference remover**
```javascript
function removeCircular(obj) {
  const seen = new WeakSet();
  return JSON.parse(JSON.stringify(obj, (key, value) => {
    if (typeof value === 'object' && value !== null) {
      if (seen.has(value)) {
        return '[Circular]';
      }
      seen.add(value);
    }
    return value;
  }));
}
```

## Null/Undefined Values

**Symptom:**
Event contains `undefined` or fails serialization.

**Cause:**
JavaScript `undefined` is not valid JSON (but `null` is).

**Fixes:**

```javascript
// Wrong: undefined is not valid JSON
data.optionalField = undefined;  // Will be omitted or cause error

// Correct: use null for empty values
data.optionalField = null;  // Valid JSON

// Or omit the field entirely
if (value !== undefined && value !== null) {
  data.optionalField = value;
}
```

## Invalid Data Types

**Symptom:**
```
Error: Cannot serialize function/symbol/BigInt to JSON
```

**Cause:**
Event data contains non-serializable JavaScript types.

**Fixes:**

```javascript
// Wrong: functions can't be serialized
data.callback = function() { ... };  // Error

// Wrong: symbols can't be serialized
data.id = Symbol('id');  // Error

// Wrong: BigInt needs conversion
data.bigNumber = 9007199254740991n;  // Error

// Correct: use serializable types
data.id = 'unique-id-string';
data.bigNumber = '9007199254740991';  // String for large numbers
```

## Prevention

### 1. Validate Before Sending

```javascript
function validateEvent(data) {
  try {
    JSON.stringify(data);
    return true;
  } catch (e) {
    console.error('Invalid event data:', e);
    return false;
  }
}

if (validateEvent(eventData)) {
  trackEvent(eventData);
}
```

### 2. Use TypeScript

TypeScript can catch many serialization issues at compile time:
```typescript
interface EventData {
  field1: string;
  field2: number;
  // TypeScript prevents invalid types
}
```

### 3. Sanitize User Input

```javascript
function sanitizeInput(input) {
  if (typeof input !== 'string') {
    return String(input);
  }
  // Remove control characters
  return input.replace(/[\x00-\x1F\x7F]/g, '');
}
```

### 4. Set Size Limits

```javascript
const MAX_EVENT_SIZE = 10000;  // 10KB

function checkEventSize(data) {
  const size = new Blob([JSON.stringify(data)]).size;
  if (size > MAX_EVENT_SIZE) {
    console.error(`Event too large: ${size} bytes`);
    return false;
  }
  return true;
}
```

## Diagnostic Tools

```bash
# Validate JSON structure
python scripts/validate_event_json.py --event-file event.json

# Check event size
python scripts/validate_event_json.py --event-file event.json --check-size

# Validate Snowplow required fields
python scripts/validate_event_json.py --event-file event.json --check-snowplow-fields
```

## Quick Reference

| Issue | Symptom | Quick Fix |
|-------|---------|-----------|
| Invalid JSON | Parse error | Use JSON.stringify() |
| Missing Snowplow fields | Missing field error | Verify tracker initialization |
| Character encoding | UTF-8 error | Encode special characters |
| Oversized event | Size exceeded | Truncate or paginate data |
| Circular reference | Serialization error | Remove circular refs |
| Undefined values | Serialization error | Use null or omit field |
| Invalid data types | Serialization error | Use serializable types only |
