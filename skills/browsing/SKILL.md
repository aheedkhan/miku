---
name: browsing
description: >-
  Web research via Hermes web_search / web_extract (SearXNG + Firecrawl /
  keyless fallbacks). Use when the user asks to browse, search the web, open a
  URL, fetch a page, dig into docs/advisories, or research something online.
---

# Browsing (web search + extract)

## Goal
Find primary sources fast, extract what matters, cite URLs, and optionally stash notes in RAG.

## When to use
- "Search / browse / look up / fetch this URL"
- CVE advisories, vendor writeups, AOSP docs, MSDN, man pages online
- Before `malware-intel` or `report-generation` when local RAG is thin

## Tools (Hermes)
Configured in `config.yaml` → `web:`:
- `web_search` — SearXNG preferred (`SEARXNG_URL` in `.env`); keyless fallbacks on
- `web_extract` — Firecrawl / extract backend for page text

Caps: `tool_loop_guardrails.loop_caps.max_web_searches` (default 80). Don't burn the budget.

## Workflow
1. **Query design** — specific terms + year/version/CVE id when known
2. **Search** — `web_search`; skim titles; prefer primary sources (NVD, vendor, kernel.org, android.googlesource, MSDN)
3. **Extract** — `web_extract` on 1–5 best URLs (not 20)
4. **Synthesize** — bullets + direct quotes sparingly; always cite URL + retrieval date
5. **Persist (optional)** — save notes under the right `workspace/` folder, then remind `hermes workspace index`
6. **Hand off** — `report-generation` for a formal writeup; `malware-intel` for family cards

## Query tips
| Need | Pattern |
|------|---------|
| CVE | `CVE-YYYY-NNNNN NVD` / vendor advisory name |
| AOSP | `site:android.googlesource.com <path>` or tag `android-16.0.0_r4` |
| Windows | API name + `site:learn.microsoft.com` |
| Malware family | family name + `MalwareBazaar` / vendor report |

## Parallelism
- Leaf A: search + shortlist URLs
- Leaf B: extract top pages
- Parent: merge, conflict-check, cite

## Honesty
- Conflicting sources → say so
- Never invent CVE IDs, patch SHAs, or "confirmed exploited" without a source
- Paywalled / empty extract → note failure; try alternate URL

## Never
- Treat one blog as ground truth
- Dump full copyrighted pages into git — short excerpts + link
- Browse toward attacking third parties outside authorized scope
