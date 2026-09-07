# CVE research workflow (lab)

Authorized targets only. Pair with skills `cve-research` and `cve-malware-test`.

## Pipeline

1. **Find** — NVD, OSV, MSRC, CISA KEV, vendor advisories
2. **Scope** — affected product/version vs your lab build (`winver`, APK version, package)
3. **Card** — write `workspace/cves/CVE-YYYY-NNNN.md` with root cause hypothesis
4. **Harness** — minimal trigger under `labs/` that asserts a symptom (crash, priv, wrong auth)
5. **Run twice** — vulnerable snapshot vs patched (or fixed config)
6. **Detection** — Sigma / ETW / log idea for the same technique
7. **Index** — `hermes workspace index` so RAG can recall the card

## Card template

```markdown
# CVE-YYYY-NNNN
- Status: researching | harnessed | verified | wontfix
- Product / version:
- Lab target:
- Root cause (one paragraph):
- Public PoC cited:
- Harness path:
- Result: [UNVERIFIED] until harness output saved
- Detection twin:
```

## Honesty rules

- Never invent CVE IDs
- Mark `[UNVERIFIED]` until harness evidence exists
- Cite primary advisory URLs and file:line when patch-diffing

## Windows lab notes

- Capture Defender Operational log + Sysmon if installed
- Record build number, HVCI on/off, cloud protection on/off
- Snapshot VM before first exploit attempt
