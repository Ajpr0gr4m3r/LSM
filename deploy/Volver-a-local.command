#!/bin/zsh
set -eu
SENA_ROOT="${0:A:h:h}"
cd "$SENA_ROOT"
"$SENA_ROOT/.venv/bin/python" "$SENA_ROOT/private_server.py" disable
read -r '?Pulsa Enter para cerrar. '
