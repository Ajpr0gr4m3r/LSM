'use strict';
let accountState = null, accountBoot = null;
// Envía operaciones de cuenta con el CSRF de acceso, separado del token del estado de cámara.
async function accountApi(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type':'application/json', 'X-LSM-Token':accountState?.csrf || ''},
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'No se pudo acceder al equipo.');
  return result;
}
// Renueva el acceso del navegador si la sesión caducó.
function recoverAccess() {
  if (accountBoot) return;
  accountState = null;
  if (stream) void stopCamera();
  void bootstrapAccounts().catch(error => notice(error.message, true));
}
// Comparte la carga inicial en curso para evitar consultas de acceso duplicadas.
async function bootstrapAccounts() {
  if (accountBoot) return accountBoot;
  accountBoot = loadAccount();
  try { return await accountBoot; } finally { accountBoot = null; }
}
// Obtiene la sesión de visitante o reutiliza una sesión vigente.
async function loadAccount() {
  accountState = await accountApi('/api/auth/status');
  if (!accountState.user) {
    throw new Error('El servidor no ofrece acceso de visitante. Actualiza el despliegue de Seña.');
  }
  await refresh();
}
// Aplica identidad y permisos y oculta controles de cuentas cuando está activo el modo local.
function renderTeam() {
  const user = state?.user || accountState?.user;
  if (!user) return;
  const admin = !!user.studio_admin;
  for (const element of document.querySelectorAll('[data-admin-only]')) element.hidden = !admin;
  const adminToggle = $('studio-admin-toggle');
  adminToggle.textContent = admin ? 'Cerrar admin' : 'Admin';
  adminToggle.setAttribute('aria-label', admin ? 'Cerrar modo administrador' : 'Modo administrador');
  if (!admin && typeof ADMIN_VIEWS !== 'undefined') {
    clearSpelling();
    if (ADMIN_VIEWS.has(currentView)) void navigateStudio('home');
  }
  const local = !!user.local;
  $('team-settings').hidden = local || !!user.guest || admin;
  $('account-logout').hidden = local || !!user.guest || admin;
  $('current-account').textContent = user.name;
  if (local) {
    const consent = $('shared-camera-consent');
    const label = consent.closest('label');
    for (const node of Array.from(label.childNodes)) {
      if (node.nodeType === Node.TEXT_NODE) node.remove();
    }
    label.append(document.createTextNode(' Permito procesar mi cámara en esta Mac. Las imágenes no se guardan; solo se guardan los puntos de las tomas que confirme.'));
  }
  $('team-account-info').textContent = user.guest ? 'Estás usando Seña como visitante. El acceso no requiere cuenta.' : `${user.name} · @${user.username} · ${admin ? 'Administrador' : 'Colaborador'}`;
  $('capture-participant').readOnly = !local && !user.guest;
  if (!local && !user.guest) $('capture-participant').value = user.name;
  else if ($('capture-participant').value === 'Modo local') $('capture-participant').value = '';
  $('team-admin').hidden = user.role !== 'admin' || admin;
  document.querySelector('.admin-panel').hidden = !admin;
  $('sample-admin').hidden = !admin;
  if (!admin) {
    for (const id of ['train-model','import-dataset','add-alphabet','add-all-alphabets','add-alphabet-extras']) {
      const element = $(id); if (element) element.disabled = true;
    }
    $('train-reason').textContent = 'El administrador del equipo configura y activa los entrenamientos.';
  }
}
const adminDialog = $('studio-admin-dialog');
const adminForm = $('studio-admin-form');
const adminPassword = $('studio-admin-password');
const adminError = $('studio-admin-error');
const adminSubmit = $('studio-admin-submit');
adminDialog.addEventListener('close', () => { adminPassword.value = ''; });
$('studio-admin-cancel').addEventListener('click', () => adminDialog.close());
$('studio-admin-toggle').addEventListener('click', async () => {
  if (!state?.user?.studio_admin) {
    adminError.hidden = true;
    adminDialog.showModal();
    adminPassword.focus();
    return;
  }
  try {
    await changeStudioAccess('/api/admin/lock');
    await navigateStudio('home');
  } catch (error) {
    notice(error.message, true);
  }
});
adminForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (adminSubmit.disabled) return;
  adminError.hidden = true;
  adminSubmit.disabled = true;
  try {
    await changeStudioAccess('/api/admin/unlock', {password: adminPassword.value});
    adminDialog.close();
    await navigateStudio('dataset');
  } catch (error) {
    adminError.textContent = error.message;
    adminError.hidden = false;
  } finally {
    adminPassword.value = '';
    adminSubmit.disabled = false;
  }
});

async function changeStudioAccess(route, body = {}) {
  if (!accountState?.user) await bootstrapAccounts();
  if (stream || session) await stopCamera();
  // Deja terminar una lectura con la identidad anterior antes de rotar la cookie.
  if (stateRequest) await stateRequest.catch(() => {});
  await accountApi(route, body);
  accountState = null;
  selectedDraft = null;
  displayedDraft = null;
  await bootstrapAccounts();
}

$('account-logout').addEventListener('click', async () => {
  try {
    await stopCamera();
    accountState = await accountApi('/api/auth/logout', {});
    state = undefined; stateRequest = null; selectedDraft = null; displayedDraft = null;
    $('team-users').replaceChildren(); $('team-invite-code').value = '';
    for (const field of document.querySelectorAll('input[type=password]')) field.value = '';
    for (const dialog of document.querySelectorAll('dialog[open]')) dialog.close();
    clearHistory(); await bootstrapAccounts();
  } catch(error) { notice(error.message, true); }
});
$('create-invite').addEventListener('click', async () => {
  try {
    const result = await accountApi('/api/auth/invite', {});
    $('team-invite-code').value = result.invite;
    $('team-message').textContent = 'Invitación creada. Solo sirve para una cuenta y vence en siete días.';
  } catch(error) { $('team-message').textContent = error.message; }
});
$('refresh-users').addEventListener('click', async () => {
  try {
    const result = await accountApi('/api/auth/users', {});
    $('team-users').replaceChildren();
    for (const user of result.users) {
      const row = document.createElement('div'), label = document.createElement('span');
      label.textContent = `${user.name} · @${user.username} · ${user.active ? 'Activa' : 'Desactivada'}`;
      row.append(label);
      if (user.role !== 'admin') {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'text-button';
        button.textContent = user.active ? 'Desactivar' : 'Reactivar';
        button.addEventListener('click', async () => {
          try { await accountApi(user.active ? '/api/auth/disable' : '/api/auth/enable', {user_id:user.id}); $('refresh-users').click(); }
          catch(error) { $('team-message').textContent = error.message; }
        }); row.append(button);
      }
      $('team-users').append(row);
    }
  } catch(error) { $('team-message').textContent = error.message; }
});
