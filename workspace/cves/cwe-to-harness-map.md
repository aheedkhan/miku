# CWE → lab harness map

Quick mapping from common CWEs to **minimal authorized-lab** trigger styles.
Used by CVE ingest develop hints and skill `cve-malware-test`.

| CWE | Class | Harness idea |
|-----|-------|--------------|
| CWE-119 / 120 / 121 / 122 / 787 | Memory corruption | Crafted length/payload into parser; ASAN/PageHeap |
| CWE-125 | OOB read | Boundary lengths; assert crash or controlled leak marker |
| CWE-416 | UAF | Free-then-reclaim sequence on lab build with ASAN |
| CWE-476 | NULL deref | Empty/optional null into vulnerable path |
| CWE-190 | Integer overflow | Size math near wrap; watch alloc/copy |
| CWE-22 | Path traversal | `../` sequences against file API root |
| CWE-78 | OS command injection | Shell metacharacters into tainted sink (lab shell) |
| CWE-89 | SQLi | Boolean/time payloads on lab DB only |
| CWE-79 | XSS | Minimal script in reflected/stored sink (lab app) |
| CWE-94 | Code injection | Untrusted code into eval/template; assert marker |
| CWE-502 | Insecure deser | Crafted object stream / gadget; lab RCE marker |
| CWE-287 / 306 / 862 / 863 | AuthZ/AuthN | Skip/replay/IDOR with two lab identities |
| CWE-362 | Race | Concurrent workers; assert broken invariant |

## Platform sketch

| Platform | Typical entry |
|----------|----------------|
| Android | Intent/Binder/provider path, JNI/NDK ioctl, WebView bridge |
| Linux | Local setuid/helper, netfilter/socket, file parse, ioctl |
| Windows | Win32 API, driver IOCTL, service RPC, file/registry parse |

## After the harness works

1. Run on patched build (expect fail/block)
2. Note Defender / audit / ASAN telemetry
3. Write detection twin in the CVE card
4. `hermes workspace index`
