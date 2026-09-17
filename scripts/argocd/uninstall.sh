#!/usr/bin/env bash

set -euo pipefail

readonly ARGOCD_NAMESPACE="argocd"
readonly ARGOCD_RELEASE="argocd"

helm uninstall "${ARGOCD_RELEASE}" --namespace "${ARGOCD_NAMESPACE}" --wait

