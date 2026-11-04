'use strict';
let accountState = null, accountMode = 'login', accountBusy = false, accountBoot = null;
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
// Oculta el estudio, detiene la cámara y vuelve a consultar la sesión de acceso.
function lockAccount() {
  accountState = null;
  $('team-workspace').hidden = true;
  $('account-gate').hidden = false;
  if (stream) void stopCamera();
  void bootstrapAccounts().catch(error => { $('account-message').textContent = error.message; });
}
// Configura los campos de registro o inicio de sesión del modo autenticado heredado.
function accountScreen(mode) {
  accountMode = mode;
  const setup = accountState?.setup_required, registering = mode !== 'login';
  $('account-title').textContent = setup ? 'Prepara el espacio del equipo.' : registering ? 'Únete a tu equipo.' : 'Iniciar sesión';
  $('account-description').textContent = setup
    ? 'Elige tu usuario y contraseña para crear la primera cuenta administradora del equipo.'
    : registering ? 'Pide al administrador un código de invitación y elige tu contraseña.' : 'Inicia sesión para acceder a los ejemplos y modelos del equipo.';
  $('account-tabs').hidden = !!setup;
  for (const id of ['account-name-label','account-consent-label']) $(id).hidden = !registering;
  $('account-invite-label').hidden = !registering || setup;
  $('account-password').minLength = registering ? 12 : 1;
  $('account-password').autocomplete = registering ? 'new-password' : 'current-password';
  $('account-submit').textContent = setup ? 'Crear espacio de equipo' : registering ? 'Crear mi cuenta' : 'Entrar';
  $('account-password').value = '';
  $('account-message').textContent = '';
}
// Comparte la carga inicial en curso para evitar consultas de acceso duplicadas.
async function bootstrapAccounts() {
  if (accountBoot) return accountBoot;
  accountBoot = loadAccount();
  try { return await accountBoot; } finally { accountBoot = null; }
}
// Abre el estudio en modo local o muestra el acceso del despliegue autenticado.
async function loadAccount() {
  accountState = await accountApi('/api/auth/status');
  if (accountState.user) {
    $('account-gate').hidden = true;
    $('team-workspace').hidden = false;
    await refresh();
    renderTeam();
  } else {
    $('team-workspace').hidden = true;
    $('account-gate').hidden = false;
    accountScreen(accountState.setup_required ? 'setup' : 'login');
  }
}
// Aplica identidad y permisos y oculta controles de cuentas cuando está activo el modo local.
function renderTeam() {
  const user = state?.user || accountState?.user;
  if (!user) return;
  const admin = user.role === 'admin';
  const local = !!user.local;
  $('team-settings').hidden = local;
  $('account-logout').hidden = local;
  $('current-account').textContent = user.name;
  if (local) {
    const consent = $('shared-camera-consent');
    const label = consent.closest('label');
    for (const node of Array.from(label.childNodes)) {
      if (node.nodeType === Node.TEXT_NODE) node.remove();
    }
    label.append(document.createTextNode(' Permito procesar mi cámara en esta Mac. Las imágenes no se guardan; solo se guardan los puntos de las tomas que confirme.'));
  }
  $('team-account-info').textContent = `${user.name} · @${user.username} · ${admin ? 'Administrador' : 'Colaborador'}`;
  $('capture-participant').readOnly = !local;
  if (!local) $('capture-participant').value = user.name;
  else if ($('capture-participant').value === 'Modo local') $('capture-participant').value = '';
  $('team-admin').hidden = !admin;
  document.querySelector('.admin-panel').hidden = !admin;
  $('sample-admin').hidden = !admin;
  if (!admin) {
    for (const id of ['train-model','import-dataset','add-alphabet','add-all-alphabets','add-alphabet-extras']) {
      const element = $(id); if (element) element.disabled = true;
    }
    $('train-reason').textContent = 'El administrador del equipo configura y activa los entrenamientos.';
  }
}
$('account-login-tab').addEventListener('click', () => accountScreen('login'));
$('account-register-tab').addEventListener('click', () => accountScreen('register'));
$('account-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (accountBusy) return;
  accountBusy = true; $('account-submit').disabled = true;
  try {
    const route = accountMode === 'setup' ? 'setup' : accountMode === 'register' ? 'register' : 'login';
    accountState = await accountApi('/api/auth/' + route, {
      username:$('account-username').value.trim(), name:$('account-name').value.trim(),
      password:$('account-password').value,
      invite:$('account-invite').value.trim(), shared_consent:$('account-consent').checked,
    });
    $('account-form').reset();
    state = undefined; stateRequest = null; selectedDraft = null; displayedDraft = null;
    await bootstrapAccounts();
    $('shared-camera-consent').checked = false;
  } catch(error) { $('account-message').textContent = error.message; }
  finally { accountBusy = false; $('account-submit').disabled = false; }
});
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
