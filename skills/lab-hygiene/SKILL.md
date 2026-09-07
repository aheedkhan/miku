---
name: lab-hygiene
description: >-
  Lab safety and longevity — isolation, disk reclaim, no binaries in git,
  secrets hygiene, VM discipline, backup of notes. Use for cleanup, "is this
  safe to commit," sample handling, or Qubes/analysis-VM practice.
---

# Lab hygiene

## Goal
Keep the lab powerful **and** durable: notes/RAG survive; disks and secrets don't get wrecked.

## Hard rules
- **No live malware binaries in git** — analysis VM paths only; notes reference hashes
- **No secrets in repo** — `.env` local; redact tokens/keys
- **Authorized scope only** for live attacks
- **Warn once** before disk-wipe / force-push main / mass prune — then proceed if confirmed

## Disk
- Prefer targeted reclaim (builder prune, unused caches) — not blind mass deletion unless asked
- Don't delete HERMES_HOME / this repo without explicit ask

## Sample / research handling
| Do | Don't |
|----|-------|
| Hash + note in `workspace/` | Commit PE/APK/ELF samples |
| Detonate in disposable VM | Run unknowns on daily driver |
| Dual loop: build → analyze → detect | Mix author & victim data in one folder carelessly |

## Git hygiene
- Commit only when asked
- Check `git status` for `.env`, keys, cores, `out/`
- Small reviewable commits; no `--no-verify` unless asked

## Qubes direction
See `docs/qubes-deployment.md` — Ollama VM vs Hermes AppVM vs disposable analysis VM. Long-term: binaries never live in the notes VM.

## Session end checklist
- [ ] Notes saved under correct `workspace/` path
- [ ] Remind `hermes workspace index` if new durable knowledge
- [ ] No secrets staged
- [ ] Temp build junk noted or cleaned if user wants
