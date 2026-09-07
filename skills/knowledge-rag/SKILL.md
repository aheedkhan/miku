---
name: knowledge-rag
description: >-
  Long-term memory via Hermes workspace RAG — ingest notes, index, search,
  family cards, digests, reports. Use when saving knowledge, "remember this,"
  searching prior work, or after browsing/intel sessions.
---

# Knowledge / RAG

## Goal
Turn today's work into next month's retrieval — markdown in `workspace/`, indexed by Hermes.

## Layout (put things in the right drawer)
| Path | Content |
|------|---------|
| `malware-reports/` | Family cards + sources |
| `malware-analysis/` | Triage case notes |
| `cves/` + `cves/tests/` | CVE cards + harness designs |
| `os-internals/{linux,windows}/` | API / syscall cards |
| `android/` | Platform + Android malware notes |
| `digests/` | Daily currency |
| `reports/` | Formal writeups + `pdf/` |
| `decisions/` | ADRs (see `adr-decisions`) |
| `pentest/` | Authorized-scope templates only |

## Commands
```bash
hermes workspace index          # workspace notes + skills playbooks
hermes workspace cves [days]    # pull open CVEs (android/windows/linux) + KEV + related
hermes workspace status
hermes workspace search "CVE-2024 buffer overflow"
hermes workspace refresh        # CVEs + malware intel + re-index notes
```

Relevance floor (~0.58 cosine) drops junk matches. Re-index after editing notes — unchanged files are skipped; changed files replace their chunks.

CVE cards in RAG include **develop/harness hints** (CWE → trigger style). See `workspace/cves/how-to-develop-harness.md`.

## Reference links (start here)
- **Master index:** `workspace/references/curated-links.md` — CVE databases, malware dev/analysis,
  Windows 11 internals, Defender/AMSI/ETW/LOLBAS, open-source offensive research repos (lab only)
- **Win11 + Defender lab:** `workspace/os-internals/windows/defender-win11-lab.md`

## Workflow
1. **Write** durable notes (mechanism + citations), not chat paste dumps
2. **Place** under the correct folder (templates exist — copy them)
3. **Index** after meaningful adds
4. **Search RAG first** next session before re-browsing
5. Prefer primary sources in citations (URL, file:line, hash)

## Quality bar
- One topic per file; clear `# Title`
- Date + sources at top or bottom
- Mark `[UNVERIFIED]` when not proven
- Short excerpts + links — don't dump whole copyrighted pages

## Hand-offs
- Web gather → `browsing` then ingest here
- Formal doc → `report-generation` (± `pdf-creation`)
- MalwareBazaar → `malware-intel` family card format
