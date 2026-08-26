# npm scripts for Snowtype

Add to `package.json` so the lock-file dance is one command and nobody runs `generate` before `update` once a lock file exists.

**First run on a project with no `.snowtype-lock.json`:** run `npm run snowtype:generate` alone — `generate` creates the lock; `update` errors without one. Use the combined `snowtype` script from then on. Add `--latestDraft` to the update script while the specs are unpublished drafts.

## One tracker

```json
"scripts": {
  "snowtype:update": "snowtype update --yes",
  "snowtype:generate": "snowtype generate",
  "snowtype": "npm run snowtype:update && npm run snowtype:generate"
}
```

## JavaScript tag tracker (`@snowplow/javascript-tracker`)

Same as above, but chain a post-generate step that strips the stray `export` from the output so it loads as a classic script (see `reference/gotchas.md#javascript-tag-tracker`). Copy `templates/snowtype-postgenerate.js` to the project root, then:

```json
"snowtype:generate": "snowtype generate && node snowtype-postgenerate.js"
```

The script takes an optional config path argument (`node snowtype-postgenerate.js snowtype.config.client.json`) for two-config projects.

## Two trackers (client + server)

One config per tracker, selected with `-c`. Each has its own `outpath`.

```json
"scripts": {
  "snowtype:client": "snowtype update --yes -c snowtype.config.json && snowtype generate -c snowtype.config.json",
  "snowtype:server": "snowtype update --yes -c snowtype.config.server.json && snowtype generate -c snowtype.config.server.json",
  "snowtype": "npm run snowtype:client && npm run snowtype:server"
}
```

## CI (either layout)

Run the same scripts, then add `--disallowDevSchemas` to the `generate` call so dev-only schemas fail the build. Fail the job (or open a PR) if the generated output differs from what is committed.
