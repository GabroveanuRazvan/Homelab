#!/usr/bin/env bash

set -euo pipefail

readonly REPOSITORY_KEY_PATH="${ARGOCD_REPOSITORY_KEY_PATH:-${HOME}/.ssh/argocd-homelab}"

if [[ -e "${REPOSITORY_KEY_PATH}" || -e "${REPOSITORY_KEY_PATH}.pub" ]]; then
  echo "Refusing to overwrite an existing key: ${REPOSITORY_KEY_PATH}" >&2
  exit 1
fi

umask 077
ssh-keygen \
  -t ed25519 \
  -N "" \
  -C "argocd-homelab-read-only" \
  -f "${REPOSITORY_KEY_PATH}"

echo
echo "Add this public key to the GitHub repository as a read-only deploy key:"
cat "${REPOSITORY_KEY_PATH}.pub"

