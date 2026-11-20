'use strict';
// Conversación continua: cierra frases tras la pausa, sin límite de duración, y lee una vez cada frase.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { execFileSync } = require('node:child_process');

function serverPhrasebook() {
  const code = "import json, vocabulary_catalog as v; print(json.dumps(v.phrasebook('lsm')))";
  for (const python of [process.env.PYTHON, 'python3', 'python'].filter(Boolean)) {
    try {
      return JSON.parse(execFileSync(python, ['-c', code], { cwd: path.join(__dirname, '..'), encoding: 'utf8' }));
    } catch (_) {}
  }
  throw new Error('No se encontró Python para leer vocabulary_catalog.py');
}
const PHRASEBOOK = serverPhrasebook();

function element(tag = 'div') {
  return {
    tag, value: '', textContent: '', hidden: false, disabled: false, title: '', type: '', className: '',
    children: [], options: [], scrollTop: 0, scrollHeight: 0, listeners: {},
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = [...items]; },
    addEventListener(name, fn) { this.listeners[name] = fn; },
  };
}

function load() {
  const elements = new Map();
  const $ = (id) => {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
  };
  $('transcript-pause').value = '3000';
  $('transcript-pause').options = [{ value: '3000' }];
  $('transcript-voice').value = 'sentence';
  $('transcript-voice').options = [{ value: 'sentence' }, { value: 'sign' }, { value: 'off' }];
  let now = 1_000_000;
  class FakeDate extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return now; }
  }
  const spoken = [];
  const timers = [];
  const context = {
    $, Date: FakeDate, console, JSON, Number, String, Math, Object,
    localStorage: { getItem: () => null, setItem() {} },
    document: { createElement: (tag) => element(tag) },
    setInterval: (fn) => timers.push(fn),
    automaticSpeech: { enqueue: (text) => spoken.push(text) },
    profile: () => ({ locale: 'es-MX', phrasebook: PHRASEBOOK }),
    notice() {},
  };
  vm.createContext(context);
  const root = path.join(__dirname, '..', 'static');
  vm.runInContext(fs.readFileSync(path.join(root, 'phrases.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(root, 'transcript.js'), 'utf8'), context);
  return { context, $, spoken, tick: (ms) => { now += ms; timers.forEach((fn) => fn()); } };
}

test('una conversación larga se divide en frases por pausas y no se corta', () => {
  const { context, $, spoken, tick } = load();
  assert.equal(context.transcriptSpeaksEachSign(), false);
  // 40 frases a lo largo de varios minutos: no hay límite de 30 segundos.
  for (let n = 0; n < 40; n++) {
    context.transcriptAddSign({ id: 'a', text: 'Hola' }, 0.95);
    tick(1000);
    context.transcriptAddSign({ id: 'b', text: 'Gracias' }, 0.95);
    tick(1000);
    assert.equal($('transcript-list').children.length, n, 'no cierra antes de la pausa');
    tick(3000);
  }
  assert.equal($('transcript-list').children.length, 40);
  assert.equal(spoken.length, 40);
  assert.equal(spoken[0], 'Hola, gracias.');
  assert.equal($('transcript-duration').textContent, '3:16');
  context.transcriptClear();
  assert.equal($('transcript-list').children.length, 0);
});

test('quitar la última seña y terminar la frase manualmente', () => {
  const { context, $, spoken } = load();
  for (const text of ['Yo', 'Querer', 'Agua', 'B']) context.transcriptAddSign({ id: text, text }, 0.9);
  $('transcript-undo').listeners.click();
  assert.equal($('transcript-draft').textContent, 'Quiero agua.');
  context.transcriptFinish();
  assert.deepEqual(spoken, ['Quiero agua.']);
  assert.equal($('transcript-finish').disabled, true);
});

test('cada confirmación nueva llega a la conversación una sola vez', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'static', 'app.js'), 'utf8');
  const elements = new Map();
  const $ = (id) => { if (!elements.has(id)) elements.set(id, { value: '', textContent: '', disabled: false }); return elements.get(id); };
  const added = [];
  let spoken = 0;
  const context = {
    $, profile: () => ({ model: true }), resetResult() {}, renderAlternatives() {}, renderHistory() {},
    sessionConfirmedText: () => '', window: { speechSynthesis: {} }, history: [], lastSpoken: null,
    lastConfirmationId: null, checks: 0, correct: 0, speak() { spoken++; },
    transcriptAddSign: (sign) => added.push(sign.text), transcriptSpeaksEachSign: () => false,
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function showPrediction('), source.indexOf('// Dibuja las confirmaciones')), context);
  const accepted = { candidate: { id: 'b', text: 'B' }, confirmed: { id: 'b', text: 'B' }, confirmation_id: '1',
    confirmed_confidence: 0.99, confidence: 0.99, stability: 3, stability_required: 3 };
  context.showPrediction(accepted);
  context.showPrediction(accepted);
  context.showPrediction({ ...accepted, confirmation_id: '2', confirmed: { id: 'c', text: 'C' } });
  assert.deepEqual(added, ['B', 'C']);
  assert.equal(spoken, 0, 'con «Cada frase completa» no se lee cada seña');
});
