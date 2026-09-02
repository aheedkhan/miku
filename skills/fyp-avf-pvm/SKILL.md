---
name: fyp-avf-pvm
description: FYP AVF/Microdroid — Android host, headless pVMs, host-initiated vsock, OCR-DLP and sys-net, transport ladder. Use for isolation work.
---

# FYP AVF / pVM isolation

## Locked model
- Android = **host** (user-facing OS)
- pVMs = headless Microdroid workers (OCR-DLP, sys-net; vault slot reserved)
- **Not** Qubes dom0 — AVF cannot invert that
- Payload hosts vsock **server**; host always connects **to** it — no proactive push from pVM
- No FD passthrough — bytes copied

## Workstreams
- Transport ladder (`15` §6.4): 256 KB → 16 MB until throw — high value/hour, needs no full MDM
- S4 typed vsock round trip (host → payload → typed result)
- OCR-DLP: returns typed verdict; no keys, no network, no persistent store
- sys-net: terminates mTLS; holds **no** private key

## Cite
`05`, `05a`, `15-avf-spike.md` (only measured results doc), `GOV-023` for protected-VM claims on CF.
