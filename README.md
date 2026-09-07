# Hermes (Miku)

Miku is a local, portable, CLI-only agentic assistant that runs entirely against your own
[Ollama](https://ollama.com) server — no cloud API, no telemetry, no account. She's built as a
coding partner and teacher for a developer/security-researcher workflow: general dev help,
Android reverse engineering and malware analysis, CVE research, and full git/GitHub workflows,
all from one terminal agent that never leaves your machine. Point her at whatever project
directory you're standing in and she reads, edits, greps, and runs shell/git commands there —
same model as Claude Code's own tools, just wired to a model you host yourself.

## Quickstart

**Fresh WSL Debian/Ubuntu** (apt packages, Ollama, models, Hermes, RAG/research tools):

```bash
git clone <this-repo-url> miku && cd miku
./install-wsl.sh
source .venv/bin/activate && miku
```

`SKIP_MODELS=1` skips the large `ollama pull`s; `SKIP_ANDROID=1` skips Android RE helpers.

**Python-only** (system packages + Ollama already present):

```bash
./install.sh
source .venv/bin/activate && hermes
```

`install.sh` creates a `.venv`, installs dependencies plus the `hermes`/`miku` console
scripts, drops a first-run `config.yaml` into `~/.config/hermes/`, and tells you whether it
found a local Ollama to talk to. Re-run it any time you pull new dependencies — it's idempotent
and never overwrites a config you've already edited. KVM/qemu is intentionally not part of
this install path (WSL-friendly).

## What's included

- **RAG over your own knowledge base** — drop malware-dev notes, CVE writeups, and converted
  PDFs into `knowledge/`; Miku chunks, embeds (`nomic-embed-text`), and retrieves them alongside
  live CVE data and MalwareBazaar sample intel, all in one local vector store.
- **Key-free web search** — DuckDuckGo search out of the box via `ddgs`, no API key required
  (SearXNG also supported if you run your own instance).
- **Full git + GitHub workflow** — status/diff/commit/branch locally via git, plus PRs and
  issues via the `gh` CLI when it's installed (degrades gracefully to a clear "install gh" or
  "set GITHUB_TOKEN" message otherwise).
- **Android RE / malware toolchain wrapper** — apktool, jadx, zipalign, apksigner, adb, and
  frida/objection dynamic instrumentation, orchestrated as one tool. See
  [`docs/android-workflow.md`](docs/android-workflow.md).
- **Sub-agent spawning** — the same agent loop spins up scoped, restricted-toolset sub-agents
  for focused sub-tasks; only their final answer re-enters your context, not their internal
  turns.
- **Daily CVE + project refresh** — a background job that diffs and re-embeds new Android CVEs,
  cross-platform MalwareBazaar sample intel (Android/Windows/Linux), and any external project
  repos you're tracking (see `projects:` below), so retrieval stays current without manual
  re-indexing. Runs from inside the REPL (`/refresh-cve`) or standalone via cron/systemd
  (`python -m hermes.rag.daily_refresh` — see [`docs/android-workflow.md`](docs/android-workflow.md)).
- **Windows API / Linux kernel / MITRE ATT&CK reference corpora** — a one-time opt-in fetch
  (`/fetch-references` in the REPL, or `python -m hermes.rag.fetch_references`) pulls Microsoft's
  own Win32/WDK API docs, the Linux kernel's `Documentation/` tree, and MITRE ATT&CK's technique
  data (converted to clean per-technique notes) into RAG — real OS-internals and cross-platform
  malware-technique knowledge she can draw on for both analysis and writing new
  Windows/Linux/Android malware, kept current via the daily refresh above. Not fetched
  automatically by `install.sh` (some of this is a real, sizeable download) — run it once
  yourself when you're ready.

## Configuration

Everything lives in `~/.config/hermes/config.yaml` (copied there on first install from
[`config.example.yaml`](config.example.yaml) — edit it directly, it's yours). The main things
you'll want to touch:

- **Model choice** — the `models:` map assigns an Ollama model + context window per role
  (`default`, `code`, `fast`, `embed`). Swap in whatever you've pulled with `ollama pull`.
- **`projects:`** — a list of other repos you want Miku tracking alongside `knowledge/`, e.g. a
  course project or FYP you're building together. Daily-refreshed and re-embedded the same way
  as CVE deltas.
- **`ollama_host`** — override for a Qubes-style setup where Ollama runs in a separate VM; see
  [`docs/qubes-deployment.md`](docs/qubes-deployment.md).

Secrets (`GITHUB_TOKEN`, `NVD_API_KEY`, `MALWAREBAZAAR_AUTH_KEY`) go in `.env` in the repo root
(copied from `.env.example` on first install) — every one of them is optional, and tools that
need one tell you exactly where to get it if it's missing.

## Make her yours

Miku's persona/tone lives in a plain markdown file at
[`hermes/persona/miku.md`](hermes/persona/miku.md) — edit it to change how she talks, what she
prioritizes, or her name entirely.

## Qubes / multi-VM

Running Ollama in its own qube and Hermes in a client VM? See
[`docs/qubes-deployment.md`](docs/qubes-deployment.md) for the full network-isolation setup
(binding Ollama non-locally, `provides_network` chaining, optional nftables lockdown, and
realistic CPU-only performance expectations).
