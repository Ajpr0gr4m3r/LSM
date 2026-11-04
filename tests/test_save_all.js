'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
async function run(fail) {
  const drafts = [{id:'one'}, {id:'two'}, {id:'three'}];
  const calls = [], notices = [];
  const elements = {
    'sign-name': {value:'Ñ'},
    'name-capture': {reportValidity:()=>true},
    'save-all-captures': {},
  };
  const context = {
    savingDraft:false, batch:{active:false}, state:{job:null}, language:'lsm',
    $:id=>elements[id], profile:()=>({drafts}),
    api:async(route,body)=>{
      calls.push([route,body]);
      if(fail && body.draft_id==='two') throw Error('Red interrumpida');
      drafts.shift();
    },
    render(){}, refresh:async()=>{},
    notice:(message,error)=>notices.push({message,error}),
  };
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('async function saveAllCaptures('),source.indexOf('// Retira una toma pendiente')),context);
  await context.saveAllCaptures();
  assert.equal(context.savingDraft,false);
  assert(calls.every(([route,p])=>route==='/api/capture/save' && p.name==='Ñ' && p.language==='lsm'));
  if(fail) {
    assert.equal(drafts.length,2);
    assert(notices[0].error && notices[0].message.includes('1 de 3'));
  } else {
    assert.equal(drafts.length,0);
    assert.equal(calls.length,3);
    assert(notices[0].message.includes('3 tomas'));
  }
}
Promise.all([run(false),run(true)]).then(()=>console.log('Guardado múltiple: lista fija, etiqueta común y pendientes conservados tras error.'));
