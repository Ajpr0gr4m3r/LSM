'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/conversation.js'), 'utf8');
const nodes = new Map();
function element(id = '') {
  const item = {id, hidden:false, value:'', textContent:'', disabled:false, children:[], className:'',
    append(...children) { for (const child of children) { this.children.push(child); if (child.id) nodes.set(child.id, child); } },
    replaceChildren(...children) { for (const child of this.children) if (child.id && nodes.get(child.id) === child) nodes.delete(child.id); this.children=[]; this.append(...children); },
    addEventListener(){}, removeAttribute(){}, select(){}, scrollTop:0, scrollHeight:0 };
  if (id) nodes.set(id, item);
  return item;
}
for (const id of ['conversation-empty','conversation-messages','conversation-status','conversation-input','send-conversation-message',
  'conversation-link-box','conversation-link','conversation-qr','conversation-consent','create-conversation','close-conversation','conversation-link-status','conversation-form','copy-conversation-link']) element(id);
nodes.get('conversation-messages').append(nodes.get('conversation-empty'));
const context = {console, setInterval:()=>1, clearInterval(){}, setTimeout, profile:()=>({locale:'es-MX'}),
  currentView:'conversation', language:'lsm', api:async()=>({}), publishRecognizedSign(){}, notice(){},
  SenaSpeechQueue:class {constructor(){} enqueue(){}}, window:{speechSynthesis:{}, SpeechSynthesisUtterance:function(){}, addEventListener(){}},
  navigator:{clipboard:{writeText:async()=>{}}}, document:{getElementById:id=>nodes.get(id)||null,
    createElement:()=>element(), addEventListener(){}} };
context.$ = id => context.document.getElementById(id);
vm.createContext(context);
vm.runInContext(source, context);
vm.runInContext("conversationRender({messages:[{id:1,sender:'Teléfono',text:'Hola',kind:'text'}],phone_connected:true,expires_in:300})", context);
assert.equal(nodes.has('conversation-empty'), false, 'el estado con mensajes retira el marcador vacío del DOM');
assert.doesNotThrow(() => vm.runInContext("closeConversationUI('Conversación terminada')", context));
assert.equal(nodes.get('conversation-empty').hidden, false);
assert.equal(nodes.get('conversation-messages').children[0].id, 'conversation-empty');
console.log('Conversación: terminar la sala restaura el estado vacío incluso después de recibir mensajes.');
