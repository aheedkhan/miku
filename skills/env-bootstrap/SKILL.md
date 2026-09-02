---
name: env-bootstrap
description: >-
  Bootstrap and repair the Miku/Hermes environment — install.sh, Ollama,
  .env, SearXNG, Qubes split, model pulls. Use on new machines, broken
  endpoints, "miku won't start," or migrating to Qubes.
---

# Env bootstrap

## Goal
A working `miku` shell talking to Ollama (local or Qubes VM) with this `HERMES_HOME`.

## Happy path
```bash
cd ~/Documents/agent_dev   # or clone path
./install.sh
# optional remote Ollama:
# ./install.sh http://10.137.0.XX:11434/v1
miku
```

Models: `scripts/setup-ollama.sh` — default freedom model + `qwen3-coder:30b` for heavy code.

## Check order when broken
1. `command -v hermes` / `command -v miku`
2. `curl` Ollama: `$OLLAMA_BASE_URL` → `/models` or native `/api/tags`
3. `hermes-home/.env` vs `config.yaml` `model.base_url` agree
4. Disk space for models + (if FYP) AOSP tree
5. Web: `SEARXNG_URL` optional; keyless fallbacks exist in config

## Qubes
Follow `qubes/README.md`:
- Ollama VM listens `0.0.0.0:11434`
- Firewall: Hermes AppVM → Ollama :11434 only
- Analysis VM separate for samples

## After bootstrap
- `hermes workspace index` once workspace has notes
- Confirm personality/skills load from this `HERMES_HOME`
- Don't commit `.env`

## Never
- Point production secrets at chat logs
- Expose Ollama to the real internet unless the user explicitly wants that
