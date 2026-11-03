'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../static');
const html = fs.readFileSync(path.join(root, 'phone.html'), 'utf8');
const nodes = new Map();
function node(id) {
  const item = {hidden:false, disabled:true, checked:false, value:'', children:[], listeners:{},
    textContent:'', append(...items){this.children.push(...items)}, replaceChildren(){this.children=[]},
    addEventListener(name, fn){this.listeners[name]=fn}, querySelector(){return nodes.get('send-button')}};
  if(id) nodes.set(id,item);
  return item;
}
for (const [,id] of html.matchAll(/id="([^"]+)"/g)) node(id);
node('send-button');
const requests = [];
const bodies = [];
const delays = [];
let frameCanvas;
const context = {console, location:{pathname:'/phone/room/key'}, navigator:{},
  document:{getElementById:id=>nodes.get(id),createElement:tag=>{const item=node(); if(tag==='canvas'){frameCanvas=item;item.getContext=()=>({drawImage(){}});item.toDataURL=()=> 'data:image/jpeg;base64,AAAA';} return item;}},
  window:{addEventListener(){},isSecureContext:true}, setInterval(){},clearInterval(){},clearTimeout(){},setTimeout(fn,ms){delays.push(ms);},
  fetch:async(url,options)=>{requests.push(url);bodies.push(JSON.parse(options.body));return {ok:true,json:async()=>url==='/api/phone/snapshot'?{accepted:true,label:{text:'A'},conversation:{messages:[],sign_drafts:{phone:'A'}}}:{messages:[],expires_in:3600}}}};
vm.createContext(context);
for(const [,src] of html.matchAll(/<script[^>]+src="([^\"]+)"/g)) {
  vm.runInContext(fs.readFileSync(path.join(root,path.basename(src)),'utf8'),context,{filename:src});
}
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(typeof nodes.get('phone-start').listeners.click,'function');
  nodes.get('phone-consent').checked=true;
  nodes.get('phone-consent').listeners.change();
  assert.equal(nodes.get('phone-start').disabled,false);
  assert(requests.includes('/api/phone/state'));
  assert.equal(nodes.get('phone-input').disabled,false,'el chat debe funcionar sin activar la cámara');
  nodes.get('phone-input').value='Hola';
  await nodes.get('phone-form').listeners.submit({preventDefault(){}});
  assert(requests.includes('/api/phone/message'));
  nodes.get('phone-video').videoWidth=1280;
  nodes.get('phone-video').videoHeight=720;
  await vm.runInContext("(async()=>{phoneStream={};phoneSession='session';await phoneFrame()})()",context);
  assert(requests.includes('/api/phone/frame'));
  assert.equal(frameCanvas.width,640);
  assert.equal(frameCanvas.height,360);
  const reusedCanvas=frameCanvas;
  await vm.runInContext('phoneFrame()',context);
  assert.equal(frameCanvas,reusedCanvas,'reutilizar canvas sin reducir resolución');
  assert(delays.some(ms=>ms>=0 && ms<=100));
  nodes.get('phone-snapshot-mode').checked=true;
  await vm.runInContext('phoneFrame()',context);
  assert(bodies.some(body=>body.snapshot_mode===true));
  const preview=nodes.get('phone-snapshot-preview');
  preview.getContext=()=>({drawImage(){}});preview.toDataURL=()=> 'data:image/jpeg;base64,AAAA';
  await context.takePhoneSnapshot();
  assert(requests.includes('/api/phone/snapshot'));
  assert(nodes.get('phone-snapshot-result').textContent.includes('A'));
  assert(!nodes.get('phone-snapshot-result').textContent.includes('%'));
  console.log('Página móvil: scripts reales arrancan, cámara habilitada por consentimiento y chat disponible sin cámara.');
})().catch(error=>{console.error(error);process.exitCode=1});
