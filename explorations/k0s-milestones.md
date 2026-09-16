# k0s implementation milestones and repo bootstrap

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: milestone plan, not a staffed program.
> Date: 2026-09-16.

**Evidence boundary:** no milestone was executed for this note.

## 1. Ground rules

New Go repository (module path, registry, ownership are ADRs there, not here). CRDs first, Pods later, CRI last. Workestrate keeps policy compilation, configuration provenance, launch identity, and credential custody throughout. No silent revive, ever.

## 2. Layout

Go operator repo: API types, controllers, backend adapters, broker client, fencing, provenance; shared conformance package; unit plus envtest plus end-to-end plus fault suites; Nix, k0s, k3s-fallback, and ARC manifests.

## 3. Phases

M0 contract frozen plus conformance green against the local backend. M1 one host, one declared workload, truthful readiness, no duplication across controller disruption, deliberate stop stays stopped. M2 durable recovery plus bounded brokered children. M3 CubeSandbox adapter behind the same contract with measured (not vendor) numbers. M4 multi-host placement with taints and ARC runners. M5 deferred: complete-state restore and warm branching, only if M1-M4 hold.

## 4. Gates

Same binary-level contract suite both repos run. Unit to envtest to conformance-local to end-to-end and fault matrix. Negative controls red on purpose per promotion. ADRs 001 through 010 live in the owning repo when reached.
