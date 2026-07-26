#!/usr/bin/env bash

set -eou pipefail\


ENV_FILE="../.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Can't find env file...exiting"
    exit 1
fi

set -o allexport
source "$ENV_FILE"
set +o allexport

# Login with API key if not already logged in
if ! bw login --check &>/dev/null; then
    bw login --apikey
fi

export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)

if [ -z "$BW_SESSION" ]; then
    echo -e "Error: Failed to unlock Bitwarden vault. Check your BW_PASSWORD."
    exit 1
fi

for json_file in *.json; do
    echo "Processing: $json_file"
    item_name=$(cat "$json_file" | jq -r .name)
    existing_item=$(bw get item "$item_name" --session "$BW_SESSION" 2>/dev/null)

    if [ -n "$existing_item" ]; then
        echo "Item '$item_name' exists, updating..."
        item_id=$(echo "$existing_item" | jq -r .id)
        cat "$json_file" | bw encode | bw edit item "$item_id" --session "$BW_SESSION"
    else
        echo "Item '$item_name' does not exist, creating..."
        cat "$json_file" | bw encode | bw create item --session "$BW_SESSION"
    fi
done
