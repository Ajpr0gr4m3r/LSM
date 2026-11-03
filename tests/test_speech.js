'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const deployed = path.join(__dirname, '../static/speech.js');
const source = fs.readFileSync(fs.existsSync(deployed) ? deployed : path.join(__dirname, 'speech.js'), 'utf8');
const timers = [], spoken = [], errors = [];
const context = {setTimeout: fn => timers.push(fn)};
vm.createContext(context);
vm.runInContext(source + '\nthis.Queue = SenaSpeechQueue;', context);
const remote = {lang:'es-MX',localService:false};
const local = {lang:'es_ES',localService:true};
let voices = [];
const synthesis = {paused:false, getVoices:()=>voices, speak:u=>spoken.push(u), cancel:()=>{throw Error('Should not cut speech');}};
class Utterance {constructor(text){this.text=text;}}
const queue = new context.Queue(synthesis,Utterance,error=>errors.push(error));
voices = [remote,local];
queue.enqueue('Hola','es-MX');
queue.enqueue('Hola','es-MX');
queue.enqueue('Gracias','es-MX');
assert.equal(spoken.length,1);
assert.equal(spoken[0].voice,local);
assert.equal(queue.current,spoken[0]);
spoken[0].onend();
assert.equal(spoken.length,1);
timers.shift()();
assert.equal(spoken[1].text,'Gracias');
// A repeated sign is allowed once the previous announcement has finished.
spoken[1].onend();timers.shift()();
queue.enqueue('Hola','es-MX');
assert.equal(spoken.length,3);
queue.enqueue('Adiós','es-MX');
spoken[2].onerror({error:'synthesis-failed'});timers.shift()();
assert.equal(errors.length,1);
assert.equal(spoken[3].text,'Adiós');
// A browser delivering both callbacks must not release a different utterance.
spoken[2].onend();assert.equal(queue.current,spoken[3]);
console.log('Voz: cola sin interrupciones, deduplicación, referencias vivas, voces locales y recuperación de errores correctas.');
