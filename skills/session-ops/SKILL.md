---
name: session-ops
description: >-
  Session start/end rituals — load context, pick skill, write durable memory,
  index RAG, suggest next actions. Use at session open/close, "what were we
  doing," or when switching FYP vs research modes.
---

# Session ops

## Goal
Every session leaves the lab smarter than it found it.

## Session start
1. Skim `memories/MEMORY.md` + `memories/USER.md`
2. If FYP / `/home/mania/Documents/FYP` → run **`fyp-progress`** gate
3. Else ask (or infer): build | research | report | browse | teach
4. RAG search before redoing old work: `hermes workspace search "…"`
5. State **today's 1–3 outcomes** in plain bullets

## During
- Prefer skills over improvising process
- Spawn subagents for parallel fetch vs implement vs review
- Dangerous footguns → warn once (`lab-hygiene`)

## Session end
1. Update durable notes (`workspace/…`) if anything worth remembering
2. Optional: short MEMORY.md bullet (preferences, blockers, decisions)
3. Remind `hermes workspace index` after new files
4. Offer next actions (not a lecture)
5. If a design was locked → draft/update ADR (`adr-decisions`)

## Mode switch cheat sheet
| User signal | Lean on |
|-------------|---------|
| FYP / ROM / Cuttlefish | `fyp-*` |
| Build (non-AOSP) | `lab-build` |
| Broken / crash | `debug-triage` |
| Web / URL | `browsing` |
| Writeup / PDF | `report-generation` → `pdf-creation` |
| Remember / search notes | `knowledge-rag` |
| wifu / hi wifu | Voice only (SOUL) — capabilities unchanged |
