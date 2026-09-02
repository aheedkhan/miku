# workspace/

Long-term memory for Miku — markdown notes, CVE cards, malware family reports, digests,
and decisions. Everything here gets embedded into the local RAG vector store so future
sessions can retrieve it via `rag_query` or `hermes workspace search`.

## Layout

| Path | Content |
|------|---------|
| `malware-reports/` | Family cards + sources |
| `malware-analysis/` | Triage case notes |
| `cves/` + `cves/tests/` | CVE cards + harness designs |
| `os-internals/linux/` | Linux syscall / kernel notes |
| `os-internals/windows/` | Win32 API cards |
| `android/` | Platform + Android malware notes |
| `digests/` | Daily currency digests |
| `reports/` | Formal writeups |
| `decisions/` | ADRs |
| `pentest/` | Authorized-scope templates |

## Commands

```bash
hermes workspace index      # ingest new/changed files now
hermes workspace status     # chunk counts + last refresh
hermes workspace search "query"
hermes workspace refresh    # CVE + malware + workspace + projects
```

While Miku is running, RAG auto-refreshes every 5 hours (see `rag_refresh_interval_hours`
in config). Mid-chat, the agent can also call `rag_remember` to save durable facts.

This folder is gitignored (except this README) — your research stays private.
