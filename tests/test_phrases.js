'use strict';
// Compositor de frases: orden LSM → español escrito, con las reglas reales del servidor.
const assert = require('node:assert/strict');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { test } = require('node:test');
const { SenaPhrasebook } = require('../static/phrases.js');

function serverPhrasebook() {
  const root = path.join(__dirname, '..');
  const code = "import json, vocabulary_catalog as v; print(json.dumps(v.phrasebook('lsm')))";
  for (const python of [process.env.PYTHON, 'python3', 'python'].filter(Boolean)) {
    try {
      return JSON.parse(execFileSync(python, ['-c', code], { cwd: root, encoding: 'utf8' }));
    } catch (_) {}
  }
  throw new Error('No se encontró Python para leer vocabulary_catalog.py');
}

const book = new SenaPhrasebook(serverPhrasebook());
const say = (...signs) => book.compose(signs.map((text) => ({ text })));

test('frases conocidas y deletreo de nombres', () => {
  assert.equal(say('Hola', 'Yo', 'Nombre', 'A', 'N', 'A'), 'Hola, me llamo Ana.');
  assert.equal(say('Tú', 'Nombre', 'Qué'), '¿Cómo te llamas?');
  assert.equal(say('Baño', 'Dónde'), '¿Dónde está el baño?');
  assert.equal(say('Me llamo', 'J', 'U', 'A', 'N'), 'Me llamo Juan.');
  assert.equal(say('H', 'O', 'L', 'A', 'Espacio', 'A', 'N', 'A'), 'Hola, Ana.');
});

test('pronombre + verbo, negación y complementos', () => {
  assert.equal(say('Yo', 'Querer', 'Agua'), 'Quiero agua.');
  assert.equal(say('Yo', 'Querer', 'No'), 'No quiero.');
  assert.equal(say('Yo', 'Entender', 'No'), 'No entiendo.');
  assert.equal(say('Mañana', 'Yo', 'Ir', 'Escuela'), 'Mañana voy a la escuela.');
  assert.equal(say('Yo', 'Trabajar', 'Hospital'), 'Trabajo en el hospital.');
  assert.equal(say('Nosotros', 'Venir', 'Hospital'), 'Venimos del hospital.');
  assert.equal(say('Yo', 'Gustar', 'Comida'), 'Me gusta la comida.');
  assert.equal(say('Él', 'Comer'), 'Él come.');
});

test('estados, profesiones y preguntas al inicio', () => {
  assert.equal(say('Yo', 'Cansado'), 'Estoy cansado.');
  assert.equal(say('Ella', 'Cansado'), 'Ella está cansada.');
  assert.equal(say('Ella', 'Doctor'), 'Ella es doctora.');
  assert.equal(say('Yo', 'Hambre'), 'Tengo hambre.');
  assert.equal(say('Yo', 'Cansado', 'No'), 'No estoy cansado.');
  assert.equal(say('Tú', 'Comer', 'Qué'), '¿Qué comes?');
  assert.equal(say('Hola', '¿Cómo estás?'), 'Hola, ¿cómo estás?');
});

test('sin reglas sigue funcionando y no inventa texto', () => {
  const empty = new SenaPhrasebook({});
  assert.equal(empty.compose([]), '');
  assert.equal(empty.compose([{ text: 'Te quiero' }]), 'Te quiero.');
  assert.equal(empty.compose([{ text: 'B' }, { text: 'Y' }]), 'By.');
});
