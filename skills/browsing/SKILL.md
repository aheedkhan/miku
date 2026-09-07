---
name: browsing
description: >-
  Web research via web_search + web_fetch (and GitHub explore when the answer
  is in a repo). Use to search, open URLs, fetch advisories/docs, or dig online.
---

# Browsing (search → fetch → cite)

## Goal
Primary sources fast, extracted cleanly, cited, optionally saved to RAG.

## Tools
| Tool | Role |
|------|------|
| `web_search` | DuckDuckGo / SearXNG — titles, URLs, snippets |
| `web_fetch` | Pull URL → readable text (HTML stripped) |
| `github` explore | Prefer for repo code (skill `github-explore`) |
| `rag_query` | Check local notes before spending search budget |

## Workflow
1. **RAG first** — maybe we already know
2. **Query design** — specific terms + year/CVE/version
3. **`web_search`** — shortlist 1–5 primary URLs (NVD, vendor, MSDN, kernel.org, android.googlesource, GitHub)
4. **`web_fetch`** those URLs (not 20)
5. If hit is a repo → switch to `github` `contents` / `file_get`
6. **Synthesize** — bullets + citations (URL + date)
7. **Persist** — `workspace/` + remind index / `rag_remember`

## Query tips
| Need | Pattern |
|------|---------|
| CVE | `CVE-YYYY-NNNN NVD` / vendor advisory |
| Windows API | name + `site:learn.microsoft.com` |
| Android | `site:android.googlesource.com` / bulletin |
| Prior art | then `github` `search_repos` / `code_search` |

## Parallelism
- Leaf A: search + shortlist
- Leaf B: fetch top pages / GitHub files
- Parent: merge, conflict-check, cite

## Honesty
- Conflicting sources → say so
- Never invent CVE IDs or "confirmed exploited" without a source
- Empty fetch → note failure; try `github` or alternate URL

## Never
- One blog as ground truth
- Dump full copyrighted pages into git
- Browse toward attacking third parties outside authorized scope
