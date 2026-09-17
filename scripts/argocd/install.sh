#!/usr/bin/env bash

set -euo pipefail

readonly ARGOCD_CHART_VERSION="${ARGOCD_CHART_VERSION:-10.9.1}"
readonly ARGOCD_NAMESPACE="argocd"
readonly ARGOCD_RELEASE="argocd"
readonly ARGO_HELM_REPOSITORY="https://argoproj.github.io/argo-helm"
readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIRECTORY}/../.." && pwd)"
readonly VALUES_FILE="${REPOSITORY_ROOT}/helm/argocd/values.yaml"

kubectl cluster-info >/dev/null

helm repo add argo "${ARGO_HELM_REPOSITORY}" --force-update
helm repo update argo

helm upgrade --install "${ARGOCD_RELEASE}" argo/argo-cd \
  --namespace "${ARGOCD_NAMESPACE}" \
  --create-namespace \
  --version "${ARGOCD_CHART_VERSION}" \
  --values "${VALUES_FILE}" \
  --rollback-on-failure \
  --wait \
  --wait-for-jobs \
  --timeout 10m \
  --history-max 5

kubectl --namespace "${ARGOCD_NAMESPACE}" get pods

