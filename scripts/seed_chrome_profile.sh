#!/bin/zsh
set -euo pipefail

# Copiar el perfil Chrome a data/chrome-profile/. Ejecutar en Terminal.app
# (tiene permiso TCC). Cierra Google Chrome antes.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${HOME}/Library/Application Support/Google/Chrome"
DEST="${ROOT}/data/chrome-profile"
PROFILE_NAME="${1:-Default}"

if [[ -e "${SRC}/SingletonLock" ]]; then
  echo "Cierra todas las ventanas de Google Chrome e inténtalo de nuevo." >&2
  exit 1
fi

mkdir -p "${DEST}"
if [[ -f "${SRC}/Local State" ]]; then
  cp "${SRC}/Local State" "${DEST}/Local State"
fi
rm -rf "${DEST}/${PROFILE_NAME}"
cp -R "${SRC}/${PROFILE_NAME}" "${DEST}/${PROFILE_NAME}"
echo "Perfil copiado a ${DEST}/${PROFILE_NAME}"
