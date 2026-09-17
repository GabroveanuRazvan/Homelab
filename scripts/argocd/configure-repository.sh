#!/usr/bin/env bash

set -euo pipefail

readonly ARGOCD_NAMESPACE="argocd"
readonly REPOSITORY_SECRET="homelab-git-repository"
readonly REPOSITORY_URL="git@github.com:GabroveanuRazvan/Ansible-Playbooks.git"
readonly REPOSITORY_KEY_PATH="${ARGOCD_REPOSITORY_KEY_PATH:-${HOME}/.ssh/argocd-homelab}"


kubectl create secret generic "${REPOSITORY_SECRET}" \
  --namespace "${ARGOCD_NAMESPACE}" \
  --from-literal=type=git \
  --from-literal=url="${REPOSITORY_URL}" \
  --from-file=sshPrivateKey="${REPOSITORY_KEY_PATH}" \
  --dry-run=client \
  --output=yaml |
kubectl apply \
  --server-side \
  --field-manager=argocd-repository-bootstrap \
  --filename=-

kubectl label secret "${REPOSITORY_SECRET}" \
  --namespace "${ARGOCD_NAMESPACE}" \
  argocd.argoproj.io/secret-type=repository \
  --overwrite
