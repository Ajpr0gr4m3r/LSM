#!/bin/zsh
set -eu
SENA_ROOT="${0:A:h:h}"
cd "$SENA_ROOT"
"$SENA_ROOT/.venv/bin/python" "$SENA_ROOT/private_server.py" enable || {
  print '\nNo se activó el acceso. Corrige el aviso anterior y vuelve a ejecutar este archivo.'
  read -r '?Pulsa Enter para cerrar. '
  exit 1
}
print '\nComparte la dirección HTTPS mostrada solo con los miembros de tu laboratorio.'
read -r '?Pulsa Enter para cerrar. '
