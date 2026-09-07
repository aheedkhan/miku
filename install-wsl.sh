#!/usr/bin/env bash
# Full bootstrap for a fresh WSL Debian/Ubuntu host.
#
# Installs system packages, Ollama + models used by Miku/Hermes, Python venv,
# optional WhatsApp bridge Node deps, and Android RE helpers when available.
# Does NOT install KVM/qemu/libvirt (not used on WSL for this project).
#
#   ./install-wsl.sh              # everything (apt needs sudo)
#   SKIP_MODELS=1 ./install-wsl.sh # packages + Hermes, skip ollama pull
#   SKIP_ANDROID=1 ./install-wsl.sh # skip jadx / apktool / sdk bits
#
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
cd "$SCRIPT_DIR"

BOLD="$(tput bold 2>/dev/null || true)"
DIM="$(tput dim 2>/dev/null || true)"
RESET="$(tput sgr0 2>/dev/null || true)"

info()  { printf '%s\n' "${BOLD}==>${RESET} $*"; }
note()  { printf '%s\n' "${DIM}    $*${RESET}"; }
warn()  { printf '%s\n' "${BOLD}!!${RESET} $*" >&2; }
die()   { warn "$*"; exit 1; }

# Models from config.example.yaml — keep in sync when you change roles there.
OLLAMA_MODELS=(
  "huihui_ai/qwen3-abliterated-64k:30b"   # models.default
  "qwen3-coder:30b"                      # models.code
  "huihui_ai/gpt-oss-abliterated:20b"     # models.fast
  "nomic-embed-text"                     # models.embed (RAG)
)

# --- (0) Distro / WSL sanity -------------------------------------------------------
if [ ! -f /etc/os-release ]; then
  die "Cannot read /etc/os-release — this script targets Debian/Ubuntu (incl. WSL)."
fi
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}:${ID_LIKE:-}" in
  debian:*|ubuntu:*|*:debian*|*:ubuntu*) ;;
  *) die "Expected Debian/Ubuntu, found ID=${ID:-?} ID_LIKE=${ID_LIKE:-?}" ;;
esac
note "Detected ${PRETTY_NAME:-$ID}"

if grep -qi microsoft /proc/version 2>/dev/null; then
  note "WSL detected"
fi

if [ "$(id -u)" -eq 0 ]; then
  die "Run as a normal user (script will sudo for apt). Do not run as root."
fi

# --- (1) APT packages --------------------------------------------------------------
info "Installing apt packages (sudo)..."
export DEBIAN_FRONTEND=noninteractive

APT_BASE=(
  build-essential
  ca-certificates
  curl
  wget
  git
  jq
  unzip
  zip
  tar
  gnupg
  software-properties-common
  pkg-config
  python3
  python3-pip
  python3-venv
  python3-dev
  ripgrep
  fd-find
  tree
  htop
  tmux
  vim
  nano
  less
  openssh-client
  rsync
  # compile / debug toolchain
  cmake
  ninja-build
  gdb
  lldb
  strace
  binutils
  mingw-w64
)

# Soft-optional: skip cleanly if a distro mirror lacks them
APT_SOFT=(
  ltrace
)

# RAG / research / docs tooling
APT_RESEARCH=(
  pandoc
  poppler-utils
  tesseract-ocr
  graphviz
)

# Android RE helpers available from distro repos (jadx often needs a manual drop-in)
APT_ANDROID=(
  apktool
  adb
  android-sdk-platform-tools-common
)

# Optional but useful for git/GitHub + PDF path (large — soft-fail)
APT_EXTRA=(
  gh
  texlive-latex-recommended
  texlive-fonts-recommended
  lmodern
)

sudo apt-get update -y
# Base first so a missing optional package cannot abort the whole bootstrap under set -e
sudo apt-get install -y "${APT_BASE[@]}"
sudo apt-get install -y "${APT_RESEARCH[@]}" || warn "Some research apt packages failed — continue; install later if needed."
for pkg in "${APT_SOFT[@]}" "${APT_EXTRA[@]}"; do
  sudo apt-get install -y "$pkg" || warn "Optional apt package skipped: $pkg"
done

if [ "${SKIP_ANDROID:-0}" != "1" ]; then
  info "Installing Android RE apt packages..."
  sudo apt-get install -y "${APT_ANDROID[@]}" || warn "Android apt packages incomplete — install missing tools later (see docs/android-workflow.md)."
fi

# fd-find ships as `fdfind` on Debian/Ubuntu — symlink for muscle memory
if command -v fdfind &>/dev/null && ! command -v fd &>/dev/null; then
  sudo ln -sf "$(command -v fdfind)" /usr/local/bin/fd
  note "Linked fdfind -> /usr/local/bin/fd"
fi

# --- (2) Node.js (WhatsApp bridge) -------------------------------------------------
info "Ensuring Node.js 20+ for whatsapp-bridge..."
need_node=0
if ! command -v node &>/dev/null; then
  need_node=1
else
  NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
  if [ "${NODE_MAJOR:-0}" -lt 20 ]; then
    need_node=1
  fi
fi
if [ "$need_node" -eq 1 ]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
note "node $(node -v) / npm $(npm -v)"

# --- (3) Ollama --------------------------------------------------------------------
info "Installing / verifying Ollama..."
if ! command -v ollama &>/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
else
  note "ollama already on PATH: $(command -v ollama)"
fi

# WSL: start server if nothing answers on 11434
if ! curl -sf --max-time 2 http://127.0.0.1:11434/api/version &>/dev/null; then
  info "Starting Ollama server in background..."
  nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  for _ in $(seq 1 30); do
    if curl -sf --max-time 1 http://127.0.0.1:11434/api/version &>/dev/null; then
      break
    fi
    sleep 1
  done
fi

if curl -sf --max-time 2 http://127.0.0.1:11434/api/version &>/dev/null; then
  note "Ollama reachable at 127.0.0.1:11434"
else
  warn "Ollama still not reachable — start it with: ollama serve"
fi

# --- (4) Pull models ---------------------------------------------------------------
if [ "${SKIP_MODELS:-0}" = "1" ]; then
  warn "SKIP_MODELS=1 — not pulling Ollama models."
else
  info "Pulling Ollama models (large downloads — 20B/30B need disk + RAM)..."
  for model in "${OLLAMA_MODELS[@]}"; do
    info "ollama pull ${model}"
    ollama pull "$model" || warn "Failed to pull ${model} — pull manually later."
  done
  note "Installed models:"
  ollama list || true
fi

# --- (5) jadx (GitHub release — often missing/outdated in apt) ---------------------
if [ "${SKIP_ANDROID:-0}" != "1" ]; then
  if ! command -v jadx &>/dev/null; then
    info "Installing jadx into ~/.local/bin..."
    mkdir -p "$HOME/.local/bin" "$HOME/.local/share/jadx"
    JADX_VER="1.5.1"
    TMP="$(mktemp -d)"
    if curl -fsSL -o "$TMP/jadx.zip" \
      "https://github.com/skylot/jadx/releases/download/v${JADX_VER}/jadx-${JADX_VER}.zip"; then
      unzip -qo "$TMP/jadx.zip" -d "$HOME/.local/share/jadx"
      ln -sfn "$HOME/.local/share/jadx/bin/jadx" "$HOME/.local/bin/jadx"
      ln -sfn "$HOME/.local/share/jadx/bin/jadx-gui" "$HOME/.local/bin/jadx-gui"
      note "jadx ${JADX_VER} -> ~/.local/bin/jadx"
    else
      warn "Could not download jadx — install from https://github.com/skylot/jadx/releases"
    fi
    rm -rf "$TMP"
  else
    note "jadx already present: $(command -v jadx)"
  fi
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *)
      note "Add ~/.local/bin to PATH (e.g. in ~/.bashrc): export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac
fi

# --- (6) Hermes / Miku Python stack ------------------------------------------------
info "Running project install.sh (venv + hermes + config)..."
bash "$SCRIPT_DIR/install.sh"

info "Installing optional Android dynamic-analysis Python tools into .venv..."
"$SCRIPT_DIR/.venv/bin/pip" install -q frida-tools objection || \
  warn "frida-tools/objection pip install failed — skip if you do not need dynamic Android work."

# --- (7) WhatsApp bridge -----------------------------------------------------------
if [ -f "$SCRIPT_DIR/whatsapp-bridge/package.json" ]; then
  info "npm install for whatsapp-bridge..."
  (cd "$SCRIPT_DIR/whatsapp-bridge" && npm install) || \
    warn "whatsapp-bridge npm install failed — optional; skip if unused."
fi

# --- (8) Summary -------------------------------------------------------------------
echo
info "WSL bootstrap done."
note "Activate:  source .venv/bin/activate && miku"
note "Or:        ./.venv/bin/miku"
note "Config:    ~/.config/hermes/config.yaml"
note "Models:    ollama list"
note "RAG:       drop notes in workspace/; use knowledge-rag / research-pipeline skills"
note "No KVM:    qemu/libvirt intentionally not installed (WSL)."
echo
warn "Disk tip: 30B models are multi-GB each. Use SKIP_MODELS=1 and pull only what you need."
