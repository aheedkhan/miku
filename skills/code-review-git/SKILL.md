---
name: code-review-git
description: Security-minded code review plus git commit/PR hygiene. Use when reviewing diffs, committing, or opening PRs.
---

# Code review & git

## Review checklist
- Correctness and edge cases
- Memory safety (C/C++), injection, authz, path traversal
- Android: exported components, PendingIntent, WebView, JNI bounds
- Secrets in diff, unsafe subprocess, `curl | sh`
- Tests updated? Docs needed?

## Git behavior
- Commit **only** when the user asks.
- Message = why, 1–2 sentences; match repo style if present.
- Never `git push --force` to main/master; never `--no-verify` unless asked.
- Prefer small reviewable commits.

## Parallelism
For large changes: spawn a **reviewer** subagent on the diff while the parent continues implementation, then merge findings.
