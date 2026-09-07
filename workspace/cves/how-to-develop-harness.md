# How to develop a CVE lab harness

Authorized lab / owned targets only. Pair with skills `cve-research` and `cve-malware-test`.

## Goal

Turn an **open or newly published CVE** into a **minimal research harness** that proves
(or fails to prove) the vulnerable path on a lab build — then write the detection twin.

## Pipeline (always)

1. **Confirm the ID** — NVD / OSV / vendor advisory. Never invent CVE numbers.
2. **Pull into RAG** — `hermes workspace cves 14` (or `/refresh-cve`) so related + KEV land in search.
3. **Root cause in one paragraph** — vulnerable API, parser, IPC, driver, Binder, Win32 path.
4. **Map CWE → trigger type** — see `cwe-to-harness-map.md`.
5. **Design card** — `workspace/cves/tests/CVE-YYYY-NNNN.md` (target build, trigger, success signal).
6. **Build minimal sample** under `labs/cve-tests/<android|linux|windows>/CVE-YYYY-NNNN/`.
7. **A/B** — vulnerable snapshot first, then patched if available.
8. **Record** — versions, logs, Defender/ASAN/crash evidence; mark verified vs `[UNVERIFIED]`.
9. **Detection twin** — Sigma / YARA / ETW / log idea for the same behavior.
10. **Index** — `hermes workspace index`.

## Success signals (pick one)

- Crash / ASAN report
- Log line / toast / flag file you control
- Privilege flip you can observe (lab user A → B)
- Clear auth deny vs allow on the same call

Silent “maybe worked” is not a result.

## Related CVEs

When researching CVE-X:

- Query RAG: `hermes workspace search "CWE-XXX <product>"`
- Use `cve_lookup` with `recent_days` + `platform`
- Check CISA KEV (`include_kev=true`) — known exploited often share the same class
- Related-by-CWE entries are ingested automatically during `workspace cves` / refresh

## Develop checklist

- [ ] Primary advisory cited
- [ ] Vulnerable vs fixed version known (or explicitly unknown)
- [ ] Harness is minimal (no campaign wrapper, no third-party targeting)
- [ ] Package/binary clearly labeled research (`MIKU_CVE_…`)
- [ ] Detection note written in the same card
- [ ] RAG updated

## Never

- Aim harnesses at third-party production
- Claim “verified” without a run (or mark design-only)
- Skip the detection twin after a successful trigger
