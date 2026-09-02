# Windows 11 + Microsoft Defender — lab research index

Companion to [`curated-links.md`](curated-links.md). Focused entry points for
**Windows 11** security features and **Defender/AMSI/ETW** research in authorized VMs.

## Windows 11 hardening stack (what you're up against in lab)

1. **Smart App Control / reputation** — blocks unknown unsigned code early
2. **HVCI / Memory integrity** — kernel code integrity via VBS
3. **Credential Guard** — isolates LSASS secrets (when enabled)
4. **Microsoft Defender AV** — real-time + cloud-delivered protection
5. **AMSI** — in-process scanning for scripts, .NET, Office macros
6. **ETW + kernel callbacks** — telemetry to Defender / third-party EDR
7. **ASR rules** — configurable attack surface reduction
8. **Tamper Protection** — blocks disabling Defender from userland

Docs hub: https://learn.microsoft.com/en-us/windows/security/

## Defender components to study (in order)

| Layer | Learn | Tooling |
|-------|-------|---------|
| Scan engine | Real-time, on-access, cloud | `MpCmdRun.exe`, Defender logs |
| AMSI | Script & memory scan API | `amsi.dll`, PowerShell `$amsiInitFailed` tests |
| ETW | Event providers | `logman`, KrabsETW, SilkETW |
| ASR | Policy blocks | Intune / GPO ASR rule IDs |
| Network protection | SmartScreen URLs | Controlled browser tests |

Defender event log: `Microsoft-Windows-Windows Defender/Operational`

## Open-source CVE → Windows harness pipeline

1. **Find CVE** — NVD + MSRC + CISA KEV (`curated-links.md`)
2. **Confirm build** — affected Windows 11 build vs your VM (`winver`)
3. **Design** — `workspace/cves/tests/CVE-YYYY-NNNN.md`
4. **Build PoC** — `labs/cve-tests/windows/CVE-YYYY-NNNN/` (minimal, cited)
5. **Run twice** — vulnerable snapshot vs patched
6. **Record** — detection ideas (Sigma/ETW fields), not just "it worked"
7. **Index** — `hermes workspace index`

## Evasion research → detection twin (required)

For every technique you implement, fill this in the same note:

```markdown
## Detection twin
- ATT&CK:
- Telemetry source: (Sysmon Event ID / ETW provider / Defender log)
- Sigma / rule idea:
- Expected alert in Defender for Business:
- Baseline test command (Atomic Red Team test # if applicable):
```

Atomic Red Team: https://github.com/redcanaryco/atomic-red-team

## Useful one-liners (lab VM)

```powershell
# Defender status
Get-MpComputerStatus | Select AMServiceEnabled, AntispywareEnabled, RealTimeProtectionEnabled, IoavProtectionEnabled

# ASR rules (if managed)
Get-MpPreference | Select -Expand AttackSurfaceReductionRules_Ids

# OS build
[System.Environment]::OSVersion | Format-List *
Get-ComputerInfo | Select OsName, OsVersion, OsBuildNumber
```

## See also

- Full link table: `workspace/references/curated-links.md`
- Skill: `windows-api`, `malware-authoring`, `cve-malware-test`
