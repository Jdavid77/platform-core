#!/bin/bash
# Forces Flux reconciliation for the platform infrastructure kustomizations,
# then runs the Gateway smoke test to validate Istio is routing traffic.
#
# Usage:
#   PULUMI_STACK=platform-sandbox SMOKE_HOST=platform-sandbox.local \
#     ./scripts/flux_reconcile.sh
#
# Prerequisites: flux, kubectl, jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."

NAMESPACE="${FLUX_NAMESPACE:-flux-system}"
SMOKE_HOST="${SMOKE_HOST:-platform-sandbox.local}"
RECONCILE_TIMEOUT="${RECONCILE_TIMEOUT:-300}"

reconcile() {
  local kustomization="$1"
  echo "==> Forcing Flux reconciliation: ${kustomization} in ${NAMESPACE}"
  flux reconcile kustomization "${kustomization}" -n "${NAMESPACE}" --with-source

  echo "==> Waiting for ${kustomization} to be Ready..."
  local deadline=$(( $(date +%s) + RECONCILE_TIMEOUT ))
  while true; do
    local status
    status=$(flux get kustomization "${kustomization}" \
      -n "${NAMESPACE}" -o json 2>/dev/null \
      | jq -r '.status.conditions[] | select(.type=="Ready") | .status' \
      || echo "Unknown")

    if [ "${status}" = "True" ]; then
      echo "==> ${kustomization} is Ready."
      break
    fi

    if [ "$(date +%s)" -ge "${deadline}" ]; then
      echo "ERROR: ${kustomization} did not reconcile within ${RECONCILE_TIMEOUT}s"
      flux get kustomization "${kustomization}" -n "${NAMESPACE}"
      exit 1
    fi

    echo "    Status: ${status} — waiting 5s..."
    sleep 5
  done
}

reconcile $PULUMI_STACK

# ── Gateway smoke test ────────────────────────────────────────────────────────
echo "==> Running Gateway smoke test (Host: ${SMOKE_HOST})"

cleanup() {
  kubectl -n istio-system delete -f "${REPO_ROOT}/smoke/gateway_job.yaml" --ignore-not-found
  kubectl -n istio-system delete -f "${REPO_ROOT}/smoke/http-gateway.yaml" --ignore-not-found
  kubectl -n istio-system delete -f "${REPO_ROOT}/smoke/nginx.yaml" --ignore-not-found
}
trap cleanup EXIT

kubectl -n istio-system apply -f "${REPO_ROOT}/smoke/nginx.yaml"
kubectl -n istio-system wait \
  --for=condition=available \
  deployment/smoke-nginx \
  --timeout=60s

kubectl -n istio-system apply -f "${REPO_ROOT}/smoke/http-gateway.yaml"
kubectl -n istio-system apply -f "${REPO_ROOT}/smoke/gateway_job.yaml"

kubectl -n istio-system wait \
  --for=condition=complete \
  job/smoke-gateway \
  --timeout=120s \
  || {
    echo "ERROR: smoke-gateway Job did not complete — fetching logs:"
    kubectl -n istio-system logs job/smoke-gateway
    exit 1
  }

echo "==> Smoke test PASSED."
