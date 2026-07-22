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

echo "==> Forcing Flux reconciliation: ${PULUMI_STACK} in ${NAMESPACE}"
flux reconcile kustomization "${PULUMI_STACK}" -n "${NAMESPACE}" --with-source

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
