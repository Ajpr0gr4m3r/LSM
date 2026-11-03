'use strict';
// Parse complete shipped scripts, in page order, before testing extracted functions.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static/index.html'), 'utf8');
const scripts = [...html.matchAll(/<script[^>]+src="(\/static\/[^"?]+\.js)"/g)].map(match => match[1]);
assert(scripts.length > 0, 'La página debe cargar los scripts de la aplicación.');
const sources = scripts.map(file => {
  const source = fs.readFileSync(path.join(root, file.slice(1)), 'utf8');
  assert.doesNotThrow(() => new vm.Script(source, {filename:file}), file);
  return source;
});
assert.doesNotThrow(() => new vm.Script(sources.join('\n;\n')), 'Los scripts clásicos no deben redeclarar variables globales.');
console.log('Scripts completos: sintaxis y declaraciones globales correctas.');
