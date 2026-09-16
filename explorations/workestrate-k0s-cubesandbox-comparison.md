# k0s vs CubeSandbox vs current Workestrate, with a k3s comparative

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: comparison sketch, not a selection decision or an implementation specification.
> Date: 2026-09-16.
> Related: [Workestrate Kubernetes control plane](https://github.com/rybskiworks/sketchbook/pull/32) (open PR #32), [Compartmentalized NixOS workstation](compartmentalized-nixos-architecture-seed.md), [Shared Nix store fabric](shared-nix-store-microvm-fabric.md).

**Evidence boundary:** repository inspection plus vendor-published benchmarks only. No KVM host was provisioned, no benchmark was run, and no k0s, k3s, or CubeSandbox deployment was stood up for this note. Vendor latency and size numbers are reported as vendor claims, not reproduced results. Pins: Workestrate `f2db169` (2026-09-16), CubeSandbox `d4a93fa` (2026-09-16), sketchbook `3c75279`.

## question

Workestrate today is a local-first operator tool. Two adjacent options promise fleet behavior: k0s as a Kubernetes control plane under a Workestrate adapter, and CubeSandbox as a ready-made KVM microVM fleet with an E2B-compatible API. How do they compare against the current system, against each other, and where does k3s change the answer?

## the current baseline

Workestrate at `f2db169` is a Rust CLI with no daemon: the operator runs `workload plan`, `workload up`, and `workload exec` (services take `up`/`down`/`logs`/`plan`, agents take `exec`/`down`/`plan`). There are no runners and no networked worker protocol. Execution is local, through a pinned microsandbox fork (`rybskiworks/microsandbox@251b368a`, recorded in `flake.nix` and `control/agentctl/src/commands/versions.rs`). Strengths: explicit operator intent, policy compilation, credential custody, and Nix-pinned construction stay in one tree. Limits: one operator, one host, no placement, no remote lifecycle, no admission control, no bounded delegation to agents.

Anything compared below must preserve the strengths (policy and credential custody in Workestrate) while adding only the fleet behavior that is actually missing.

## k0s vs current Workestrate

k0s (upstream `k0sproject/k0s`) ships Kubernetes as a single ~262MB binary: controllers can run isolated from workers, storage is kine (SQLite by default, etcd for HA), CNI is kube-router or Calico, and multi-host provisioning is done with k0sctl. Against the baseline, k0s adds a declarative API, placement primitives, and a recovery story for the management plane. It does not add workload execution by itself: scheduling Pods is not scheduling Workestrate workloads, and a custom resource needs its own placement and accounting controller, as the control-plane PRD already records.

The concrete gap is NixOS packaging: nixpkgs has no k0s package or NixOS module, so a NixOS fleet would carry a new packaging burden (flake-built binary plus hand-written systemd units). k0s fits a team that wants plain upstream Kubernetes semantics and is willing to pay that packaging cost. It does not change the runtime at all.

## k0s plus CubeSandbox vs current Workestrate

In this combination k0s owns the control API and CubeSandbox owns fast KVM execution behind it. CubeSandbox (`tencentcloud/CubeSandbox`, Apache-2.0) is a KVM microVM fleet: E2B-compatible API, vendor-claimed ~48ms serial cold start on bare metal (min 43.5 / p95 57.4, from its own benchmark post), XFS reflink (FICLONE) CoW storage via the cubecow engine, eBPF plus L7 egress policy, and sub-5MB per-sandbox overhead claims. Against the baseline this pair adds both control and dense fast execution at once.

The costs are boundary costs. CubeSandbox requires root, `/dev/kvm`, and Docker in its deployment story; there is no NixOS or rootless path upstream, so it lands on a fleet as an opaque service beside the Nix world, not inside it. Its E2B API is a second control surface with its own identity and credential model, which must be brokered rather than adopted wholesale, or Workestrate loses exactly the custody boundary that justifies its existence. And the two projects evolve independently: k0s upgrades and CubeSandbox upgrades compose only through the adapter this team would own.

## CubeSandbox vs current Workestrate

Taken alone, CubeSandbox replaces neither the CLI nor the policy layer. It is an execution backend with an agent-facing API, not an operator tool: no workload definitions under version control, no plan/up semantics, no Nix construction inputs. Adopting it directly means trading Workestrate's declarative operator model for an imperative sandbox API, and inheriting its posture (root, KVM, Docker, no NixOS story) on every host.

The honest use of CubeSandbox alone is as a fast sandbox service for agent and CI workloads where Workestrate policy is enforced above it, not as a Workestrate replacement. That enforcement layer still has to be built, with or without Kubernetes.

## k3s comparative

k3s (upstream `k3s-io/k3s`) is the batteries-included counterpart: a ~74-82MB single binary bundling flannel, Traefik, local-path storage, and a Helm controller; SQLite by default with etcd for HA. The decisive practical difference for this project is NixOS fit: nixpkgs ships a `services.k3s` module, so a NixOS fleet declares k3s rather than packaging it. And for on-demand GitHub runners, ARC `gha-runner-scale-set` is a working pattern on k3s today.

Against k0s, k3s trades architectural minimalism for operational completeness: opinionated bundled components reduce choice but also reduce assembly work, and the smaller binary suits edge and single-node profiles. Nothing in the k3s column removes the need for a Workestrate adapter; Pod scheduling still is not workload scheduling.

## k0s-vs-k3s pick guide

Pick k0s when the priority is minimal, composable Kubernetes: isolated controllers matter, the CNI and ingress choices must stay open (kube-router or Calico, own ingress), and the team accepts packaging k0s for NixOS as explicit work. Pick k3s when the priority is fastest fleet on NixOS: the existing `services.k3s` module, the smaller binary, and the proven ARC runner pattern outweigh the cost of carrying bundled components that may later be swapped or disabled. Either choice keeps the same adapter architecture: external-runtime CRDs first, Pod-backed execution later, Workestrate retaining policy and credential custody.

What would change this ranking: a nixpkgs k0s module would erase k3s's largest practical advantage; a CubeSandbox rootless or NixOS deployment story would lower the cost of the k0s-plus-CubeSandbox combination; measured (not vendor) cold-start and density numbers on our own hardware would turn the performance column from claims into evidence.

## smallest useful experiments

1. Package k0s in a flake with systemd units on one NixOS KVM host and record the maintenance surface. This sizes the gap honestly.
2. Declare one external-runtime workload through a prototype CRD against local Workestrate execution, with no CubeSandbox involved. This tests the adapter boundary before any backend is added.
3. Only then, front a single CubeSandbox node with the same contract and compare cold start and density against the microsandbox fork on identical hardware. Vendor numbers set expectations; they are not results.

## references and evidence

- Workestrate `f2db169` (2026-09-16): Rust CLI, `workload plan`/`up`/`exec`, microsandbox fork pin `251b368a` in `flake.nix`.
- CubeSandbox `d4a93fa` (2026-09-16): Apache-2.0; cold-start claim `docs/blog/posts/2026-06-01-cubesandbox-perf-benchmark.md`; cubecow XFS reflink engine (`cubecow/README.md`); KVM and x86_64 Linux requirement (`README.md`).
- k0s and k3s characterizations are upstream project documentation as summarized in the task brief; no source audit or deployment was performed here.
- [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44): separate Go operator repo intent, external-runtime CRD first.
