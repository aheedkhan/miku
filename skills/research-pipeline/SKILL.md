---
name: research-pipeline
description: >-
  End-to-end research loop — browse, synthesize into RAG, optional harness,
  report, PDF. Use for "research X properly," multi-hour investigations, or
  when the user wants a durable deliverable not a one-off chat answer.
---

# Research pipeline

## Goal
One coherent loop so research compounds:

**browse → RAG notes → (optional) harness → report → PDF**

## When to use
- Multi-source investigations (CVE, family, API, design spike)
- "Do it properly / long-term / so we don't lose this"
- Teaching a topic into the knowledge base

## Pipeline
1. **Scope** — question, success criteria, time box
2. **RAG first** — `knowledge-rag` search; skip duplicate browsing
3. **Browse** — `browsing` (primary sources only, cite dates)
4. **Synthesize** — family/CVE/internals card in the right `workspace/` folder
5. **Verify (optional)** — `test-harness` / domain lab skill on owned targets
6. **Report** — `report-generation`
7. **PDF** — `pdf-creation` if they want a shareable artifact
8. **Index** — `hermes workspace index`
9. **Decide** — if a choice was locked, `adr-decisions`

## Parallelism
- Leaf A: search/extract
- Leaf B: draft card / harness
- Parent: honesty pass, save paths, next actions

## Quality bar
- Citations on non-obvious claims
- `[UNVERIFIED]` until harness/evidence exists
- No invented CVE IDs
- Wifu tone never replaces the artifact quality
