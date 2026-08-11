# Validation Errors Reference

Common Iglu schema validation errors encountered in Micro, their causes, and fixes.

## Error: Schema Not Found

**Symptom:**
```json
{
  "error": "ResolutionError",
  "message": "Schema iglu:com.example/event_name/jsonschema/1-0-0 not found"
}
```

**Cause:**
The schema referenced by the event does not exist in any Iglu registry that Micro is configured to use.

**Fix:**
1. **Verify schema exists**: Check if schema is deployed to DEV environment in Snowplow Console
2. **Deploy schema to DEV**: If schema exists but not in DEV, deploy it using Console or tracking-design skill
3. **Check Iglu registry configuration**: Ensure Micro is configured to use the correct Iglu registry (see setup-micro skill)
4. **Verify schema URI**: Ensure the Iglu URI in tracking code exactly matches the deployed schema (vendor, name, version)

## Error: Required Property Missing

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "object has missing required properties: [\"field_name\"]"
}
```

**Cause:**
The event or entity is missing a field that the schema marks as required.

**Fix:**
1. **Check schema**: Review schema definition to identify required fields
2. **Update tracking code**: Ensure all required fields are included in the tracking call
3. **Check field names**: Verify field names match schema exactly (case-sensitive)

Example fix for JavaScript:
```javascript
// Missing required field 'action'
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: {
    label: 'Sign Up'  // Missing: action
  }
});

// Fixed
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: {
    label: 'Sign Up',
    action: 'click'  // Added required field
  }
});
```

## Error: Additional Property Not Allowed

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "object instance has properties which are not allowed by the schema: [\"extra_field\"]"
}
```

**Cause:**
The event includes a field that is not defined in the schema, and the schema has `additionalProperties: false`.

**Fix:**
1. **Remove extra field**: If the field was added by mistake, remove it from tracking code
2. **Update schema**: If the field should be tracked, add it to the schema and deploy new version
3. **Check field names**: Verify no typos in field names (e.g., `button_label` vs `buttonLabel`)

## Error: Type Mismatch

**Symptom:**
```json
{
  "error": "ValidationError",
  "message": "instance type (string) does not match any allowed primitive type (number)"
}
```

**Cause:**
A field value has the wrong data type (e.g., string instead of number).

**Fix:**
1. **Check schema**: Verify expected data type for the field
2. **Convert value**: Ensure tracking code sends correct type

Example fix for JavaScript:
```javascript
// Wrong type: sending string instead of number
trackSelfDescribingEvent({
  schema: 'iglu:com.example/purchase/jsonschema/1-0-0',
  data: {
    amount: '29.99'  // String, but schema expects number
  }
});

// Fixed: convert to number
trackSelfDescribingEvent({
  schema: 'iglu:com.example/purchase/jsonschema/1-0-0',
  data: {
    amount: 29.99  // Number type
  }
});
```

## Error: Schema Version Not Found

**Symptom:**
```json
{
  "error": "ResolutionError",
  "message": "Schema iglu:com.example/event_name/jsonschema/1-0-1 not found. Found versions: 1-0-0"
}
```

**Cause:**
The tracking code references a schema version that doesn't exist. A different version exists in the registry.

**Fix:**
1. **Check deployed versions**: Verify which schema versions exist in DEV environment
2. **Update tracking code**: Use the correct version number in the Iglu URI
3. **Deploy new version**: If you need the newer version, deploy it to DEV first

## Error: Malformed JSON

**Symptom:**
```json
{
  "error": "ParseError",
  "message": "Invalid JSON structure"
}
```

**Cause:**
The event payload is not valid JSON (syntax error, malformed structure).

**Fix:**
1. **Check tracking code**: Ensure object is properly formed with valid JSON syntax
2. **Validate payload**: Use JSON.stringify to verify structure before sending
3. **Check encoding**: Ensure special characters are properly escaped

## Error: Entity Context Not Attached

**Symptom:**
Event validates but expected context entity is missing from the event in /good endpoint.

**Cause:**
The context entity was not attached to the event, or was attached incorrectly.

**Fix:**
1. **Verify context attachment**: Ensure context is passed in the contexts array
2. **Check context structure**: Context must be an array of self-describing JSONs

Example fix for JavaScript:
```javascript
// Missing context
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: { label: 'Sign Up' }
});

// Fixed: context attached
trackSelfDescribingEvent({
  schema: 'iglu:com.example/button_click/jsonschema/1-0-0',
  data: { label: 'Sign Up' },
  context: [
    {
      schema: 'iglu:com.example/user_context/jsonschema/1-0-0',
      data: { user_tier: 'premium' }
    }
  ]
});
```

## Diagnosis Workflow

When encountering validation errors:

1. **Read the error message**: Iglu validation errors are usually specific and actionable
2. **Check schema**: Review the schema definition in Console or locally
3. **Compare with tracking code**: Ensure tracking code matches schema requirements
4. **Test incrementally**: Fix one error at a time and re-test
5. **Verify schema deployment**: Ensure schema is in DEV before testing with Micro

## Getting More Details

For detailed validation output:
```bash
# Show full event payloads and validation details
python scripts/check_good_bad.py --port 9090 --show-details
```

This displays the full event JSON and complete validation error messages, which can help diagnose complex issues.
