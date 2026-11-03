'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
function $(id) {
  if(!elements.has(id))elements.set(id,{value:'',textContent:'',hidden:false,disabled:false,checked:false,handlers:{},
    addEventListener(event,callback){this.handlers[event]=callback;},reset(){for(const key of ['account-password'])$(key).value='';},replaceChildren(){},close(){}});
  return elements.get(id);
}
let status={user:null,csrf:'anonymous',setup_required:true},calls=[],refreshes=0,stops=0;
const ctx={$,fetch:async(path,options)=>{
  const body=options?.body ? JSON.parse(options.body) : null;calls.push({path,options,body});
  let result=status;
  if(path.endsWith('/logout'))status=result={user:null,csrf:'new-anonymous',setup_required:false};
  else if(options?.method==='POST')status=result={user:{id:'alice',name:'Alicia',username:'alice',role:'member'},csrf:'member-token',setup_required:false};
  return {ok:true,json:async()=>result};
},document:{querySelector:()=>$('admin-panel'),querySelectorAll:()=>[]},
refresh:async()=>{refreshes++;},stopCamera:async()=>{stops++;},notice:()=>{},clearHistory:()=>{},console};
vm.createContext(ctx);
vm.runInContext('let state, stateRequest=null, selectedDraft=null, displayedDraft=null, stream=null;'+fs.readFileSync(require('node:path').join(__dirname,'../static/accounts.js'),'utf8'),ctx);
(async()=>{
  await ctx.bootstrapAccounts();
  assert($('team-workspace').hidden);assert($('account-invite-label').hidden);
  assert.equal($('account-submit').textContent,'Crear espacio de equipo');
  status={user:null,csrf:'anonymous2',setup_required:false};await ctx.bootstrapAccounts();
  assert($('account-consent-label').hidden);
  ctx.accountScreen('register');assert(!$('account-consent-label').hidden);assert(!$('account-invite-label').hidden);
  $('account-username').value='alice';$('account-name').value='Alicia';$('account-password').value='fixture-password-only';$('account-consent').checked=true;
  await $('account-form').handlers.submit({preventDefault(){}});
  const call=calls.find(c=>c.path.endsWith('/register'));
  assert.equal(call.options.headers['X-LSM-Token'],'anonymous2');assert.equal(call.body.shared_consent,true);assert(!('admin_password' in call.body));
  assert(!$('team-workspace').hidden);assert($('account-gate').hidden);assert.equal($('current-account').textContent,'Alicia');
  assert($('team-admin').hidden);assert($('sample-admin').hidden);assert($('train-model').disabled);
  assert.equal($('account-password').value,'');assert(refreshes>0);
  await $('account-logout').handlers.click();assert($('team-workspace').hidden);assert(!$('account-gate').hidden);assert(stops>0);
  assert.equal($('team-invite-code').value,'');
  console.log('Cuentas UI: configuración inicial, invitación, CSRF, acceso por rol y cierre de sesión correctos.');
})().catch(error=>{console.error(error);process.exitCode=1;});
