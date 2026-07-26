#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <stack>"
    exit 1
fi

STACK="$1"
OUTPUT="${HOME}/.kube/${STACK}-oidc.yaml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

( cd "$SCRIPT_DIR/.." && pulumi stack output kubeconfig --stack "$STACK" --show-secrets > "$OUTPUT" )

ISSUER_URL=$(cd "$SCRIPT_DIR/../../pulumi-shared" && pulumi stack output auth0_issuer_url --show-secrets)
CLIENT_ID=$(cd "$SCRIPT_DIR/../../pulumi-shared" && pulumi stack output "auth0_client_id_${STACK}"  --show-secrets)

kubectl config --kubeconfig "$OUTPUT" set-credentials oidc \
  --exec-api-version=client.authentication.k8s.io/v1beta1 \
  --exec-command=kubectl \
  --exec-arg=oidc-login \
  --exec-arg=get-token \
  "--exec-arg=--oidc-issuer-url=${ISSUER_URL}" \
  "--exec-arg=--oidc-client-id=${CLIENT_ID}" \
  "--exec-arg=--oidc-pkce-method=S256" \
  "--exec-arg=--oidc-extra-scope=email" \
  "--exec-arg=--oidc-extra-scope=profile"

kubectl config --kubeconfig "$OUTPUT" set-context "kind-${STACK}" --user=oidc

echo "Saved to: $OUTPUT"
echo "Use with: KUBECONFIG=$OUTPUT kubectl get nodes"
