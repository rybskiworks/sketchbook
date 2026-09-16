# Rust-Go integration contract

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: contract direction, not an implemented API.
> Date: 2026-09-16.

**Evidence boundary:** no contract was implemented for this note. Direction recorded from the surge review: JSON over stdio to the pinned Workestrate binary plus a Unix-socket control endpoint for the one long-lived case.

## 1. Decision

No cgo, no linked FFI, no gRPC. The Go operator shells a pinned `workestrate` binary (JSON verbs, additive-only stdout views, strict stdin, stable error envelope) and, for the single long-lived case, speaks to a Unix-socket control endpoint. Rationale: cgo crosses the custody boundary with linked memory; gRPC buys schema machinery the narrow verb set does not need.

## 2. Surface

Allowed verbs: versions pin check, workload plan, ps/instances/workloads reads, validate-config/generate-schema/doctor reads, up/down/exec mutations, control-serve socket. Explicitly out: run passthrough, msb passthrough, broker wire, registry/DB/key files. Versioning: tool version plus schema bytes plus protocol version; additive stdout, strict stdin; Go side pins the binary via Nix and fails closed on skew, redacts secrets, runs conformance.
