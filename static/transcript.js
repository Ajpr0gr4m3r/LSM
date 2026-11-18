'use strict';
// Conversación continua: acumula señas confirmadas sin límite de tiempo, cierra
// cada frase tras una pausa y la convierte en español con SenaPhrasebook.

const transcript = {
  sentences: [],   // {text, signs, start, end}
  current: [],     // señas de la frase en curso: {id, text, confidence, time}
  lastSignAt: 0,
  startedAt: null,
  phrasebook: null,
  bookKey: null,
};

function transcriptBook() {
  const book = typeof profile === 'function' ? profile()?.phrasebook : null;
  const key = JSON.stringify(book || {});
  if (!transcript.phrasebook || transcript.bookKey !== key) {
    transcript.phrasebook = new SenaPhrasebook(book || {});
    transcript.bookKey = key;
  }
  return transcript.phrasebook;
}

function transcriptPauseMs() {
  return Number($('transcript-pause').value) || 3000;
}

// La voz por seña sigue activa solo si se eligió «Cada seña».
function transcriptSpeaksEachSign() {
  return $('transcript-voice').value === 'sign';
}

function transcriptAddSign(sign, confidence) {
  if (!sign?.text) return;
  const now = Date.now();
  transcript.startedAt ??= now;
  transcript.current.push({ id: sign.id, text: sign.text, confidence, time: now });
  transcript.lastSignAt = now;
  renderTranscript();
}

function transcriptFinish() {
  if (!transcript.current.length) return;
  const signs = transcript.current;
  const text = transcriptBook().compose(signs);
  transcript.current = [];
  if (!text) return renderTranscript();
  transcript.sentences.push({ text, signs: signs.map((s) => s.text), start: signs[0].time, end: signs.at(-1).time });
  if ($('transcript-voice').value === 'sentence' && typeof automaticSpeech !== 'undefined')
    automaticSpeech.enqueue(text, profile()?.locale || 'es-MX');
  if (typeof publishRecognizedSign === 'function') void publishRecognizedSign(text, null);
  renderTranscript();
}

function transcriptClock(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(seconds / 3600);
  const mm = String(Math.floor((seconds % 3600) / 60)).padStart(hours ? 2 : 1, '0');
  const ss = String(seconds % 60).padStart(2, '0');
  return hours ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

function transcriptPlainText() {
  return transcript.sentences.map((s) => s.text).join('\n');
}

function renderTranscript() {
  const hasCurrent = transcript.current.length > 0;
  const hasSentences = transcript.sentences.length > 0;
  $('transcript-draft').textContent = hasCurrent ? transcriptBook().compose(transcript.current) : '—';
  $('transcript-glosses').replaceChildren(...transcript.current.map((s) => {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = s.text;
    return chip;
  }));
  const list = $('transcript-list');
  if (list.children.length > transcript.sentences.length) list.replaceChildren();
  for (const sentence of transcript.sentences.slice(list.children.length)) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.title = 'Escuchar de nuevo';
    button.textContent = sentence.text;
    button.addEventListener('click', () => {
      if (typeof automaticSpeech !== 'undefined') automaticSpeech.enqueue(sentence.text, profile()?.locale || 'es-MX');
    });
    const detail = document.createElement('small');
    detail.textContent = `${new Date(sentence.end).toLocaleTimeString('es-MX')} · ${sentence.signs.join(' + ')}`;
    item.append(button, detail);
    list.append(item);
    list.scrollTop = list.scrollHeight;
  }
  $('transcript-empty').hidden = hasSentences;
  $('transcript-finish').disabled = !hasCurrent;
  $('transcript-undo').disabled = !hasCurrent;
  for (const id of ['transcript-copy', 'transcript-download', 'transcript-clear'])
    $(id).disabled = !hasSentences && !hasCurrent;
  $('transcript-duration').textContent = transcript.startedAt
    ? transcriptClock((hasCurrent ? Date.now() : (transcript.sentences.at(-1)?.end ?? Date.now())) - transcript.startedAt)
    : '0:00';
}

function transcriptClear() {
  transcript.sentences = [];
  transcript.current = [];
  transcript.startedAt = null;
  $('transcript-list').replaceChildren();
  renderTranscript();
}

function transcriptDownload() {
  transcriptFinish();
  const header = `Conversación en LSM traducida por Seña · ${new Date().toLocaleString('es-MX')}\n\n`;
  const body = transcript.sentences
    .map((s) => `[${new Date(s.end).toLocaleTimeString('es-MX')}] ${s.text}\n    Señas: ${s.signs.join(' + ')}`)
    .join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([header + body + '\n'], { type: 'text/plain;charset=utf-8' }));
  link.download = `conversacion-lsm-${new Date().toISOString().slice(0, 19).replaceAll(':', '-')}.txt`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

// Cierra la frase cuando pasa la pausa elegida sin señas nuevas.
setInterval(() => {
  if (transcript.current.length && Date.now() - transcript.lastSignAt >= transcriptPauseMs()) transcriptFinish();
  else if (transcript.current.length) renderTranscript();
}, 300);

$('transcript-finish').addEventListener('click', transcriptFinish);
$('transcript-undo').addEventListener('click', () => {
  transcript.current.pop();
  transcript.lastSignAt = Date.now();
  renderTranscript();
});
$('transcript-copy').addEventListener('click', async () => {
  transcriptFinish();
  try {
    await navigator.clipboard.writeText(transcriptPlainText());
    notice('Conversación copiada.');
  } catch (_) {
    notice('El navegador no permitió copiar. Usa Descargar.', true);
  }
});
$('transcript-download').addEventListener('click', transcriptDownload);
$('transcript-clear').addEventListener('click', transcriptClear);
for (const id of ['transcript-pause', 'transcript-voice']) {
  const saved = localStorage.getItem(`sena-${id}`);
  if (saved && [...$(id).options].some((o) => o.value === saved)) $(id).value = saved;
  $(id).addEventListener('change', () => localStorage.setItem(`sena-${id}`, $(id).value));
}
renderTranscript();
