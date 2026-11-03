'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/studio.js'), 'utf8');
const helper = source.slice(source.indexOf('function renderRecognitionDiagnostics('), source.indexOf('function renderVersions('));
class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.textContent = ''; }
  append(...items) { this.children.push(...items); }
}
const node = (tag, text, className) => {
  const result = new Element(tag);
  if (text !== undefined) result.textContent = text;
  if (className) result.className = className;
  return result;
};
const context = vm.createContext({node});
vm.runInContext(helper, context);
const render = context.renderRecognitionDiagnostics;
const all = root => root ? [root, ...root.children.flatMap(all)] : [];
const text = root => all(root).map(item => item.textContent).join('\n');
assert.equal(render({labels: []}), null, 'Los modelos históricos no deben mostrar diagnósticos inventados.');
const report = render({
  validation_protocol: {independent_calibration: false, selection_samples: 8, calibration_samples: 8, note: 'Faltan sesiones independientes.'},
  recognition_diagnostics: {
    validation: {stages: [{name: 'model', evaluated: 8, accepted: 8, correct_accepted: 5, false_accepts: 3, correct_rejected: 0, coverage: 1}]},
    test: {stages: [{name: 'final', evaluated: 6, accepted: 0, correct_accepted: 0, false_accepts: 0, correct_rejected: 4, coverage: 0}], unsupported_labels: ['<img src=x onerror=alert(1)>']},
  },
});
assert(text(report).includes('Validación compartida'));
assert(text(report).includes('Selección: 8 tomas · Calibración: 8 tomas.'));
assert(text(report).includes('Prueba reservada'));
assert(text(report).includes('0 / 6'));
assert(text(report).includes('0.0 %'), 'Cero cobertura debe conservarse como cero.');
assert(text(report).includes('<img src=x onerror=alert(1)>'), 'Las etiquetas se muestran como texto.');
assert(!all(report).some(item => item.tagName === 'img'));
assert(text(report).includes('no es precisión'));
assert(text(report).includes('no miden la confirmación con la cámara en vivo'));
const independent = render({validation_protocol: {independent_calibration: true, selection_samples: 10, calibration_samples: 12}, recognition_diagnostics: {calibration: {stages: [], policy_class_support: [{id: 'a', text: 'A', support: 6, accepted: 0}]}}});
assert(text(independent).includes('grupos separados'));
assert(!text(independent).includes('Validación compartida'));
assert(text(independent).includes('Calibración · ajuste de umbrales'));
assert(text(independent).includes('Aceptadas al calibrar'));
console.log('Diagnóstico de reconocimiento: etapas, separación de conjuntos, ceros y etiquetas seguras.');
