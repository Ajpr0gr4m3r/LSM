'use strict';
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',disabled:false});return elements.get(id);};
let spoken=0;
const context={
 $, profile:()=>({model:true}),resetResult(){},renderAlternatives(){}, renderHistory(){},
 sessionConfirmedText:()=>'',window:{speechSynthesis:{}},history:[],lastSpoken:null,
 lastConfirmationId:null,checks:0,correct:0,speak(){spoken++;}
};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function showPrediction('),source.indexOf('// Dibuja las confirmaciones')),context);
const accepted={candidate:{id:'b',text:'B'},confirmed:{id:'b',text:'B'},confirmation_id:'1',confirmed_confidence:.99,confidence:.99,stability:3,stability_required:3};
context.showPrediction(accepted);
context.showPrediction({...accepted,candidate:null,inference_skipped:true});
assert.equal(spoken,1);assert.equal(context.history.length,1);
context.showPrediction({candidate:null,confirmed:null,hands:true,confidence:.99,stability:0,rejection_reason:'Movimiento insuficiente.'});
assert.equal(spoken,1);assert.equal($('confidence-progress').value,0);
assert.equal($('result-description').textContent,'Movimiento insuficiente.');
console.log('Confirmaciones: voz única tras reenvío, rechazo al 99 % sin confirmación falsa.');
