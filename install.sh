#!/usr/bin/env bash
# Hermes (Miku) installer.
#
# Sets up a local virtualenv, installs dependencies plus the `hermes` console script,
# and lays down a first-run config.yaml / .env from the tracked examples without ever
# clobbering ones that already exist. Safe to re-run any time you pull new deps.
#
#   ./install.sh
#   source .venv/bin/activate && hermes
#
set -euo pipefail

# Resolve the repo root from this script's own location so it works no matter the cwd
# it's invoked from.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

BOLD="$(tput bold 2>/dev/null || true)"
DIM="$(tput dim 2>/dev/null || true)"
RESET="$(tput sgr0 2>/dev/null || true)"

info()  { printf '%s\n' "${BOLD}==>${RESET} $*"; }
note()  { printf '%s\n' "${DIM}    $*${RESET}"; }
warn()  { printf '%s\n' "${BOLD}!!${RESET} $*" >&2; }

# --- (a) Python version check -------------------------------------------------------
info "Checking Python version..."
if ! command -v python3 &>/dev/null; then
    warn "python3 not found on PATH. Install Python 3.11 or newer and re-run this script."
    exit 1
fi

PY_VERSION="$(python3 --version 2>&1 | awk '{print $2}')"
PY_MAJOR="${PY_VERSION%%.*}"
PY_REST="${PY_VERSION#*.}"
PY_MINOR="${PY_REST%%.*}"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    warn "Hermes needs Python 3.11+, found ${PY_VERSION} (python3 -> $(command -v python3))."
    warn "Install a newer Python 3 and re-run, or point python3 at one via PATH/pyenv/update-alternatives."
    exit 1
fi
note "python3 ${PY_VERSION} OK"

# --- (b) Virtualenv + dependencies ---------------------------------------------------
VENV_DIR="$SCRIPT_DIR/.venv"

if command -v uv &>/dev/null; then
    info "uv found — using it for a faster venv + install."
    if [ -x "$VENV_DIR/bin/python3" ]; then
        note ".venv already exists with a python3 binary — skipping venv creation."
    else
        uv venv "$VENV_DIR"
    fi
    uv pip install --python "$VENV_DIR/bin/python3" -r requirements.txt
else
    info "uv not found — falling back to python3 -m venv + pip."
    note "(install uv from https://docs.astral.sh/uv/ for a noticeably faster setup next time)"
    if [ -x "$VENV_DIR/bin/python3" ]; then
        note ".venv already exists with a python3 binary — skipping venv creation."
    else
        python3 -m venv "$VENV_DIR"
    fi
    "$VENV_DIR/bin/pip" install -U pip
    "$VENV_DIR/bin/pip" install -r requirements.txt
fi

# --- (c) Editable-install Hermes itself so the `hermes` console script exists --------
info "Installing Hermes itself (editable) so the 'hermes' command is available..."
"$VENV_DIR/bin/pip" install -e .

# --- (d) Optional: gh CLI for full GitHub PR/issue support ---------------------------
if ! command -v gh &>/dev/null; then
    warn "gh not found — for full GitHub PR/issue support, install it: sudo dnf install gh (Fedora) / see https://cli.github.com"
else
    note "gh CLI found ($(command -v gh)) — GitHub PR/issue tools fully available."
fi

# --- (e) First-run config.yaml -------------------------------------------------------
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
HERMES_CONFIG_DIR="$CONFIG_HOME/hermes"
mkdir -p "$HERMES_CONFIG_DIR"

if [ -f "$HERMES_CONFIG_DIR/config.yaml" ]; then
    note "Existing config found at $HERMES_CONFIG_DIR/config.yaml — leaving it untouched."
else
    cp config.example.yaml "$HERMES_CONFIG_DIR/config.yaml"
    info "Wrote first-run config to $HERMES_CONFIG_DIR/config.yaml (edit freely — see README)."
fi

# --- (f) First-run .env ---------------------------------------------------------------
if [ -f "$SCRIPT_DIR/.env" ]; then
    note "Existing .env found at $SCRIPT_DIR/.env — leaving it untouched."
else
    cp .env.example .env
    info "Wrote first-run .env to $SCRIPT_DIR/.env (all keys optional — edit as needed)."
fi

# --- (g) Ollama reachability check ----------------------------------------------------
info "Checking for a local Ollama server..."
if curl -sf --max-time 2 http://127.0.0.1:11434/api/version &>/dev/null; then
    note "Local Ollama detected on 127.0.0.1:11434 — you're good to go."
else
    warn "No local Ollama detected on 127.0.0.1:11434."
    note "On a normal machine: install/start Ollama (https://ollama.com) and pull your models."
    note "On a Qubes client VM this is EXPECTED to fail — Ollama runs in a separate VM."
    note "Set OLLAMA_HOST in .env to that VM's address instead. See docs/qubes-deployment.md."
fi

# --- (h) Done --------------------------------------------------------------------------
echo
info "Done."
note "Run:   source .venv/bin/activate && hermes"
note "  or:  ./.venv/bin/hermes          (without activating)"
