---
name: research-pipeline
description: >-
  End-to-end research loop — RAG, browse, GitHub prior art, synthesize, optional
  harness, report, PDF. Use for "research X properly" or durable investigations.
---

# Research pipeline

## Goal
**RAG → browse/GitHub → notes → (harness) → report → index** so research compounds.

## When to use
- Multi-source investigations (CVE, family, API, implant design)
- "Do it properly / so we don't lose this"
- Teaching a topic into the knowledge base

## Pipeline
1. **Scope** — question, success criteria, time box
2. **RAG first** — `rag_query` / `knowledge-rag`; skip duplicate work
3. **Browse** — `browsing` (`web_search` → `web_fetch`)
4. **GitHub prior art** — `github-explore` when implementation matters
5. **CVE depth** — `cve_lookup` / `workspace cves` if vuln-shaped
6. **Synthesize** — card in the right `workspace/` folder; `rag_remember` key facts
7. **Verify (optional)** — `test-harness` / `cve-malware-test` / domain skill on owned targets
8. **Report** — `report-generation` (± `pdf-creation`)
9. **Index** — `hermes workspace index`
10. **Decide** — `adr-decisions` if a design locked

## Parallelism
- Leaf A: search/fetch
- Leaf B: GitHub file reads / draft card
- Leaf C: harness scaffold
- Parent: honesty pass, save paths, next actions

## Quality bar
- Citations on non-obvious claims
- `[UNVERIFIED]` until harness/evidence exists
- No invented CVE IDs
- Prefer mechanism diagrams + file:line over vibes
