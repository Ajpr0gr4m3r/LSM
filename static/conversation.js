'use strict';
let conversationRoom = null;
let conversationTimer = null;
let conversationLastMessage = 0;
let conversationSeen = new Set();
const conversationEmpty = $('conversation-empty');
const conversationSpeech = new SenaSpeechQueue(window.speechSynthesis, window.SpeechSynthesisUtterance,
  () => { $('conversation-status').textContent = 'Voz no disponible'; });

// Dibuja mensajes y borradores temporales y anuncia solamente respuestas nuevas de la otra persona.
function conversationRender(data) {
  const host = $('conversation-messages');
  const messages = data.messages || [];
  host.replaceChildren();
  conversationEmpty.hidden = messages.length > 0;
  if (!messages.length) host.append(conversationEmpty);
  for (const message of messages) {
    const row = document.createElement('article');
    row.className = 'conversation-message' + (message.sender === 'Computadora' ? ' mine' : '');
    const heading = document.createElement('div');
    heading.className = 'conversation-message-meta';
    heading.textContent = message.kind === 'sign' ? `${message.sender} · seña reconocida` : message.sender;
    const text = document.createElement('p');
    text.textContent = message.text;
    row.append(heading, text);
    if (message.kind === 'sign' && Number.isFinite(message.confidence)) {
      const confidence = document.createElement('small');
      confidence.textContent = `${(message.confidence * 100).toFixed(0)}% de confianza`;
      row.append(confidence);
    }
    host.append(row);
    if (!conversationSeen.has(message.id)) {
      conversationSeen.add(message.id);
      if (message.sender !== 'Computadora' && message.sender !== 'Señas')
        conversationSpeech.enqueue(message.text, profile()?.locale || data.locale || 'es-MX');
      else if (message.sender === 'Señas')
        conversationSpeech.enqueue(message.text, profile()?.locale || data.locale || 'es-MX');
    }
  }
  const drafts = Object.values(data.sign_drafts || {});
  if (drafts.length) {
    const pending = document.createElement('p');
    pending.className = 'help';
    pending.textContent = `Escribiendo: ${drafts.join(' · ')} — se enviará tras ${data.sign_pause_seconds || 4} s de pausa.`;
    host.append(pending);
  }
  host.scrollTop = host.scrollHeight;
  $('conversation-status').textContent = data.phone_connected
    ? `Teléfono conectado · ${Math.ceil(data.expires_in / 60)} min`
    : `Esperando teléfono · ${Math.ceil(data.expires_in / 60)} min`;
  $('conversation-input').disabled = false;
  $('send-conversation-message').disabled = false;
}
// Consulta el estado de la sala y limpia la interfaz si vence o deja de estar disponible.
async function conversationPoll() {
  if (!conversationRoom) return;
  try {
    const data = await api('/api/conversation/state', conversationRoom);
    conversationRender(data);
    if (!data.expires_in) closeConversationUI('La sala venció. Crea otra para continuar.');
  } catch (error) {
    closeConversationUI(error.message);
  }
}
// Restablece controles y estado vacío conservando una referencia estable al mensaje inicial.
function closeConversationUI(message = '') {
  clearInterval(conversationTimer);
  conversationTimer = null;
  conversationRoom = null;
  $('conversation-link-box').hidden = true;
  $('conversation-link').value = '';
  $('conversation-qr').removeAttribute('src');
  $('conversation-qr').hidden = true;
  $('conversation-consent').disabled = false;
  $('create-conversation').disabled = false;
  $('create-conversation').hidden = false;
  $('close-conversation').hidden = true;
  $('conversation-input').disabled = true;
  $('send-conversation-message').disabled = true;
  $('conversation-status').textContent = 'Sin iniciar';
  const host = $('conversation-messages');
  host.replaceChildren();
  conversationEmpty.hidden = false;
  conversationEmpty.textContent = 'Crea una sala y envía el primer mensaje.';
  host.append(conversationEmpty);
  if (message) $('conversation-link-status').textContent = message;
}
// Crea una sala con consentimiento y presenta QR y enlace si se configuró HTTPS móvil.
async function createConversation() {
  if (!$('conversation-consent').checked) {
    $('conversation-link-status').textContent = 'Confirma primero el uso de los mensajes en esta sala.';
    return;
  }
  $('create-conversation').disabled = true;
  try {
    const result = await api('/api/conversation/create', {language, shared_consent: true});
    conversationRoom = {room: result.room, key: result.desktop_key};
    conversationSeen.clear();
    $('conversation-consent').disabled = true;
    $('create-conversation').hidden = true;
    $('close-conversation').hidden = false;
    $('conversation-messages').replaceChildren();
    conversationEmpty.hidden = false;
    $('conversation-messages').append(conversationEmpty);
    if (result.phone_url) {
      $('conversation-link').value = result.phone_url;
      $('conversation-qr').src = `data:image/png;base64,${result.qr_png}`;
      $('conversation-qr').hidden = false;
      $('conversation-link-box').hidden = false;
      $('conversation-expiry').textContent = 'Este enlace deja de funcionar en 60 minutos o cuando termines la sala.';
      $('conversation-link-status').textContent = 'Escanea el código con el teléfono. Ambos dispositivos deben estar conectados a la red privada del laboratorio.';
    } else {
      $('conversation-link-box').hidden = true;
      $('conversation-link-status').textContent = 'La sala de texto está lista en esta computadora. Para enlazar el teléfono, inicia el servidor con su dirección HTTPS privada; consulta docs/CAMARA_TELEFONO.md.';
    }
    await conversationPoll();
    conversationTimer = setInterval(conversationPoll, 1400);
  } catch (error) {
    $('conversation-link-status').textContent = error.message;
    $('create-conversation').disabled = false;
  }
}
// Revoca la sala en el servidor y elimina su presentación local.
async function endConversation() {
  if (!conversationRoom) return;
  const room = conversationRoom;
  try { await api('/api/conversation/close', room); } catch (_) {}
  closeConversationUI('Conversación terminada. El enlace del teléfono ya no es válido.');
}
// Envía una respuesta escrita y la incorpora al historial compartido.
async function sendConversationMessage(event) {
  event.preventDefault();
  if (!conversationRoom || !$('conversation-input').value.trim()) return;
  const text = $('conversation-input').value.trim();
  $('send-conversation-message').disabled = true;
  try {
    const data = await api('/api/conversation/message', {...conversationRoom, text});
    $('conversation-input').value = '';
    conversationRender(data);
  } catch (error) {
    $('conversation-link-status').textContent = error.message;
  } finally {
    $('send-conversation-message').disabled = !conversationRoom;
  }
}
// Acumula una confirmación de la cámara de computadora en el borrador de su sala.
async function publishRecognizedSign(text, confidence) {
  if (!conversationRoom || currentView !== 'recognition') return;
  try {
    const data = await api('/api/conversation/sign', {...conversationRoom, text, confidence});
    conversationRender(data);
    notice(`Escribiendo: ${data.sign_drafts?.desktop || text} · envío tras 4 s de pausa.`);
  }
  catch (error) { notice(error.message, true); }
}
$('create-conversation').addEventListener('click', createConversation);
$('close-conversation').addEventListener('click', endConversation);
$('conversation-form').addEventListener('submit', sendConversationMessage);
$('copy-conversation-link').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('conversation-link').value);
    $('conversation-link-status').textContent = 'Enlace copiado. Envíalo solo a la persona con quien vas a hablar.';
  } catch (_) { $('conversation-link').select(); $('conversation-link-status').textContent = 'Selecciona y copia el enlace.'; }
});
window.addEventListener('pagehide', () => { clearInterval(conversationTimer); });
