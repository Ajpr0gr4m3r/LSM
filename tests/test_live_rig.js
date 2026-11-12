'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const events=[];
const ctx={clearRect(){},save(){events.push('save')},translate(x,y){events.push(['translate',x,y])},scale(x,y){events.push(['scale',x,y])},
 drawImage(source){events.push(['image',source])},restore(){events.push('restore')},beginPath(){},moveTo(){},lineTo(){},stroke(){},
 arc(x,y){events.push(['point',x,y])},fill(){}};
const canvas={width:640,height:480,hidden:true,style:{},getContext:()=>ctx};
const context={stream:{},$:id=>id==='hand-rig'?canvas:{checked:true},clearTimeout(){},setTimeout(fn,delay){context.expire=fn;context.delay=delay;}};
vm.createContext(context);
vm.runInContext(code.slice(code.indexOf('const handRigEdges ='),code.indexOf('function setHandRig(')),context);
const frame={name:'captured-frame'};
context.drawHandRig([Array.from({length:21},()=>[.7,.5])],640,480,frame);
assert(!events.some(e=>Array.isArray(e)&&e[0]==='image'), 'El rig no debe congelar el video con una foto');
assert(!events.some(e=>Array.isArray(e)&&e[0]==='scale'), 'Los puntos ya vienen reflejados');
assert(events.some(e=>Array.isArray(e)&&e[0]==='point'&&e[1]===448&&e[2]===240));
assert.equal(canvas.hidden,false);
assert.equal(context.delay,850);
const originalExpiry = context.expire;
context.drawHandRig([],640,480);
assert.equal(canvas.hidden,false);
assert.equal(canvas.style.opacity,'.45');
assert.equal(context.expire,originalExpiry, 'Un cuadro sin manos no debe prolongar el dibujo');
context.drawHandRig([Array.from({length:21},()=>[.6,.5])],640,480);
assert.equal(canvas.style.opacity,'1');
context.expire();
assert.equal(canvas.hidden,true);
console.log('Rig transparente: video continuo, coordenadas sin doble espejo y puntos antiguos retirados.');
