# Microsandbox storage CoW and memory-efficiency enablement

[Catalogue](README.md) | [Parent tracker #23](https://github.com/rybskiworks/sketchbook/issues/23) | [Workstation seed](compartmentalized-nixos-architecture-seed.md)

**Status:** implementation roadmap and issue decomposition, not an implemented feature release.

**Inspection date:** 2026-09-13. **Initial target:** Linux x86_64. **Scope:** Microsandbox, its actual dependency graph, and upward integration into Workestrate. Storage sharing comes first. KSM, free-page reclamation and complete execution-state CoW restore have separate milestones.

**Evidence boundary:** source inspection and upstream PR metadata/code, not reproduced runtime results. No Nix/Cargo build, VM boot, KSM activation, filesystem benchmark or live-state change was performed. Acceptance tests below are proposed. The execution container could not resolve github.com to obtain a checkout and had no /dev/kvm. Canonical repository unit/docs checks were not run; no passing CI is claimed.

## 1. Recommendation

The first implementation should expose and qualify existing primitives, not replace the copy engine or hypervisor. The consumed stack already has reusable immutable image layers, private flat-root cloning with explicit reflink policy, native raw/qcow2 dependency chains, private file-backed guest RAM, free-page reporting and runtime memory targets. What needs building is their ownership, policy, lifecycle and reporting contract through to Workestrate. [S3], [S4], [S5], [S7], [S8], [S9], [S15]

Recommended order:

1. Expose existing layered/flat root and clone choices through Workestrate without changing omitted defaults.
2. Qualify immutable-base retention, stopped disk checkpoints, private volumes, collection and block-chain behavior.
3. Add optional selective KSM enrollment plus host-owned admission/reporting, independently of snapshots.
4. Qualify backing-aware reclamation and memory pressure behavior.
5. Reconcile newer upstream full-checkpoint/CoW-memory work, then expose only operations qualified on the complete selected Linux package tuple.

No milestone requires seamless graphics or a new VMM. [PR #22](https://github.com/rybskiworks/sketchbook/pull/22) remains the separate desktop roadmap. Its statement that the consumed SDK is disk-only remains correct, but newer upstream implementation should now be considered rather than designing memory branching from scratch. [S6], [U1], [U2], [U3]

## 2. Inspected dependency graph

These identify inspected source and selected packages, not installed host state or byte-identical builds.

| Layer | Identity | Responsibility |
| :--- | :--- | :--- |
| Workestrate | `beaab036fe9fb59f132c83bdb81d443863914d9f`, main | Plans, policy, adapter and Nix composition |
| Microsandbox | `251b368a868d578ead123071c3e6bc8eec013817`, main, 0.6.18 | Cache, SDK, runtime, snapshot and control contracts |
| Native libkrun | `9c0c8b517d5685672a89a7bf6810ef9a114ec07b`, krun, msb_krun 0.1.34 | Block/memory/device primitives |
| libkrunfw | `d575b13e79368b23246be3d93d7935899dec5a3b`, krunfw | Source-built guest kernel and private device protocols |
| Patched rust-vmm | `f798d4f274db22a3c458ba756900db2cd03e6fe9`, msb-vm-memory 0.18.0-msb.1 | Mapping primitives and shared memory-crate identity |
| imago | msb-imago 0.1.5, confirmed in Microsandbox Cargo.lock | Raw/qcow2 storage and explicit open-gate behavior |
| Effective root tooling | `a403c2c111e24db64feb5748bbba939308048c07` | Workestrate package/toolchain composition |

The locked msb-imago checksum is `8563624d245da0b51b13959708758f06d1412cacdd17000b001f5ccae80cf6af`. Record the lockfile identity rather than only the manifest's compatible version range. [S2], [S10], [S17]

Workestrate makes Microsandbox's tooling input follow its root tooling. Standalone Microsandbox declares tooling `1120aa22cddf4a9a3424f38aadbebadd8a963c4b`; the same runtime source can therefore have a different effective package graph through Workestrate. Record source pins and output hashes. The source-built firmware Nix input is also distinct from the vendor submodule/prebuilt-release path. [S18], [S19]

The inspected imago and rust-vmm dependencies are not automatically rybskiworks-owned forks. Change the owner of a demonstrated missing primitive and fork/bump only when necessary. Reconcile Cargo patches at every consuming workspace root; a dependency's workspace patches are not inherited automatically. [S2], [S10]

```text
Workestrate config / plan / admission / inspect
                      |
                      v
Microsandbox SDK + durable spec + launcher + runtime
        |                    |                    |
        v                    v                    v
image/cache/snapshot      msb_krun           guest agent/bootstrap
        |                    |                    |
EROFS / ext4 / copy       block + RAM         libkrunfw kernel
                             |
                   imago + msb-vm-memory
                             |
                   host filesystem / KVM
                   host KSM / cgroups
```

These are ownership boundaries, not permissions. Guest requests do not authorize privileged host tuning.

## 3. Existing mechanisms, missing integration

| Mechanism | Inspected state | Remaining contract |
| :--- | :--- | :--- |
| Shared OCI EROFS layers | Materialization and reusable layer identity exist | Durable references, collection and measured physical reuse |
| Layered root | Existing default with immutable lower content and private changes | Workestrate policy, full attachment scope, lifecycle qualification |
| Flat root cloning | auto/copy/reflink and resolved mode already exist | Upward exposure, strict refusal, sizing/reuse compatibility |
| Block-CoW chains | Native raw/qcow2 explicit opener exists | Consumer wiring, zero/discard/flush and compaction qualification |
| Stopped snapshots | Restricted OCI-managed root path exists | Scope, consistency, flat/volume support and child ownership |
| KSM | No control in inspected native builder/mapping entry points | Selective enrollment, host admission, status and measurements |
| Reporting / virtio-mem | Native device and runtime controls exist | Backing-aware release, guest convergence and pressure behavior |
| Private RAM backing | Native MAP_PRIVATE primitive exists | Complete execution/device/identity continuation through SDK |
| Full restore / branch | Newer upstream implementation inspected | Adoption, downstream reconciliation and final Linux qualification |

Source existence, exposed API, host support, admission, activation and measured benefit are different facts. This table does not certify every combination. [S3], [S4], [S6], [S7], [S8], [S9], [S11], [S12], [S15], [S20], [U1], [U3]

### 3.1 Shared layers and Nix images

The materializer caches EROFS by uncompressed OCI diff_id, composes layered metadata by manifest, and can build flat ext4 from the verified inputs. Normal pulls reuse valid layers; target selection determines which representations are built. Extend existing locks and publication owners rather than creating another cache. [S3]

A shared NixOS OCI base can feed multiple leaves. Equal Nix paths in independently assembled images do not alone establish equal layer digests, imported-object reuse, shared extents or shared guest RAM. Measure those boundaries independently. Existing base/leaf assembly and registration are reusable inputs, not a reason to rebuild NixOS boot support. [S13]

Keep the Nix engine and guest-owned store model independent of storage sharing. Exported immutable store generations or local-overlay can be later profiles, not prerequisites. No host Nix daemon socket or live mutable host store needs to be exposed.

### 3.2 Flat reflinks: the first usable slice

Private flat-root creation already distinguishes auto, copy and reflink. Auto returns the actual mechanism; copy preserves sparsity without requiring shared extents; reflink refuses if the requested clone fails. Private growth and file synchronization precede publication. Reuse these functions instead of shelling out to cp. [S4], [S5]

Workestrate should validate against the actual source/destination pair and expose requested/effective results. Its current root_disk_mib contract does not simply accept every flat-root configuration, so preserve or explicitly migrate that contract. Reusing an existing VM reports drift, rather than silently resizing, reformatting or replacing storage. [S1], [S14]

Model reflinks separately from hardlinks and qcow dependencies. Independent reflink inodes retain filesystem extent references even if the original pathname is removed; a qcow child needs its backing objects. Metadata can still retain a reflink's base for reproducibility/export. The collector must understand why a reference exists, not treat every CoW relationship identically.

### 3.3 Native block-CoW chains

BlockBackendSpec opens caller-resolved raw/qcow2 layers from base to head, predecessors read-only and only the final head optionally writable. The imago deny gate blocks implicit backing/data-file opens from image metadata. This interface excludes VMDK, despite VMDK being used by a different image-composition path. [S7]

Qualify capacities, chain depth, exclusive writers, file identity, implicit-path refusal, flush propagation, failure latching, explicit zeros and negotiated discard behavior. A hole, an explicit zero and an OverlayFS whiteout are different operations. Arbitrary hole-punching of image metadata is not a storage-reclaim implementation.

Compaction should create a new immutable generation and switch an owned reference only after verification. Do not rewrite ancestors beneath other readers. Budget scratch space, preserve old roots for snapshots/exporters, and define crash recovery and incremental-export effects. Upstream growth/compaction work is an implementation lead, not local acceptance. [U2], [U3]

## 4. Storage ownership and consistency

Proposed lifecycle, to be reconciled with existing SDK/DB owners:

```text
staging -> verified -> published -> referenced -> retired -> collectible
    |          |           |           |
    +----------+-----------+-----------+--> crash reconciliation
```

The durable closure can include image layers, composed metadata, flat bases, sealed block ancestors, checkpoint payloads and Nix registrations. Live guests, stopped restorable instances, snapshots, import/export and in-flight child creation can retain different parts. Expired heartbeats alone cannot authorize deletion.

Required implementation invariants:

- Only the instance-owned upper or head is writable; aliases cannot reach shared bases or siblings.
- Publication never exposes partial payloads/manifests. Audit file and directory durability, not rename alone.
- Collection respects live, durable and operation references, including after controller restart.
- Immutable cache reuse does not require sharing an incompatible mutable MSB_HOME database.
- A storage-only child cold-boots. Capturing its root cannot claim capture of all attachments or external effects.
- Unsupported requested scope or consistency fails explicitly before destructive mutation.

These are requirements for #24-#26, not a report of reproduced corruption.

Every attachment needs a branch policy: private clone, shared read-only reference, explicit external exclusion or refusal. Shared writable storage needs a separate intentional contract. A source mount path is not permission to copy that attachment into every child.

Keep Nix database/registration and store paths coherent. Do not clone only the database, mutate a shared lower, or collect a lower still needed by a stopped checkpoint. Reuse the [shared-store exploration](shared-nix-store-microvm-fabric.md) and #8 for the broader lifetime model. Active OverlayFS lower mutations have kernel-level constraints. [S13], [K4]

Start stopped-only, with exclusive lifecycle/storage ownership and observed final flush. A DB status or arbitrary sleep is not writer exclusion. Sequential file reflinks of a running multi-volume service do not establish a coherent application checkpoint. Guest quiescence and atomic multi-volume scope require independent tests.

Cold clones also need identity policy for machine IDs, host keys, credential files and cached grants. Not copying RAM does not make inherited persistent authority harmless. Secret-bearing snapshots need access, retention and export controls.

## 5. KSM enrollment and host policy

KSM merges eligible duplicate private anonymous pages and makes later writes private again. It does not deduplicate clean file pagecache. Enrollment, scanner activity and measured savings are distinct; registration can succeed without useful sharing. [K1], [K2]

### 5.1 Native implementation boundary

Ordinary memory already uses private anonymous mappings. Final libkrun construction also handles private restore, borrowed kernel payloads, hotplug ranges and filesystem/GPU windows. Do not blindly enroll every GuestMemory range. [S8], [S11], [S12]

Proposed implementation:

1. Classify the final mappings after payload/private-memory replacements by ownership, kind and supported backing.
2. Apply checked, page-aligned MADV_MERGEABLE only to selected supported guest-RAM VMAs.
3. Exclude host heaps/secrets, borrowed library/firmware regions, MMIO and filesystem/GPU windows; refuse unqualified TEE/restore combinations.
4. Handle hotplug/remap and partial advice failure before admission; report eligible and enrolled bytes.
5. Return compiled support, policy admission, registration, scanner observation and measurements separately.

Libkrun owns range selection. A vm-memory helper is justified only for a reusable safe primitive; Workestrate must not manipulate pointers. Avoid process-wide merging as a shortcut because the VMM also stores unrelated host allocations. Inspect inherited process/service merging policy and normalize or refuse incompatible broad enrollment for strict profiles.

### 5.2 The host, not an app guest, owns scanning

The kernel running the VMM owns scanner controls. On a normal host this is outside libkrunfw; with an L1 workload host it can be L1 scanning L2 VMM RAM. Also account for L0 enrollment of the outer domains. This placement follows the host-process memory model. [K1], [S11]

Do not let a workload start ksmd, write global sysfs, change THP or alter overcommit. An opt-in operator-owned NixOS module can establish prerequisites; doctor reports them read-only. Firmware work is guest-feature qualification, not enabling CONFIG_KSM inside every app image.

### 5.3 No fictional merge-group security

The documented interface provides range enrollment and global scanner settings, including a NUMA choice, not arbitrary isolated pools for fleet names, UIDs or cgroups. Do not advertise a trust_group string as enforcing that boundary. [K1], [K3]

Proposed admission must account for all enrolled workloads on the kernel. Separate appropriately configured host kernels or no cross-cohort enrollment are options when independent security domains require it. Check outer-host enrollment too. Treat content-equality sharing and potential timing observability as threat-model inputs, not a guarantee that VM isolation removes side channels.

A compromised VMM with permission to change mapping advice is not constrained by a TOML deny. Host confinement owns that authority; compose with #19 rather than claim a builder option alone enforces hostile-process policy.

### 5.4 Disable and pressure semantics

Stopping scanning does not undo merged pages; unmerging can require substantial memory and fail or trigger pressure. Prefer create-time participation changes initially. No per-workload cleanup should perform global unmerge. [K1]

Budget private growth even when current sharing is high. KSM is an optimization, not a memory reservation. A workload dirtying previously shared pages still needs a defined budget and failure policy; do not admit extra guests solely on an expected deduplication ratio.

## 6. Free-page reclaim and memory targets

Reporting and virtio-mem control already exist. Extend them rather than create an unrelated balloon daemon. Target/current/max represent different convergence stages; none alone proves physical host reclaim. [S9], [S15]

Backing-aware behavior is the key audit. The free-page path uses MADV_DONTNEED and private restore uses MAP_PRIVATE files. Construction already refuses a private-memory/NUMA combination pending backing-aware support. Test release/refault, promised zeroing, unplug/replug and capture tracking for each backing; do not assume identical semantics. [S8], [S11], [S15], [K2]

This is not a reproduced vulnerability. Build regression evidence for the exact path and promised guest semantics first; refuse combinations that cannot satisfy them. Qualify actual firmware configuration, negotiated devices and observed reporting/offlining before adding kernel patches.

A guest can delay or refuse memory offlining. Use bounded convergence, floors/ceilings and hysteresis. Host cgroup enforcement remains separate from guest cooperation. Host THP, guest THP, NUMA, swap and KSM need individual measurements before combined tuning is advertised. [S9], [K2], [K3]

## 7. Newer upstream adoption track

States inspected on 2026-09-13: these PRs were merged on September 10 into named stacked development branches. That does not prove inclusion in the selected downstream runtime.

| PR | Inspected head | Merge target | Relevant implementation |
| :--- | :--- | :--- | :--- |
| [#1503][U1] | `ca6ae47ea359cd2ebcf4c6da6ae024a36612f20d` | `appcypher/composite-checkpoint-pr` | Full capture/eager restore, disk-only restore, checkpoint/runtime filesystem state |
| [#1533][U2] | `3645a5d2c36529ca2d973b4011ac94a53f032038` | `appcypher/checkpoint-restore-clone` | Live/stopped private root growth, recovery fencing and captured capacities |
| [#1537][U3] | `df385fc6e4b4a7c11ba4907fa548a7056ee2b36d` | `appcypher/live-root-disk-growth` | Resident pause/resume, private-memory restore, direct branch, grouping/export/compaction |

The #1537 snapshot source was inspected as well as its description. Typed closure/capture and source-recovery code establishes a concrete adoption track. Meanwhile the consumed SDK still explicitly rejects resumable snapshots. [S6], [U4]

The newer stack cites native 0.1.35, msb-vm-memory 0.18.0-msb.2 and msb-imago 0.1.7, with package-patching and SDK-name changes. Reconcile downstream mount, CID, SSH, init and Nix deltas before updating pins. Review actual ancestry/diffs and memory-crate identity; do not blindly remove downstream patches because upstream removed its development patches. [U2], [U3]

Full restore requires RAM, CPU/interrupt/timer state, device queues, filesystem handles, disk/memory generations and activation ordering to agree. A native private mapping or ordinary OS fork of a multithreaded VMM is not that contract. Qualify the final integrated Linux x86_64 build; upstream historical platform reports are not tests rerun here.

Canonical immutable RAM objects privately mapped by multiple children have different pagecache behavior from separate reflinked inodes. Verify physical RAM sharing separately from disk sharing. Read-only descriptors alone do not prevent another writer from mutating or truncating backing files; enforce publication ownership throughout their lifetime. [S8]

Refresh instance/launch/grant identity, CIDs, endpoints and approved RNG/time generation state. Reauthorize credentials/connections and reject unqualified graphics, passthrough, published-port or nested-device combinations. Never disguise a cold disk boot as live continuation.

Respect upstream limitations for disk-only incremental exports and new baselines after compaction. Restoring local state cannot reverse external actions. Yggdrasil can later consume the primitives without making Workestrate own model-specific search policy. [U3]

## 8. Proposed upward contract

This is illustrative design, not current valid Workestrate syntax. Reuse existing types and compatibility rules when selecting final names.

```toml
# PROPOSED ONLY, not an executable current fleet configuration.
[workloads.example.storage.root]
layout = "flat"       # alternatively, existing layered representation
clone = "reflink"     # strict; auto may resolve to sparse copy

[workloads.example.memory_policy]
ksm = "off"           # proposed off / prefer / require
```

Root sizing must reconcile with root_disk_mib, not add a competing value. Clone policy applies only to supported layouts. Resolve base identity through the ordinary pinned image declaration, not arbitrary untrusted host paths.

| Record category | Proposed facts |
| :--- | :--- |
| Storage | Image/materializer identity, root layout, ancestors, writable owner, requested/effective clone method, capacity |
| Lifecycle | Instance/launch/operation IDs, durable references, checkpoint parent, capture scope and consistency |
| Memory | Boot/target/current/max, backing type, KSM admission/enrollment, scanner observation, sharing/reclaim measurements |
| Qualification | Runtime/firmware/tooling tuple, host support, refusal/degradation reason, evidence identity |

A single supports_cow boolean cannot represent those differences. A backend can support reflink provisioning but not flat snapshots, or KSM enrollment but not private-memory continuation.

Persist declared topology and ownership, not host pointers, reusable live descriptors or bearer secrets in public plans. Decide hash membership explicitly; current nested-policy hash exclusions are not automatically appropriate for disk format, writable ownership or device topology. [S1]

Use required launch capabilities so an old runtime refuses unsupported required behavior before mutation rather than silently ignoring a field. Existing-instance skew remains visible and non-destructive. [S16]

## 9. Implementation packages and dependency graph

The Microsandbox and libkrun fork trackers are disabled, so their tasks are coordinated here with explicit component owners. No repository settings were changed.

| ID | Deliverable | Owner | Issue |
| :--- | :--- | :--- | :--- |
| C01 | Selected graph, formats and effective build identities | Microsandbox + Workestrate | [#23](https://github.com/rybskiworks/sketchbook/issues/23) |
| C02 | Existing root layout and clone policy exposure | Workestrate | [workestrate #40](https://github.com/rybskiworks/workestrate/issues/40) |
| C03 | Immutable closures, leases and conservative GC | Microsandbox cache/SDK | [#24](https://github.com/rybskiworks/sketchbook/issues/24) |
| C04 | Stopped disk checkpoints and private volumes | Microsandbox + Workestrate | [#25](https://github.com/rybskiworks/sketchbook/issues/25) |
| C05 | Block-CoW wiring and zero/discard/flush tests | libkrun + imago + runtime | [#26](https://github.com/rybskiworks/sketchbook/issues/26) |
| C06 | New-generation compaction and growth recovery | Runtime/image/block backend | [#26](https://github.com/rybskiworks/sketchbook/issues/26), upstream #1533/#1537 |
| C07 | Selective KSM enrollment and SDK/launch wiring | libkrun + Microsandbox | [#27](https://github.com/rybskiworks/sketchbook/issues/27) |
| C08 | KSM admission/status and host-owner boundary | Workestrate + opt-in host module | [workestrate #41](https://github.com/rybskiworks/workestrate/issues/41) |
| C09 | Backing-aware reclaim and bounded convergence | libkrun/runtime/firmware | [#28](https://github.com/rybskiworks/sketchbook/issues/28) |
| C10 | Upstream full-state CoW adoption | Runtime/dependency graph | [#29](https://github.com/rybskiworks/sketchbook/issues/29) |
| C11 | Branch identity and activation fencing | Runtime + Workestrate broker | [#29](https://github.com/rybskiworks/sketchbook/issues/29), workestrate #39 |
| C12 | Physical accounting and fault/conformance harness | Native -> SDK -> Workestrate | [#30](https://github.com/rybskiworks/sketchbook/issues/30) |

```text
C01 -> C02                              first usable storage-policy slice
C01 -> C03 -> C04 -> C05 -> C06          durable disk branches and compaction
C01 -> C07 -> C08                       KSM, independent of snapshots
C01 -> C09                             reclaim/pressure qualification
C03 + C04 + C05 + C09 -> C10 -> C11      full execution-state branching
C12 accompanies every slice            tests belong to each acceptance gate
```

Early C04 can use stopped layered-root snapshots; advanced flat/block-chain capture follows separately. This avoids circular dependencies around basic storage validation.

Represent accepted slices in each owner's existing Beads graph with these URLs and actual prerequisites. GitHub issue creation is not a claim that Beads was updated. Do not initialize or migrate tracker databases as part of planning.

Reuse #8 for store lifetime, #7 for branching taxonomy, #17/#19 for compartment/confinement work and workestrate #39 for generic capabilities. None is closed by this document.

## 10. Qualification and physical accounting

Implement #30 with already-built runtime/image inputs, sanitized private HOME/MSB_HOME and bounded scratch resources. Reuse nix-tooling's opt-in NixOS runner shape without introducing a tooling-to-runtime dependency cycle. [S13]

| Experiment | Positive evidence | Negative/control |
| :--- | :--- | :--- |
| Layered siblings | Shared base composition, private writes, restart | Whiteouts/renames leave sibling and lower unchanged |
| Flat clones | Effective mode matches strict request or declared auto fallback | Unsupported strict reflink leaves no admitted partial instance |
| Snapshot scope | Contents and consistency match manifest | Excluded binds/volumes are not reported as restored |
| Block chain | Correct parent reads, child writes/zeros/flushes | Missing/malformed/implicit backing refuses before writable launch |
| Publish/GC | Live and durable closures stay readable | Crash cannot expose partial artifacts or collect required bases |
| KSM | Touched matching nonzero RAM shares after observation | Off/unique/churn cohorts and later private writes |
| Reclaim | Touched RAM released, measured, safely reused | Guest refusal, incompatible backing, zero-only false savings |
| Full branch | In-RAM counter continues, source survives, children diverge | Disk child cold-boots; stale authority/unsupported devices refuse |

Measure provisioning/boot/application-ready latency, pause time, storage I/O, dirty growth and failures. Disk accounting needs filesystem-specific exclusive/shared extents or isolated whole-fixture allocation; summed per-file blocks can count shared extents twice. RAM accounting should distinguish RSS, PSS, private/shared mappings, cgroup charges, host pressure and KSM observations. No single number universally expresses total physical cost. [S4], [K1], [K3]

Use matching nonzero data, unique/changing data and real workload phases. Empty demand-paged memory and sparse files are baselines, not useful application-sharing evidence. Do not count unrelated global KSM activity as this fleet's savings. Preserve unsupported/unavailable states, repetitions and raw bounded evidence.

Keep cold/warm conditions explicit. No global cache dropping, destructive GC, filesystem creation or KSM activation without an authorized disposable fixture. Exercise ENOSPC/EIO, concurrent creators/writers, interrupted publication/compaction, failed thaw, stale grants, lost controllers and guest refusal to offline pages. No fixed density/performance ratio is justified before measurement.

## 11. First milestone and boundaries

Start with **workestrate #40**: expose the existing layout/clone policy, preserve defaults, and return truthful requested/effective records, backed by two-sibling tests. It can land without KSM or full-memory adoption.

Then qualify durable storage ownership and checkpoints through #24/#25, advanced block chains through #26, and selective KSM through #27 plus Workestrate #41. Complete #28 before claiming safe dense private-memory restore; adopt #29 only after reviewing the real upstream stack and preserving downstream contracts.

Dependency updates, host-generation switches and active-state migrations remain separate reviewed operations. This document and its issues contain no deployment, host tuning, reproduced benchmark or promise of a target sharing ratio.

## Source map

Repository links are pinned where behavior was inspected. Upstream PR links supply inspection-time status and revision-scoped author reports; their status can change.

[S1]: https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/control/agentctl/src/microsandbox/plan.rs
[S2]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/Cargo.toml
[S3]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/crates/image/MATERIALIZATION.md
[S4]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/sdk/rust/lib/sandbox/flat_rootfs.rs
[S5]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/crates/utils/lib/copy.rs
[S6]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/sdk/rust/lib/snapshot/create.rs
[S7]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/devices/src/virtio/block/backend.rs
[S8]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/vmm/src/private_memory.rs
[S9]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/crates/runtime/lib/control.rs
[S10]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/devices/Cargo.toml
[S11]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/vmm/src/builder.rs#L2747-L2995
[S12]: https://github.com/superradcompany/rust-vmm/blob/f798d4f274db22a3c458ba756900db2cd03e6fe9/vm-memory/src/mmap/unix.rs#L45-L255
[S13]: https://github.com/rybskiworks/nix-tooling/blob/a403c2c111e24db64feb5748bbba939308048c07/docs/nixos-oci-images.md
[S14]: https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/docs/runtime-provisioning.md
[S15]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/devices/src/virtio/balloon/device.rs
[S16]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/COMPATIBILITY.md
[S17]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/Cargo.lock#L4394-L4410
[S18]: https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/flake.nix
[S19]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/flake.nix
[S20]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/krun/src/api/builders.rs
[U1]: https://github.com/superradcompany/microsandbox/pull/1503
[U2]: https://github.com/superradcompany/microsandbox/pull/1533
[U3]: https://github.com/superradcompany/microsandbox/pull/1537
[U4]: https://github.com/superradcompany/microsandbox/blob/df385fc6e4b4a7c11ba4907fa548a7056ee2b36d/sdk/rust/lib/snapshot/create.rs
[K1]: https://www.kernel.org/doc/html/latest/admin-guide/mm/ksm.html
[K2]: https://man7.org/linux/man-pages/man2/madvise.2.html
[K3]: https://docs.kernel.org/admin-guide/cgroup-v2.html
[K4]: https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html

[QEMU memory-backend merge](https://www.qemu.org/docs/master/system/qemu-manpage.html) is a separate existing API reference, not an additional backend requirement.
