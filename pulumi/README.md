# pulumi

Pulumi stack that provisions the local kind Kubernetes cluster, wires it for OIDC login against Auth0, and bootstraps Flux so it starts reconciling from GitOps.

## Project structure

```text
pulumi/
├── __main__.py          # Entrypoint — wires config, creates resources, exports outputs
├── modules/
│   ├── network.py       # Docker network for the kind cluster
│   ├── cluster.py       # kind cluster creation + OIDC apiserver config
│   └── flux.py          # Flux Operator install + FluxInstance sync config
├── Pulumi.yaml               # Stack definition
├── Pulumi.platform-sandbox.yaml  # Stack config for the platform-sandbox stack
└── Pulumi.app-dev.yaml           # Stack config for the app-dev stack
```

## What it manages

**Docker network** — a dedicated network per stack (`network.py`), so each kind cluster gets its own isolated subnet.

**Kind cluster** — created by shelling out to the `kind` CLI (`local.Command`, since Pulumi has no native kind provider). The kubeadm config is patched with `--oidc-issuer-url` / `--oidc-client-id` pointed at the `pulumi-shared` stack's Auth0 tenant, read via `pulumi.StackReference("Jdavid77/pulumi-shared/shared")`.

**Flux bootstrap** — installs the Flux Operator via Helm, then creates a `FluxInstance` that syncs from [`platform-gitops`](https://github.com/Jdavid77/platform-gitops) at `clusters/<stack-name>`.

## Stack outputs

| Output | Description |
|--------|-------------|
| `kubeconfig` | Raw kubeconfig for the kind cluster (secret) |
| `dockerNetwork` | Name of the Docker network the cluster runs on |
| `clusterName` | Name of the kind cluster |

Use `.scripts/get-oidc-kubeconfig.sh <stack>` rather than the raw `kubeconfig` output directly — it patches in the `kubectl oidc-login` exec credentials needed to actually authenticate.

## Known issue: moving machines breaks `pulumi refresh`

`local.Command` has no `read` and only re-runs on `triggers` changes, so switching machines
leaves Pulumi believing the (now nonexistent) kind cluster/network still exist.

## Fix

Don't `pulumi destroy` — its delete commands fail against resources that never existed here.
Drop the stale resources from state and recreate instead:

```bash
pulumi state delete 'urn:pulumi:<stack>::platform-core::command:local:Command::docker:net' \
  --target-dependents --stack <stack>
pulumi up --stack <stack>
```

Repeat for each stack (`platform-sandbox`, `app-dev`).
