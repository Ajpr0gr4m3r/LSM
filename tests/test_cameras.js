'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync(require('node:path').join(__dirname, '../static/app.js'), 'utf8');
const cameraCode = app.slice(app.indexOf('async function refreshCameras()'), app.indexOf('async function sendFrame('));
const elements = new Map();
const $ = id => {
  if (!elements.has(id)) elements.set(id, {value:'', textContent:'', disabled:false, hidden:false, play:async () => {}, replaceChildren(...options) { this.options = options; this.value = ''; }});
  return elements.get(id);
};
let devices = [{kind:'videoinput', deviceId:'builtin', label:'FaceTime'}, {kind:'videoinput', deviceId:'usb', label:'USB'}, {kind:'audioinput', deviceId:'mic'}];
let stopped = 0, constraints, ended, messages = [], closed = 0, sent = 0;
const streamMock = () => ({getTracks:() => [{stop:() => stopped++}], getVideoTracks:() => [{getSettings:() => ({deviceId:'usb'}), addEventListener:(event, callback) => { ended = callback; }}]});
$('shared-camera-consent').checked = true;
const sandbox = { $, navigator:{mediaDevices:{enumerateDevices:async () => devices, getUserMedia:async c => { constraints = c; return streamMock(); }}},
  makeOption:(value, text) => ({value, text}), api:async path => { if (path === '/api/close') closed++; return {session:'session-id'}; },
  clearHandRig:() => {}, render:() => {}, notice:(text,error) => messages.push({text,error}), sendFrame:() => sent++, setTimeout, clearTimeout, console,
  cameraFingerprint:async () => 'anonymous-device', profile:() => ({model:true}), batch:{stop:() => {}}, language:'lsm', mode:'train', state:{} };
vm.createContext(sandbox);
vm.runInContext('let stream=null, session=null, generation=0, timer=null, countdown=false, recording=false, frameReady=false, cameraStarting=false, cameraListing=false;'+cameraCode, sandbox);
(async () => {
  await sandbox.refreshCameras();
  assert.deepEqual($('camera-device').options.map(x => x.value), ['', 'builtin', 'usb']);
  $('camera-device').value = 'usb';
  await sandbox.startCamera();
  assert.equal(constraints.video.deviceId.exact, 'usb');
  assert.equal(constraints.audio, false);
  assert.equal($('camera-device').value, 'usb');
  assert.equal(sent, 1);
  await sandbox.stopCamera();
  assert.equal(stopped, 1); assert.equal(closed, 1);
  // Una caída del servidor deja visible el video y permite conectar de nuevo.
  let attempts = 0;
  const previousApi = sandbox.api;
  sandbox.api = async (path, body) => {
    if (path === '/api/session') {
      assert.equal($('camera').hidden, false, 'La vista previa debe estar visible antes de la conexión');
      if (++attempts === 1) throw new Error('Servidor temporalmente ocupado');
    }
    return previousApi(path, body);
  };
  await sandbox.startCamera();
  assert.equal($('retry-camera-connection').hidden, false);
  assert.equal(stopped, 1);
  await sandbox.startCamera();
  assert.equal($('retry-camera-connection').hidden, true);
  assert.equal(attempts, 2);
  await sandbox.stopCamera();
  assert.equal(stopped, 2);
  sandbox.api = previousApi;
  // Preserve selection on refresh, remove it if disconnected.
  await sandbox.refreshCameras(); assert.equal($('camera-device').value, 'usb');
  devices = devices.filter(x => x.deviceId !== 'usb');
  await sandbox.refreshCameras(); assert.equal($('camera-device').value, '');
  sandbox.navigator.mediaDevices.getUserMedia = async () => { const error = new Error('denied'); error.name='NotAllowedError'; throw error; };
  await sandbox.startCamera();
  assert(messages.some(x => x.error && x.text.includes('Permite la cámara')));
  devices = [];
  await sandbox.refreshCameras(); assert($('camera-device-status').textContent.includes('No hay cámaras'));
  devices = [{kind:'videoinput', deviceId:'usb', label:'USB'}];
  sandbox.navigator.mediaDevices.getUserMedia = async c => { constraints=c; return streamMock(); };
  await sandbox.startCamera();
  assert.equal(constraints.video.facingMode, 'user');
  devices = []; await sandbox.refreshCameras();
  assert.equal(stopped, 3);
  assert(messages.some(x => x.error && x.text.includes('desconectó')));
  // Late permission grant after cancellation must release the acquired camera.
  let grant;
  sandbox.navigator.mediaDevices.getUserMedia = () => new Promise(resolve => { grant = resolve; });
  const pending = sandbox.startCamera(); await sandbox.stopCamera(); grant(streamMock()); await pending;
  assert.equal(stopped, 4);
  // Un token obsoleto debe renovar el acceso sin pedir la cámara otra vez.
  devices = [{kind:'videoinput', deviceId:'usb', label:'USB'}];
  sandbox.navigator.mediaDevices.getUserMedia = async () => streamMock();
  sandbox.state = {token:'old', user:{id:'local'}};
  sandbox.refresh = async () => { sandbox.state = {token:'new', user:{id:'local'}}; };
  attempts = 0;
  sandbox.api = async (path, body) => {
    if (path === '/api/session' && ++attempts === 1) {
      throw Object.assign(new Error('Token obsoleto'), {status:403, code:'csrf_mismatch'});
    }
    return previousApi(path, body);
  };
  await sandbox.startCamera();
  assert.equal(attempts, 2);
  assert.equal(stopped, 4);
  assert.equal($('retry-camera-connection').hidden, true);
  await sandbox.stopCamera();

  // Una negativa por origen no debe volver a enviar la solicitud.
  attempts = 0;
  sandbox.api = async () => {
    attempts++;
    throw Object.assign(new Error('Origen incorrecto'), {status:403});
  };
  await sandbox.startCamera();
  assert.equal(attempts, 1);
  assert.equal($('retry-camera-connection').hidden, false);
  assert(messages.some(x => x.error && x.text.includes('Origen incorrecto')));
  assert.equal($('hands-status').textContent, 'Origen incorrecto');
  await sandbox.stopCamera();
  console.log('Cámaras: enumeración, selección exacta, desconexión, permiso denegado y cancelación comprobados.');
})().catch(error => { console.error(error); process.exitCode=1; });
