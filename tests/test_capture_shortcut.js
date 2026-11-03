'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
const handler = source.slice(source.indexOf('function capturePauseShortcut('), source.indexOf("document.addEventListener('keydown', capturePauseShortcut)"));
let calls=0, blocked=false, editable=false;
const context={currentView:'dataset',batch:{active:true},document:{querySelector:()=>blocked},toggleContinuousPause:()=>{calls++}};
vm.createContext(context);vm.runInContext(handler,context);
function press(overrides={}) {
  let prevented=false;
  const event={code:'Space',repeat:false,target:{closest:()=>editable},preventDefault(){prevented=true},...overrides};
  context.capturePauseShortcut(event);return prevented;
}
assert.equal(press(),true);assert.equal(calls,1);
editable=true;assert.equal(press(),false);assert.equal(calls,1);editable=false;
assert.equal(press({repeat:true}),false);
assert.equal(press({ctrlKey:true}),false);
assert.equal(press({code:'Enter'}),false);
blocked=true;assert.equal(press(),false);blocked=false;
context.currentView='recognition';assert.equal(press(),false);
context.currentView='dataset';context.batch.active=false;assert.equal(press(),false);
assert.equal(calls,1);
console.log('Atajo de pausa: Espacio solo en tandas de Dataset, sin interferir con formularios o diálogos.');
