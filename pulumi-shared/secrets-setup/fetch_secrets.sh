#!/usr/bin/env bash
set -eou pipefail

ENV_FILE="../.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Can't find env file...exiting"
    exit 1
fi

set -o allexport
source "$ENV_FILE"
set +o allexport

if ! bw login --check &>/dev/null; then
    bw login --apikey
fi

export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)

if [ -z "$BW_SESSION" ]; then
    echo "Error: Failed to unlock Bitwarden vault."
    exit 1
fi

auth0_item=$(bw get item "Auth0 Secrets" --session "$BW_SESSION")

auth0_client_id=$(echo "$auth0_item" | jq -r '.fields[] | select(.name == "pulumi-client-id") | .value')
auth0_client_secret=$(echo "$auth0_item" | jq -r '.fields[] | select(.name == "pulumi-client-secret") | .value')

(
    cd ..
    pulumi config set --secret auth0:clientId "$auth0_client_id"
    pulumi config set --secret auth0:clientSecret "$auth0_client_secret"
)

echo "Pulumi config updated."
