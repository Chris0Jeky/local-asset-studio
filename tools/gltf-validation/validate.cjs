'use strict';
// The only loaded code is this repository's explicitly installed, pinned tool.
// Model metadata cannot choose a module, path, shell command or resource loader.
const fs = require('node:fs');
const crypto = require('node:crypto');
const validator = require('./node_modules/gltf-validator');
const MAX_BYTES = 128 * 1024 * 1024;
async function main() {
  if (process.argv.length !== 3) throw new Error('Expected one GLB path');
  const input = process.argv[2];
  const fd = fs.openSync(input, 'r');
  let bytes;
  try {
    const size = fs.fstatSync(fd).size;
    if (size < 20 || size > MAX_BYTES) throw new Error('GLB byte budget exceeded');
    bytes = Buffer.alloc(size);
    let offset = 0;
    while (offset < size) {
      const count = fs.readSync(fd, bytes, offset, size - offset, offset);
      if (!count) throw new Error('GLB changed during read');
      offset += count;
    }
    if (fs.fstatSync(fd).size !== size) throw new Error('GLB changed during read');
  } finally { fs.closeSync(fd); }
  const report = await validator.validateBytes(new Uint8Array(bytes), {
    uri: 'asset.glb', format: 'glb', writeTimestamp: false, maxIssues: 1000,
    externalResourceFunction: async () => { throw new Error('External resources are disabled'); }
  });
  report.sourceSha256 = crypto.createHash('sha256').update(bytes).digest('hex');
  report.validatorVersion = validator.version();
  process.stdout.write(JSON.stringify(report) + '\n');
}
main().catch(error => { process.stderr.write(String(error.message) + '\n'); process.exitCode = 2; });
