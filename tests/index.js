// Node 24 resolves an explicit test directory through its index entry point.
const fs = require('node:fs');
const path = require('node:path');

for (const name of fs.readdirSync(__dirname).filter(name => name.endsWith('.test.cjs')).sort()) {
  require(path.join(__dirname, name));
}
