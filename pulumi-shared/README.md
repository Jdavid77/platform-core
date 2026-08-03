# pulumi-shared

Pulumi stack that provisions shared Auth0 infrastructure used as the OIDC identity provider for Kubernetes clusters.

> **Why Auth0 instead of Keycloak?** The book has you self-host Keycloak inside the Kubernetes cluster, but that's a chicken-and-egg problem here: the cluster's apiserver needs an OIDC issuer to come up with OIDC auth configured, and that issuer can't be a workload running on the same cluster it's meant to authenticate. Running Keycloak in Docker alongside kind was also considered, but keeping the two networks reachable from each other added more complexity than it solved. Auth0 sidesteps both problems as a hosted IdP that exists independently of the cluster's lifecycle.

## Project structure

```text
pulumi-shared/
├── __main__.py          # Entrypoint — wires config, creates resources, exports outputs
├── modules/
│   └── auth0.py         # Auth0 resource factories (client, role, post-login action)
├── Pulumi.yaml          # Stack definition
└── Pulumi.shared.yaml   # Stack config (clusters, roles, Auth0 credentials)
```

## What it manages

**Auth0 clients** — one native app per cluster (e.g. `kubernetes-platform-sandbox`). Native app type means no client secret is required; authentication uses PKCE instead.

**Auth0 roles** — named roles (e.g. `platform-admin`, `platform-user`) that can be assigned to users in the Auth0 dashboard.

**Post-login Action** — an Auth0 Action that runs after every login and injects the user's roles into the ID token as a custom claim:

```
https://platform.internal/roles: ["platform-admin"]
```

This is the claim the kube-apiserver reads to determine group membership for RBAC.

## Stack outputs

| Output | Description |
|--------|-------------|
| `auth0_issuer_url` | Auth0 tenant URL, used as `--oidc-issuer-url` on the apiserver |
| `auth0_client_id_<cluster>` | Client ID for each cluster, used as `--oidc-client-id` |

Downstream cluster stacks read these via `pulumi.StackReference`.

## Prerequisites

- An Auth0 tenant with a Machine-to-Machine application that has the **Auth0 Management API** authorized — its credentials go into the stack config

## Configuration

`Pulumi.shared.yaml` holds the stack config:

```yaml
config:
  auth0:domain: <your-tenant>.us.auth0.com
  auth0:clientId:
    secure: <encrypted>        # Auth0 Management API client ID
  auth0:clientSecret:
    secure: <encrypted>        # Auth0 Management API client secret
  clusters:
    - platform-sandbox
    - app-dev
  roles:
    - name: platform-admin
      description: "Kubernetes Cluster Admin"
    - name: platform-user
      description: "Kubernetes User (Read-Only)"
```

`clusters` controls which Auth0 clients get created (one per entry). `roles` controls which Auth0 roles get created.

## Secrets management

Both scripts below need a `.env` file (gitignored) in `pulumi-shared/` with a `BW_PASSWORD` for unlocking the Bitwarden vault.

**`secrets-setup/fetch_secrets.sh`** — pulls the Auth0 Management API credentials out of Bitwarden and writes them into pulumi config. It logs into Bitwarden, unlocks the vault, reads the **"Auth0 Secrets"** item, and sets `auth0:clientId` / `auth0:clientSecret` from its `pulumi-client-id` / `pulumi-client-secret` fields. This is the script to run before `pulumi up`.

**`secrets-setup/inject_secrets.sh`** — the reverse direction. It reads local `*.json` files in `secrets-setup/` (see `auth0_secrets.json_example` for the expected shape) and creates or updates the matching item in Bitwarden. Use this to seed or update the "Auth0 Secrets" item itself, not to configure pulumi.
