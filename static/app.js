'use strict';
const $ = (id) => document.getElementById(id);
let state,
  language = ['lsm'].includes(
    localStorage.getItem('sena-profile'),
  )
    ? localStorage.getItem('sena-profile')
    : 'lsm',
  mode = 'test',
  session = null,
  stream = null;
let generation = 0,
  timer = null,
  countdown = false,
  recording = false,
  frameReady = false;
const trialDiagnostics = new Map();
let history = [],
  lastSpoken = null,
  lastConfirmationId = null,
  checks = 0,
  correct = 0,
  lastJobState = '';
let stateRequest = null;
let selectedDraft = null,
  displayedDraft = null,
  savingDraft = false;
let selectedLetter = null,
  addingAlphabet = false;
const batch = new ContinuousCapture();

let batchPause = 3;
let cameraStarting = false,
  cameraListing = false;
let snapshotBusy = false;
let deletingRecordings = false,
  adminLanguage = null,
  displayedModelKey = null;
const profile = () => state?.profiles.find((p) => p.id === language);

// Muestra o limpia una notificación general, indicando si es un error.
function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = error ? 'error' : '';
  $('notice').hidden = !message;
}
// Envía JSON a la API con el CSRF actual y convierte errores HTTP en mensajes utilizables.
async function api(path, body) {
  const options =
    body === undefined
      ? {}
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-LSM-Token': state?.token || '' },
          body: JSON.stringify(body),
        };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && typeof lockAccount === 'function') lockAccount();
    if (response.status === 404 && path.startsWith('/api/admin/')) {
      throw new Error(
        'El servidor activo es una versión anterior sin administración. Detén web_app.py con Ctrl+C, vuelve a ejecutarlo y recarga la página.',
      );
    }
    throw new Error(data.error || 'No se pudo completar la solicitud.');
  }
  return data;
}
// Crea una opción de selector usando texto seguro, sin interpretar HTML.
function makeOption(value, text) {
  const element = document.createElement('option');
  element.value = value;
  element.textContent = text;
  return element;
}
// Actualiza vocabulario, controles y estados habilitados según cámara, perfil y operaciones en curso.
function render() {
  const p = profile();
  if (!p) return;
  const modelKey = `${language}:${p.model?.created_at || 'disabled'}`;
  if (displayedModelKey !== modelKey) {
    displayedModelKey = modelKey;
    clearHistory();
  }
  $('languages').replaceChildren();
  for (const item of state.profiles) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'language-button';
    button.setAttribute('aria-current', String(item.id === language));
    const code = document.createElement('span');
    code.className = 'lang-code';
    code.textContent = item.code;
    const copy = document.createElement('span');
    copy.className = 'lang-copy';
    copy.textContent = item.written;
    const region = document.createElement('small');
    region.textContent = item.region;
    copy.append(region);
    const dot = document.createElement('span');
    dot.className = 'ready-dot' + (item.model ? ' ready' : '');
    dot.title = item.model ? 'Modelo entrenado' : 'Sin modelo';
    button.append(code, copy, dot);
    button.addEventListener('click', () => selectLanguage(item.id));
    $('languages').append(button);
  }
  $('breadcrumb').textContent = p.code;
  $('language-name').textContent = p.name;
  $('language-detail').textContent = `${p.region} · Texto de salida en ${p.written.toLowerCase()}`;
  $('output-language').textContent = p.written.toUpperCase();
  $('model-badge').textContent = p.model
    ? 'Modelo entrenado'
    : p.model_error
      ? 'Modelo no disponible'
      : 'Necesita entrenamiento';
  $('model-badge').className = 'badge' + (p.model ? ' ready' : '');
  $('legacy-note').hidden = !state.legacy_model;
  const drafts = p.drafts || [];
  if (!drafts.some((d) => d.id === selectedDraft)) selectedDraft = drafts[0]?.id || null;
  const draftKey = `${language}:${selectedDraft || ''}`;
  if (draftKey !== displayedDraft) {
    $('sign-name').value = selectedLetter || '';
    displayedDraft = draftKey;
  }
  $('name-capture').hidden = !selectedDraft;
  $('draft-language').textContent =
    `Esta grabación pertenece a ${p.code} · ${p.name}. Se conservará pendiente hasta que la guardes o descartes.`;
  $('draft-picker').replaceChildren(
    ...drafts.map((d) => makeOption(d.id, new Date(d.created_at * 1000).toLocaleString())),
  );
  if (selectedDraft) $('draft-picker').value = selectedDraft;
  $('draft-picker').hidden = drafts.length < 2;
  $('draft-picker-label').hidden = drafts.length < 2;
  $('sign-suggestions').replaceChildren(
    ...p.labels.map((item) => makeOption(item.text, item.text)),
  );
  const expected = $('expected-label').value;
  $('expected-label').replaceChildren(
    makeOption('', 'Sin seña esperada'),
    ...(p.model?.labels || []).map((item) => makeOption(item.id, item.text)),
  );
  if (p.model?.labels.some((x) => x.id === expected)) $('expected-label').value = expected;
  $('sample-list').replaceChildren();
  for (const item of p.labels) {
    const row = document.createElement('div');
    row.className = 'sample-row' + (item.samples >= state.minimum_samples ? ' enough' : '');
    const label = document.createElement('span');
    label.textContent = item.text;
    const count = document.createElement('strong');
    count.textContent = `${item.samples} / ${state.minimum_samples} mín. · recomendado 30–${state.recommended_samples}`;
    if (item.samples > 0 && !p.model?.labels.some((x) => x.id === item.id)) {
      const status = document.createElement('small');
      status.className = 'pending-label';
      status.textContent = 'Por entrenar';
      label.append(status);
    }
    row.append(label, count);
    if (item.invalid) {
      const invalid = document.createElement('small');
      invalid.textContent = ` ${item.invalid} inválidos`;
      row.append(invalid);
    }
    $('sample-list').append(row);
  }
  const populated = selectedTrainingClasses(p);
  const eligible =
    populated.length >= 2 && populated.every((x) => x.samples >= state.minimum_samples);
  const busy = state.job?.state === 'running';
  renderAdmin();
  $('train-model').disabled =
    !eligible || busy || recording || countdown || batch.active || !!selectedDraft || savingDraft;
  $('train-reason').textContent = selectedDraft
    ? 'Pon nombre y guarda tu grabación pendiente antes de entrenar.'
    : busy
      ? 'Hay un entrenamiento en curso. Puedes seguir viendo su avance.'
      : eligible
        ? `Se entrenarán ${populated.length} señas de ${p.code}. Recomendamos entre 30 y ${state.recommended_samples} ejemplos variados por palabra o letra. Las tandas pueden ser de 5 tomas; el entrenamiento requiere 30 por palabra o letra.`
        : `Completa al menos ${state.minimum_samples} ejemplos de cada seña que empezaste y reúne 2 señas diferentes. Recomendado: 30–${state.recommended_samples} por palabra o letra.`;
  $('start-camera').disabled = busy || cameraStarting;

  $('camera-device').disabled = busy || cameraStarting || savingDraft;
  $('refresh-cameras').disabled = cameraListing || cameraStarting;
  $('record').disabled =
    !stream ||
    !frameReady ||
    countdown ||
    recording ||
    batch.active ||
    busy ||
    !!selectedDraft ||
    savingDraft;
  $('save-capture').disabled = savingDraft || busy || batch.active;
  $('discard-capture').disabled = savingDraft || batch.active;
  $('save-all-captures').hidden = drafts.length < 2;
  $('save-all-description').hidden = drafts.length < 2;
  $('save-all-captures').disabled = savingDraft || busy || batch.active;
  $('save-all-captures').textContent = savingDraft ? 'Guardando…' : `Guardar las ${drafts.length} tomas con este nombre`;
  $('sign-name').disabled = savingDraft || busy || batch.active;
  $('draft-picker').disabled = batch.active;
  $('start-batch').disabled =
    !stream || !frameReady || countdown || recording || batch.active || savingDraft || busy;
  $('capture-countdown').disabled = recording || countdown || batch.active;
  $('take-snapshot').disabled = !stream || !frameReady || snapshotBusy || !$('snapshot-mode').checked;
  $('stop-batch').disabled = !batch.active;
  $('pause-batch').disabled = !batch.active || (batch.paused && (recording || countdown));
  $('pause-batch').textContent = batch.paused ? 'Continuar tanda' : 'Pausar tanda';
  $('batch-limit').disabled = batch.active;
  $('batch-pause').disabled = batch.active;
  renderBatchCounter();
  $('batch-status').textContent = batch.active
    ? batch.paused
      ? (recording ? 'Terminando la toma actual antes de pausar…' : `Tanda pausada · ${batch.count}/${batch.limit} tomas completas. Pulsa Continuar tanda.`)
      : 'Repite la seña después de cada cuenta atrás.'
    : batch.count
      ? 'Ponles nombre en Grabaciones pendientes.'
      : 'Elige cuántas tomas quieres y empieza la tanda.';
  $('expected-label').disabled = !p.model;
  if (!stream && !history.length) resetResult();
  $('recognition-vocabulary').textContent = p.model
    ? `Este modelo aprendió: ${p.model.labels.map(label => label.text).join(', ')}. Otras señas pueden confundirse; primero debes entrenarlas.`
    : 'Este perfil todavía no tiene señas aprendidas.';
  const summary = $('model-summary');
  summary.replaceChildren();
  if (p.model) {
    const strong = document.createElement('strong');
    strong.textContent = `${p.code}: ${p.model.labels.length} señas entrenadas. `;
    const learned = new Set(p.model.labels.map(label => label.id));
    const untrained = p.labels.filter(label => label.samples > 0 && !learned.has(label.id));
    if (untrained.length) {
      const warning = document.createElement('p');
      warning.className = 'model-warning';
      warning.textContent = `Aún no aprendió: ${untrained.map(label => label.text).join(', ')}. Inclúyelas en un nuevo entrenamiento antes de probarlas.`;
      summary.append(warning);
    }
    summary.append(
      strong,
      `Aciertos en prueba reservada: ${(100 * p.model.test_accuracy).toFixed(1)}% (${p.model.split.test} ejemplos). ${p.model.evaluation_note}`,
    );
  } else {
    summary.textContent =
      p.model_error ||
      `Este perfil está preparado para aprender. Todavía no tiene un modelo de ${p.code}; activar la cámara no generará detecciones inventadas.`;
  }
  $('model-metrics').replaceChildren();
  if (p.model?.validation_by_class) {
    for (const item of p.model.validation_by_class) {
      const row = document.createElement('p');
      row.textContent = `${item.text} · Validación: recuperación ${(100 * item.recall).toFixed(0)}%, cobertura ${(100 * item.coverage).toFixed(0)}%, precisión confirmada ${item.precision == null ? 'sin confirmaciones' : (100 * item.precision).toFixed(0) + '%'}.`;
      $('model-metrics').append(row);
    }
  }
  if (p.model?.report) {
    const title = document.createElement('h3');
    title.textContent = 'Resultados por seña en la prueba reservada';
    $('model-metrics').append(title);
    for (const label of p.model.labels) {
      const metric = p.model.report[label.id] || p.model.report[label.text];
      if (!metric) continue;
      const row = document.createElement('p');
      row.textContent = `${label.text}: precisión ${(100 * metric.precision).toFixed(1)}% · recuperación ${(100 * metric.recall).toFixed(1)}% · F1 ${(100 * metric['f1-score']).toFixed(1)}% · ${metric.support} ejemplos`;
      $('model-metrics').append(row);
    }
    const decision = p.model.test_decisions;
    const comparison = p.model.model_comparison;
    if (comparison?.previous_validation) {
      const row = document.createElement('p');
      row.textContent = `Comparación en validación: modelo anterior ${(100 * comparison.previous_validation.accuracy).toFixed(1)}% de aciertos; versión actual ${(100 * comparison.candidate_validation.accuracy).toFixed(1)}%. ${comparison.note}`;
      $('model-metrics').append(row);
    }
    if (decision) {
      const row = document.createElement('p');
      row.textContent = `Predicciones aceptadas con el filtro: ${decision.accepted} de ${decision.evaluated}. Aciertos entre las aceptadas: ${decision.accepted_accuracy === null ? 'sin predicciones aceptadas' : (100 * decision.accepted_accuracy).toFixed(1) + '%'}. Las demás se rechazan como dudosas.`;
      $('model-metrics').append(row);
    }
    if (!p.model.preprocessing) {
      const row = document.createElement('p');
      row.textContent =
        'Modelo anterior: reúne al menos 30 ejemplos por palabra o letra (recomendado: 30–60) y reentrena para aplicar la normalización y el entrenamiento mejorado.';
      $('model-metrics').append(row);
    }
  }
  renderAlphabet();
  renderJob();
  if (typeof renderStudio === 'function') renderStudio();
  if (typeof renderTeam === 'function') renderTeam();
}
// Dibuja los símbolos y su progreso y permite elegir una letra para nombrar la siguiente toma.
function renderAlphabet() {
  const p = profile(),
    alphabet = p.alphabet;
  if (!alphabet) return;
  $('alphabet-title').textContent = `${alphabet.title} · ${p.code}`;
  $('alphabet-note').textContent = alphabet.note;
  $('alphabet-count').textContent = `${alphabet.symbols.length} entradas básicas`;
  const registered = alphabet.symbols.filter((x) => x.label_id).length;
  const trained = alphabet.symbols.filter((x) => x.trained).length;
  $('alphabet-progress').textContent =
    `${registered} / ${alphabet.symbols.length} añadidas al vocabulario · ${trained} incluidas en el modelo. Pulsa una letra para grabar sus ejemplos.`;
  const busy = addingAlphabet || batch.active || state.job?.state === 'running';
  $('add-alphabet').disabled = busy || registered === alphabet.symbols.length;
  $('add-alphabet').textContent =
    registered === alphabet.symbols.length ? 'Abecedario añadido' : 'Añadir todo el abecedario';
  $('add-all-alphabets').disabled = busy;
  $('add-alphabet-extras').disabled = busy || alphabet.extras.every((x) => x.label_id);
  $('alphabet-extras').hidden = !alphabet.extras.length;
  const buildGrid = (id, entries) => {
    $(id).replaceChildren();
    for (const entry of entries) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'letter-tile' + (entry.trained ? ' trained' : '');
      button.setAttribute('aria-pressed', String(selectedLetter === entry.symbol));
      button.setAttribute(
        'aria-label',
        `${entry.symbol}: ${entry.samples} ejemplos${entry.trained ? ', incluida en el modelo' : ''}`,
      );
      button.disabled = recording || countdown || savingDraft || batch.active;
      const symbol = document.createElement('span');
      symbol.textContent = entry.symbol;
      const count = document.createElement('small');
      count.textContent = `${entry.samples} / ${state.minimum_samples}`;
      button.append(symbol, count);
      button.addEventListener('click', () => {
        selectedLetter = entry.symbol;
        if (selectedDraft) $('sign-name').value = entry.symbol;
        renderAlphabet();
        if (selectedDraft) {
          $('name-capture').scrollIntoView({ behavior: 'smooth', block: 'center' });
          $('sign-name').focus({ preventScroll: true });
        } else $('camera-workspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      $(id).append(button);
    }
  };
  buildGrid('alphabet-grid', alphabet.symbols);
  buildGrid('alphabet-extra-grid', alphabet.extras);
  $('alphabet-selection').textContent = selectedLetter
    ? `Letra seleccionada: ${selectedLetter} · ${p.code}. Al terminar la captura, confirma ese nombre y guarda el ejemplo.`
    : 'Selecciona una letra para preparar su nombre al terminar la grabación.';
  $('clear-alphabet-selection').hidden = !selectedLetter;
  $('alphabet-source').hidden = !alphabet.source;
  if (alphabet.source) $('alphabet-source').href = alphabet.source;
}
// Solicita registrar símbolos del perfil LSM, sin crear ejemplos ficticios.
async function addAlphabet(scope, extras = false) {
  if (addingAlphabet) return;
  const chosenLanguage = language;
  addingAlphabet = true;
  renderAlphabet();
  try {
    const result = await api('/api/alphabet', { language: chosenLanguage, scope, extras });
    await refresh();
    const added = result.results
      ? result.results.reduce((total, item) => total + item.added, 0)
      : result.added;
    notice(
      `${added} letras o caracteres añadidos al vocabulario español. Ahora puedes grabar ejemplos y entrenarlos.`,
    );
  } catch (error) {
    notice(error.message, true);
  } finally {
    addingAlphabet = false;
    renderAlphabet();
  }
}

// Muestra estado, época y métricas del trabajo real de entrenamiento.
function renderJob() {
  const job = state.job;
  $('job-panel').hidden = !job;
  if (!job) return;
  const code = state.profiles.find((p) => p.id === job.language)?.code || '';
  $('job-title').textContent =
    job.state === 'completed'
      ? job.activated === false
        ? `${code} · Versión guardada sin activar`
        : `${code} · Modelo listo para probar`
      : job.state === 'failed'
        ? `${code} · El entrenamiento no se completó`
        : `${code} · Época ${job.epoch || 0} de ${job.epochs || '…'}`;
  const weak = (job.result?.validation_by_class || []).filter(item =>
    item.recall < .6 || item.accepted < 2 || (item.precision || 0) < .9 || item.coverage < .25);
  $('job-description').textContent = (job.message || '') +
    (weak.length ? ` Necesitan revisión: ${weak.map(item => item.text).join(', ')}.` : '');
  $('job-progress').max = job.epochs || 40;
  $('job-progress').value = job.state === 'completed' ? job.epochs || 40 : job.epoch || 0;
  $('job-metrics').textContent = job.result
    ? `Prueba reservada: ${(100 * job.result.test_accuracy).toFixed(1)}% de aciertos`
    : job.metrics
      ? `Validación: ${(100 * (job.metrics.val_accuracy || 0)).toFixed(1)}% · F1: ${job.metrics.val_macro_f1 == null ? '—' : (100 * job.metrics.val_macro_f1).toFixed(1) + '%'} · Peor letra: ${job.metrics.val_min_recall == null ? '—' : (100 * job.metrics.val_min_recall).toFixed(1) + '%'} · Pérdida: ${(job.metrics.val_loss || 0).toFixed(3)}`
      : 'Preparando el modelo…';
  const fingerprint = `${job.id}:${job.state}`;
  if (lastJobState && fingerprint !== lastJobState && job.state === 'completed')
    notice(
      job.activated === false
        ? job.message
        : 'Entrenamiento terminado. Abre “Reconocimiento” y activa la cámara para comprobarlo.',
    );
  if (lastJobState && fingerprint !== lastJobState && job.state === 'failed')
    notice(job.message, true);
  lastJobState = fingerprint;
}
// Reutiliza la consulta de estado en curso y solo vuelve a dibujar cuando cambian sus datos.
async function refresh() {
  if (stateRequest) return stateRequest;
  const accountIdentity = typeof accountState !== 'undefined' ? accountState?.user?.id : null;
  stateRequest = api('/api/state')
    .then((data) => {
      if (typeof accountState !== 'undefined' && accountIdentity !== accountState?.user?.id) return;
      const changed = JSON.stringify(data) !== JSON.stringify(state);
      state = data;
      if (changed) render();
    })
    .finally(() => {
      stateRequest = null;
    });
  return stateRequest;
}
// Detiene la cámara, cambia el perfil y limpia estados que no deben cruzarse entre lenguas.
async function selectLanguage(id) {
  if (id === language) return;
  await stopCamera();
  language = id;
  localStorage.setItem('sena-profile', id);
  selectedLetter = null;
  batch.count = 0;
  clearHistory();
  notice('');
  render();
  if (typeof loadVersions === 'function' && currentView === 'training') await loadVersions();
}
// Traduce los modos históricos a las vistas actuales del estudio.
async function selectMode(next) {
  return navigateStudio(
    next === 'train' ? 'dataset' : next === 'guide' ? 'settings' : 'recognition',
  );
}
// Restaura el panel de reconocimiento sin inventar candidatos o confianza.
function resetResult() {
  $('result-word').textContent = profile()?.model ? 'Esperando una seña.' : 'Sin modelo activo.';
  $('result-description').textContent = profile()?.model
    ? 'Activa la cámara y realiza una de las señas entrenadas.'
    : 'Primero necesitas un modelo entrenado para esta lengua.';
  $('confidence').textContent = '—';
  $('confidence-progress').value = 0;
  $('stability').textContent = 'Esperando una secuencia';
}
// Actualiza opciones de borrado y sus requisitos según vocabulario, operación y permisos.
function renderAdmin() {
  const p = profile();
  const previous = adminLanguage === language ? $('admin-label').value : '';
  if (adminLanguage !== language) {
    $('admin-password').value = '';
    $('admin-confirm').checked = false;
    $('admin-message').textContent = '';
  }
  adminLanguage = language;
  const available = p.labels.filter((item) => item.samples + item.invalid > 0);
  $('admin-label').replaceChildren(
    makeOption('', 'Selecciona una palabra o letra'),
    ...available.map((item) =>
      makeOption(item.id, `${item.text} · ${item.samples + item.invalid} grabaciones`),
    ),
  );
  if (available.some((item) => item.id === previous)) $('admin-label').value = previous;
  else $('admin-confirm').checked = false;
  const selected = available.find((item) => item.id === $('admin-label').value);
  $('admin-target').textContent = selected
    ? `${p.code} · ${selected.text}: se retirarán ${selected.samples + selected.invalid} grabaciones del conjunto de entrenamiento.`
    : `${p.code} · Elige la palabra o letra cuyos ejemplos quieres borrar.`;
  const blocked =
    deletingRecordings || state.job?.state === 'running' || recording || countdown || batch.active;
  $('admin-label').disabled = blocked;
  $('admin-password').disabled = blocked;
  $('admin-confirm').disabled = blocked;
  $('admin-delete').disabled = blocked || !selected;
}
// Envía el borrado administrativo confirmado y actualiza el estado después de archivar ejemplos.
async function deleteRecordings(event) {
  event.preventDefault();
  if (deletingRecordings) return;
  const selectedLanguage = language,
    label = $('admin-label').value;
  const password = $('admin-password').value,
    confirmed = $('admin-confirm').checked;
  if (!label || !password || !confirmed) return;
  deletingRecordings = true;
  $('admin-password').value = '';
  renderAdmin();
  try {
    await stopCamera();
    const result = await api('/api/admin/delete-recordings', {
      language: selectedLanguage,
      label,
      password,
      confirmed,
    });
    if (language === selectedLanguage) {
      $('admin-confirm').checked = false;
      $('admin-message').textContent =
        `Se retiraron ${result.deleted} grabaciones. Se conservaron en la carpeta de recuperación. ${result.model_invalidated ? 'El modelo anterior se desactivó para que no siga reconociendo la seña borrada. Reentrena con los ejemplos restantes.' : 'Los ejemplos de esta seña no pertenecían al modelo activo.'}`;
    }
    await refresh();
  } catch (error) {
    if (language === selectedLanguage) $('admin-message').textContent = error.message;
  } finally {
    deletingRecordings = false;
    render();
  }
}
// Enumera cámaras disponibles y conserva la selección si el dispositivo sigue conectado.
async function refreshCameras() {
  if (cameraListing) return;
  cameraListing = true;
  $('refresh-cameras').disabled = true;
  try {
    if (!navigator.mediaDevices?.enumerateDevices)
      throw new Error(
        'Este navegador no permite consultar las cámaras. Usa la dirección local y permite el acceso a la cámara.',
      );
    const selected = $('camera-device').value;
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter(
      (device) => device.kind === 'videoinput',
    );
    const active = stream?.getVideoTracks()[0]?.getSettings().deviceId;
    $('camera-device').replaceChildren(
      makeOption('', 'Cámara predeterminada'),
      ...devices.map((device, index) =>
        makeOption(device.deviceId, device.label || `Cámara ${index + 1}`),
      ),
    );
    const choice = active || selected;
    if (devices.some((device) => device.deviceId === choice)) $('camera-device').value = choice;
    $('camera-device-status').textContent = devices.length
      ? `${devices.length} cámara(s) disponible(s). ${devices.some((device) => !device.label) ? 'Activa la cámara para mostrar sus nombres.' : 'Selecciona la que quieras usar.'}`
      : 'No hay cámaras visibles para el navegador. Conecta una cámara y permite el acceso.';
    if (active && !devices.some((device) => device.deviceId === active)) {
      await stopCamera();
      notice('La cámara activa se desconectó. Selecciona otra y actívala.', true);
    }
  } catch (error) {
    $('camera-device-status').textContent = error.message;
  } finally {
    cameraListing = false;
    $('refresh-cameras').disabled = cameraStarting;
  }
}
// Solicita permiso, abre la cámara seleccionada y crea su sesión de procesamiento en el servidor.
async function startCamera() {
  if (stream || cameraStarting) return;
  if (!$('shared-camera-consent').checked) return notice('Acepta el procesamiento en el servidor antes de activar la cámara.', true);
  cameraStarting = true;
  $('start-camera').disabled = true;
  $('camera-device').disabled = true;
  const mark = ++generation;
  try {
    if (!navigator.mediaDevices?.getUserMedia)
      throw new Error(
        'La cámara necesita HTTPS o localhost. Abre la dirección segura de Seña.',
      );
    const deviceId = $('camera-device').value;
    const acquired = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        ...(deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'user' }),
      },
      audio: false,
    });
    if (mark !== generation) {
      acquired.getTracks().forEach((t) => t.stop());
      return;
    }
    stream = acquired;
    acquired.getVideoTracks()[0].addEventListener(
      'ended',
      () => {
        if (stream === acquired) {
          stopCamera();
          notice('La cámara se desconectó. Selecciona otra cámara.', true);
        }
      },
      { once: true },
    );
    const created = await api('/api/session', {
      language,
      participant: $('capture-participant').value.trim(),
      camera: deviceId ? await cameraFingerprint(deviceId) : '',
      quality_gate: true,
      shared_consent: $('shared-camera-consent').checked,
    });
    if (mark !== generation) {
      await api('/api/close', { session: created.session });
      return;
    }
    session = created.session;
    $('camera').srcObject = stream;
    await $('camera').play();
    $('camera').hidden = false;
    $('camera-placeholder').hidden = true;
    $('stop-camera').disabled = false;
    $('camera-state').textContent = 'Preparando detección…';
    $('capture-instruction').textContent =
      mode === 'train'
        ? 'Pulsa “Grabar una seña”. Le pondrás nombre al terminar.'
        : profile().model
          ? 'Realiza una seña dentro del encuadre.'
          : 'Vista previa · Esta lengua todavía no tiene modelo.';
    notice('');
    sendFrame(mark);
    await refreshCameras();
  } catch (error) {
    await stopCamera();
    notice(
      error.name === 'NotAllowedError'
        ? 'Permite la cámara para este sitio y para tu navegador en la configuración de privacidad de macOS.'
        : error.name === 'OverconstrainedError' || error.name === 'NotFoundError'
          ? 'La cámara seleccionada no está disponible. Pulsa Detectar cámaras y elige otra.'
          : error.message,
      true,
    );
  } finally {
    cameraStarting = false;
    render();
  }
}
// Cancela cuentas atrás y tandas, apaga pistas y libera la sesión de cámara remota.
async function stopCamera() {
  clearHandRig();
  batch.stop();
  ++generation;
  clearTimeout(timer);
  countdown = false;
  recording = false;
  frameReady = false;
  if (stream) stream.getTracks().forEach((track) => track.stop());
  stream = null;
  $('camera').srcObject = null;
  $('camera').hidden = true;
  $('camera-placeholder').hidden = false;
  if ($('quality-message'))
    $('quality-message').textContent = 'Activa la cámara para comprobar el encuadre.';
  $('stop-camera').disabled = true;
  $('record').disabled = true;
  $('record').textContent = 'Grabar una seña';
  $('camera-state').textContent = 'Cámara apagada';
  $('capture-instruction').textContent = 'La cámara se activa solo cuando tú lo decides.';
  $('frame-progress').value = 0;
  $('frame-counter').textContent = '0 / 30';
  $('hands-status').textContent = 'Tu mano derecha aparecerá a la derecha.';
  const previous = session;
  session = null;
  if (previous) {
    try {
      await api('/api/close', { session: previous });
    } catch (_) {}
  }
  if (state) render();
}
// Captura un fotograma conservando proporción y calidad, lo procesa y programa el siguiente sin solapar envíos.
async function sendFrame(mark) {
  if (!stream || mark !== generation || !session) return;
  const started = performance.now();
  try {
    const canvas = $('frame-canvas'),
      video = $('camera');
    const width = Math.round((video.videoWidth || 640) * Math.min(640 / (video.videoWidth || 640), 480 / (video.videoHeight || 480), 1));
    const height = Math.round((width * (video.videoHeight || 480)) / (video.videoWidth || 640));
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const result = await api('/api/frame', {
      session,
      image: canvas.toDataURL('image/jpeg', 0.82).split(',')[1],
      confirmation_ack: lastConfirmationId,
      show_hand_rig: $('show-hand-rig').checked,
      mode: mode === 'test' && $('snapshot-mode').checked ? 'preview' : mode,
      strict: localStorage.getItem('sena-confirmation') === 'strict',
    });
    if (mark !== generation) return;
    drawHandRig(result.hand_rig, canvas.width, canvas.height, canvas);
    const quality = result.quality;
    if (quality) {
      $('quality-status').dataset.quality = quality.usable ? 'good' : 'poor';
      $('quality-message').textContent = quality.message;
    }
    $('frame-latency').textContent = `${Math.round(performance.now() - started)} ms`;
    if (result.phase === 'waiting-for-hands')
      $('capture-instruction').textContent = 'Esperando buen encuadre para iniciar la toma…';
    if (!frameReady) {
      frameReady = true;
      render();
    }
    $('camera-state').textContent = result.hands ? (quality?.usable ? (result.tracking_recovered ? 'Seguimiento recuperado' : 'Manos visibles') : 'Revisando encuadre') : 'Buscando manos';
    $('hands-status').textContent = result.hands
      ? 'Manos detectadas · Mantén el movimiento natural.'
      : 'Encuadra la mano que hace la seña, incluida la muñeca.';
    const count = recording ? result.captured : result.buffer;
    $('frame-progress').max = state.sequence_length;
    $('frame-progress').value = count;
    $('frame-counter').textContent = `${count} / ${state.sequence_length}`;
    if (result.draft_id) {
      selectedDraft = result.draft_id;
      recording = false;
      if (batch.active) {
        const serial = batch.serial;
        const progress = batch.complete(result.draft_id, serial);
        renderBatchCounter();
        if (progress && !progress.done && batch.current(serial)) {
          if (mark !== generation) return;
          notice(
            `La siguiente toma empieza en ${batchPause} segundos.`,
          );
          void recordExample(true, serial);
        } else if (progress && !progress.done && batch.paused) {
          await refresh();
          notice(`Tanda pausada. Conservas ${batch.count}/${batch.limit} tomas completas.`);
        } else {
          await stopCamera();
          await refresh();
          notice(
            'Tanda completa. Ponles nombre en Grabaciones pendientes.',
          );
          $('name-capture').scrollIntoView({ behavior: 'smooth', block: 'center' });
          $('sign-name').focus({ preventScroll: true });
          return;
        }
      } else {
        await stopCamera();
        await refresh();
        notice(
          result.capture_warning ||
            'Grabación completa. Escribe qué significa y pulsa “Guardar e integrar”.',
        );
        $('name-capture').scrollIntoView({ behavior: 'smooth', block: 'center' });
        $('sign-name').focus({ preventScroll: true });
        return;
      }
    }
    if (mode === 'test' && !$('snapshot-mode').checked && (!result.inference_skipped || result.confirmed)) showPrediction(result);
  } catch (error) {
    if (mark !== generation) return;
    notice(error.message, true);
    // Cerrar la sesión también descarta cualquier captura parcial en el servidor.
    await stopCamera();
    return;
  }
  if (mark === generation)
    timer = setTimeout(
      () => sendFrame(mark),
      Math.max(0, 1000 / state.target_fps - (performance.now() - started)),
    );
}
// Presenta aceptación o rechazo y añade solamente confirmaciones estables al historial y la voz.
function showPrediction(result) {
  if (!profile().model) {
    resetResult();
    return;
  }
  const trial = $('expected-label').value;
  if (trial && !result.inference_skipped && (result.rejection_code || result.candidate)) {
    const proposed = result.alternatives?.[0]?.text || result.candidate?.text || '—';
    const outcome = result.rejection_code || result.phase;
    const key = JSON.stringify([trial, proposed, outcome]);
    const row = trialDiagnostics.get(key) || {
      expected: profile().model.labels.find(l => l.id === trial)?.text || trial,
      proposed, outcome, windows: 0,
    };
    row.windows++;
    trialDiagnostics.set(key,row);
    $('download').disabled = false;
  }
  renderAlternatives(result.alternatives || []);
  $('confidence').textContent = result.candidate ? `${(100 * result.confidence).toFixed(1)}%` : '—';
  $('confidence-progress').value = result.candidate ? 100 * result.confidence : 0;
  $('stability').textContent = `${result.stability} / ${result.stability_required || 5} confirmaciones estables`;
  if (result.candidate || result.confirmed) {
    $('result-word').textContent = (result.confirmed || result.phase === 'held')
      ? (result.confirmed || result.candidate).text
      : (result.stability >= 2 ? sessionConfirmedText(result) : 'Observando el gesto…');
    $('result-description').textContent =
      result.rejection_reason ||
      (result.confirmed
        ? 'Seña confirmada y añadida a tu sesión.'
        : result.phase === 'held'
          ? 'Puedes hacer otra seña sin retirar la mano.'
        : 'Coincidencia provisional. Esperando estabilidad para confirmar.');
  } else {
    $('result-word').textContent = result.hands ? 'Sin confirmación' : 'Esperando tus manos…';
    $('result-description').textContent =
      result.rejection_reason || 'Haz una seña del vocabulario entrenado y espera la confirmación.';
  }
  if (result.confirmed && (!result.confirmation_id || result.confirmation_id !== lastConfirmationId)) {
    if (result.confirmation_id) lastConfirmationId = result.confirmation_id;
    const expected = $('expected-label').value;
    if (expected) {
      checks++;
      if (expected === result.confirmed.id) correct++;
    }
    history.push({
      ...result.confirmed,
      confidence: result.confirmed_confidence ?? result.confidence,
      expected,
      time: new Date().toISOString(),
    });
    if (typeof animateUI === 'function') animateUI($('result-word'), 400);
    lastSpoken = result.confirmed.text;
    $('speak').disabled = !('speechSynthesis' in window);
    if ('speechSynthesis' in window) speak();
    if (typeof publishRecognizedSign === 'function') void publishRecognizedSign(result.confirmed.text, result.confirmed_confidence ?? result.confidence);
    renderHistory();
  }
}
// Dibuja las confirmaciones y actualiza aciertos comprobados y exportación de sesión.
function renderHistory() {
  $('history').replaceChildren();
  for (const item of history.slice(-12)) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = item.text;
    $('history').append(chip);
  }
  $('history-empty').hidden = history.length > 0;
  $('practice-score').textContent = `${correct} / ${checks} aciertos`;
  $('download').disabled = !history.length && !trialDiagnostics.size;
}
// Limpia historial, estadísticas locales y resultado visible de reconocimiento.
function clearHistory() {
  trialDiagnostics.clear();
  history = [];
  checks = correct = 0;
  lastSpoken = null;
  $('speak').disabled = true;
  renderHistory();
  resetResult();
}
// Espera la preparación elegida y solicita una toma completa, comprobando cancelaciones de tanda.
async function recordExample(automatic = false, serial = null) {
  if (
    !stream ||
    !frameReady ||
    recording ||
    countdown ||
    (automatic ? !batch.current(serial) : selectedDraft || batch.active)
  )
    return;
  countdown = true;
  render();
  const mark = generation;
  try {
    for (let n = automatic ? batchPause : Number($('capture-countdown').value); n > 0; n--) {
      if (mark !== generation || (automatic && !batch.current(serial))) return;
      $('record').textContent = `Prepárate… ${n}`;
      $('capture-instruction').textContent = `La grabación empieza en ${n}…`;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    if (mark !== generation || (automatic && !batch.current(serial))) return;
    await api('/api/capture', {
      session,
      consecutive: automatic,
      batch_id: automatic ? `batch-${batch.serial}` : '',
    });
    if (mark !== generation || (automatic && !batch.active)) return;
    recording = true;
    $('record').textContent = 'Grabando…';
    $('capture-instruction').textContent = 'Haz la seña completa ahora.';
  } catch (error) {
    notice(error.message, true);
    if (automatic) await stopCamera();
  } finally {
    if (mark === generation) {
      countdown = false;
      render();
    }
  }
}
// Muestra completas/objetivo en la cámara y mantiene su etiqueta accesible.
function renderBatchCounter() {
  const visible = mode === 'train' && batch.limit > 0 && (batch.active || batch.count > 0);
  const counter = $('batch-counter');
  counter.hidden = !visible;
  counter.textContent = `${batch.count}/${batch.limit}`;
  counter.setAttribute('aria-label', `${batch.count} de ${batch.limit} tomas completas`);
  $('camera-state').hidden = visible;
}
// Valida tamaño y pausa y comienza la primera captura de una tanda consecutiva.
async function startContinuous() {
  if (!stream || !frameReady || recording || countdown || batch.active || savingDraft) return;
  try {
    const pause = Number($('batch-pause').value);
    if (!Number.isInteger(pause) || pause < 1 || pause > 10)
      throw new Error('Elige una pausa de 1 a 10 segundos.');
    batchPause = pause;
    const serial = batch.start(Number($('batch-limit').value));
    renderBatchCounter();
    notice(
      'Tanda iniciada. Repite la seña después de cada cuenta atrás; podrás nombrar las tomas al terminar.',
    );
    await recordExample(true, serial);
  } catch (error) {
    notice(error.message, true);
  } finally {
    render();
  }
}
// Pausa entre tomas o al terminar la actual y reanuda conservando el progreso.
async function toggleContinuousPause() {
  if (!batch.active) return;
  if (batch.paused) {
    if (recording || countdown) return;
    const serial = batch.resume();
    render();
    notice('Tanda reanudada. Prepárate para la siguiente toma.');
    await recordExample(true, serial);
  } else {
    batch.pause();
    render();
    notice(recording
      ? 'La toma actual terminará y la tanda quedará pausada.'
      : `Tanda pausada. Conservas ${batch.count}/${batch.limit} tomas completas.`);
  }
}
// Cierra la cámara y conserva las tomas completas pendientes de nombrar.
async function stopContinuous() {
  await stopCamera();
  await refresh();
  notice(
    'Tanda detenida. Ponles nombre en Grabaciones pendientes; la toma incompleta se descartó.',
  );
}
// Integra una toma pendiente con su significado en el vocabulario del perfil seleccionado.
async function saveNamedCapture(event) {
  event.preventDefault();
  if (!selectedDraft || savingDraft) return;
  const name = $('sign-name').value.trim();
  if (!name) return notice('Escribe el nombre o significado de la seña.', true);
  const capturedLanguage = language,
    draft = selectedDraft;
  savingDraft = true;
  render();
  try {
    const result = await api('/api/capture/save', {
      language: capturedLanguage,
      draft_id: draft,
      name,
    });
    selectedDraft = null;
    await refresh();
    if (language === capturedLanguage)
      notice(
        `“${result.label.text}” se integró al vocabulario de ${profile().code}. Puedes grabar más ejemplos con ese nombre y actualizar el modelo al completar los requisitos.`,
      );
  } catch (error) {
    notice(error.message, true);
  } finally {
    savingDraft = false;
    render();
  }
}
// Conserva una lista fija para no incluir tomas que lleguen durante el guardado.
async function saveAllCaptures() {
  if (savingDraft || batch.active || state.job?.state === 'running') return;
  const name = $('sign-name').value.trim();
  if (!name) return notice('Escribe la palabra o letra para estas tomas.', true);
  const capturedLanguage = language;
  const drafts = [...(profile().drafts || [])];
  if (!drafts.length || !$('name-capture').reportValidity()) return;
  savingDraft = true;
  let saved = 0;
  render();
  try {
    for (const draft of drafts) {
      await api('/api/capture/save', {language: capturedLanguage, draft_id: draft.id, name});
      saved++;
      $('save-all-captures').textContent = `Guardando ${saved}/${drafts.length}…`;
    }
    await refresh();
    notice(`Se guardaron ${saved} tomas en “${name}”.`);
  } catch (error) {
    await refresh().catch(() => {});
    if (language === capturedLanguage) $('sign-name').value = name;
    notice(`Se guardaron ${saved} de ${drafts.length} en “${name}”. Las restantes siguen pendientes. ${error.message}`, true);
  } finally {
    savingDraft = false;
    render();
  }
}
// Retira una toma pendiente sin incorporarla al entrenamiento.
async function discardCapture() {
  if (!selectedDraft || savingDraft) return;
  savingDraft = true;
  render();
  try {
    await api('/api/capture/discard', { language, draft_id: selectedDraft });
    selectedDraft = null;
    await refresh();
    notice('Grabación descartada. Ya puedes activar la cámara y repetirla.');
  } catch (error) {
    notice(error.message, true);
  } finally {
    savingDraft = false;
    render();
  }
}

// Cierra la cámara y solicita entrenar las clases y estrategia elegidas.
async function trainModel() {
  const epochs = Number($('epochs').value);
  if (!Number.isInteger(epochs) || epochs < 5 || epochs > 200)
    return notice('Elige entre 5 y 200 épocas.', true);
  $('train-model').disabled = true;
  try {
    await stopCamera();
    await api('/api/train', {
      language,
      epochs,
      labels: selectedTrainingClasses(profile()).map((x) => x.id),
      strategy: $('training-strategy').value,
    });
    notice(
      'Entrenamiento iniciado. El progreso aparecerá debajo; puedes dejar esta página abierta.',
    );
    await refresh();
  } catch (error) {
    notice(error.message, true);
    render();
  }
}
const automaticSpeech = new SenaSpeechQueue(window.speechSynthesis, window.SpeechSynthesisUtterance,
  () => notice('No se pudo reproducir la voz. Revisa el sonido y los permisos del navegador.', true));
// Añade la última confirmación a la cola de voz con el idioma del perfil.
function speak() {
  if (lastSpoken) automaticSpeech.enqueue(lastSpoken, profile().locale);
}
$('start-camera').addEventListener('click', startCamera);
$('admin-delete-form').addEventListener('submit', deleteRecordings);
$('admin-label').addEventListener('change', () => {
  $('admin-confirm').checked = false;
  $('admin-message').textContent = '';
  renderAdmin();
});
$('refresh-cameras').addEventListener('click', refreshCameras);
$('camera-device').addEventListener('change', async () => {
  if (stream) {
    await stopCamera();
    await startCamera();
  }
});
if (navigator.mediaDevices?.addEventListener)
  navigator.mediaDevices.addEventListener('devicechange', refreshCameras);
refreshCameras();
$('stop-camera').addEventListener('click', stopCamera);
$('record').addEventListener('click', () => recordExample());
$('start-batch').addEventListener('click', startContinuous);
$('stop-batch').addEventListener('click', stopContinuous);
$('pause-batch').addEventListener('click', toggleContinuousPause);
// Usa Espacio para pausar o continuar Dataset sin interferir con escritura, diálogos ni otras vistas.
function capturePauseShortcut(event) {
  if (event.code !== 'Space' || event.repeat || event.defaultPrevented ||
      event.ctrlKey || event.altKey || event.metaKey || event.shiftKey ||
      currentView !== 'dataset' || !batch.active || document.querySelector('dialog[open]')) return;
  if (event.target?.closest('input, textarea, select, button, a, [contenteditable]:not([contenteditable="false"]), [role="textbox"]')) return;
  event.preventDefault();
  void toggleContinuousPause();
}
document.addEventListener('keydown', capturePauseShortcut);
$('add-alphabet').addEventListener('click', () => addAlphabet('language'));
$('add-all-alphabets').addEventListener('click', () => addAlphabet('all'));
$('add-alphabet-extras').addEventListener('click', () => addAlphabet('language', true));
$('clear-alphabet-selection').addEventListener('click', () => {
  selectedLetter = null;
  renderAlphabet();
});
$('name-capture').addEventListener('submit', saveNamedCapture);
$('discard-capture').addEventListener('click', discardCapture);
$('save-all-captures').addEventListener('click', saveAllCaptures);
$('draft-picker').addEventListener('change', () => {
  selectedDraft = $('draft-picker').value;
  render();
});
$('train-model').addEventListener('click', trainModel);
$('clear-history').addEventListener('click', async () => {
  clearHistory();
  if (session) {
    try {
      await api('/api/reset', { session });
    } catch (e) {
      notice(e.message, true);
    }
  }
});
$('speak').addEventListener('click', speak);
$('download').addEventListener('click', () => {
  const blob = new Blob(
    [
      JSON.stringify(
        { language, name: profile().name, records: history, checked: checks, correct, diagnostics: [...trialDiagnostics.values()] },
        null,
        2,
      ),
    ],
    { type: 'application/json' },
  );
  const url = URL.createObjectURL(blob),
    link = document.createElement('a');
  link.href = url;
  link.download = `sesion-${language}-${Date.now()}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
for (const tab of document.querySelectorAll('[data-mode]'))
  tab.addEventListener('click', () => selectMode(tab.dataset.mode));
document.addEventListener('visibilitychange', () => {
  if (document.hidden && stream) stopCamera();
});
window.addEventListener('pagehide', () => {
  if (stream) stream.getTracks().forEach((t) => t.stop());
  if (session) void fetch('/api/close', {
    method: 'POST', keepalive: true,
    headers: {'Content-Type': 'application/json', 'X-LSM-Token': state?.token || ''},
    body: JSON.stringify({session}),
  }).catch(() => {});
});
window.addEventListener('DOMContentLoaded', () => {
  bootstrapAccounts().catch(error => { $('account-message').textContent = error.message; });
  setInterval(() => {
    if (accountState?.user) refresh().catch(error => notice(error.message, true));
  }, 4000);
});

// The server detects the mirrored image; do not mirror these coordinates again.
const handRigEdges = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],
  [5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],
  [13,17],[0,17],[17,18],[18,19],[19,20]];
let handRigExpiry;
// Borra el dibujo y cancela su vencimiento para no dejar puntos antiguos sobre la cámara.
function clearHandRig() {
  clearTimeout(handRigExpiry);
  const canvas = $('hand-rig');
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
  canvas.hidden = true;
}
// Dibuja la imagen analizada reflejada una vez y sus puntos sincronizados, no el video adelantado.
function drawHandRig(hands, width, height, sourceFrame = null) {
  clearHandRig();
  if (!$('show-hand-rig').checked || !stream || !hands?.length) return;
  const canvas = $('hand-rig');
  canvas.width = width; canvas.height = height; canvas.hidden = false;
  const ctx = canvas.getContext('2d');
  if (sourceFrame) {
    // The landmarks refer to this exact captured frame, mirrored by the server.
    // Painting over the newer live video would visibly detach them from the hand.
    ctx.save();
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(sourceFrame, 0, 0, width, height);
    ctx.restore();
  }
  ctx.lineWidth = 2; ctx.strokeStyle = canvas.dataset?.stroke || '#efb08b'; ctx.fillStyle = '#ffffff';
  ctx.shadowColor = '#172139'; ctx.shadowBlur = 3;
  for (const hand of hands) {
    if (hand.length !== 21 || !hand.every(p => p.length === 2 && p.every(Number.isFinite))) continue;
    ctx.beginPath();
    for (const [a,b] of handRigEdges) {
      ctx.moveTo(hand[a][0]*width, hand[a][1]*height);
      ctx.lineTo(hand[b][0]*width, hand[b][1]*height);
    }
    ctx.stroke();
    for (const [x,y] of hand) {
      ctx.beginPath(); ctx.arc(x*width,y*height,3,0,Math.PI*2); ctx.fill();
    }
  }
  handRigExpiry = setTimeout(clearHandRig, 800);
}
// Activa o desactiva el rig y conserva la preferencia visual en el navegador.
function setHandRig(enabled, persist = true) {
  $('show-hand-rig').checked = enabled;
  const toggle = $('camera-rig-toggle');
  toggle.setAttribute('aria-pressed', String(enabled));
  toggle.setAttribute('aria-label', enabled ? 'Ocultar rig de manos' : 'Mostrar rig de manos');
  toggle.textContent = enabled ? 'Rig de manos · activo' : 'Rig de manos · apagado';
  clearHandRig();
  if (persist) {
    try { localStorage.setItem('sena.hand-rig', String(enabled)); } catch (_) {}
  }
}
let savedHandRig = false;
try { savedHandRig = localStorage.getItem('sena.hand-rig') === 'true'; } catch (_) {}
setHandRig(savedHandRig, false);
$('show-hand-rig').addEventListener('change', () => setHandRig($('show-hand-rig').checked));
$('camera-rig-toggle').addEventListener('click', () => setHandRig(!$('show-hand-rig').checked));


// Captura una imagen en memoria y muestra comparación experimental o rechazo, sin probabilidad inventada.
async function takeSnapshot() {
  if (!stream || !session || snapshotBusy || !$('snapshot-mode').checked) return;
  const video = $('camera'), canvas = $('snapshot-preview');
  if (!video.videoWidth || !video.videoHeight) return;
  const mark = generation;
  const scale = Math.min(640/video.videoWidth,480/video.videoHeight,1);
  canvas.width = Math.round(video.videoWidth*scale); canvas.height = Math.round(video.videoHeight*scale);
  canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
  canvas.hidden = false;
  const image = canvas.toDataURL('image/jpeg',.82).split(',')[1];
  snapshotBusy = true; render();
  $('snapshot-result').textContent = 'Comparando la foto con las formas aprendidas…';
  try {
    const result = await api('/api/snapshot',{session,image});
    if (mark !== generation) return;
    $('confidence').textContent = '—'; $('confidence-progress').value = 0;
    $('stability').textContent = 'Foto experimental · sin probabilidad temporal';
    if (result.accepted) {
      $('result-word').textContent = result.label.text;
      $('result-description').textContent = result.note;
      $('snapshot-result').textContent = `${result.label.text} · referencia de validación: ${result.validation_support} grabaciones. Resultado experimental.`;
      history.push({...result.label, method:'snapshot-hand-shape-v1', confidence:null, expected:'', time:new Date().toISOString()});
      renderHistory();
      lastSpoken = result.label.text;
      $('speak').disabled = !('speechSynthesis' in window);
      automaticSpeech.enqueue(lastSpoken,profile().locale);
      if (typeof publishRecognizedSign === 'function') void publishRecognizedSign(lastSpoken,null);
    } else {
      $('result-word').textContent = 'Foto sin confirmar';
      $('snapshot-result').textContent = result.reason;
      $('result-description').textContent = result.reason;
    }
  } catch (error) { $('snapshot-result').textContent = error.message; }
  finally { snapshotBusy = false; render(); }
}
$('take-snapshot').addEventListener('click',takeSnapshot);
$('snapshot-mode').addEventListener('change',async()=>{
  $('snapshot-preview').hidden = true;
  resetResult();render();
  if (session && mode === 'test') {
    try { await api('/api/reset',{session}); } catch(error) { notice(error.message,true); }
  }
});
