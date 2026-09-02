---
name: daily-android-cve
description: Daily digest workflow — scan Android security / AOSP news and new CVEs, write dated digest markdown into RAG workspace, never invent CVE IDs.
---

# Daily Android + CVE digest

## Goal
Keep Miku (and the user) **current** on Android platform security and CVEs. Run via Hermes cron daily, or on demand.

## When to use
- Cron job `miku-daily-android-cve`
- User asks “what’s new in Android / CVEs today?”

## Method (self-contained — cron has no chat memory)
1. **Web search** for the last ~24–48h:
   - Android Security Bulletin / AOSP security
   - Google Play / Android malware family writeups
   - NVD / vendor advisories with `android`, `aosp`, `qualcomm`, `mediatek`, `samsung` when relevant
   - High-severity CVEs the user care about (mobile, Linux kernel used on Android, Chromium on Android)
2. **Dedupe** against existing files in `workspace/digests/android/` and `workspace/digests/cves/` (same CVE or bulletin month → update, don’t duplicate fiction).
3. **Write digests** (markdown only):
   - `workspace/digests/android/YYYY-MM-DD.md`
   - `workspace/digests/cves/YYYY-MM-DD.md`
4. For any CVE worth keeping long-term, also add/update `workspace/cves/CVE-YYYY-NNNN.md` from primary sources.
5. **Never invent** CVE IDs, patch levels, or bulletin contents — if search is thin, say so.
6. **Index** — remind to run `hermes workspace index`.
7. Short teach-back (≤15 bullets total).
8. **Harness candidates** — list lab-testable CVEs; mention skill `cve-malware-test` (build only if user asks).

## Digest template — Android
```markdown
# Android digest YYYY-MM-DD
## Bulletins / platform
- ...
## Malware / abuse (public reports)
- ...
## AOSP / OEM patches worth noting
- ...
## Sources
- URL — title
```

## Digest template — CVEs
```markdown
# CVE digest YYYY-MM-DD
## New / updated (verify on NVD or vendor)
| CVE | Product | Severity | One-line root cause | Source |
|-----|---------|----------|---------------------|--------|
| | | | | |
## Deep-dive candidates
- ...
## Harness candidates (lab-testable)
- CVE-… — why testable — suggested platform (android/linux/windows)
## Sources
- ...
```

## Sources to prefer
- https://source.android.com/docs/security/bulletin
- NVD / CVE.org
- Vendor security bulletins (Google, Samsung, etc.)
- Reputable malware writeups (tag Android)
