# The Platform Engineer's Handbook - Platform Core

[![Pulumi](https://github.com/Jdavid77/platform-core/actions/workflows/pulumi.yaml/badge.svg)](https://github.com/Jdavid77/platform-core/actions/workflows/pulumi.yaml)
[![Pulumi Shared](https://github.com/Jdavid77/platform-core/actions/workflows/pulumi-shared.yaml/badge.svg)](https://github.com/Jdavid77/platform-core/actions/workflows/pulumi-shared.yaml)

Follow-along repository for *The Platform Engineer's Handbook*.

This repo provisions the core platform: a local [kind](https://kind.sigs.k8s.io/) Kubernetes cluster wired for OIDC login against Auth0, bootstrapped with a [Flux](https://fluxcd.io/) operator so it can pull the rest of its configuration from GitOps. A self-hosted GitHub Actions runner drives the pipeline that builds, previews, and applies all of this.

## Prerequisites

- [pulumi cli](https://www.pulumi.com/docs/get-started/install/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [docker](https://docs.docker.com/get-docker/)
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- kubectl + [kubelogin](https://github.com/int128/kubelogin) (oidc-login plugin)
- [flux cli](https://fluxcd.io/flux/installation/)
- [bats](https://bats-core.readthedocs.io/)
- [Bitwarden CLI](https://bitwarden.com/help/cli/) (`bw`) — used to fetch the Auth0 secrets
- An Auth0 tenant (see [`pulumi-shared/README.md`](pulumi-shared/README.md))

To run the CI pipeline yourself, register a self-hosted runner (`RUNNER_TOKEN=<token> ./scripts/start-runner.sh`) and configure the `platform-sandbox` / `app-dev` GitHub Environments with required reviewers and a `PULUMI_ACCESS_TOKEN` secret.

## What's in here

**[`pulumi/`](pulumi/README.md)** — the cluster stack: kind cluster, OIDC config, Flux bootstrap.

**[`pulumi-shared/`](pulumi-shared/README.md)** — the Auth0/OIDC identity provider stack. Must be deployed before the cluster stack.

**`scripts/start-runner.sh`** — installs and starts the self-hosted GitHub Actions runner that the CI pipeline requires (`runs-on: self-hosted`).

**`scripts/flux_reconcile.sh`** + **`smoke/`** — forces a Flux reconciliation and runs a Gateway smoke test through Istio to confirm the cluster is actually routing traffic. Run by CI in the `validate-sandbox` / `validate-app-dev` jobs.

**`tests/infrastructure.bats`** — validates the Docker network, cluster reachability, and Flux health. Also run by CI in the `validate-sandbox` / `validate-app-dev` jobs.

## CI/CD pipeline

Two independent workflows, one per Pulumi project. `pulumi-shared.yaml` runs on GitHub-hosted runners, since it only talks to the Auth0 API; `pulumi.yaml` runs on the **self-hosted** runner (`scripts/start-runner.sh`) because it needs Docker to create the kind cluster. Approval gates are plain GitHub Environments with required reviewers — no extra tooling.

```text
pulumi-shared.yaml (push to main, touching pulumi-shared/**)
------------------------------------------------------------------
  [lint-code]       --+
                      +--> [preview-shared] --> (approve-shared) --> [update-shared]
  [static-analysis] --+


pulumi-sandbox.yaml (push to main touching pulumi/**, or tag v*)
------------------------------------------------------------------
  [lint-code]       --+
                        +--> [pre-flight] --> [preview-sandbox]
  [static-analysis] --+                            |
                                                   v
                                             (approve-sandbox) --> [update-sandbox] --> [validate-sandbox]
                                                                                                 |
                                                                                                 | tag push only
                                                                                                 v

app-dev (only on v* tags, once sandbox validates)
------------------------------------------------------------------
                    [pre-flight-app-dev] --> [preview-app-dev]
                                                     |
                                                     v
                                             (approve-app-dev) --> [update-app-dev] --> [validate-app-dev]
```

## Related repos

Part of *The Platform Engineer's Handbook* series:

- [**platform-gitops**](https://github.com/Jdavid77/platform-gitops) — the Flux source this cluster reconciles from (app-of-apps pattern).
- [**platform-services**](https://github.com/Jdavid77/platform-services) — OPA/conftest policies and per-environment service config.
- [**platform-team-admin**](https://github.com/Jdavid77/platform-team-admin) — manages this GitHub org itself (repos, branch protection) as Pulumi code.
