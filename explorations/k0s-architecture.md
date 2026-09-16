# k0s architecture for the Workestrate fleet

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: architecture survey, not a selection decision or an implementation specification.
> Date: 2026-09-16.
> Related: [k0s vs CubeSandbox vs current Workestrate](workestrate-k0s-cubesandbox-comparison.md), [Workestrate fleet control plane](workestrate-fleet-control-plane-implementation.md), [Workestrate Kubernetes control plane](https://github.com/rybskiworks/sketchbook/pull/32) (open PR #32).

**Evidence boundary:** upstream project documentation as summarized here plus the pins below. No k0s deployment was stood up, no benchmark was run, no source audit was performed for this note. Every integration claim below is a proposal.

## 1. What k0s is

k0s (upstream `k0sproject/k0s`) ships Kubernetes as a single binary (order ~262MB): controllers can run isolated from workers, storage is kine (SQLite by default, etcd for HA), CNI is kube-router or Calico, and multi-host provisioning is done with k0sctl. Against the Workestrate baseline (local-first Rust CLI, no daemon, no networked worker protocol at `f2db169`), k0s adds a declarative API, placement primitives, and a recovery story for the management plane. It adds no workload execution by itself.

## 2. What k0s does NOT provide

- Scheduling Pods is not scheduling Workestrate workloads. A custom resource needs its own placement and accounting controller.
- No VM orchestration, no microVM backend, no snapshot/fork semantics, no credential custody, no policy compilation.
- No NixOS packaging: nixpkgs has no k0s package or NixOS module, so a NixOS fleet carries a flake-built binary plus hand-written systemd units and tracks upstream releases explicitly. This is the decisive practical gap versus k3s (`services.k3s` exists).

## 3. How an external-runtime operator plugs in

Phase one is an external-runtime custom resource: one workload, one explicitly selected host, with reservations, fencing, and launch identity before any scheduling cleverness. The operator records what the host reports (booted, ready, stopped) and never duplicates a workload across controller restarts; deletion means stop, and stop is not resurrected. The host need not run kubelet. Before multi-host release, one durable placement and reservation authority is chosen; the host atomically admits each reservation and a stale controller view never overrules local capacity.

## 4. Later phases

Pod-backed launcher (controller creates a Pod genuinely containing a VM launcher, reusing scheduler placement) and CRI/containerd integration are deferred until the external-runtime phase proves the contract. k0s supports an externally managed CRI endpoint, but the runtime must implement the interfaces; a partial CRI adapter for diagram value is rejected.

## references and evidence

- Workestrate `f2db169` (2026-09-16): local CLI baseline, microsandbox fork pin `251b368a`.
- [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44): separate Go operator repo intent, k0s reference.
