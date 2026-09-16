# Workestrate fleet control plane: implementation sketch

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: implementation sketch, not an accepted specification or an implemented API.
> Date: 2026-09-16.
> Related: [k0s vs CubeSandbox vs current Workestrate](workestrate-k0s-cubesandbox-comparison.md), [Workestrate Kubernetes control plane](https://github.com/rybskiworks/sketchbook/pull/32) (open PR #32), [Compartmentalized NixOS workstation](compartmentalized-nixos-architecture-seed.md), [Shared Nix store fabric](shared-nix-store-microvm-fabric.md).

**Evidence boundary:** no Kubernetes deployment, Nix build, VM boot, or benchmark was performed for this note. Every interface, repository, and milestone below is a proposal. Pins: Workestrate `f2db169`, CubeSandbox `d4a93fa`, sketchbook `3c75279` (all inspected 2026-09-16).

## question

If the control-plane direction from workestrate#44 is accepted, what gets built, in what order, and where does each piece live, down to repositories, Nix packaging, services, and integrations?

## answer in brief

Build a separate Go operator repository (per the workestrate#44 intent), reconcile external-runtime custom resources first, add Pod-backed and CRI execution later, package the Kubernetes distribution with Nix flakes, keep CubeSandbox behind a versioned backend contract as an option, broker agent-spawned sandboxes through launch-bound credentials, run GitHub jobs on ARC scale sets, and fit the whole thing into the Qubes-like NixOS compartment model where the host stays small. Workestrate's Rust tree keeps policy compilation, configuration provenance, launch identity, and credential custody throughout.

## 1. Organization and repositories

One new repository owns the fleet layer: a Go operator plus its CRDs, conformance tests, and deployment manifests. It must not live inside the Workestrate Rust tree, because the two evolve on different rhythms (operator against Kubernetes APIs, Workestrate against policy and runtime pins) and because the operator is allowed to fail or upgrade without taking the local CLI with it. The Workestrate side gains a narrow, versioned integration contract (workload intent in, lifecycle state out) and a conformance suite both sides run. Closed decisions later (module paths, image registries, ownership) are ADRs in the owning repo, not in this sketch.

## 2. Execution model: CRDs first, Pods later, CRI last

Phase one is an external-runtime custom resource: one workload, one explicitly selected host, with reservations, fencing, and launch identity before any scheduling cleverness. The operator records what the host actually reports (booted, ready, stopped) and never duplicates a workload across controller restarts; deletion means stop, and stop is not resurrected. This is deliberately not Pod scheduling: kube-scheduler places Pods, while placement and accounting for external runtimes belong to this controller.

Phase two adds a Pod-backed launcher for workloads that fit container semantics, reusing scheduler placement and standard observability. Phase three, a CRI or containerd shim, is deferred until the first two phases prove the contract; it is the most invasive option and buys the least until density demands it. Each phase keeps the same Workestrate contract underneath, so backends change without renegotiating policy custody.

## 3. Nix delivery and the k0s gap

The fleet is deployed with Nix flakes: pinned Kubernetes binaries, systemd units, and configuration closures per host role (controller, worker, agent host). k3s is the low-friction path because nixpkgs already provides `services.k3s`. k0s is the preferred-architecture path from the control-plane PRD, but nixpkgs provides no k0s package or module, so choosing k0s means owning a flake-built binary plus hand-maintained systemd units and tracking upstream releases explicitly. Either way, Nix remains responsible for pinned construction and deployment inputs; the operator never builds host closures itself.

## 4. CubeSandbox as an optional backend

CubeSandbox (`tencentcloud/CubeSandbox`, Apache-2.0) sits behind the same versioned backend contract as the local microsandbox fork, never beside it as a second control plane. The operator sees one interface (launch, observe, stop, snapshot where capable); CubeSandbox specifics (E2B-compatible API, XFS reflink CoW via cubecow, eBPF plus L7 egress) stay inside its adapter. Vendor claims (~48ms serial cold start, sub-5MB overhead) are sizing hints, not accepted performance data, until measured on our hardware. Non-goals for the adapter: adopting CubeSandbox identity or credential models, running it rootless (upstream has no such story), or deploying it through Nix (upstream assumes root, `/dev/kvm`, Docker).

## 5. Agents and brokers

Agent-spawned sandboxes go through a broker, not through cluster credentials. The broker mints launch-bound tokens: one operation identifier, one budget (time, count, resources), one policy scope. The agent receives the operation ID and an honest result; it never sees host administration or general cluster credentials. Bounded child creation and checkpoint-derived branches (the Yggdrasil direction) are broker policies layered above the same execution contract, with external effects explicitly outside any undo boundary.

## 6. GitHub on-demand runners

Ephemeral CI uses ARC `gha-runner-scale-set` on the fleet cluster: k3s carries this pattern today, and k0s can carry it once its packaging gap is closed. Runner pools are tainted and tolerated so ordinary workloads never land on runner nodes and runners never borrow workload capacity silently. Scale sets bind to the same launch-identity and budget discipline as agent sandboxes; a workflow run is just a brokered operation with a different caller.

## 7. Qubes-like NixOS fit

Following the compartmentalized NixOS seed, the host stays small (hypervisor, networking, brokers, immutable store mounts) while compartments carry workloads under explicit cross-compartment capabilities. Workestrate is an optional control-plane component in that picture, not a requirement: the smallest deployment runs no Kubernetes at all. When Kubernetes is present, controllers live in their own compartment, workers in theirs, and desktop brokers keep GUI recovery independent of workload lifecycle. Storage CoW, RAM CoW, and KSM remain capability-gated runtime optimizations beneath the controller, never control-plane features.

## 8. Milestones and acceptance

M0: contract frozen and conformance green against the local backend. M1: one host, one declared workload, truthful readiness, no duplication across controller disruption, deliberate stop stays stopped. M2: durable recovery plus bounded brokered children. M3: CubeSandbox adapter behind the same contract with measured (not vendor) numbers. M4: multi-host placement with taints and ARC runners. M5 (deferred): complete-state restore and warm branching, only if M1-M4 hold.

## 9. Open decisions

Operator repository name and ownership; CRD group and versioning; k0s packaging owner if k0s is selected; CubeSandbox tenancy and network posture per site; runner budgets and audit retention. Each is an ADR in its owning repo when reached, not in this sketch.

## references and evidence

- [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44): Go operator intent, k0s reference.
- Workestrate `f2db169`: local CLI baseline, microsandbox fork pin `251b368a`.
- CubeSandbox `d4a93fa`: KVM fleet, E2B API, cubecow XFS reflink, vendor benchmark posts.
- [Compartmentalized NixOS workstation](compartmentalized-nixos-architecture-seed.md) section 14.5: Workestrate as an optional control plane.
- [Shared Nix store fabric](shared-nix-store-microvm-fabric.md): store generations and overlays beneath placement.
