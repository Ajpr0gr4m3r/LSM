'use strict';
// Generador de Dataset Sintético: subir fotos/videos, generar, revisar y guardar.
const synthetic = { sources: [], job: null, start: 0, poll: null, animations: new Map(), busy: false };
const SYNTHETIC_MAX_BYTES = 35 * 1024 * 1024;
const HAND_BONES = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11],
  [11, 12], [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [0, 17], [17, 18], [18, 19], [19, 20]];
const BODY_BONES = [['11', '12'], ['11', '13'], ['13', '15'], ['12', '14'], ['14', '16']];

function syntheticLanguage() {
  return typeof language !== 'undefined' ? language : 'lsm';
}

// Ajusta el encuadre a todas las manos y el torso de la animación.
function frameBounds(frames) {
  const xs = [], ys = [];
  for (const frame of frames) {
    for (const hand of frame.hands || []) if (hand) for (const [x, y] of hand) { xs.push(x); ys.push(y); }
    for (const [x, y] of Object.values(frame.body || {})) { xs.push(x); ys.push(y); }
  }
  if (!xs.length) return { x: 0, y: 0, size: 1 };
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const size = Math.max(maxX - minX, maxY - minY, .05) * 1.15;
  return { x: (minX + maxX) / 2 - size / 2, y: (minY + maxY) / 2 - size / 2, size };
}

function drawSkeleton(canvas, frame, bounds) {
  const context = canvas.getContext('2d');
  const { width, height } = canvas;
  context.clearRect(0, 0, width, height);
  const style = getComputedStyle(document.documentElement);
  const accent = style.getPropertyValue('--accent').trim() || '#e8a27c';
  const ink = style.getPropertyValue('--ink').trim() || '#ddd';
  const point = ([x, y]) => [(x - bounds.x) / bounds.size * width, (y - bounds.y) / bounds.size * height];
  context.lineWidth = 2;
  context.strokeStyle = ink;
  context.globalAlpha = .5;
  for (const [a, b] of BODY_BONES) {
    if (!frame.body?.[a] || !frame.body?.[b]) continue;
    context.beginPath(); context.moveTo(...point(frame.body[a])); context.lineTo(...point(frame.body[b])); context.stroke();
  }
  if (frame.body?.['0']) {
    const [x, y] = point(frame.body['0']);
    context.beginPath(); context.arc(x, y, width * .06, 0, Math.PI * 2); context.stroke();
  }
  context.globalAlpha = 1;
  (frame.hands || []).forEach((hand, side) => {
    if (!hand) return;
    context.strokeStyle = side ? accent : ink;
    context.fillStyle = context.strokeStyle;
    for (const [a, b] of HAND_BONES) {
      context.beginPath(); context.moveTo(...point(hand[a])); context.lineTo(...point(hand[b])); context.stroke();
    }
    for (const p of hand) { const [x, y] = point(p); context.fillRect(x - 1.5, y - 1.5, 3, 3); }
  });
}

function animate(canvas, frames) {
  if (!frames?.length) return;
  const bounds = frameBounds(frames);
  let index = 0;
  drawSkeleton(canvas, frames[0], bounds);
  if (frames.length < 2) return;
  const timer = setInterval(() => {
    if (!canvas.isConnected) return clearInterval(timer);
    index = (index + 1) % frames.length;
    drawSkeleton(canvas, frames[index], bounds);
  }, 300);
  synthetic.animations.set(canvas, timer);
}

function stopAnimations() {
  for (const timer of synthetic.animations.values()) clearInterval(timer);
  synthetic.animations.clear();
}

async function syntheticRequest(path, body = {}) {
  return api(path, { language: syntheticLanguage(), ...body });
}

async function syntheticRefresh() {
  try {
    const data = await syntheticRequest('/api/synthetic/state', { job: synthetic.job?.id, start: synthetic.start });
    synthetic.sources = data.sources;
    synthetic.job = data.job;
    synthetic.stored = data.stored || {};
    renderSynthetic();
    const working = data.sources.some((s) => s.state === 'processing') || data.job?.state === 'running';
    clearTimeout(synthetic.poll);
    if (working && currentView === 'synthetic') synthetic.poll = setTimeout(syntheticRefresh, 700);
  } catch (error) {
    notice(error.message, true);
  }
}

function syntheticOpen() {
  const labels = (profile()?.labels || []).filter((l) => l.id !== 'espacio');
  $('synthetic-labels').replaceChildren(...labels.map((l) => makeOption(l.text, l.text)));
  syntheticLoadDatasetOptions();
  syntheticRefresh();
}

let syntheticDatasetOptions = [];
async function syntheticLoadDatasetOptions() {
  const select = $('synthetic-dataset-label');
  const button = $('synthetic-dataset-add');
  const selectedLanguage = syntheticLanguage();
  button.disabled = true;
  select.replaceChildren(makeOption('', 'Cargando señas…'));
  try {
    const data = await syntheticRequest('/api/synthetic/dataset-options');
    if (selectedLanguage !== syntheticLanguage()) return;
    syntheticDatasetOptions = data.options;
    select.replaceChildren(makeOption('', 'Elige una seña · mayor validación primero'),
      ...data.options.map(row => makeOption(row.id, row.text)));
    $('synthetic-dataset-info').textContent = data.options.length
      ? 'Elige una seña para ver sus resultados de validación.'
      : 'No hay un modelo activo con señas disponibles. Entrena un modelo primero.';
  } catch (error) {
    select.replaceChildren(makeOption('', 'No se pudieron consultar las señas'));
    $('synthetic-dataset-info').textContent = error.message;
  }
}
$('synthetic-dataset-label').addEventListener('change', () => {
  const row = syntheticDatasetOptions.find(item => item.id === $('synthetic-dataset-label').value);
  $('synthetic-dataset-add').disabled = !row;
  $('synthetic-dataset-info').textContent = row
    ? `${row.precision == null ? "Sin dato" : Math.round(row.precision * 100) + " %"} de precisión de validación · ${row.accepted} aceptadas · ${row.support} ejemplos de validación.`
    : 'Elige una seña para ver sus resultados de validación.';
});
$('synthetic-dataset-add').addEventListener('click', async () => {
  const row = syntheticDatasetOptions.find(item => item.id === $('synthetic-dataset-label').value);
  if (!row) return;
  const button = $('synthetic-dataset-add');
  button.disabled = true;
  try {
    await syntheticRequest('/api/synthetic/dataset-source', {label_id: row.id});
    $('synthetic-label').value = row.text;
    $('synthetic-semantic').checked = true;
    await syntheticRefresh();
  } catch (error) {
    notice(error.message, true);
  } finally {
    button.disabled = false;
  }
});

function sourceDescription(source) {
  if (source.kind === 'dataset') {
    if (source.state === 'processing') return 'Buscando la toma con mayor puntuación…';
    if (source.state === 'error') return source.error;
    return `Dataset real · mejor puntuación disponible ${Math.round(source.confidence * 100)} %`;
  }
  if (source.state === 'processing') return source.kind !== 'image'
    ? `Procesando video… ${Math.round((source.progress || 0) * 100)} %` : 'Detectando manos…';
  if (source.state === 'error') return source.error;
  const hands = (source.hands || []).map((h, i) => (h ? (i ? 'derecha' : 'izquierda') : null)).filter(Boolean);
  const kind = source.static ? 'Foto · seña estática'
    : `${source.kind === 'camera' ? 'Grabación' : 'Video'} · ${source.frames_with_hands}/${source.frames_read} fotogramas con manos`;
  return `${kind} · mano ${hands.join(' y ') || '—'}`;
}

function renderSources() {
  $('synthetic-sources').replaceChildren(...synthetic.sources.map((source) => {
    const item = document.createElement('li');
    if (source.state === 'error') item.classList.add('error');
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 128;
    const text = document.createElement('div');
    const name = document.createElement('strong');
    name.textContent = source.name;
    const detail = document.createElement('small');
    detail.textContent = sourceDescription(source);
    text.append(name, detail);
    for (const warning of source.warnings || []) {
      const extra = document.createElement('small');
      extra.textContent = '⚠ ' + warning;
      text.append(extra);
    }
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'text-button';
    remove.textContent = 'Quitar';
    remove.addEventListener('click', async () => {
      await syntheticRequest('/api/synthetic/remove-source', { source: source.id });
      syntheticRefresh();
    });
    item.append(canvas, text, remove);
    if (source.preview?.length) animate(canvas, source.preview);
    return item;
  }));
}

function transformText(params) {
  const hand = params.hands?.find(Boolean) || {};
  const pct = (v) => `${v >= 1 ? '+' : ''}${Math.round((v - 1) * 100)} %`;
  return [`mano ${pct(hand.scale ?? 1)}`, `distancia ${pct(params.body_scale ?? 1)}`,
    `giro ${Math.round(hand.roll ?? 0)}°`, `velocidad ${pct(params.speed ?? 1)}`].join(' · ');
}

function renderJob() {
  const job = synthetic.job;
  const running = job?.state === 'running';
  $('synthetic-cancel').hidden = !running;
  $('synthetic-progress-wrap').hidden = !job;
  const ready = synthetic.sources.filter((s) => s.state === 'ready');
  $('synthetic-generate').disabled = running || !ready.length || synthetic.busy;
  $('synthetic-save').disabled = !job || running || job.state === 'saved' || !job.done;
  if (!job) {
    $('synthetic-review-title').textContent = 'Sin muestras todavía';
    $('synthetic-stats').textContent = 'Sube un archivo y genera variaciones para revisarlas aquí.';
    $('synthetic-previews').replaceChildren();
    $('synthetic-pager').hidden = true;
    return;
  }
  const rejected = Object.values(job.rejected || {}).reduce((a, b) => a + b, 0);
  const percent = Math.round((job.done / Math.max(job.count, 1)) * 100);
  $('synthetic-progress').style.width = `${percent}%`;
  const states = { running: 'Generando…', done: 'Listo para revisar', cancelled: 'Cancelado', saved: 'Guardado', error: 'Error' };
  $('synthetic-progress-text').textContent =
    `${states[job.state] || job.state} · ${job.done}/${job.count} válidas · ${rejected} descartadas de ${job.attempts} intentos · ${job.elapsed} s`;
  $('synthetic-review-title').textContent = `${job.label} · ${job.done} muestras (${job.level})`;
  const reasons = Object.entries(job.rejected || {}).map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`).join(', ');
  const semantic = { activa: 'el modelo activo confirmó cada variación',
    'sin modelo activo': 'sin comprobación con el modelo (no hay modelo activo)',
    'la seña no está en el modelo activo': 'sin comprobación con el modelo (la seña aún no está entrenada)',
    'el modelo activo no reconoce el original como esta seña': 'sin comprobación con el modelo (no reconoce el original)' }[job.semantic] || '';
  $('synthetic-stats').textContent = [
    `Aprobadas ${job.review.approved} · rechazadas ${job.review.rejected} · sin revisar ${job.review.pending}.`,
    reasons && `Descartes automáticos: ${reasons}.`, semantic && `Validación: ${semantic}.`,
    job.note, job.error].filter(Boolean).join(' ');
  stopAnimations();
  $('synthetic-previews').replaceChildren(...(job.previews || []).map((preview) => {
    const card = document.createElement('div');
    card.className = `synthetic-card ${preview.status}`;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 220;
    const info = document.createElement('small');
    info.textContent = `#${preview.index + 1} · ${transformText(preview.params)}`;
    const actions = document.createElement('div');
    actions.className = 'synthetic-actions';
    for (const [action, label, title] of [['approve', '✓', 'Aprobar'], ['reject', '✕', 'Rechazar'], ['regenerate', '↻', 'Regenerar']]) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'secondary';
      button.textContent = label;
      button.title = title;
      button.setAttribute('aria-label', `${title} muestra ${preview.index + 1}`);
      button.addEventListener('click', () => syntheticReview(preview.index, action));
      actions.append(button);
    }
    card.append(canvas, info, actions);
    animate(canvas, preview.frames);
    return card;
  }));
  const pages = Math.ceil(job.done / 24);
  $('synthetic-pager').hidden = pages < 2 || running;
  $('synthetic-page').textContent = `Página ${Math.floor(synthetic.start / 24) + 1} de ${pages}`;
  $('synthetic-prev').disabled = synthetic.start === 0;
  $('synthetic-next').disabled = synthetic.start + 24 >= job.done;
}

function renderSynthetic() {
  if (typeof currentView !== 'undefined' && currentView !== 'synthetic') return;
  renderSources();
  renderJob();
  const label = $('synthetic-label').value.trim();
  const existing = (profile()?.labels || []).find((l) => l.text.toLocaleLowerCase('es-MX') === label.toLocaleLowerCase('es-MX'));
  $('synthetic-label-info').textContent = !label ? 'Escribe o elige la seña que muestran los archivos.'
    : existing ? `Seña existente · ${existing.samples ?? 0} tomas reales · ${synthetic.stored?.[existing.id] || 0} sintéticas guardadas.`
      : 'Seña nueva: se añadirá al vocabulario al guardar.';
  const total = Object.values(synthetic.stored || {}).reduce((a, b) => a + b, 0);
  $('synthetic-stored').textContent = `${total} muestras sintéticas guardadas en este perfil.`;
}

async function syntheticUpload(files) {
  for (const file of files) {
    if (file.size > SYNTHETIC_MAX_BYTES) {
      notice(`${file.name} pesa más de 35 MB. Recorta el video a la seña.`, true);
      continue;
    }
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
      reader.onerror = () => reject(new Error(`No se pudo leer ${file.name}.`));
      reader.readAsDataURL(file);
    });
    try {
      await syntheticRequest('/api/synthetic/source', { name: file.name, type: file.type, data,
        mirror: $('synthetic-mirror').checked });
    } catch (error) {
      notice(`${file.name}: ${error.message}`, true);
    }
    syntheticRefresh();
  }
}

function syntheticCount() {
  return $('synthetic-count').value === 'custom' ? Number($('synthetic-custom').value) : Number($('synthetic-count').value);
}

async function syntheticGenerate() {
  const label = $('synthetic-label').value.trim();
  if (!label) return notice('Escribe o elige el nombre de la seña.', true);
  const count = syntheticCount();
  if (!Number.isInteger(count) || count < 1 || count > 1000) return notice('Elige entre 1 y 1000 muestras.', true);
  synthetic.busy = true;
  synthetic.start = 0;
  try {
    synthetic.job = await syntheticRequest('/api/synthetic/generate', {
      label, count, level: $('synthetic-level').value, seed: Number($('synthetic-seed').value) || 0,
      sources: synthetic.sources.filter((s) => s.state === 'ready').map((s) => s.id),
      semantic_check: $('synthetic-semantic').checked });
  } catch (error) {
    notice(error.message, true);
  } finally {
    synthetic.busy = false;
    syntheticRefresh();
  }
}

async function syntheticReview(index, action) {
  try {
    await syntheticRequest('/api/synthetic/review', { job: synthetic.job.id, index, action });
    syntheticRefresh();
  } catch (error) {
    notice(error.message, true);
  }
}

async function syntheticSave() {
  try {
    const result = await syntheticRequest('/api/synthetic/save', {
      job: synthetic.job.id, include_pending: $('synthetic-include-pending').checked,
      save_real: $('synthetic-save-real').checked, participant: $('synthetic-participant').value });
    notice(`${result.saved} muestras sintéticas guardadas para «${result.label.text}»` +
      (result.real_saved ? ` y ${result.real_saved} toma(s) real(es) del video.` : '.') +
      ' En Entrenamiento elige «Reales + sintéticas».');
    await refresh();
    await syntheticRefresh();
  } catch (error) {
    notice(error.message, true);
  }
}

const drop = $('synthetic-drop');
drop.addEventListener('click', () => $('synthetic-files').click());
drop.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('synthetic-files').click(); }
});
drop.addEventListener('dragover', (event) => { event.preventDefault(); drop.classList.add('dragging'); });
drop.addEventListener('dragleave', () => drop.classList.remove('dragging'));
drop.addEventListener('drop', (event) => {
  event.preventDefault();
  drop.classList.remove('dragging');
  syntheticUpload([...event.dataTransfer.files]);
});
$('synthetic-files').addEventListener('change', (event) => {
  syntheticUpload([...event.target.files]);
  event.target.value = '';
});
$('synthetic-count').addEventListener('change', () => {
  $('synthetic-custom-wrap').hidden = $('synthetic-count').value !== 'custom';
});
$('synthetic-label').addEventListener('input', renderSynthetic);
$('synthetic-generate').addEventListener('click', syntheticGenerate);
$('synthetic-cancel').addEventListener('click', async () => {
  await syntheticRequest('/api/synthetic/cancel', { job: synthetic.job?.id });
  syntheticRefresh();
});
$('synthetic-save').addEventListener('click', syntheticSave);
$('synthetic-prev').addEventListener('click', () => { synthetic.start = Math.max(0, synthetic.start - 24); syntheticRefresh(); });
$('synthetic-next').addEventListener('click', () => { synthetic.start += 24; syntheticRefresh(); });
$('synthetic-to-training').addEventListener('click', () => {
  $('training-data-mode').value = 'mixed';
  $('training-ratio-wrap').hidden = false;
  navigateStudio('training');
});
$('training-data-mode').addEventListener('change', () => {
  $('training-ratio-wrap').hidden = $('training-data-mode').value !== 'mixed';
});

// ── Grabar con la cámara ────────────────────────────────────────────────────
// Captura fotogramas JPEG de 640×480 a 10 fps, sin espejo: lo mismo que recibe
// /api/frame al reconocer. Reutiliza la cámara de Seña si ya está abierta.
const recorder = { stream: null, own: false, recording: false, stop: false, takes: 0 };

function recorderStatus(text) {
  $('synthetic-recorder-status').textContent = text;
}

async function openRecorder() {
  $('synthetic-recorder').hidden = false;
  $('synthetic-open-recorder').hidden = true;
  $('synthetic-recorder-seconds').value = (profile()?.frame_stride || 1) > 1 ? '6' : '3';
  try {
    if (typeof stream !== 'undefined' && stream?.active) {
      recorder.stream = stream;
      recorder.own = false;
    } else {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error('La cámara necesita HTTPS o localhost. Abre la dirección segura de Seña.');
      const deviceId = $('camera-device')?.value;
      recorder.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 },
          ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'user' }) },
        audio: false,
      });
      recorder.own = true;
    }
    $('synthetic-recorder-video').srcObject = recorder.stream;
    await $('synthetic-recorder-video').play().catch(() => {});
    recorderStatus('Encuadra hombros y manos. Empieza con las manos abajo y bájalas al terminar.');
  } catch (error) {
    recorderStatus(error.name === 'NotAllowedError'
      ? 'El navegador no dio permiso para usar la cámara. Permítelo en la barra de direcciones.'
      : error.name === 'NotReadableError'
        ? 'Otra aplicación está usando la cámara. Ciérrala e intenta de nuevo.'
        : error.message);
  }
}

function closeRecorder() {
  recorder.stop = true;
  if (recorder.own) recorder.stream?.getTracks().forEach((track) => track.stop());
  recorder.stream = null;
  recorder.own = false;
  $('synthetic-recorder-video').srcObject = null;
  $('synthetic-recorder').hidden = true;
  $('synthetic-open-recorder').hidden = false;
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function recordTake() {
  const video = $('synthetic-recorder-video');
  if (!recorder.stream || recorder.recording) return;
  if (!video.videoWidth) return recorderStatus('La cámara todavía no entrega video. Espera un momento.');
  recorder.recording = true;
  recorder.stop = false;
  $('synthetic-record').hidden = true;
  $('synthetic-record-stop').hidden = false;
  $('synthetic-recorder-seconds').disabled = $('synthetic-recorder-countdown').disabled = true;
  const seconds = Number($('synthetic-recorder-seconds').value) || 3;
  const total = seconds * 10;
  const canvas = document.createElement('canvas');
  const scale = Math.min(640 / video.videoWidth, 480 / video.videoHeight, 1);
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const context = canvas.getContext('2d');
  const frames = [];
  try {
    for (let n = Number($('synthetic-recorder-countdown').value); n > 0 && !recorder.stop; n--) {
      $('synthetic-recorder-count').textContent = n;
      recorderStatus('Prepárate: manos abajo.');
      await wait(1000);
    }
    $('synthetic-recorder-count').textContent = '';
    if (recorder.stop) return recorderStatus('Grabación cancelada.');
    $('synthetic-recorder-live').hidden = false;
    recorderStatus('Grabando… haz la seña completa.');
    const start = performance.now();
    while (frames.length < total && !recorder.stop) {
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      frames.push(canvas.toDataURL('image/jpeg', 0.82).split(',')[1]);
      $('synthetic-recorder-progress').style.width = `${(frames.length / total) * 100}%`;
      // Mantener 10 fps reales aunque un fotograma tarde más en codificarse.
      await wait(Math.max(0, start + frames.length * 100 - performance.now()));
    }
    $('synthetic-recorder-live').hidden = true;
    if (frames.length < 15) return recorderStatus('La grabación fue demasiado corta (mínimo 1.5 s). Inténtalo de nuevo.');
    recorder.takes += 1;
    recorderStatus(`Enviando ${frames.length} fotogramas (${(frames.length / 10).toFixed(1)} s)…`);
    await syntheticRequest('/api/synthetic/source', {
      name: `Grabación ${recorder.takes} · ${(frames.length / 10).toFixed(1)} s`, frames });
    recorderStatus('Listo: la grabación aparece en la lista. Puedes grabar otra toma.');
    syntheticRefresh();
  } catch (error) {
    recorderStatus(error.message);
  } finally {
    $('synthetic-recorder-live').hidden = true;
    $('synthetic-recorder-count').textContent = '';
    $('synthetic-recorder-progress').style.width = '0';
    $('synthetic-record').hidden = false;
    $('synthetic-record').textContent = 'Grabar otra toma';
    $('synthetic-record-stop').hidden = true;
    $('synthetic-recorder-seconds').disabled = $('synthetic-recorder-countdown').disabled = false;
    recorder.recording = false;
  }
}

$('synthetic-open-recorder').addEventListener('click', openRecorder);
$('synthetic-recorder-close').addEventListener('click', closeRecorder);
$('synthetic-record').addEventListener('click', recordTake);
$('synthetic-record-stop').addEventListener('click', () => { recorder.stop = true; });
// Al salir del Generador se libera la cámara que abrió el grabador.
new MutationObserver(() => {
  if ($('view-synthetic').hidden && !$('synthetic-recorder').hidden && !recorder.recording) closeRecorder();
}).observe($('view-synthetic'), { attributes: true, attributeFilter: ['hidden'] });
