'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const events=[];
const ctx={clearRect(){},save(){events.push('save')},translate(x,y){events.push(['translate',x,y])},scale(x,y){events.push(['scale',x,y])},
 drawImage(source){events.push(['image',source])},restore(){events.push('restore')},beginPath(){},moveTo(){},lineTo(){},stroke(){},
 arc(x,y){events.push(['point',x,y])},fill(){}};
const canvas={width:640,height:480,hidden:true,getContext:()=>ctx};
const context={stream:{},$:id=>id==='hand-rig'?canvas:{checked:true},clearTimeout(){},setTimeout(){}};
vm.createContext(context);
vm.runInContext(code.slice(code.indexOf('const handRigEdges ='),code.indexOf('function setHandRig(')),context);
const frame={name:'captured-frame'};
context.drawHandRig([Array.from({length:21},()=>[.7,.5])],640,480,frame);
assert(events.some(e=>Array.isArray(e)&&e[0]==='image'&&e[1]===frame));
assert(events.some(e=>Array.isArray(e)&&e[0]==='scale'&&e[1]===-1&&e[2]===1));
assert(events.indexOf('restore')<events.findIndex(e=>Array.isArray(e)&&e[0]==='point'));
assert(events.some(e=>Array.isArray(e)&&e[0]==='point'&&e[1]===448&&e[2]===240));
assert.equal(canvas.hidden,false);
console.log('Rig en vivo: puntos sobre el fotograma analizado, imagen reflejada una vez y coordenadas sin doble espejo.');
