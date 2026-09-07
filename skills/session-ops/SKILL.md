---
name: session-ops
description: >-
  Session start/end rituals — load context, pick skill, RAG, GitHub/web when
  needed, write durable memory. Use at open/close or "what were we doing."
---

# Session ops

## Goal
Every session leaves the lab smarter than it found it.

## Session start
1. Skim memories if present
2. **`rag_query`** what you think you remember — don't trust vibes alone
3. Infer mode: build | research | CVE | RAT | Android RE | report
4. **`use_skill`** the matching playbook early
5. State **today's 1–3 outcomes**

## During
- Prefer skills + tools over improvising process
- Stuck on an API/design? `github-explore` or `browsing` before guessing
- Spawn subagents for parallel fetch vs implement vs review
- Footguns → warn once (`lab-hygiene`)

## Session end
1. Update `workspace/…` notes worth keeping
2. `rag_remember` durable facts/decisions
3. Remind `hermes workspace index` (and `workspace cves` if CVE day)
4. Offer next actions
5. Design locked → `adr-decisions`

## Mode cheat sheet
| Signal | Lean on |
|--------|---------|
| Research / "dig in" | `research-pipeline` |
| GitHub / prior art | `github-explore` |
| Web / URL | `browsing` |
| CVE | `cve-research` → `cve-malware-test` |
| Setup Win11 lab from zero | `env-bootstrap` + spoon-feed `docs/windows11-lab-setup-atoz.md` |
| TTPs / ATT&CK / techniques | `attack-ttps` → `malware-authoring` |
| Win11 RAT | `windows-rat-dev` |
| Android malware/RE | `android-malware-*` |
| Build / compile | `lab-build` |
| WSL `.exe` / PE | `wsl-windows-exe` |
| Until it works / Defender lab | `lab-iterate` |
| Test fail / need harness | `test-harness` |
| Crash / hang / step | `debugger` → `debug-triage` |
| Writeup | `report-generation` |
| Remember | `knowledge-rag` |
| Spoon-feed / teach | `teaching-lab` |
