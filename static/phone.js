'use strict';
const $p = id => document.getElementById(id);
const parts = location.pathname.split('/').filter(Boolean);
const roomId = parts[1], roomKey = parts[2];
let phoneStream = null, phoneSession = null, phoneTimer = null, phoneBusy = false;
let phoneSnapshotBusy = false;
let phoneSeen = new Set();
let phoneFrameCanvas = null;
let phoneMessagesSignature = null;
const phoneSpeech = new SenaSpeechQueue(window.speechSynthesis, window.SpeechSynthesisUtterance,
  () => { $p('phone-connection').textContent = 'Voz no disponible'; });
// Envía peticiones móviles con la llave temporal de la sala sin utilizar cuentas del estudio.
async function phoneApi(route, body = {}) {
  const response = await fetch(route, {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({...body, room: roomId, key: roomKey})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo conectar a la conversación.');
  return result;
}
// Muestra o limpia el error de la página móvil.
function phoneError(text) {
  $p('phone-error').textContent = text;
  $p('phone-error').hidden = !text;
}
// Actualiza mensajes y borrador solo cuando cambian y lee respuestas recibidas una sola vez.
function drawPhoneMessages(data) {
  const signature = JSON.stringify([data.messages || [], data.sign_drafts || {}, data.locale]);
  if (signature === phoneMessagesSignature) {
    $p('phone-connection').textContent = data.phone_connected ? 'Teléfono conectado' : 'Sala activa';
    return;
  }
  phoneMessagesSignature = signature;
  const host = $p('phone-messages');
  host.replaceChildren();
  const messages = data.messages || [];
  if (!messages.length) {
    const empty = document.createElement('p'); empty.className = 'help'; empty.textContent = 'Esperando mensajes…'; host.append(empty);
  }
  for (const message of messages) {
    const row = document.createElement('article');
    row.className = 'conversation-message' + (message.sender !== 'Teléfono' && message.sender !== 'Señas' ? ' mine' : '');
    const meta = document.createElement('div'); meta.className = 'conversation-message-meta';
    meta.textContent = message.kind === 'sign' ? `${message.sender} · seña reconocida` : message.sender;
    const text = document.createElement('p'); text.textContent = message.text;
    row.append(meta, text); host.append(row);
    if (!phoneSeen.has(message.id)) {
      phoneSeen.add(message.id);
      if (message.sender !== 'Teléfono' && message.sender !== 'Señas') phoneSpeech.enqueue(message.text, data.locale || 'es-MX');
    }
  }
  const draft = data.sign_drafts?.phone;
  if (draft) {
    const pending = document.createElement('p');
    pending.className = 'help';
    pending.textContent = `Escribiendo: ${draft} — se enviará tras ${data.sign_pause_seconds || 4} s de pausa.`;
    host.append(pending);
  }
  host.scrollTop = host.scrollHeight;
  $p('phone-connection').textContent = data.phone_connected ? 'Teléfono conectado' : 'Sala activa';
  $p('phone-input').disabled = false;
  $p('phone-form').querySelector('button').disabled = false;
}
// Consulta la sala cuando no se están enviando fotogramas y avisa si dejó de estar disponible.
async function pollPhoneState() {
  try { drawPhoneMessages(await phoneApi('/api/phone/state')); }
  catch (error) { phoneError(error.message); stopPhone(false); }
}
// Reutiliza el lienzo para enviar un fotograma y mantiene una cadencia objetivo sin peticiones superpuestas.
async function phoneFrame() {
  if (!phoneStream || !phoneSession || phoneBusy) return;
  phoneBusy = true;
  const frameStarted = Date.now();
  try {
    const video = $p('phone-video');
    if (!video.videoWidth || !video.videoHeight) return;
    const canvas = phoneFrameCanvas || (phoneFrameCanvas = document.createElement('canvas'));
    const ratio = Math.min(640 / video.videoWidth, 480 / video.videoHeight, 1);
    const width = Math.round(video.videoWidth * ratio), height = Math.round(video.videoHeight * ratio);
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const context = canvas.getContext('2d', {alpha: false});
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const jpeg = canvas.toDataURL('image/jpeg', .82).split(',', 2)[1];
    const result = await phoneApi('/api/phone/frame', {image: jpeg, snapshot_mode: $p('phone-snapshot-mode').checked});
    if (result.hands) $p('phone-camera-state').textContent = result.quality?.usable === false ? 'Revisando encuadre' : (result.tracking_recovered ? 'Seguimiento recuperado' : 'Manos visibles');
    else $p('phone-camera-state').textContent = 'Buscando manos…';
    if ($p('phone-snapshot-mode').checked) {
      if (result.quality?.usable === false) $p('phone-camera-state').textContent = result.quality.message;
    } else if (result.confirmed) $p('phone-result').textContent = `${result.confirmed.text} · ${(100 * result.confidence).toFixed(0)}%`;
    else if (result.rejection_reason) $p('phone-result').textContent = result.rejection_reason;
    else if (result.candidate) $p('phone-result').textContent = 'Observando el gesto…';
    else if (!result.hands) $p('phone-result').textContent = 'Esperando tus manos…';
    if (result.conversation) drawPhoneMessages(result.conversation);
  } catch (error) { phoneError(error.message); await stopPhone(false); }
  finally {
    phoneBusy = false;
    if (phoneStream && phoneSession) phoneTimer = setTimeout(phoneFrame, Math.max(0, 100 - (Date.now() - frameStarted)));
  }
}
// Solicita permiso de cámara y conecta su flujo con la sesión móvil de la sala.
async function startPhone() {
  if (!$p('phone-consent').checked) return;
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    phoneError('El navegador requiere HTTPS para acceder a la cámara. Abre el enlace privado de Seña.'); return;
  }
  $p('phone-start').disabled = true;
  try {
    const joined = await phoneApi('/api/phone/join');
    phoneSession = joined.session;
    phoneStream = await navigator.mediaDevices.getUserMedia({audio: false, video: {facingMode: 'user', width: {ideal: 1280}, height: {ideal: 720}}});
    $p('phone-video').srcObject = phoneStream;
    await $p('phone-video').play();
    $p('phone-camera').hidden = false;
    $p('phone-start').hidden = true;
    $p('phone-stop').hidden = false;
    $p('phone-snapshot').disabled = !$p('phone-snapshot-mode').checked;
    $p('phone-input').disabled = false;
    $p('phone-form').querySelector('button').disabled = false;
    $p('phone-intro').textContent = 'Haz una seña entrenada y espera a que aparezca en la conversación. Puedes responder escribiendo.';
    phoneSeen = new Set((joined.messages || []).map(item => item.id));
    drawPhoneMessages(joined);
    void phoneFrame();
    phoneError('');
  } catch (error) { phoneError(error.message); $p('phone-start').disabled = false; }
}
// Detiene pistas y temporizador y, si corresponde, libera la sesión móvil en el servidor.
async function stopPhone(notify = true) {
  clearTimeout(phoneTimer); phoneTimer = null;
  if (phoneStream) phoneStream.getTracks().forEach(track => track.stop());
  phoneStream = null; phoneSession = null;
  $p('phone-video').srcObject = null;
  $p('phone-camera').hidden = true;
  $p('phone-stop').hidden = true;
  $p('phone-snapshot').disabled = true;
  $p('phone-start').hidden = false;
  $p('phone-start').disabled = !$p('phone-consent').checked;
  $p('phone-camera-state').textContent = 'Cámara apagada';
  if (notify) { try { await phoneApi('/api/phone/leave'); } catch (_) {} }
}
// Envía el texto escrito a la otra persona y muestra el historial actualizado.
async function sendPhoneMessage(event) {
  event.preventDefault();
  const input = $p('phone-input'), text = input.value.trim();
  if (!text) return;
  try { const data = await phoneApi('/api/phone/message', {text}); input.value = ''; drawPhoneMessages(data); }
  catch (error) { phoneError(error.message); }
}
$p('phone-consent').addEventListener('change', () => { $p('phone-start').disabled = !$p('phone-consent').checked; });
$p('phone-start').addEventListener('click', startPhone);
$p('phone-stop').addEventListener('click', () => stopPhone(true));
$p('phone-form').addEventListener('submit', sendPhoneMessage);
window.addEventListener('pagehide', () => {
  clearTimeout(phoneTimer);
  phoneStream?.getTracks().forEach(track => track.stop());
  if (phoneSession) void fetch('/api/phone/leave', {method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({room: roomId, key: roomKey})}).catch(() => {});
});
void pollPhoneState();
setInterval(() => { if (!phoneStream) void pollPhoneState(); }, 1800);


// Congela una foto en memoria y compara su forma mediante el modo experimental de la sala.
async function takePhoneSnapshot() {
  if (!phoneStream || !phoneSession || phoneSnapshotBusy || !$p('phone-snapshot-mode').checked) return;
  const video=$p('phone-video'), canvas=$p('phone-snapshot-preview');
  if (!video.videoWidth || !video.videoHeight) return;
  const mark=phoneSession;
  const scale=Math.min(640/video.videoWidth,480/video.videoHeight,1);
  canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
  canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);canvas.hidden=false;
  const image=canvas.toDataURL('image/jpeg',.82).split(',')[1];
  phoneSnapshotBusy=true;$p('phone-snapshot').disabled=true;
  $p('phone-snapshot-result').textContent='Comparando la foto…';
  try {
    const result=await phoneApi('/api/phone/snapshot',{image});
    if (mark!==phoneSession) return;
    $p('phone-snapshot-result').textContent=result.accepted ? `${result.label.text} · comparación de forma, sin probabilidad temporal.` : result.reason;
    $p('phone-result').textContent=result.accepted ? result.label.text : 'Foto sin confirmar';
    if (result.conversation) drawPhoneMessages(result.conversation);
  } catch(error) {phoneError(error.message);}
  finally {phoneSnapshotBusy=false;$p('phone-snapshot').disabled=!phoneStream || !$p('phone-snapshot-mode').checked;}
}
$p('phone-snapshot').addEventListener('click',takePhoneSnapshot);
$p('phone-snapshot-mode').addEventListener('change',()=>{
  $p('phone-snapshot').disabled=!phoneStream || phoneSnapshotBusy || !$p('phone-snapshot-mode').checked;
  $p('phone-snapshot-preview').hidden=true;
});
