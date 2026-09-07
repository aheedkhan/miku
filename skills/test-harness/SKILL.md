---
name: test-harness
description: >-
  Compile-test-debug loop — unit/smoke tests, CVE triggers, detection twins.
  Use when proving a fix, keeping a repro red/green, or before calling something
  verified.
---

# Test harness

## Goal
A claim becomes a **command that can fail**. Red → fix → green. No "looks fine."

## When to use
- After `lab-build` (smoke + unit)
- CVE lab PoCs (`cve-malware-test`)
- Detection twins after malware authoring
- Regression when fixing a bug from `debug-triage`

## Compile → test → debug loop
```
lab-build (Debug/ASAN) → run test/harness → fail?
    ├─ compile fail → lab-build / first error
    ├─ assert/wrong result → fix code; keep test
    └─ crash/hang → debugger / debug-triage
→ green → record evidence path → rag_remember if durable
```

## Workflow
1. State the **claim** in one sentence
2. Define **pass/fail** (exit code, log line, HTTP status, file artifact, ASAN clean)
3. Smallest harness: `pytest` / `ctest` / `cargo test` / script / `adb shell`
4. Run; capture output path
5. On fail: triage — don't delete the test to silence it
6. Document evidence for "verified"

## Patterns
| Domain | Harness |
|--------|---------|
| Library/tool | `pytest` / `cargo test` / gtest + ctest |
| CVE | Minimal trigger + assert symptom; owned target |
| Malware detect | YARA/sigma against known hash |
| RAT C2 lab | Python protocol tests + optional VM checkin |
| Android | instrumented test or host-side binder expect |

## Rules
- Never invent green results or CVE IDs
- Keep harnesses in-repo; samples/binaries stay off git when malware
- Fail-secure for security checks (expect DENY by default when that's the design)
- Crash in a test → skill `debugger`, don't shrug

## Hand-offs
- Build → `lab-build`
- Crash → `debugger` / `debug-triage`
- Writeup → `report-generation`
