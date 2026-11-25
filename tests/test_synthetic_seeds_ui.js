'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const code = fs.readFileSync(path.join(__dirname, '../static/synthetic.js'), 'utf8');

test('loads validation evidence and adds a dataset source with its label and semantic checks', async () => {
  const elements = new Map();
  const $ = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', disabled: false, checked: false, textContent: '', events: {},
      addEventListener(name, action) { this.events[name] = action; },
      replaceChildren(...items) { this.options = items; },
    });
    return elements.get(id);
  };
  let refreshed = 0;
  const calls = [];
  const context = {
    $, makeOption: (value, text) => ({value, text}), syntheticLanguage: () => 'lsm',
    syntheticRefresh: async () => { refreshed++; }, notice: text => { throw Error(text); },
    syntheticRequest: async (route, body) => {
      calls.push([route, body]);
      return {options: [{id: 'sample-label', text: 'Una seña', precision: .98, accepted: 12, support: 20}]};
    },
  };
  vm.createContext(context);
  vm.runInContext(code.slice(code.indexOf('let syntheticDatasetOptions'), code.indexOf('function sourceDescription')), context);
  await context.syntheticLoadDatasetOptions();
  assert.equal($('synthetic-dataset-label').options[1].text, 'Una seña');
  $('synthetic-dataset-label').value = 'sample-label';
  $('synthetic-dataset-label').events.change();
  assert.equal($('synthetic-dataset-add').disabled, false);
  assert.match($('synthetic-dataset-info').textContent, /98 %.*12 aceptadas.*20 ejemplos/);
  await $('synthetic-dataset-add').events.click();
  assert.equal(calls[1][0], '/api/synthetic/dataset-source');
  assert.equal(calls[1][1].label_id, 'sample-label');
  assert.equal($('synthetic-label').value, 'Una seña');
  assert.equal($('synthetic-semantic').checked, true);
  assert.equal(refreshed, 1);
});
