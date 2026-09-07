---
name: code-review-git
description: >-
  Security-minded code review plus git/GitHub PR hygiene. Use when reviewing
  diffs, committing, opening PRs, or comparing against upstream GitHub code.
---

# Code review & git

## Review checklist
- Correctness and edge cases
- Memory safety (C/C++), injection, authz, path traversal
- Android: exported components, PendingIntent, WebView, JNI bounds
- Windows: handle leaks, impersonation, dangerous `CreateProcess` flags
- Secrets in diff, unsafe subprocess, `curl | sh`
- Tests / detection twin updated?

## Compare with prior art
When reviewing implant/C2/CVE harness code:
1. `github` `code_search` / `file_get` for similar patterns upstream
2. Note where you diverge (and why) in the project card
3. Don't copy license-incompatible code blindly

## Git behavior
- Commit **only** when the user asks
- Message = why, 1–2 sentences; match repo style
- Never `git push --force` to main/master; never `--no-verify` unless asked
- Prefer small reviewable commits

## GitHub PRs/issues
Use `github` actions `pr_*` / `issue_*` (needs `gh` or `GITHUB_TOKEN`).

## Parallelism
Large changes: spawn a **reviewer** subagent on the diff while parent continues, then merge findings.
