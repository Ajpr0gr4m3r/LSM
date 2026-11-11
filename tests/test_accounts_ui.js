'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
function $(id) {
  if(!elements.has(id))elements.set(id,{value:'',textContent:'',hidden:false,disabled:false,checked:false,handlers:{},
    addEventListener(event,callback){this.handlers[event]=callback;},replaceChildren(){},close(){}});
  return elements.get(id);
}
const visitor = {id:'guest:fixture', name:'Visitante', username:'fixture', role:'collaborator', guest:true};
const member = {id:'alice', name:'Alicia', username:'alice', role:'member'};
let status = {user:visitor, csrf:'visitor-token', setup_required:true};
const calls = [];
let refreshes = 0, stops = 0;
const ctx = {$, fetch:async(path,options)=>{
  calls.push({path,options});
  if (path.endsWith('/logout')) {
    status = {user:visitor, csrf:'new-visitor-token', setup_required:false};
  }
  return {ok:true,json:async()=>status};
}, document:{querySelector:()=>$('admin-panel'),querySelectorAll:()=>[]},
refresh:async()=>{refreshes++;},stopCamera:async()=>{stops++;},notice:()=>{},clearHistory:()=>{},console};
const staticDir = require('node:path').join(__dirname, '../static');
vm.createContext(ctx);
vm.runInContext('let state, stateRequest=null, selectedDraft=null, displayedDraft=null, stream=null;'+fs.readFileSync(staticDir+'/accounts.js','utf8'),ctx);
(async()=>{
  const html = fs.readFileSync(staticDir+'/index.html','utf8');
  assert.match(html, /<div class="app-layout" id="team-workspace">/);
  assert.doesNotMatch(html, /id="(?:account-gate|account-form|admin-login)"/);

  await ctx.bootstrapAccounts();
  assert.equal(refreshes,1);
  ctx.renderTeam();
  assert.equal($('current-account').textContent,'Visitante');
  assert($('account-logout').hidden);
  assert($('team-admin').hidden);
  assert($('sample-admin').hidden);
  assert($('train-model').disabled);

  status = {user:member, csrf:'member-token', setup_required:false};
  await ctx.bootstrapAccounts();
  ctx.renderTeam();
  assert(!$('account-logout').hidden);
  await $('account-logout').handlers.click();
  ctx.renderTeam();
  assert.equal(calls.find(c=>c.path.endsWith('/logout')).options.headers['X-LSM-Token'],'member-token');
  assert.equal(stops,1);
  assert.equal($('current-account').textContent,'Visitante');
  assert($('account-logout').hidden);
  console.log('Acceso directo de visitante, permisos de interfaz y cierre de sesión verificados.');
})().catch(error=>{console.error(error);process.exitCode=1;});
