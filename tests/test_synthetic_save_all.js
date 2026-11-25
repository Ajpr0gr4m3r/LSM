'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const code = fs.readFileSync(path.join(__dirname, '../static/synthetic.js'), 'utf8');
const saveCode = code.slice(code.indexOf('async function syntheticSave('), code.indexOf('\nconst drop ='));

test('save all includes pending on every page and prevents duplicate clicks', async () => {
  const elements = {
    'synthetic-include-pending': {checked:false}, 'synthetic-save-real':{checked:false},
    'synthetic-participant':{value:'person-01'}, 'synthetic-save-status':{},
  };
  let resolveSave;
  const requests = [];
  const ctx = {
    $: id => elements[id], synthetic: {saving:false, job:{id:'large-job', state:'done'}, start:240},
    renderJob() {}, notice() {}, refresh:async()=>{}, syntheticRefresh:async()=>{},
    syntheticRequest: async (route, body) => {
      requests.push({route, body});
      return new Promise(resolve => {resolveSave = resolve;});
    },
  };
  vm.createContext(ctx);
  vm.runInContext(saveCode, ctx);
  const first = ctx.syntheticSave(true);
  await ctx.syntheticSave(true);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].body.include_pending, true);
  assert.equal(requests[0].body.job, 'large-job');
  assert.equal(requests[0].body.save_real, false);
  assert.equal(requests[0].body.start, undefined);
  assert.equal(ctx.synthetic.saving, true);
  resolveSave({saved:10000, real_saved:0, label:{text:'Prueba'}});
  await first;
  assert.equal(ctx.synthetic.job.state, 'saved');
  assert.equal(ctx.synthetic.saving, false);
  assert.match(elements['synthetic-save-status'].textContent, /10000/);
  await ctx.syntheticSave(true);
  assert.equal(requests.length, 1);
});

test('save failure releases the controls so it can be retried', async () => {
  const status = {};
  const ctx = {$:()=>status, synthetic:{saving:false,job:{id:'job',state:'done'}},
    renderJob(){}, notice(){}, syntheticRequest:async()=>{throw Error('Disco lleno');}};
  vm.createContext(ctx);
  vm.runInContext(saveCode, ctx);
  await ctx.syntheticSave(true);
  assert.equal(ctx.synthetic.saving, false);
  assert.equal(ctx.synthetic.job.state, 'done');
  assert.equal(status.textContent, 'Disco lleno');
});
