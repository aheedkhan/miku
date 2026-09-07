---
name: report-generation
description: >-
  Draft structured technical reports (lab findings, CVE harness results, malware
  triage, pentest authorized-scope writeups). Use when the user asks for a
  report, writeup, findings doc, executive summary, or markdown deliverable.
---

# Report generation

## Goal
Produce a clear, citable markdown report the user can keep in RAG, share, or hand to `pdf-creation`.

## When to use
- "Write a report / writeup / findings doc"
- Lab triage, CVE verification, malware analysis, authorized pentest notes
- Anything that needs exec summary + evidence + next steps

## Workflow
1. **Clarify type** (if unclear): `lab` | `cve` | `malware` | `pentest` | `general`
2. **Gather** — RAG (`hermes workspace search`), notes under `workspace/`, tool output, citations
3. **Draft** markdown using the matching template under `workspace/reports/templates/` if present
4. **Save** to `workspace/reports/<type>/<YYYY-MM-DD>-<slug>.md` (create dirs as needed)
5. **Honesty** — mark `[UNVERIFIED]` / unknowns; never invent CVE IDs or IOCs
6. **Offer PDF** — if they want a PDF, hand off to `pdf-creation`

## House rules
- Lead with **Executive summary** (≤5 bullets or one short paragraph)
- Every claim that isn't from local verified work needs a **source** (URL, file:line, hash, command)
- Separate **Findings** from **Recommendations**
- No secrets, live malware binaries, or third-party attack artifacts in git
- Authorized-scope only for pentest-style reports

## Default outline (general / lab)
```markdown
# <Title>
- Date:
- Author: Miku (for <user>)
- Scope / target:
- Classification: lab | internal | draft

## Executive summary
-

## Background / objective
-

## Method
-

## Findings
### F-01 —
- Evidence:
- Impact:
- Confidence: high | medium | low | [UNVERIFIED]

## Recommendations
1.

## Appendix
- Commands / hashes / links
- Open questions
```

## Type-specific notes
| Type | Extra sections |
|------|----------------|
| `cve` | CVE id, affected component, patch refs, harness path under `labs/` or `workspace/cves/` |
| `malware` | Family/hash, ATT&CK, detection ideas; link family card if any |
| `pentest` | Scope, rules of engagement, severity ratings; no client secrets in repo |

## Subagents
- Leaf A: collect evidence / citations
- Leaf B: draft findings body
- Parent: merge, honesty pass, save path

## Never
- Invent CVEs, fake "verified" results, or unsourced IOCs
- Commit passwords, API keys, or malware samples
