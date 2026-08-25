# npm scripts for Snowtype

Add to `package.json` so the lock-file dance is one command and nobody runs `generate` before `update`.

## One tracker

```json
"scripts": {
  "snowtype:update": "snowtype update --yes",
  "snowtype:generate": "snowtype generate",
  "snowtype": "npm run snowtype:update && npm run snowtype:generate"
}
```

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
