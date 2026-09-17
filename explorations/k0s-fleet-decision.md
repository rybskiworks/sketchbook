# k0s fleet options: decision record (2026-09-17)

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: decision record under spec 05 (`/work` assessment specs). No cluster, no build, no benchmark behind it.
> Date: 2026-09-17.
> Related: [comparison](workestrate-k0s-cubesandbox-comparison.md), [fleet control-plane sketch](workestrate-fleet-control-plane-implementation.md), [k0s milestones](k0s-milestones.md), [pluggable backends](pluggable-backends.md), [CubeSandbox deep dive](cubesandbox.md).

## Verdicts per option (spec 05 section 4)

- **Option A, k3s inside one workload VM: SPIKE, time-boxed, k3s first.** k3s has the nixpkgs package and the `services.k3s` module; k0s has neither. The spike answers guest userland, tun, NIC, and cgroup delegation only. A pass is a capability fact, not a fleet decision.
- **Option B, k0s on the host as fleet control plane: DEFER.** No accepted fleet need (workestrate#56 covers near-term dogfood on plain hosts), no ownership ADR from workestrate#44/#66, no k0s nixpkgs path, no second host. The surge notes on this branch ([architecture](k0s-architecture.md), [operator patterns](go-operator-patterns.md), [packaging](nix-k0s-packaging.md), [contract](rust-go-contract.md), [CRD design](fleet-crd-design.md), [milestones](k0s-milestones.md)) are the retained detail set for when the deferral lifts. Six of them are marked surveys (provider-outage retry writers); treat them as scoped starting points, not reviewed designs.
- **Option C, CubeSandbox backend: UNADOPTED OPTION, measurement-only.** License resolved 2026-09-17: the LICENSE file is Apache-2.0 with named third-party exceptions (GitHub API still reports NOASSERTION; the file governs). Posture unchanged: root plus `/dev/kvm` plus Docker, no rootless or NixOS story. First legitimate use is a measured comparison behind the backend contract, after the contract exists. No identity or credential model adoption, ever, without a new decision.
- **Option D, contract only: SEQUENCED, not now.** Gate: ownership ADR from #44/#66 plus a second host. Phase order stands: external-runtime CRD, then Pod-backed, then CRI last.

## What changed on this branch

Reconciled against the surge: fixed three wrong sibling filenames in `pluggable-backends.md` section 8 (`fleet-crd-design.md`, `go-operator-patterns.md`, `broker-arc-runners.md`), linked the orphaned `fleet-threat-fault.md` note in the catalogue, and corrected the CubeSandbox license line to Apache-2.0 with third-party exceptions. PR #33 content is byte-identical inside PR #35, so #35 fuses #33; close #33 as superseded once #35 lands.
