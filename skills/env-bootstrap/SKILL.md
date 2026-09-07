---
name: env-bootstrap
description: >-
  Bootstrap and repair the Miku/Hermes environment — install-wsl.sh, Ollama, and
  Windows 11 lab VM A→Z setup. Use on new machines, "miku won't start," or
  "setup Windows lab / Hyper-V from scratch."
---

# Env bootstrap

## Goal
A working `miku` shell talking to Ollama (local or Qubes VM) with this `HERMES_HOME`.

## Windows 11 lab VM (A→Z)
When the user needs a **full Windows lab from zero** (Hyper-V/VMware/VBox, ISO, snapshot,
firewall, copy `.exe`, Defender tools):

1. Spoon-feed from **`docs/windows11-lab-setup-atoz.md`** (one letter A→T per turn)
2. Index card: `workspace/references/windows11-lab-setup.md`
3. Skills: `teaching-lab`, `wsl-windows-exe`

User trigger phrases: “setup Windows lab”, “A to Z”, “spoon-feed Windows”, “Hyper-V from scratch”.

## Happy path (new WSL Debian/Ubuntu)
```bash
cd ~/Documents/miku   # or clone path
./install-wsl.sh      # apt + ollama + models + venv + RAG/research tools
source .venv/bin/activate && miku
```

Flags:
- `SKIP_MODELS=1` — skip multi-GB `ollama pull` (pull manually later)
- `SKIP_ANDROID=1` — skip apktool/adb/jadx bits

## Happy path (Python-only / already have system packages)
```bash
./install.sh
source .venv/bin/activate && miku
```

Models pulled by `install-wsl.sh` match `config.example.yaml`:
default / code / fast / embed (`nomic-embed-text` for RAG).

## Check order when broken
1. `command -v hermes` / `command -v miku`
2. `curl` Ollama: `http://127.0.0.1:11434/api/tags` (or `$OLLAMA_HOST`)
3. `.env` vs `~/.config/hermes/config.yaml` `ollama_host` agree
4. Disk space for models
5. Web: SearXNG optional; keyless `ddgs` is default

## Qubes
Follow `docs/qubes-deployment.md`:
- Ollama VM listens `0.0.0.0:11434`
- Firewall: Hermes AppVM → Ollama :11434 only
- Analysis VM separate for samples

## After bootstrap
- Index workspace notes for RAG when ready
- Confirm personality/skills load from this repo
- Don't commit `.env`

## Never
- Point production secrets at chat logs
- Expose Ollama to the real internet unless the user explicitly wants that
- Install KVM/qemu/libvirt for this project on WSL (removed from repo)
