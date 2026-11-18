'use strict';
// Catálogo de palabras y frases del Dataset. Funciona igual que el abecedario:
// pulsar una entrada prepara su nombre para la siguiente grabación.
let addingVocabulary = false;

function vocabularyCategoryId(catalog) {
  const stored = localStorage.getItem('sena-vocabulary-category');
  const current = $('vocabulary-category').value || stored;
  return catalog.some((c) => c.id === current) ? current : catalog[0]?.id;
}

function renderVocabulary() {
  const p = typeof profile === 'function' ? profile() : null;
  const catalog = p?.catalog;
  $('vocabulary-panel').hidden = !catalog?.length;
  if (!catalog?.length) return;
  const chosen = vocabularyCategoryId(catalog);
  const options = catalog.map((c) => {
    const registered = c.entries.filter((e) => e.label_id).length;
    return makeOption(c.id, `${c.title} · ${registered}/${c.entries.length}`);
  });
  $('vocabulary-category').replaceChildren(...options);
  $('vocabulary-category').value = chosen;
  const category = catalog.find((c) => c.id === chosen);
  const all = catalog.flatMap((c) => c.entries);
  $('vocabulary-count').textContent =
    `${all.filter((e) => e.trained).length} entrenadas · ${all.length} en el catálogo`;
  const registered = category.entries.filter((e) => e.label_id).length;
  const ready = category.entries.filter((e) => e.samples >= state.minimum_samples).length;
  const trained = category.entries.filter((e) => e.trained).length;
  $('vocabulary-progress').textContent =
    `${registered} / ${category.entries.length} en el vocabulario · ${ready} con ${state.minimum_samples}+ ejemplos · ${trained} incluidas en el modelo.`;
  const busy = addingVocabulary || batch.active || state.job?.state === 'running';
  $('add-vocabulary-category').disabled = busy || registered === category.entries.length;
  $('add-vocabulary-category').textContent = registered === category.entries.length
    ? 'Categoría añadida' : 'Añadir categoría al vocabulario';
  $('vocabulary-grid').replaceChildren(...category.entries.map((entry) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'letter-tile' + (entry.trained ? ' trained' : '') + (category.kind === 'frase' ? ' phrase' : '');
    button.setAttribute('aria-pressed', String(selectedLetter === entry.text));
    button.setAttribute('aria-label',
      `${entry.text}: ${entry.samples} ejemplos${entry.trained ? ', incluida en el modelo' : ''}`);
    button.disabled = recording || countdown || savingDraft || batch.active;
    const text = document.createElement('span');
    text.textContent = entry.text;
    const count = document.createElement('small');
    count.textContent = `${entry.samples} / ${state.minimum_samples}`;
    button.append(text, count);
    button.addEventListener('click', () => {
      selectedLetter = entry.text;
      if (selectedDraft) $('sign-name').value = entry.text;
      renderAlphabet();
      renderVocabulary();
      if (selectedDraft) {
        $('name-capture').scrollIntoView({ behavior: 'smooth', block: 'center' });
        $('sign-name').focus({ preventScroll: true });
      } else $('camera-workspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    return button;
  }));
  $('vocabulary-selection').textContent = selectedLetter
    ? `Seleccionada: «${selectedLetter}». Graba la seña; al terminar, el nombre ya estará escrito.`
    : 'Selecciona una palabra o frase para preparar su nombre al terminar la grabación.';
}

async function addVocabularyCategory() {
  if (addingVocabulary) return;
  const category = $('vocabulary-category').value;
  const chosenLanguage = language;
  addingVocabulary = true;
  renderVocabulary();
  try {
    const result = await api('/api/vocabulary/category', { language: chosenLanguage, category });
    await refresh();
    notice(`${result.added} palabras o frases añadidas al vocabulario. Ahora graba ejemplos de cada una y entrena.`);
  } catch (error) {
    notice(error.message, true);
  } finally {
    addingVocabulary = false;
    renderVocabulary();
  }
}

$('vocabulary-category').addEventListener('change', () => {
  localStorage.setItem('sena-vocabulary-category', $('vocabulary-category').value);
  renderVocabulary();
});
$('add-vocabulary-category').addEventListener('click', addVocabularyCategory);
