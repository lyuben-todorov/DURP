#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu 22.04+/24.04 box for the Cargo pipeline.
#
# Idempotent — safe to rerun. Assumes:
#   - docker + docker-compose-v2 (or docker.io) already installed
#   - user already in the `docker` group (rerun shell after addgroup)
#   - sudo access for one apt-get install
#   - a GitHub PAT you can paste when prompted
#
# After this, deploy/smoke.sh verifies the install end-to-end.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/lyuben-todorov/dep-updates-rp.git}"
REPO_DIR="${REPO_DIR:-$HOME/rp2026}"
BUILDX_NAME="${BUILDX_NAME:-rp2026}"

log() { printf '\033[36m[bootstrap]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[bootstrap] %s\033[0m\n' "$*" >&2; exit 1; }

# ---- 1. prereqs -------------------------------------------------------------

log "checking prereqs"
command -v docker  >/dev/null || die "docker not installed"
command -v python3 >/dev/null || die "python3 not installed"
command -v git     >/dev/null || die "git not installed"

docker info >/dev/null 2>&1 \
  || die "can't talk to the docker daemon — are you in the docker group? (id -nG; newgrp docker)"

PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
[ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ] \
  || die "python3 >= 3.11 required (got $PY_MAJOR.$PY_MINOR)"

# docker buildx — install if missing. On Ubuntu's docker.io the package is
# `docker-buildx`, not `docker-buildx-plugin` (that's docker-ce's name).
if ! docker buildx version >/dev/null 2>&1; then
  log "installing docker-buildx + python3-venv (needs sudo)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-buildx python3-venv python3-pip
  docker buildx version >/dev/null 2>&1 \
    || die "buildx install didn't take effect — rerun the script"
fi

# buildx builder — docker-container driver so `rewrite-timestamp=true` works
if ! docker buildx inspect "$BUILDX_NAME" >/dev/null 2>&1; then
  log "creating buildx builder '$BUILDX_NAME'"
  docker buildx create --use --name "$BUILDX_NAME" --bootstrap >/dev/null
else
  log "buildx builder '$BUILDX_NAME' exists"
fi
docker buildx use "$BUILDX_NAME" >/dev/null

# ---- 2. GitHub host key -----------------------------------------------------

if ! ssh-keygen -F github.com >/dev/null 2>&1; then
  log "adding github.com to ~/.ssh/known_hosts"
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  ssh-keyscan -t ed25519,rsa github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null
fi

# ---- 3. repo ----------------------------------------------------------------

if [ -d "$REPO_DIR/.git" ]; then
  log "repo already at $REPO_DIR — pulling"
  git -C "$REPO_DIR" pull --quiet
  git -C "$REPO_DIR" submodule sync --recursive >/dev/null
  git -C "$REPO_DIR" submodule update --init --recursive
else
  log "cloning $REPO_URL → $REPO_DIR"
  git clone --recurse-submodules "$REPO_URL" "$REPO_DIR"
fi

# ---- 4. venv + install ------------------------------------------------------

cd "$REPO_DIR"
if [ ! -d .venv ]; then
  log "creating .venv"
  python3 -m venv .venv
fi

log "installing bump_ext (editable)"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e '.[cargo]'
.venv/bin/python3 -c "from bump_ext import PipelineDB, SCHEMA_VERSION; print(f'bump_ext {SCHEMA_VERSION} + PipelineDB import ok')"

# ---- 5. GitHub token --------------------------------------------------------

if [ -f "$REPO_DIR/.env" ] && grep -q '^GITHUB_TOKEN=' "$REPO_DIR/.env"; then
  log ".env exists with GITHUB_TOKEN — skipping prompt"
else
  log "paste a GitHub PAT (scope: public_repo) — input hidden"
  printf 'GITHUB_TOKEN: '
  read -rs TOKEN
  echo
  [ -n "$TOKEN" ] || die "empty token"
  umask 077
  printf 'GITHUB_TOKEN=%s\n' "$TOKEN" > "$REPO_DIR/.env"
  chmod 600 "$REPO_DIR/.env"
fi

# verify the token works
# shellcheck disable=SC1091
set -a; . "$REPO_DIR/.env"; set +a
if curl -sf -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/rate_limit >/dev/null; then
  log "GitHub token verified"
else
  die "GitHub token appears invalid"
fi

# ---- 6. rebuild the SQLite index --------------------------------------------

log "building pipeline.sqlite index"
.venv/bin/python3 scripts/rebuild_index.py
.venv/bin/python3 scripts/verify_index.py

# ---- done -------------------------------------------------------------------

cat <<EOF

  bootstrap complete.

  next steps:
    cd $REPO_DIR
    set -a && . .env && set +a           # load GITHUB_TOKEN in each new shell
    ./deploy/smoke.sh                    # end-to-end verify (~10 min, builds a fat image)

  or to run a batch:
    .venv/bin/python3 -m pipelines.cargo.cargo_drive --help

EOF
