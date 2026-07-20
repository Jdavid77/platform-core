#!/usr/bin/env bash
# Installs and starts a GitHub Actions self-hosted runner on macOS.
#
# Usage:
#   RUNNER_TOKEN=<token> ./scripts/start-runner.sh
#
# The runner binary is downloaded once to ~/.actions-runner/ and reused on
# subsequent runs. Set RUNNER_DIR to override the install location.

set -euo pipefail

_raw_url="$(git remote get-url origin)"
# Normalize SSH (git@github.com:org/repo.git) → HTTPS, strip trailing .git
REPO_URL="$(echo "$_raw_url" | sed 's|git@github.com:|https://github.com/|; s|\.git$||')"
RUNNER_NAME="${RUNNER_NAME:-platform-runner}"
RUNNER_LABELS="${RUNNER_LABELS:-macos-runner}"
RUNNER_DIR="${RUNNER_DIR:-../.actions-runner}"
RUNNER_VERSION="${RUNNER_VERSION:-2.325.0}"

if [[ -z "${RUNNER_TOKEN:-}" ]]; then
  echo "Error: set RUNNER_TOKEN before running this script." >&2
  exit 1
fi

# ── Install runner binary if not already present ──────────────────────────────
if [[ ! -f "${RUNNER_DIR}/run.sh" ]]; then

  echo "Downloading GitHub Actions runner v${RUNNER_VERSION}..."
  mkdir -p "${RUNNER_DIR}"
  ARCHIVE="actions-runner-osx-arm64-${n}.tar.gz"
  curl -fsSL \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${ARCHIVE}" \
    -o "/tmp/${ARCHIVE}"
  tar -xzf "/tmp/${ARCHIVE}" -C "${RUNNER_DIR}"
  rm "/tmp/${ARCHIVE}"

  cd "${RUNNER_DIR}"

  # ── Configure (reconfigure if already set up) ─────────────────────────────────
  echo "Configuring runner '${RUNNER_NAME}' → ${REPO_URL}"
  ./config.sh \
    --url "${REPO_URL}" \
    --token "${RUNNER_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --unattended \
    --replace

fi

cd "${RUNNER_DIR}"

# ── Start ─────────────────────────────────────────────────────────────────────
echo "Starting runner (press Ctrl+C to stop)..."
./run.sh
