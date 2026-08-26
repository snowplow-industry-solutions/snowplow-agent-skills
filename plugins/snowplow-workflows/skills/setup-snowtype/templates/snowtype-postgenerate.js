// Post-generate step for the JavaScript tag tracker (@snowplow/javascript-tracker).
//
// Snowtype 0.17.3 emits classic-script output meant for a <script> tag, but
// leaves one ES-module line in it: `export function createEventSpecification`.
// A classic script throws SyntaxError on that line and defines none of the
// functions. This strips the leading `export` after every generate.
//
// Copy to the project root and chain it in package.json:
//   "snowtype:generate": "snowtype generate && node snowtype-postgenerate.js"
// Never hand-edit the generated file — regenerate and let this run.
const fs = require('fs');
const path = require('path');

const configPath = process.argv[2] || 'snowtype.config.json';
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
// `outpath` is relative to the working directory Snowtype ran in, not to the
// config file; run this from the same directory as `snowtype generate`.
// 0.17.3 names the JavaScript-tracker output file `snowplow.js`.
const outfile = path.resolve(config.outpath, 'snowplow.js');

const before = fs.readFileSync(outfile, 'utf8');
const after = before.replace(/^export function /gm, 'function ');
if (before !== after) {
  fs.writeFileSync(outfile, after);
  console.log(`snowtype-postgenerate: removed 'export' from ${outfile}`);
}
