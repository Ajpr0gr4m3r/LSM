'use strict';
let currentView = 'home',
  auditData = null,
  versionData = [],
  studioBusy = false;
const trainingChoices = new Map();
const headings = {
  home: [
    'TU ESPACIO DE TRABAJO',
    'De tus manos, a tus datos.',
    'Captura, entrena y reconoce señas. Con los ejemplos de tu equipo.',
  ],
  recognition: [
    'RECONOCIMIENTO EN VIVO',
    'Haz la seña. Espera la confirmación.',
    'Un resultado claro, solo cuando el modelo tiene suficiente evidencia.',
  ],
  dataset: [
    'CAPTURA Y REVISIÓN',
    'Mejores ejemplos, mejores resultados.',
    'Organiza el vocabulario y revisa la calidad de tus grabaciones.',
  ],
  training: [
    'MODELOS Y EVALUACIÓN',
    'Entrena. Compara. Conserva lo mejor.',
    'Cada versión queda guardada. La validación decide qué modelo activar.',
  ],
  settings: [
    'AJUSTES DEL ESTUDIO',
    'A tu manera. Con tu equipo.',
    'Elige la cámara, la apariencia y cómo confirmar las detecciones.',
  ],
};
const labelsByView = {
  home: 'Inicio',
  recognition: 'Reconocimiento',
  dataset: 'Dataset',
  training: 'Entrenamiento',
  settings: 'Configuración',
};
function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(svg.namespaceURI, 'use');
  use.setAttribute('href', `/static/vendor/lucide.svg#${name}`);
  svg.append(use);
  return svg;
}
function selectedTrainingClasses(p) {
  if (!p) return [];
  const selected = trainingChoices.get(p.id);
  return p.labels.filter(
    (x) => x.samples >= state.minimum_samples && (!selected || selected.has(x.id)),
  );
}
async function cameraFingerprint(id) {
  if (!crypto.subtle) return '';
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(id));
  return [...new Uint8Array(bytes)]
    .map((x) => x.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 16);
}
function sessionConfirmedText(result) {
  return result.stability ? `Confirmando ${result.candidate.text}…` : 'Observando…';
}
function renderAlternatives(items) {
  const host = $('alternatives');
  host.replaceChildren();
  if (!items.length) return;
  host.append(node('div', 'Otras coincidencias · orientativas', 'small-label'));
  for (const item of items) {
    const row = node('div', undefined, 'alternative-row');
    row.append(node('span', item.text), node('span', `${Math.round(item.confidence * 100)} %`));
    host.append(row);
  }
}
async function navigateStudio(view) {
  if (!headings[view]) view = 'home';
  if (currentView !== view) await stopCamera();
  window.scrollTo({ top: 0, behavior: 'auto' });
  currentView = view;
  mode = view === 'dataset' ? 'train' : 'test';
  const [eyebrow, title, subtitle] = headings[view];
  $('view-eyebrow').textContent = eyebrow;
  $('view-title').textContent = title;
  $('view-subtitle').textContent = subtitle;
  $('view-breadcrumb').textContent = labelsByView[view];
  for (const key of Object.keys(headings)) $('view-' + key).hidden = key !== view;
  for (const button of document.querySelectorAll('.main-nav [data-view]'))
    button.setAttribute('aria-current', String(button.dataset.view === view));
  $('camera-workspace').hidden = false;
  $(view === 'dataset' ? 'dataset-camera' : 'recognition-camera').append($('camera-workspace'));
  $('capture-controls').hidden = view !== 'dataset';
  $('test-controls').hidden = view !== 'recognition';
  $('test-results').hidden = false;
  $('training-results').hidden = false;
  $('alphabet-panel').hidden = false;
  historyReplace(view);
  notice('');
  if (state) render();
  if (view === 'training' && state) await loadVersions();
}
function historyReplace(view) {
  window.history.replaceState(null, '', '#' + view);
}
function applyTheme(value) {
  localStorage.setItem('sena-theme', value);
  const dark =
    value === 'dark' || (value === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  $('appearance').value = value;
  $('theme-toggle').replaceChildren(icon(dark ? 'sun' : 'moon'));
  $('theme-toggle').setAttribute('aria-label', dark ? 'Activar modo claro' : 'Activar modo oscuro');
}
function renderStudio() {
  const p = profile();
  if (!p) return;
  const selected = $('profile-select').value;
  $('profile-select').replaceChildren(
    ...state.profiles.map((x) => makeOption(x.id, `${x.code} · ${x.written}`)),
  );
  $('profile-select').value = language;
  const all = state.profiles.flatMap((x) => x.labels),
    samples = all.reduce((n, x) => n + x.samples, 0),
    learned = state.profiles.reduce((n, x) => n + (x.model?.labels.length || 0), 0),
    models = state.profiles.filter((x) => x.model).length;
  const stats = [
    ['Ejemplos guardados', samples, 'Puntos de referencia, sin video', 'database'],
    ['Señas en modelos', learned, 'Vocabulario con reconocimiento activo', 'hand'],
    ['Modelos activos', `${models} / 7`, 'Un modelo por lengua', 'cpu'],
    [
      'Tomas pendientes',
      state.profiles.reduce((n, x) => n + x.drafts.length, 0),
      'Completas, listas para nombrar',
      'folder',
    ],
  ];
  $('dashboard-stats').replaceChildren(
    ...stats.map(([label, value, note, glyph]) => {
      const card = node('article', undefined, 'stat-card');
      const copy = node('div');
      copy.append(
        node('span', label, 'stat-label'),
        node('strong', String(value), 'stat-value'),
        node('small', note),
      );
      card.append(copy, icon(glyph));
      return card;
    }),
  );
  const incomplete = p.labels.filter((x) => x.samples > 0 && x.samples < state.minimum_samples);
  $('next-step').textContent = incomplete.length
    ? `${p.code}: ${incomplete.length} seña(s) necesitan más ejemplos. Completa las tomas y revisa su calidad antes de entrenar.`
    : p.model
      ? `${p.code} tiene ${p.model.labels.length} señas en su modelo activo. Comprueba el reconocimiento con una toma nueva.`
      : `Prepara al menos dos señas de ${p.code}, con 30 ejemplos completos en cada una.`;
  $('profile-grid').replaceChildren(
    ...state.profiles.map((x) => {
      const card = node('button', undefined, 'profile-card' + (x.id === language ? ' active' : ''));
      card.type = 'button';
      const top = node('div', undefined, 'profile-top');
      top.append(node('span', x.code, 'code'), icon('arrow-up-right'));
      const info = node('div', undefined, 'profile-stats');
      info.append(
        node('span', `${x.labels.reduce((n, r) => n + r.samples, 0)} ejemplos`),
        node('span', x.model ? `${x.model.labels.length} señas activas` : 'Sin modelo'),
      );
      card.append(top, node('strong', x.written), node('p', x.name), info);
      card.addEventListener('click', async () => {
        await selectLanguage(x.id);
        await navigateStudio('recognition');
      });
      return card;
    }),
  );
  $('recent-activity').replaceChildren();
  for (const item of (state.activity || []).slice(0, 4)) {
    const row = node('div', undefined, 'activity-row'),
      copy = node('div');
    copy.append(
      node(
        'strong',
        item.kind === 'training'
          ? `Entrenamiento · ${(item.language || '').toUpperCase()}`
          : 'Dataset actualizado',
      ),
      node('p', item.message),
      node(
        'small',
        new Date(item.time * 1000).toLocaleString('es-MX', {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit',
        }),
      ),
    );
    row.append(icon(item.kind === 'training' ? 'activity' : 'database'), copy);
    $('recent-activity').append(row);
  }
  if (!$('recent-activity').children.length)
    $('recent-activity').append(
      node('div', 'Aquí aparecerán tus entrenamientos y cambios de dataset.', 'empty-state'),
    );
  $('vocabulary-total').textContent = `${p.labels.length} etiquetas`;
  filterVocabulary();
  const classes = $('train-classes');
  classes.replaceChildren();
  const chosen = trainingChoices.get(language);
  for (const item of p.labels.filter((x) => x.samples > 0)) {
    const row = node('div', undefined, 'train-class'),
      label = node('label'),
      checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = item.id;
    checkbox.disabled = item.samples < state.minimum_samples;
    checkbox.checked = !checkbox.disabled && (!chosen || chosen.has(item.id));
    checkbox.addEventListener('change', () => {
      trainingChoices.set(
        language,
        new Set([...classes.querySelectorAll('input:checked')].map((x) => x.value)),
      );
      render();
    });
    label.append(checkbox, node('span', item.text));
    row.append(label, node('span', `${item.samples} / ${state.minimum_samples} mín.`));
    classes.append(row);
  }
  const curve =
    state.job?.state === 'running' && state.job?.language === language && state.job?.history?.length
      ? state.job.history
      : p.model?.history;
  $('curve-context').textContent = state.job?.state === 'running' && state.job?.language === language ? 'Curvas del entrenamiento en curso' : 'Curvas de la versión activa';
  drawCurve('accuracy-chart', curve, 'accuracy', 'val_accuracy', true);
  drawCurve('loss-chart', curve, 'loss', 'val_loss', false);
  $('split-note').textContent =
    p.model?.provenance?.note ||
    'Los modelos históricos no documentan sesión o participante. Sus métricas no demuestran independencia entre personas.';
  drawConfusion(p.model);
  $('export-dataset').disabled = studioBusy || !p.labels.some((x) => x.samples);
  $('import-dataset').disabled = studioBusy || state.job?.state === 'running';
  if (auditData && auditData.language !== language) {
    auditData = null;
    $('audit-rows').replaceChildren();
    $('audit-summary').textContent =
      'Analiza las grabaciones de esta lengua para revisar su calidad.';
  }
}
function filterVocabulary() {
  const query = $('vocabulary-search').value.trim().toLocaleLowerCase();
  for (const row of $('sample-list').children)
    row.hidden = !row.firstChild.textContent.toLocaleLowerCase().includes(query);
}
function drawCurve(id, history, trainKey, valKey, rate) {
  const host = $(id);
  host.replaceChildren();
  if (!history?.length) {
    host.append(
      node('p', 'Esta versión no guardó curvas. Los nuevos entrenamientos las mostrarán aquí.'),
    );
    return;
  }
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 320 140');
  svg.setAttribute('role', 'img');
  svg.setAttribute(
    'aria-label',
    `${rate ? 'Aciertos' : 'Pérdida'} de entrenamiento y validación durante ${history.length} épocas`,
  );
  const values = history.flatMap((x) => [x[trainKey], x[valKey]]).filter(Number.isFinite);
  const min = 0,
    max = rate ? 1 : Math.max(0.01, ...values) * 1.05;
  for (let level = 0; level < 3; level++) {
    const line = document.createElementNS(svg.namespaceURI, 'line');
    line.setAttribute('x1', '18');
    line.setAttribute('x2', '310');
    line.setAttribute('y1', String(12 + level * 56));
    line.setAttribute('y2', String(12 + level * 56));
    line.setAttribute('stroke', 'var(--line)');
    svg.append(line);
  }
  for (const [key, color] of trainKey === valKey
    ? [[trainKey, '#8db457']]
    : [
        [trainKey, '#8db457'],
        [valKey, '#6498b2'],
      ]) {
    const poly = document.createElementNS(svg.namespaceURI, 'polyline');
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', color);
    poly.setAttribute('stroke-width', '2');
    poly.setAttribute(
      'points',
      history
        .map(
          (r, i) =>
            `${18 + (i / Math.max(1, history.length - 1)) * 292},${124 - (Math.max(0, Number(r[key]) || 0) / max) * 112}`,
        )
        .join(' '),
    );
    svg.append(poly);
  }
  host.append(svg);
  if (trainKey !== valKey) {
    const legend = node('div', undefined, 'chart-legend');
    legend.append(node('i'), document.createTextNode('Entrenamiento'));
    const mark = node('i', undefined, 'validation');
    legend.append(mark, document.createTextNode('Validación'));
    host.append(legend);
  }
}
function drawConfusion(model) {
  const host = $('confusion-matrix');
  host.replaceChildren();
  if (!model?.confusion_matrix) {
    host.append(node('p', 'Entrena un modelo para consultar su matriz de confusión.', 'help'));
    return;
  }
  const table = node('table', undefined, 'data-table'),
    head = node('tr');
  head.append(node('th', 'Real / predicha'));
  for (const label of model.labels) head.append(node('th', label.text));
  table.append(head);
  model.confusion_matrix.forEach((values, i) => {
    const row = node('tr');
    row.append(node('th', model.labels[i].text));
    values.forEach((value, j) => {
      const cell = node('td', String(value));
      if (i === j) cell.className = 'status-tag';
      row.append(cell);
    });
    table.append(row);
  });
  host.append(table);
}
async function auditDataset() {
  if (studioBusy) return;
  await stopCamera();
  studioBusy = true;
  $('audit-dataset').disabled = true;
  try {
    auditData = await api('/api/dataset/audit', { language });
    renderAudit();
  } catch (e) {
    notice(e.message, true);
  } finally {
    studioBusy = false;
    $('audit-dataset').disabled = false;
  }
}
function renderAudit() {
  if (!auditData) return;
  $('sample-confirm').checked = false;
  const summary = auditData.summary;
  $('audit-summary').textContent =
    `${summary.total} tomas · ${summary.duplicates} duplicadas · ${summary.conflicts} con etiquetas en conflicto · ${summary.low_quality} con encuadre insuficiente · ${summary.without_provenance} sin procedencia histórica.`;
  const previous = $('audit-filter').value;
  $('audit-filter').replaceChildren(
    makeOption('', 'Todas'),
    ...profile()
      .labels.filter((x) => x.samples || x.invalid)
      .map((x) => makeOption(x.id, x.text)),
  );
  if (profile().labels.some((x) => x.id === previous)) $('audit-filter').value = previous;
  $('sample-target').replaceChildren(...profile().labels.map((x) => makeOption(x.id, x.text)));
  const selected = $('audit-filter').value;
  const rows = auditData.samples.filter((x) => !selected || x.label === selected);
  $('audit-rows').replaceChildren(
    ...rows.map((item) => {
      const row = node('tr'),
        select = node('td'),
        checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = item.id;
      checkbox.setAttribute('aria-label', `Seleccionar ${item.text} ${item.id.slice(0, 8)}`);
      select.append(checkbox);
      const name = node('td');
      name.append(
        node('strong', item.text),
        node(
          'small',
          `${item.id.slice(0, 8)} · ${new Date(item.created_at * 1000).toLocaleDateString('es-MX')}`,
        ),
      );
      const preview = node('button', 'Ver toma', 'text-button');
      preview.type = 'button';
      preview.addEventListener('click', () => previewSample(item.id));
      name.append(preview);
      const status = node('td');
      status.append(
        node(
          'span',
          !item.valid
            ? 'Incompleta'
            : item.conflict
              ? 'Etiquetas en conflicto'
              : item.duplicate_of
                ? 'Duplicada'
                : 'Completa',
          'status-tag' + (!item.valid || item.conflict ? ' bad' : item.duplicate_of ? ' warn' : ''),
        ),
      );
      const quality = node(
        'td',
        item.valid
          ? `${Math.round((item.quality?.usable_ratio || 0) * 100)} % de cuadros válidos`
          : 'No evaluable',
      );
      const provenance = node(
        'td',
        item.metadata?.participant ||
          (item.metadata?.session_id
            ? 'Sesión ' + item.metadata.session_id.slice(0, 6)
            : 'Histórica · sin datos'),
      );
      row.append(select, name, status, quality, provenance);
      return row;
    }),
  );
  $('audit-select-all').checked = false;
}
async function modifySamples(action) {
  const ids = [...$('audit-rows').querySelectorAll('input:checked')].map((x) => x.value);
  const password = $('sample-password').value,
    confirmed = $('sample-confirm').checked;
  if (!ids.length || !password || !confirmed)
    return notice('Selecciona ejemplos, escribe la contraseña y confirma la modificación.', true);
  if (studioBusy) return;
  studioBusy = true;
  $('sample-password').value = '';
  try {
    await stopCamera();
    const r = await api('/api/dataset/' + action, {
      language,
      samples: ids,
      password,
      confirmed,
      target: $('sample-target').value,
    });
    $('sample-confirm').checked = false;
    await refresh();
    auditData = await api('/api/dataset/audit', { language });
    renderAudit();
    notice(`${r.changed} ejemplo(s) actualizados. Revisa el estado del modelo antes de reconocer.`);
  } catch (e) {
    notice(e.message, true);
  } finally {
    studioBusy = false;
  }
}
async function loadVersions() {
  try {
    const result = await api('/api/models/list', { language });
    versionData = result.versions;
    renderVersions();
  } catch (e) {
    notice(e.message, true);
  }
}
function renderRecognitionDiagnostics(version) {
  const protocol = version.validation_protocol;
  const diagnostics = version.recognition_diagnostics;
  const movement = version.motion_profile;
  if (!protocol && !diagnostics && !movement) return null;
  const section = node('section');
  section.append(node('h4', 'Validación y rechazos'));
  if (movement) {
    const names = (movement.moving_classes || []).map(i => version.labels?.[i]?.text).filter(Boolean);
    section.append(node('p', names.length ? `Movimiento observado en entrenamiento: ${names.join(', ')}. Haz el recorrido completo antes de mantener la posición final.` : 'No se identificaron clases con movimiento claramente separado del resto en este entrenamiento.', 'help'));
  }
  if (protocol) {
    section.append(node('p', protocol.independent_calibration
      ? 'Selección del modelo y calibración con grupos separados.'
      : 'Validación compartida: los umbrales y el modelo usan los mismos grupos.', 'help'));
    section.append(node('p', `Selección: ${protocol.selection_samples ?? '—'} tomas · Calibración: ${protocol.calibration_samples ?? '—'} tomas.`));
    if (protocol.note) section.append(node('p', protocol.note, 'help'));
  }
  const percent = value => Number.isFinite(value) ? (value * 100).toFixed(1) + ' %' : '—';
  const stageNames = {
    model: 'Clasificación sin filtros',
    network: 'Predicción del modelo',
    rival: 'Comparación entre formas similares',
    confidence: 'Confianza y ambigüedad',
    hand: 'Forma de las manos',
    temporal: 'Movimiento',
    final: 'Decisión final',
  };
  const splits = [
    ['validation', 'Validación del modelo'],
    ['calibration', 'Calibración · ajuste de umbrales'],
    ['test', 'Prueba reservada'],
  ];
  for (const [key, title] of splits) {
    const report = diagnostics?.[key];
    if (!report) continue;
    section.append(node('h4', title));
    if (report.stages?.length) {
      const table = node('table', undefined, 'data-table'), header = node('tr');
      for (const text of ['Etapa', 'Aceptadas / evaluadas', 'Cobertura', 'Aciertos aceptados', 'Errores aceptados', 'Correctas descartadas']) header.append(node('th', text));
      table.append(header);
      for (const stage of report.stages) {
        const row = node('tr');
        const values = [stageNames[stage.name] || stage.name,
          `${stage.accepted ?? '—'} / ${stage.evaluated ?? '—'}`, percent(stage.coverage),
          stage.correct_accepted ?? '—', stage.false_accepts ?? '—', stage.correct_rejected ?? '—'];
        for (const value of values) row.append(node('td', String(value)));
        table.append(row);
      }
      const wrapper = node('div', undefined, 'table-scroll');
      wrapper.append(table);
      section.append(wrapper);
    }
    if (report.unsupported_labels?.length) section.append(node('p',
      `Sin evidencia suficiente para confirmar: ${report.unsupported_labels.join(', ')}. Añade tomas variadas en sesiones nuevas.`, 'help'));
    if (report.policy_class_support?.length) {
      const table = node('table', undefined, 'data-table'), header = node('tr');
      for (const text of ['Seña', 'Tomas de calibración', 'Aceptadas al calibrar']) header.append(node('th', text));
      table.append(header);
      for (const item of report.policy_class_support) {
        const row = node('tr');
        for (const value of [item.text || item.id, item.support ?? '—', item.accepted ?? '—']) row.append(node('td', String(value)));
        table.append(row);
      }
      const wrapper = node('div', undefined, 'table-scroll');
      wrapper.append(table);
      section.append(wrapper);
    }
    if (report.note) section.append(node('p', report.note, 'help'));
  }
  section.append(node('p', 'Cobertura es la proporción de tomas aceptadas; no es precisión. Las correctas descartadas son aciertos del clasificador que los filtros rechazan, acumulados hasta cada etapa. Estos resultados sobre tomas guardadas no miden la confirmación con la cámara en vivo.', 'help'));
  return section;
}
function renderVersions() {
  const host = $('model-versions');
  host.replaceChildren();
  for (const version of versionData) {
    const card = node('article', undefined, 'version-card' + (version.active ? ' active' : ''));
    const validation = version.validation_decisions || {},
      test = version.test_decisions || {};
    card.append(
      node('span', version.active ? 'ACTIVO' : 'GUARDADO', 'small-label'),
      node(
        'h3',
        new Date(version.created_at).toLocaleString('es-MX', {
          dateStyle: 'medium',
          timeStyle: 'short',
        }),
      ),
      node(
        'p',
        `${version.version.slice(0, 8)} · ${version.labels.length} señas · ${version.samples} ejemplos`,
      ),
    );
    const metrics = node('div', undefined, 'version-metrics');
    metrics.append(
      node(
        'span',
        `F1 val. ${validation.macro_f1 === undefined ? '—' : (validation.macro_f1 * 100).toFixed(1) + ' %'}`,
      ),
      node(
        'span',
        `Cobertura ${test.coverage === undefined ? '—' : (test.coverage * 100).toFixed(1) + ' %'}`,
      ),
    );
    card.append(
      metrics,
      node('p', version.provenance?.note || 'Histórico: sin agrupación documentada.'),
    );
    const details = node('details');
    details.append(node('summary', 'Comparar y ver curvas'));
    const info = node(
      'p',
      `Prueba: ${(version.test_accuracy * 100).toFixed(1)} %. Predicciones aceptadas: ${test.accepted ?? '—'}/${test.evaluated ?? '—'}. ${version.model_comparison?.note || ''}`,
    );
    details.append(info);
    const recognitionDiagnostics = renderRecognitionDiagnostics(version);
    if (recognitionDiagnostics) details.append(recognitionDiagnostics);
    const evaluation = version.test_evaluation;
    const confusions = evaluation?.confusions || version.legacy_confusions;
    if (evaluation) {
      details.append(node('p', `Macro-F1 de prueba: ${(evaluation.macro_f1*100).toFixed(1)} %. Errores aceptados: ${evaluation.false_accepts}; rechazos: ${evaluation.rejected}/${evaluation.evaluated}.`));
      details.append(node('p', evaluation.unknown_note, 'help'));
      const table = node('table', undefined, 'data-table'), header = node('tr');
      for (const text of ['Seña', 'Precisión', 'Recall', 'F1', 'Ejemplos']) header.append(node('th', text));
      table.append(header);
      for (const item of evaluation.by_class) {
        const row = node('tr');
        for (const value of [item.text, ...['precision','recall','f1-score'].map(k => (100*item[k]).toFixed(1)+' %'), item.support]) row.append(node('td', String(value)));
        table.append(row);
      }
      details.append(table);
    }
    for (const pair of confusions?.pairs || []) details.append(node('p', `${pair.a_text} → ${pair.b_text}: ${pair.a_to_b}; ${pair.b_text} → ${pair.a_text}: ${pair.b_to_a}. Revisa ejemplos de ambas señas y añade sesiones variadas.`));
    for (const group of confusions?.groups || []) details.append(node('p', 'Grupo confundido: '+group.map(id => version.labels.find(l => l.id === id)?.text || id).join(', ')));
    for (const item of version.diagnostics?.dataset?.by_class || []) {
      if (item.recommendations.length) details.append(node('p', item.text+': '+item.recommendations.join(' '), 'help'));
    }
    for (const issue of version.model_comparison?.regressions || []) details.append(node('p', `Retroceso: ${version.labels.find(l => l.id === issue.id)?.text || issue.id} · ${issue.metric}: ${(100*issue.previous).toFixed(1)} → ${(100*issue.candidate).toFixed(1)} %.`));
    if (version.model_comparison && !version.model_comparison.comparable) details.append(node('p', 'No hay datos independientes comunes suficientes para certificar que supera a la versión anterior.', 'help'));
    for (const item of version.validation_by_class || []) {
      const weak = item.recall < .6 || item.accepted < 2 || (item.precision || 0) < .9 || item.coverage < .25;
      details.append(node('p', `${item.text}: recuperación ${(100 * item.recall).toFixed(0)}%, cobertura ${(100 * item.coverage).toFixed(0)}%, precisión confirmada ${item.precision == null ? '—' : (100 * item.precision).toFixed(0) + '%'}.${weak ? ' Necesita más ejemplos variados o revisar sus etiquetas.' : ''}`));
    }
    if (version.confusion_matrix) {
      const table = node('table', undefined, 'data-table'), header = node('tr');
      header.append(node('th', 'Real / predicha'));
      for (const label of version.labels) header.append(node('th', label.text));
      table.append(header);
      version.confusion_matrix.forEach((values, i) => {
        const row=node('tr'); row.append(node('th',version.labels[i].text));
        for (const value of values) row.append(node('td',String(value)));
        table.append(row);
      });
      const wrapper=node('div',undefined,'table-scroll');wrapper.append(table);details.append(wrapper);
    }
    if (version.diagnostics?.preprocessing_probe) {
      details.append(node('p',version.diagnostics.preprocessing_probe.note,'help'));
      for (const probe of version.diagnostics.preprocessing_probe.results) details.append(node('p',`${probe.preprocessing}: F1 de validación del sondeo ${(100*probe.validation_macro_f1).toFixed(1)} %.`));
      const reviews=version.diagnostics.label_review || [];
      if (reviews.length) details.append(node('p',`${reviews.length} ejemplos de entrenamiento se parecen a otra clase. Revisa sus etiquetas; el informe exportado contiene sus identificadores.`, 'help'));
    }
    if (version.independent_test_comparison?.comparable) {
      const comparison=version.independent_test_comparison;
      details.append(node('p',`Prueba común independiente (${comparison.samples} ejemplos): F1 anterior ${(100*comparison.previous.macro_f1).toFixed(1)} %, nuevo ${(100*comparison.candidate.macro_f1).toFixed(1)} %. Esta prueba no selecciona el modelo.`));
    }
    const download=node('button','Descargar evaluación','text-button');download.type='button';
    download.addEventListener('click',()=>{
      const url=URL.createObjectURL(new Blob([JSON.stringify(version,null,2)],{type:'application/json'}));
      const link=document.createElement('a');link.href=url;link.download=`sena-evaluacion-${version.version}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });
    details.append(download);
    if (version.history?.length) {
      for (const key of ['accuracy', 'loss']) {
        const chart = node('div', undefined, 'chart');
        chart.id = `version-${version.version}-${key}`;
        details.append(chart);
      }
    } else {
      details.append(node('p', 'Esta versión no guardó curvas por época.'));
    }
    card.append(details);
    if (!version.active && state.user?.role === 'admin') {
      const activate = node('button', 'Activar esta versión', 'secondary');
      activate.type = 'button';
      activate.addEventListener('click', async () => {
        const password = $('restore-password').value;
        $('restore-password').value = '';
        if (!password)
          return notice('Escribe la contraseña de administrador para activar una versión.', true);
        try {
          await stopCamera();
          await api('/api/models/activate', { language, version: version.version, password });
          await refresh();
          await loadVersions();
          notice('Modelo comprobado y activado.');
        } catch (e) {
          notice(e.message, true);
        }
      });
      card.append(activate);
    }
    host.append(card);
    if (version.history?.length) {
      drawCurve(
        `version-${version.version}-accuracy`,
        version.history,
        'accuracy',
        'val_accuracy',
        true,
      );
      drawCurve(`version-${version.version}-loss`, version.history, 'loss', 'val_loss', false);
    }
  }
  if (!versionData.length)
    host.append(node('div', 'Todavía no hay versiones guardadas para esta lengua.', 'empty-state'));
}
async function exportDataset() {
  if (studioBusy) return;
  await stopCamera();
  studioBusy = true;
  try {
    const data = await api('/api/dataset/export', { language });
    const bytes = Uint8Array.from(atob(data.data), (c) => c.charCodeAt(0));
    downloadBlob(new Blob([bytes], { type: 'application/zip' }), data.filename);
    notice(`${data.samples} ejemplos exportados con su vocabulario y procedencia.`);
  } catch (e) {
    notice(e.message, true);
  } finally {
    studioBusy = false;
    if (state) render();
  }
}
function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob),
    link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function importDataset(event) {
  const file = event.target.files[0];
  if (!file) return;
  if (file.size > 32 * 1024 * 1024) {
    event.target.value = '';
    return notice('El ZIP supera 32 MB.', true);
  }
  studioBusy = true;
  try {
    await stopCamera();
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 16384)
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 16384));
    const result = await api('/api/dataset/import', { language, data: btoa(binary) });
    await refresh();
    notice(
      `${result.imported} ejemplos importados. ${result.skipped_duplicates} duplicados omitidos. El modelo no se modifica hasta entrenar.`,
    );
    auditData = null;
  } catch (e) {
    notice(e.message, true);
  } finally {
    event.target.value = '';
    studioBusy = false;
    if (state) render();
  }
}
// Mount the same camera controls in either recognition or dataset, never duplicate streams.
$('recognition-camera').append($('camera-workspace'));
const quality = node('div', undefined, 'quality-strip');
quality.id = 'quality-status';
quality.append(node('i', undefined, 'quality-dot'));
const qualityMessage = node('span', 'Activa la cámara para comprobar el encuadre.');
qualityMessage.id = 'quality-message';
const latency = node('small', '—');
latency.id = 'frame-latency';
quality.append(qualityMessage, latency);
$('camera-workspace').insertBefore(quality, $('test-controls'));
const alternatives = node('div');
alternatives.id = 'alternatives';
document.querySelector('.result-card').append(alternatives);
const participantLabel = $('capture-participant').parentElement;
participantLabel.classList.add('participant-field');
$('capture-controls').insertBefore(participantLabel, $('record'));
const provenanceNote = node(
  'p',
  'Graba cada seña en al menos tres sesiones. Si cambias de persona, usa otro identificador para separar sus datos al evaluar.',
  'help',
);
$('capture-controls').insertBefore(provenanceNote, $('record'));
$('capture-controls').hidden = true;
$('test-results').hidden = false;
$('training-results').hidden = false;
for (const button of document.querySelectorAll('[data-view]'))
  button.addEventListener('click', () => navigateStudio(button.dataset.view));
$('profile-select').addEventListener('change', async () => {
  await selectLanguage($('profile-select').value);
});
$('appearance').addEventListener('change', () => applyTheme($('appearance').value));
$('theme-toggle').addEventListener('click', () =>
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'),
);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  if (localStorage.getItem('sena-theme') === 'system') applyTheme('system');
});
$('reduce-motion').checked = localStorage.getItem('sena-reduce-motion') === 'true';
document.documentElement.dataset.reduceMotion = String($('reduce-motion').checked);
$('reduce-motion').addEventListener('change', () => {
  localStorage.setItem('sena-reduce-motion', String($('reduce-motion').checked));
  document.documentElement.dataset.reduceMotion = String($('reduce-motion').checked);
});
$('inference-mode').value = localStorage.getItem('sena-confirmation') || 'balanced';
$('inference-mode').addEventListener('change', () =>
  localStorage.setItem('sena-confirmation', $('inference-mode').value),
);
$('capture-participant').addEventListener('change', async () => {
  if (stream) await stopCamera();
});
$('vocabulary-search').addEventListener('input', filterVocabulary);
$('audit-dataset').addEventListener('click', auditDataset);
$('audit-filter').addEventListener('change', renderAudit);
$('audit-select-all').addEventListener('change', () => {
  $('sample-confirm').checked = false;
  for (const input of $('audit-rows').querySelectorAll('input'))
    input.checked = $('audit-select-all').checked;
});
$('delete-samples').addEventListener('click', () => modifySamples('delete'));
$('move-samples').addEventListener('click', () => modifySamples('move'));
$('refresh-versions').addEventListener('click', loadVersions);
$('export-dataset').addEventListener('click', exportDataset);
$('import-dataset').addEventListener('change', importDataset);
applyTheme(localStorage.getItem('sena-theme') || 'system');
navigateStudio(location.hash.slice(1) || 'home');

async function previewSample(id) {
  try {
    await stopCamera();
    const result = await api('/api/dataset/sample', { language, sample: id });
    $('sample-dialog-title').textContent = result.sample.text + ' · ' + id.slice(0, 8);
    $('sample-dialog-info').textContent =
      `${result.timeline.length} fotogramas · ${Math.round(result.sample.quality.usable_ratio * 100)} % con buen encuadre · ${result.sample.metadata?.participant || 'Participante no registrado'}${result.sample.quality.boundary_warning ? ' · Movimiento al final: comprueba que la seña no esté recortada.' : ''}`;
    drawCurve('sample-motion-chart', result.timeline, 'motion', 'motion', false);
    drawCurve('sample-quality-chart', result.timeline, 'quality', 'quality', true);
    $('sample-dialog').showModal();
  } catch (e) {
    notice(e.message, true);
  }
}
$('close-sample').addEventListener('click', () => $('sample-dialog').close());

document.querySelector('.brand').addEventListener('click', (event) => {
  event.preventDefault();
  navigateStudio('home');
});
