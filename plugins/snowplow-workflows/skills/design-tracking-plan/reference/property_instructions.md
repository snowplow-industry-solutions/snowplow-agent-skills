# Property Instructions for Grouped Schemas

When two or more event specs share the same data structure (the **Grouped Actions** pattern), property instructions narrow each spec to the subset of events it represents. Without them, every spec accepts the same data and governance breaks down.

Use property instructions when:

- The shared schema has a discriminator field — `type`, `action`, `category`, `status`, etc.
- Multiple event specs in the same tracking plan reference the same data structure.
- The user explicitly chooses the grouped-actions pattern.

Example: a `product_action` schema with a `type` discriminator backs three event specs:

- "Add To Cart" — narrows `type` to `["add_to_cart"]`
- "Remove From Cart" — narrows `type` to `["remove_from_cart"]`
- "View Product" — narrows `type` to `["view"]`

The same mechanism applies to entities. If a `product` entity has a `category` field, different event specs can restrict which categories are valid in their context.

When creating a new event spec on a schema already used by sibling specs:

1. Fetch the existing specs via the Snowplow MCP to see their property instructions.
2. Choose property instructions that don't overlap with the siblings.
3. If sibling specs lack property instructions, recommend adding them retroactively.

## How property instructions are stored

Property instructions are standalone JSON Schema documents — not Iglu-registered. They use the draft-04 `$schema` URL and omit the `self` block. They must be a **subtype** of the base schema: every event valid against the property instructions must also be valid against the base schema.

## Subtype rules

You **can**:

- Tighten an `enum` (drop allowed values).
- Tighten string constraints (shrink `maxLength`, add `format`, add `pattern`).
- Promote an optional field to required.
- Keep or repeat `additionalProperties: false` (draft-04 defaults to `true`, which would broaden — repeat it if the base has it).

You **cannot**:

- Add fields not present in the base schema.
- Add new enum values.
- Loosen any constraint (larger `maxLength`, drop `format`, broader `enum`, etc.).
- Drop a field from the base's `required` list.

## Worked example

Base schema (`iglu:com.acme/product_action/jsonschema/1-0-0`):

```json
{
  "$schema": "http://iglucentral.com/schemas/com.snowplowanalytics.self-desc/schema/jsonschema/1-0-0#",
  "self": {
    "vendor": "com.acme",
    "name": "product_action",
    "format": "jsonschema",
    "version": "1-0-0"
  },
  "description": "User interaction with a product",
  "type": "object",
  "properties": {
    "product_id": {
      "type": "string",
      "description": "Catalog identifier of the product",
      "format": "uuid"
    },
    "list_name": {
      "type": "string",
      "description": "Name of the listing surface that originated the action",
      "maxLength": 64
    },
    "type": {
      "type": "string",
      "description": "Discriminator: which kind of product action this is",
      "enum": ["view", "add_to_cart", "remove_from_cart"]
    }
  },
  "required": ["product_id", "type"],
  "additionalProperties": false
}
```

Property instructions for the "Add To Cart" event spec — narrows `type` to `["add_to_cart"]` and additionally requires `list_name` because the cart UI always sources from a known list:

```json
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "type": "object",
  "properties": {
    "product_id": {
      "type": "string",
      "description": "Catalog identifier of the product",
      "format": "uuid"
    },
    "list_name": {
      "type": "string",
      "description": "Name of the listing surface that originated the action",
      "maxLength": 64
    },
    "type": {
      "type": "string",
      "description": "Discriminator: which kind of product action this is",
      "enum": ["add_to_cart"]
    }
  },
  "required": ["product_id", "type", "list_name"],
  "additionalProperties": false
}
```

Counter-example — this is **not** a valid subtype:

```json
{
  "$schema": "http://json-schema.org/draft-04/schema#",
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "enum": ["add_to_cart", "favorite"]
    }
  }
}
```

Three problems: `"favorite"` is not in the base enum (adds a value), `product_id` is missing from `required` (drops a base requirement), and `additionalProperties` is unset and so defaults to `true` (allows fields the base forbids).
