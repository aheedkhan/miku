# Windows 11 lab environment — A→Z setup

**Audience:** You (human) setting up a full lab so Miku can build/test Windows `.exe` from WSL.  
**Miku:** When the user asks to set up Windows / lab VM / “from zero”, spoon-feed **one lettered step at a time** from this file. Wait for confirmation before the next step.

Related: [`wsl-windows-lab-guide.md`](wsl-windows-lab-guide.md) (daily workflow) · skills `wsl-windows-exe`, `lab-iterate`, `env-bootstrap`.

---

## What “done” looks like

- [ ] Win11 **lab VM** installed (not daily driver)
- [ ] Snapshot `win11-clean` taken
- [ ] Guest can reach host C2 IP on port **8080** (or your chosen port)
- [ ] You can copy `labrat.exe` into the guest
- [ ] Defender status commands work; Event Viewer path known
- [ ] Optional: WinDbg + Procmon installed in the guest
- [ ] WSL side: miku repo + `./install-wsl.sh` already done

---

## A — Pick hypervisor (Windows host)

Choose **one**:

| Option | When |
|--------|------|
| **Hyper-V** | Windows 10/11 Pro / Education / Enterprise |
| **VMware Workstation Player** | Free personal use; easy ISO install |
| **VirtualBox** | Free; fine for lab |

**Miku spoon-feed line:**  
> Step A: Reply with which you’ll use: Hyper-V, VMware, or VirtualBox. If unsure and you have Win11 Pro, pick Hyper-V.

---

## B — Enable virtualization in BIOS/UEFT (if needed)

1. Reboot → enter BIOS/UEFI (Del / F2 / F10 — vendor-specific)  
2. Enable **Intel VT-x** / **AMD-V** / **SVM**  
3. Save & exit  

**Check later in Windows (Admin PowerShell):**
```powershell
Get-ComputerInfo -Property "HyperV*"
systeminfo | findstr /I "Hyper-V"
```

---

## C — Install / enable hypervisor

### C1 — Hyper-V
**Admin PowerShell:**
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
# reboot if prompted
```
Or: *Settings → Apps → Optional features → More Windows features → Hyper-V*.

### C2 — VMware / VirtualBox
Download installer from vendor → Next/Next → reboot if asked.

---

## D — Get Windows 11 ISO

1. Microsoft: [Download Windows 11 Disk Image (ISO)](https://www.microsoft.com/software-download/windows11)  
2. Save e.g. `C:\ISO\Win11.iso`  
3. Note: lab VM can use a **local account**; TPM/Secure Boot usually required for official ISO — Hyper-V Gen2 supports this.

---

## E — Create the VM (specs)

| Setting | Lab default |
|---------|-------------|
| Generation | Gen 2 (Hyper-V) |
| RAM | 4–8 GB |
| CPUs | 2–4 |
| Disk | 60–80 GB dynamic |
| Network | Default switch / NAT (guest gets internet; host is gateway) |
| Secure Boot | On (Win11) |
| TPM | On (Win11) |

### E1 — Hyper-V Manager (GUI)
1. Open **Hyper-V Manager**  
2. New → Virtual Machine → Gen 2 → memory → Default Switch → create VHDX → Install from ISO  
3. Settings → Security → enable TPM  
4. Connect → Start  

### E2 — VMware / VirtualBox
New VM → Win11 → attach ISO → enable EFI/TPM options per wizard → Start  

**Miku:** Give only the subsection matching their hypervisor from A.

---

## F — Install Windows 11 (minimal)

Inside the installer:
1. Region/keyboard → **Install**  
2. When asked for Microsoft account: prefer **local account** if the build allows (or `oobe\bypassnro` tricks only if user already knows them — don’t derail)  
3. Single user e.g. `lab` / simple password  
4. Decline extra cloud/OneDrive noise where possible  
5. Finish OOBE → desktop  

Skip heavy personalization. This is a **lab**, not a daily PC.

---

## G — First-boot hygiene (guest)

**Admin PowerShell inside VM:**
```powershell
# Identity
whoami
(Get-ComputerInfo).WindowsProductName
(Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").DisplayVersion
(Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuild

# Defender baseline (record this)
Get-MpComputerStatus | Select AMProductVersion, AntispywareEnabled, RealTimeProtectionEnabled, IoavProtectionEnabled, NISEnabled, AntivirusEnabled
```

Optional: pause huge feature updates for a week so the snapshot stays stable — user choice.

---

## H — Snapshot `win11-clean` (critical)

**Before** any lab malware / Defender tests:

| Hypervisor | Action |
|------------|--------|
| Hyper-V | VM selected → **Checkpoint** → name `win11-clean` |
| VMware | Snapshot → `win11-clean` |
| VirtualBox | Machine → Take Snapshot → `win11-clean` |

**Miku must remind:** restore this checkpoint after messy Defender/evasion runs.

---

## I — Find host IP (C2 from guest)

On the **Windows host** (not inside the guest), Admin PowerShell:
```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' } |
  Select IPAddress, InterfaceAlias
```

Typical patterns:
| Setup | Guest reaches host at |
|-------|------------------------|
| Hyper-V Default Switch | Host’s `vEthernet (Default Switch)` address (often `172.x.x.1`) |
| VMware NAT | Usually `192.168.x.1` / check VMware Virtual Network Editor |
| Bridged | Host’s LAN IP e.g. `192.168.1.10` |
| WSL2 only (interop .exe on host) | Often `127.0.0.1` if C2 in WSL with localhost forwarding — **verify** |

Write the IP down → Miku sets `C2_HOST` in `labs/rat/win11/labrat/implant/include/config.h`.

---

## J — Allow C2 port on host firewall

C2 often listens in **WSL** on `0.0.0.0:8080`. Allow inbound from the lab subnet:

**Admin PowerShell on host:**
```powershell
New-NetFirewallRule -DisplayName "Miku Lab C2 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

If C2 runs on Windows host Python instead of WSL, same rule applies.

Test from **guest** browser or PowerShell later (step O).

---

## K — WSL side (if not done)

On Windows host → open **Ubuntu** WSL:
```bash
cd ~/Documents/miku   # or your clone path
./install-wsl.sh      # first time
source .venv/bin/activate && miku
x86_64-w64-mingw32-gcc --version
```

Full agent workflow: [`wsl-windows-lab-guide.md`](wsl-windows-lab-guide.md).

---

## L — Get `labrat.exe` into the guest

Pick **one** method and stick to it:

### L1 — `\\wsl$` share (easiest on Hyper-V host)
In guest Explorer address bar:
```
\\wsl$\Ubuntu\home\<YOUR_LINUX_USER>\Documents\miku\labs\rat\win11\labrat\implant
```
Copy `labrat.exe` to `C:\Users\lab\Desktop\`.

(Distro name may be `Ubuntu-22.04` etc. — check `wsl -l -v` on host.)

### L2 — HTTP from WSL
```bash
# WSL, in folder with labrat.exe
python3 -m http.server 8000 --bind 0.0.0.0
```
Guest browser: `http://<HOST_IP>:8000/labrat.exe`  
(Allow port 8000 on host firewall like step J if needed.)

### L3 — Shared folder
Hyper-V: limited; prefer L1/L2. VMware/VBox: enable Shared Folders → mount in guest.

---

## M — Lab tools inside the guest (recommended)

Install in the **VM** (not required for first checkin):

| Tool | Why |
|------|-----|
| [WinDbg / Preview](https://learn.microsoft.com/windows-hardware/drivers/debugger/) or “WinDbg” from Microsoft Store | Crash stacks for `.exe` |
| [Sysinternals Procmon](https://learn.microsoft.com/sysinternals/downloads/procmon) | File/reg/network fail paths |
| [Sysinternals DebugView](https://learn.microsoft.com/sysinternals/downloads/debugview) | `OutputDebugString` |
| Optional: Sysmon | Richer telemetry for detection twins |

After install → optional second checkpoint `win11-tools`.

---

## N — Defender “know your enemy” (guest)

```powershell
Get-MpComputerStatus
Get-MpPreference | Select DisableRealtimeMonitoring, MAPSReporting, SubmitSamplesConsent

# Live logs while testing
# Event Viewer → Applications and Services Logs → Microsoft → Windows →
#   Windows Defender → Operational
```

Record for every project card: build, Defender version, cloud on/off, HVCI:

```powershell
Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard |
  Select SecurityServicesRunning
```

---

## O — Connectivity test (guest → host C2)

1. On WSL start a listener (Miku or you):
```bash
python3 -m http.server 8080 --bind 0.0.0.0
# later: real c2_server.py
```
2. From **guest** PowerShell:
```powershell
Test-NetConnection -ComputerName <HOST_IP> -Port 8080
# or
curl.exe http://<HOST_IP>:8080/
```
3. Must succeed before expecting `labrat` checkin.

---

## P — First implant smoke (no evasion)

1. Miku builds `labrat.exe` with `C2_HOST=<HOST_IP>`  
2. Copy into guest (L)  
3. Snapshot already exists (H)  
4. Run `labrat.exe`  
5. Confirm checkin on C2 console  
6. If Defender blocks → **that’s baseline data** — record Event ID; then `lab-iterate` Phase A/B  

---

## Q — Daily restore rhythm

| After… | Do… |
|--------|-----|
| Successful clean test | Keep running or checkpoint `win11-ok-checkin` |
| Defender mess / persistence experiments | **Revert to `win11-clean`** |
| New Windows cumulative update | New clean snapshot |

---

## R — What to tell Miku when finished

Paste something like:
```
Lab ready:
- Hypervisor: Hyper-V
- Guest user: lab
- Snapshot: win11-clean
- Host IP from guest: 172.x.x.1
- C2 port: 8080 open
- Copy method: \\wsl$
- WinDbg/Procmon: yes/no
```
Then: `spoon-feed me through first labrat checkin` or `Defender in scope`.

---

## S — Troubleshooting quick map

| Problem | Check |
|---------|--------|
| VM won’t start Win11 | TPM + Secure Boot + Gen2 |
| Guest can’t hit host | Wrong IP; firewall rule J; C2 not on `0.0.0.0` |
| `\\wsl$` empty | WSL running; correct distro name; file path |
| `.exe` runs on host interop but not “Defender lab” | Interop ≠ VM baseline — use guest |
| mingw missing in WSL | `sudo apt install mingw-w64` or re-run `install-wsl.sh` |

---

## T — Safety (non-negotiable)

- Lab VM / owned hosts only  
- No third-party targeting  
- Don’t commit `.exe` to git  
- Don’t claim Defender bypass without Phase A baseline on a snapshot  

---

## Miku operator notes

When spoon-feeding this doc:
1. Ask which step letter they’re on (or start at **A**)  
2. Give **only that step’s** commands  
3. Wait for paste-back (`EXIT` / screenshot / “done”)  
4. Advance A→B→C…  
5. After **R**, switch to `wsl-windows-exe` + `lab-iterate` for the implant loop  

Skills: `teaching-lab`, `env-bootstrap`, `wsl-windows-exe`, `windows-rat-dev`.
