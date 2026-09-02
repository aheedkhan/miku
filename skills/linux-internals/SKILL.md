---
name: linux-internals
description: Learn and teach Linux internals — syscalls, processes, VFS, namespaces, cgroups, capabilities, eBPF, netlink. Store topic cards in RAG from man pages and kernel docs.
---

# Linux internals

## Goal
Build durable knowledge of **Linux kernel/user interfaces and internals**, then apply them in systems programming, Android/Linux RE, and security research.

## When to use
- Syscalls, libc wrappers, errno
- Processes/threads, clone/fork/exec, signals
- VFS, files, mounts, inodes; permissions / capabilities
- Namespaces, cgroups, seccomp, Landlock
- Networking (sockets, netlink), eBPF basics
- `/proc`, `/sys`, tracing (`strace`, `perf`, bpftrace)

## Method
1. **RAG first** — search `workspace/os-internals/linux/`.
2. **Primary docs** — `man 2`/`man 7`, kernel.org docs, LWN, glibc manual. Never invent syscall numbers/signatures for the wrong arch.
3. **Topic card** — save under `workspace/os-internals/linux/<topic>.md`.
4. **Teach** — interface → kernel behavior (high level) → pitfalls → tiny C demo.
5. **Security link** — sandbox escapes class concepts, auditd/eBPF detection angles when relevant.
6. **Index** — `hermes workspace index` after new cards.

## Topic card template
```markdown
# <syscall / subsystem>
- man section / header:
- Prototype:
- Arch notes (x86_64 / aarch64):
- Related calls:
- Permissions / caps needed:
- Example (minimal):
- Observability (strace / eBPF / audit):
- Sources:
```

## Prefer
- Clarify user vs kernel; don't confuse cgroup v1/v2.
- Call out Android differences when the user is on Android/Linux.
