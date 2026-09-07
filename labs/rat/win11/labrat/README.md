# labrat — Windows 11 RAT lab (authorized VM only)

Research implant implementing v0.1 → v0.5 from skill `windows-rat-dev`.

**Target environment:** isolated Windows 11 lab VM only (no KVM host setup in this
repo — use whatever hypervisor your machine supports, e.g. Hyper-V on Windows host).

**Never run on production systems or against third parties.**

## Versions (same codebase)

| Version | Features |
|---------|----------|
| v0.1 | HTTPS check-in, sleep/jitter |
| v0.2 | `shell` module |
| v0.3 | `upload` / `download` |
| v0.4 | `inject` (remote thread) + `persist` (Run key) |
| v0.5 | XOR config strings + ETW patch (`EtwEventWrite` stub) |

## Build (Windows or cross-compile)

```bash
# Fedora cross-compile (after: sudo dnf install mingw64-gcc mingw64-winpthreads)
cd implant
make          # labrat.exe (all features)
make test     # build + run Python integration tests against C2

# MSVC on Windows
cl ... see Makefile.msvc notes
```

## Run C2 server (dev host or lab LAN)

```bash
cd server
python3 c2_server.py --host 0.0.0.0 --port 8080
```

Edit `implant/include/config.h` — set `C2_HOST` to an IP the Win11 guest can reach
(host LAN IP or hypervisor gateway). Guest must reach that IP:port.

## Run implant (Win11 lab guest)

1. Snapshot a clean Win11 lab VM
2. Copy `labrat.exe` into guest (HTTP pull from host recommended)
3. Run `labrat.exe` inside the VM only
4. On host: `python3 c2_client.py shell whoami`

## Test matrix (document on Win11)

Record: build number, Defender version, cloud protection on/off, HVCI on/off.

```powershell
Get-MpComputerStatus | Select AMProductVersion, RealTimeProtectionEnabled
Get-ComputerInfo | Select OsBuildNumber
```

## Detection

See `detection/` for draft YARA. Fill Sigma after VM test.
