---
name: test-harness
description: >-
  Build verification harnesses — unit/smoke tests, CVE lab triggers, malware
  detection twins, FYP [UNVERIFIED]→evidence paths. Use when proving a fix,
  validating a PoC on owned targets, or turning a claim into a runnable check.
---

# Test harness

## Goal
A claim becomes a **command that can fail**. Prefer automated or scripted checks over "looks fine."

## When to use
- "Prove it" / "add a test" / "verification harness"
- CVE lab PoCs under `labs/cve-tests/` or `workspace/cves/tests/`
- Detection twins after malware authoring
- Smoke tests after `lab-build`

## Workflow
1. State the **claim** in one sentence
2. Define **pass/fail** observable (exit code, log line, HTTP status, file artifact)
3. Write the smallest harness (script, gtest, pytest, adb shell snippet)
4. Run once; capture output path
5. Document in report or CVE/malware card — evidence path mandatory for "verified"

## Patterns
| Domain | Harness style |
|--------|----------------|
| CVE | Minimal trigger + assert symptom; owned target only |
| Malware detect | Twin rule/YARA/sigma/test against known artifact hash |
| Library/tool | `pytest` / `cargo test` / ctest |
| Android service | Instrumented or host-side binder call + expect DENY/ALLOW |
| FYP | Executed test + ledger path — else stay `[UNVERIFIED]` |

## Rules
- Never invent CVE IDs or fake green results
- Keep harnesses in-repo; binaries/samples stay on analysis VM
- Fail-secure assertions for security behavior (expect DENY by default when that's the design)

## Hand-offs
- Implementation → `lab-build` / domain skills
- Writeup → `report-generation`
- FYP honesty → `fyp-progress` + verification ledger
