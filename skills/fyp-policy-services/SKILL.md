---
name: fyp-policy-services
description: FYP decision/platform services — PolicyEngine, RiskEngine, DeviceHealth, MdmCore, SecurityLog, SecureVault AIDL inventory. Use when implementing first system services.
---

# FYP policy & platform services

## Decision layer
- `PolicyEngineService` — ALLOW | DENY | REQUIRE_SCAN | REQUIRE_APPROVAL
- `RiskEngineService` — trust 0–100
- `DeviceHealthService` — AVB, SELinux, root, patch, lock signals

## Platform
- `MdmCoreService` — enrollment, identity, command channel, `did:besu`
- `SecurityLogService` — append-only hash chain, ECDSA, Merkle → Besu
- `SecureVaultService` — signing oracle only; owns no keys itself

## First code milestone (PROGRESS / CP-1)
Exercise 02-A: `PolicyEngineService`, **DENY by default**, booted SELinux-enforcing — after tree + first service path exists.

## Rules
- Service inventory locked in `14` / `01` — add/remove needs CR
- Clear calling identity on in-process Binder fan-out (`AGENTS.md` Binder refutation)
- Read `02` before inventing AIDL

## Backend (off critical path)
Node, Postgres, ELK, Besu×4, Next.js, Caddy — Podman per `07` §11; can proceed during `repo sync`.
