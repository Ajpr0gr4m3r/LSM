'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
const apiCode = source.slice(source.indexOf('async function api('), source.indexOf('// Crea una opción'));
const frameCode = source.slice(source.indexOf('async function sendFrame('), source.indexOf('// Presenta aceptación'));
function harness() {
  const elements = new Map();
  const ctx = {stream:{}, session:'session', generation:1, recording:false, countdown:false,
    batch:{active:false}, frameReady:true, mode:'test', lastConfirmationId:null,
    state:{sequence_length:30,target_fps:10}, localStorage:{getItem:()=>null},
    performance:{now:()=>0}, stopped:0, scheduled:[], notices:[],
    clearHandRig(){}, drawHandRig(){}, render(){}, showPrediction(){},
    notice(message){ctx.notices.push(message);},
    stopCamera:async()=>{ctx.stopped++;},
    setTimeout(fn,delay){ctx.scheduled.push({fn,delay});return 1;},
    $:id=>{if(!elements.has(id)) elements.set(id,{videoWidth:640,videoHeight:480,
      getContext:()=>({drawImage(){}}),toDataURL:()=> 'data:image/jpeg;base64,new-frame'});
      return elements.get(id);},
    api:async()=>{throw Object.assign(new Error('connection lost'),{networkFailure:true});}};
  vm.createContext(ctx);vm.runInContext(frameCode,ctx);return ctx;
}
test('retries network loss with bounded delay and keeps camera open', async()=>{
  const c=harness();await c.sendFrame(1);
  assert.equal(c.stopped,0);assert.equal(c.scheduled[0].delay,500);
  await c.scheduled.shift().fn();assert.equal(c.scheduled[0].delay,1000);
  await c.scheduled.shift().fn();assert.equal(c.scheduled[0].delay,1500);
  await c.scheduled.shift().fn();assert.equal(c.stopped,1);assert.equal(c.scheduled.length,0);
});
test('does not retry recording, countdown, or an active batch', async()=>{
  for(const field of ['recording','countdown','batch']) {
    const c=harness(); if(field==='batch') c.batch.active=true;else c[field]=true;
    await c.sendFrame(1);assert.equal(c.stopped,1);assert.equal(c.scheduled.length,0);
  }
});
test('does not retry server errors or revive a stopped camera', async()=>{
  const c=harness();c.api=async()=>{throw new Error('model failed');};
  await c.sendFrame(1);assert.equal(c.stopped,1);
  const d=harness();await d.sendFrame(1);d.generation++;
  await d.scheduled[0].fn();assert.equal(d.scheduled.length,1);assert.equal(d.stopped,0);
});
test('successful recovery clears reconnect notice and resumes normal scheduling', async()=>{
  const c=harness();await c.sendFrame(1);
  c.api=async()=>({hands:true,buffer:1});await c.scheduled.shift().fn();
  assert.equal(c.stopped,0);assert.equal(c.notices.at(-1),'Conexión recuperada.');
  assert.equal(c.scheduled[0].delay,100);
});
test('API distinguishes network failures from HTTP failures', async()=>{
  const c={state:{token:'token'},fetch:async()=>{throw new TypeError('Failed to fetch');}};
  vm.createContext(c);vm.runInContext(apiCode,c);
  await assert.rejects(c.api('/api/frame',{}),e=>e.networkFailure===true);
  c.fetch=async()=>({ok:false,status:500,json:async()=>({error:'Detector failed'})});
  await assert.rejects(c.api('/api/frame',{}),e=>!e.networkFailure && e.message==='Detector failed');
});

test('interrupted take keeps camera open and stops automatic batch', async()=>{
  const c=harness();c.recording=true;c.batch.active=true;
  c.batch.stop=()=>{c.batch.active=false;};
  c.api=async()=>({phase:'capture-interrupted',capture_error:'Repite la toma',buffer:0,hands:true});
  await c.sendFrame(1);
  assert.equal(c.stopped,0);assert.equal(c.recording,false);assert.equal(c.batch.active,false);
  assert.equal(c.notices.at(-1),'Repite la toma');assert.equal(c.scheduled.length,1);
});
