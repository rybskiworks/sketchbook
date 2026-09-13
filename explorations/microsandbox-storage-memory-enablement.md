# Microsandbox storage CoW and memory-efficiency enablement

[Catalogue](README.md) | [Parent tracker #23](https://github.com/rybskiworks/sketchbook/issues/23) | [Workstation seed](compartmentalized-nixos-architecture-seed.md)

**Status:** implementation roadmap and issue decomposition, not an implemented feature release.

**Inspection date:** 2026-09-13. **Initial target:** Linux x86_64. **Scope:** Microsandbox, the dependencies it actually consumes, and upward integration into Workestrate. Storage sharing comes first. KSM, free-page reclamation and complete execution-state CoW restore have separate contracts and milestones.

**Evidence boundary:** source inspection and upstream PR metadata/code are evidence here; no Nix/Cargo build, VM boot, KSM activation, filesystem benchmark or live-state change was performed. Tests described below are acceptance requirements, not measured results. A container attempt to obtain a Git checkout failed because it could not resolve github.com, and /dev/kvm was unavailable. The canonical repository unit/docs checks were not run in that environment.

## 1. Decision summary

Do not start by implementing a new copy engine or a new hypervisor. The consumed stack already has reusable immutable image layers, private flat-root cloning with explicit reflink policy, native raw/qcow2 dependency chains, private file-backed guest RAM, free-page reporting, and runtime memory targets. The missing product is a coherent, observable ownership and policy contract connecting these mechanisms to Workestrate. [S2][S3][S4][S5][S7][S8][S9]

Recommended delivery order:

1. Expose existing layered/flat root and clone choices through Workestrate, preserving omitted defaults.
2. Qualify immutable-base lifetime, stopped disk checkpoints, private child volumes, safe collection and explicit block-chain behavior.
3. Add optional range-selective KSM enrollment plus host-owned admission and reporting. This can proceed independently of checkpoint work.
4. Qualify backing-aware memory reclamation and pressure behavior.
5. Reconcile the newer upstream full-checkpoint/CoW-memory stack, then expose only the operations actually qualified on the selected Linux package tuple.

There is no dependency on seamless GUI integration or on adopting a different VMM. The [earlier enablement PR #22](https://github.com/rybskiworks/sketchbook/pull/22) remains a separate desktop roadmap. Its statement that the consumed snapshot SDK is disk-only remains correct, but newer upstream implementation must now be considered rather than designing memory branching from scratch. [S6][U1][U2][U3]

## 2. Exact inspected dependency graph

These are source/package identities, not proof of installed host state or byte-identical builds.

| Layer | Selected identity | Relevance |
| :--- | :--- | :--- |
| Workestrate | `beaab036fe9fb59f132c83bdb81d443863914d9f`, main | Plans, policy, runtime adapter, Nix composition |
| Microsandbox | `251b368a868d578ead123071c3e6bc8eec013817`, main, 0.6.18 | Image cache, SDK, runtime process, snapshot and control contracts |
| Native libkrun | `9c0c8b517d5685672a89a7bf6810ef9a114ec07b`, krun, msb_krun 0.1.34 | Memory mappings, block layers, devices, low-level restore |
| libkrunfw | `d575b13e79368b23246be3d93d7935899dec5a3b`, krunfw | Source-built guest kernel and private device protocols |
| Patched rust-vmm | `f798d4f274db22a3c458ba756900db2cd03e6fe9`, msb-vm-memory 0.18.0-msb.1 | Shared memory-crate identity and mapping primitives |
| imago | msb-imago 0.1.5, registry dependency of native devices | Raw/qcow2 storage and explicit open-gate behavior |
| Effective root tooling | `a403c2c111e24db64feb5748bbba939308048c07` | Workestrate-owned package/toolchain composition |

Workestrate makes the Microsandbox tooling input follow its root tooling. Standalone Microsandbox declares tooling `1120aa22cddf4a9a3424f38aadbebadd8a963c4b`; importing the same Microsandbox source through Workestrate can therefore use a different effective package graph. Preserve both source revisions and output hashes in qualification reports. [S1][S2]

The firmware Nix input is distinct from the upstream vendor submodule/prebuilt-release route. Likewise, the inspected imago and rust-vmm dependencies are not automatically rybskiworks-owned forks. Patch the owner of the missing primitive, and fork or bump only when necessary. Cargo workspace patches must be reconciled at each consuming root; they are not inherited merely because a dependency workspace declares them. [S2][S10]

```text
Workestrate config / plan / admission / inspect
                  |
                  v
Microsandbox SDK + durable spec + launcher + runtime
      |                    |                    |
      v                    v                    v
image/cache/snapshot    native msb_krun      guest agent/bootstrap
      |                    |                    |
EROFS / ext4 / copy     block + memory       libkrunfw kernel
                           |
                 imago + msb-vm-memory
                           |
                  host filesystem / KVM
                  host KSM / cgroups
```

The arrows are responsibility boundaries. A guest cannot authorize global host memory tuning, and a declarative desired state is not evidence of an active capability.

## 3. What already exists, and what each mechanism means

| Mechanism | Inspected status | Sharing unit | What it does not establish |
| :--- | :--- | :--- | :--- |
| Shared OCI EROFS layers | Implemented materialization contract | Immutable layer objects reused across image compositions | Shared physical guest RAM or a complete collector |
| Layered root with private writable state | Existing default image mode | Immutable lower content, scoped changes | A backup of external mounts or a mutable shared Nix store |
| Flat root, clone=auto/copy/reflink | Implemented private-root provisioning | Whole private file; reflink may share filesystem extents | Every filesystem supports reflink, or every clone shares extents |
| Explicit block-CoW chain | Native raw/qcow2 opener exists | Read-only ancestors plus writable head | Complete SDK lifecycle, safe compaction, or implicit path trust |
| Stopped root snapshot | Consumed SDK supports a restricted OCI path | Captured managed writable root | Live processes, all volumes, or arbitrary root formats |
| KSM | No control found in inspected native builder/mapping entry points | Eligible identical private anonymous pages | Instant savings, isolated named merge pools, or a VM fork |
| Free-page reporting / virtio-mem | Native device and runtime state/control exist | Guest-released or unplugged RAM | Guaranteed guest cooperation or immediate host reclaim |
| Private memory backing | Native mapping primitive exists | Immutable file-backed RAM with private writes | Complete CPU/device/identity restoration through consumed SDK |
| Full restore / direct memory branch | Newer upstream implementation inspected | Disk + RAM + execution/device/runtime state | Inclusion in the downstream pin or qualification of every device |

This table is not a claim that every listed combination works. Source existence, exposed API, host support, admission, runtime activation and measured benefit must remain separate. [S3-S9][S11][S12][U1-U3]

### 3.1 Layer reuse is already an important storage optimization

The materialization pipeline verifies and caches EROFS by uncompressed OCI diff_id, composes layered metadata by manifest, and can build a flat ext4 artifact from the same verified inputs. Normal pulls reuse valid layers; materialization targets choose which representations to create. The documented locking/publication paths should be extended, not replaced with another cache. [S3]

A common NixOS OCI base can feed many leaves. However, equal Nix store paths in two independently built images do not alone prove equal OCI layer digests, shared imported objects, shared host extents, or shared guest pagecache. Measure each boundary. The existing nix-tooling base/leaf and registration contract is useful input; it is not a reason to rewrite NixOS boot support. [S13]

For the first release, keep the Nix engine and existing guest-owned store model independent of storage sharing. An experimental local-overlay store or exported immutable /nix/store generation may be a later profile, not a requirement. Do not expose the host Nix daemon socket to obtain convenience or sharing.

### 3.2 Flat reflink roots are an available first implementation slice

The private flat-root function already supports three distinct requests: auto chooses reflink or sparse copy and returns the resolved mode; copy explicitly copies sparsely; reflink refuses when cloning fails. Growth occurs on the private temporary copy before file synchronization and publication. Reuse this implementation rather than shelling out to cp. [S4][S5]

The useful Workestrate change is to expose these choices, validate them against the actual source/destination filesystem pair, and report the result. Preserve the existing root_disk_mib contract or migrate it explicitly: its current documented scope does not simply accept every flat-root configuration. Existing-instance reuse must report drift rather than change storage behind the user's back. [S1][S14]

A reflink is not a hardlink: each child needs an independent inode and writable ownership. Filesystem extent references can survive removal of the source name. By contrast, a qcow child still needs its backing objects. The retention graph must distinguish those dependency types instead of assuming every CoW mechanism has the same parent-lifetime requirement. This is a proposed lifecycle invariant for #24/#25, not a claim that a new collector has been implemented.

### 3.3 Native block layering exists, but deserves its own correctness gate

BlockBackendSpec already opens caller-resolved raw/qcow2 layers in base-to-head order. Predecessors are read-only, the head may be writable, and the imago deny gate prevents header metadata from introducing implicit backing/data-file opens. The explicit-chain path excludes VMDK; this must not be confused with the image pipeline's separate VMDK composition. [S7]

Qualify the missing consumer paths and semantics: capacities, depth, exclusive writers, immutable ancestors, flush propagation, failure latching, explicit zeros, negotiated discard behavior and crash-safe generation publication. A qcow hole, an explicit zero and a deleted upper-layer file are not interchangeable concepts. Do not reclaim storage by punching arbitrary holes in an image format's metadata.

Compaction should publish a new immutable generation and atomically retarget an owned reference after verification. It must not rewrite a shared ancestor under surviving children. It also needs scratch-space admission, interrupted-operation recovery and rules for incremental exports. Upstream growth/compaction work is a starting point, not a promise that all these properties are already qualified locally. [U2][U3]

## 4. Storage ownership contract to implement

The following state machine is proposed. Reconcile it with current SDK/DB/image ownership rather than layering a second independent database on top.

```text
staging -> verified -> published -> referenced -> retired -> collectible
    |          |           |           |
    +----------+-----------+-----------+--> recover/reconcile after crash
```

A published object records its immutable identity and closure. A live runtime, stopped restorable instance, snapshot, export/import, compaction or pending child creation can retain different parts of that closure. A missing heartbeat is not proof that all references have vanished.

### 4.1 Required invariants

- Only the active private head or upper is writable. The runtime cannot mutate a shared base or a sibling through an alias.
- Publication cannot expose a partial payload or manifest. Review file and directory durability, not rename alone.
- GC cannot collect an object still needed by an admitted operation, live instance or durable restoration reference.
- A runtime-version state directory and a reusable immutable cache are different objects. Sharing one must not silently share the other's mutable DB.
- A storage-only child starts a fresh execution instance. Capturing a root filesystem alone cannot claim capture of all volumes or external effects.
- Any requested consistency level or scope not implemented by the backend must fail explicitly.

These are implementation requirements with positive and negative tests in #24-#26, not findings of demonstrated corruption in the current code.

### 4.2 Root, volumes and Nix state

Define branch policy for every attachment: clone privately, share read-only, exclude as an external resource, or reject. Shared writable volumes require a distinct intentional contract. A path merely being mounted in the source is not permission to mount it in every child.

For Nix, registration/database state must remain coherent with its store paths. Cloning only a database, sharing a live mutable lower, or losing the lower generation while a stopped snapshot still references it is invalid. The [shared-store exploration](shared-nix-store-microvm-fabric.md) and #8 own the broader lifetime research; this roadmap owns its runtime implementation edges. Underlying filesystem mutations beneath active OverlayFS mounts are constrained by the kernel contract. [S13][K4]

Start with cleanly stopped capture under exclusive lifecycle/storage ownership. A sequence of individual file reflinks from a running multi-volume workload does not establish a coherent application checkpoint. Add bounded guest quiescence and multi-volume capture only with explicit consistency evidence.

Cold clones also need identity policy. Persistent machine IDs, host keys, credential files and cached grants cannot be treated as harmless because RAM was not copied. Separate base content from per-instance identity and broker authorization.

## 5. KSM: native enrollment, host policy, and honest limits

KSM finds duplicate eligible private anonymous pages and write-protects shared results; later writes become private again. It does not deduplicate clean file pagecache. Enrollment and scanner activity are distinct, and registration alone can succeed without useful sharing. [K1][K2]

### 5.1 Correct implementation seam

The inspected vm-memory constructor already provides private anonymous mappings. In libkrun, final memory construction also handles private restore, borrowed kernel payloads, hotplug regions and filesystem/GPU windows. Therefore an indiscriminate loop over every guest address range is not the desired implementation. [S8][S11][S12]

Proposed native behavior:

1. Classify final host mappings by kind, ownership and supported backing after any payload/private-memory replacement.
2. Enroll only selected guest-RAM VMAs with checked page boundaries and explicit failure handling.
3. Exclude host heaps and broker/network secrets, borrowed library/firmware mappings, device windows, and unqualified TEE/restore combinations.
4. Apply the same classification to verified hotplug/remap paths; report eligible and enrolled bytes.
5. Return capability/admission facts separately from scanner status and measured sharing.

The optional lower-level vm-memory helper should exist only if it cleanly expresses a reusable safe primitive. Libkrun owns which guest ranges are eligible; Workestrate must not manipulate host pointers itself.

Avoid process-wide merging as a shortcut: the VMM also owns host allocations unrelated to guest RAM. Inspect inherited process/service merging policy, and reject or deliberately normalize incompatible inherited state before admitting a strict configuration. A missing field in a launcher JSON document must not silently enable a default-on behavior.

### 5.2 Host and nested-host responsibility

The kernel running the VMM owns the KSM scanner and controls. For ordinary application VMs this is the physical host, not libkrunfw inside the application guest. In a nested topology the L1 workload-host kernel can scan its L2 VMM mappings. The proposed host policy must also account for whether L0 enrolls the outer L1 domains. This is a placement consequence of the host-process memory model. [K1][S11]

Keep privileged scanner tuning outside per-workload requests. The generic runtime must not write sysfs, switch host THP policy or alter global overcommit. An opt-in operator-owned NixOS module can establish the host prerequisites; doctor can report them read-only.

### 5.3 Security admission is not a named merge pool

The documented KSM interface provides range enrollment and global scanner controls, including a NUMA merging choice. It does not expose arbitrary per-fleet, UID or cgroup merge namespaces. Therefore this roadmap must not advertise a `trust_group` string as enforcement of an isolated pool. [K1][K3]

Proposed admission should allow only an explicitly approved cohort on a kernel where that boundary can be enforced. Separate host kernels or disabled enrollment across cohorts are alternatives when independent security domains are required; verify the outer-host policy too. Treat content-equality sharing and its potential timing observability as threat-model inputs, not as a guarantee that memory isolation alone eliminates side channels.

A compromised VMM able to change its own mapping advice is not constrained merely by a TOML deny. The host launcher/confinement policy must own that authority. This work should compose with #19 rather than claim that a new builder option hardens a malicious host process.

### 5.4 Disable and pressure behavior

Stopping scanning does not undo existing shared pages. Unmerging can require substantial memory and fail or trigger pressure. For the first implementation, prefer create-time participation changes rather than inventing a transparent live rollback. No per-workload cleanup should invoke a global unmerge. [K1]

Budget for private growth even when observed sharing is high. KSM is an optimization, not a reservation system. A VM which dirties previously shared pages must still have a defined resource-limit and recovery contract; do not launch additional guests solely on an expected deduplication ratio.

## 6. Free-page reclamation is a separate capability

The stack already has free-page reporting and virtio-mem control. Extend their qualification instead of adding an unrelated generic balloon daemon. Target/current/max memory fields represent different stages of convergence; none alone proves that host physical pages were reclaimed. [S9][S15]

Backing-aware behavior is the central audit requirement. The current free-page path uses MADV_DONTNEED, while private-memory restore uses MAP_PRIVATE files. Memory construction already rejects a private-memory/NUMA combination pending backing-aware behavior. Test release/refault, zeroing, unplug/replug and capture accounting for each supported backing; do not assume an anonymous mapping and an immutable-image mapping behave identically. [S8][S11][S15][K2]

This is not a reproduced vulnerability report. First construct a failing or passing regression for the exact path and its promised guest semantics. Where a combination cannot satisfy them, explicit unsupported behavior is preferable to unsafe apparent compatibility.

The firmware work is role qualification: actual built configuration, negotiated guest devices and observed reporting/offlining. Enabling KSM in libkrunfw is not a host-memory deduplication solution. Avoid adding kernel options until a missing prerequisite is demonstrated.

A memory target can be delayed or refused by the guest, especially with pages that cannot be offlined. Use bounded convergence, explicit floors/ceilings and hysteresis. Host cgroup enforcement and admission remain separate from guest cooperation. Host THP, guest THP, NUMA, swap and KSM should be tested as distinct controls before combinations are advertised. [S9][K2][K3]

## 7. Newer upstream work to adopt, not recreate

The following PR states were inspected on 2026-09-13. All three were merged on September 10 into named stacked development branches. Their status does not establish that Workestrate's selected fork includes them.

| PR | Inspected head | Merge target | Relevant work |
| :--- | :--- | :--- | :--- |
| [Microsandbox #1503][U1] | `ca6ae47ea359cd2ebcf4c6da6ae024a36612f20d` | `appcypher/composite-checkpoint-pr` | Full capture/eager restore, disk-only restore, checkpoint closure and runtime filesystem state |
| [Microsandbox #1533][U2] | `3645a5d2c36529ca2d973b4011ac94a53f032038` | `appcypher/checkpoint-restore-clone` | Live/stopped private root growth, recovery fencing and captured capacities |
| [Microsandbox #1537][U3] | `df385fc6e4b4a7c11ba4907fa548a7056ee2b36d` | `appcypher/live-root-disk-growth` | Resident pause/resume, private-memory restore, direct branching and snapshot grouping/export/compaction |

The #1537 snapshot implementation was inspected in addition to its description. Its typed capture/closure and source-recovery machinery demonstrate a concrete implementation track, not merely a feature request. The consumed SDK still rejects resumable snapshots. Preserve both facts. [S6][U4]

### 7.1 Adoption hazards to resolve

The newer stack cites native 0.1.35, msb-vm-memory 0.18.0-msb.2 and msb-imago 0.1.7. It also changes package patching and public SDK names. Reconcile all downstream mount, CID, SSH, init and Nix packaging changes before moving pins. A seemingly small consumer change can otherwise select incompatible memory types or runtime/private protocol versions. [U2][U3]

Treat implementation as dependency-ordered slices, not one blind PR cherry-pick. Inspect ancestry and actual diffs; qualify the final integrated Linux x86_64 build. Upstream historical platform reports are useful evidence to reproduce, but not tests run here or proof of every final revision. No universal latency/density improvement is asserted.

Private-memory mapping is only one part of full restoration. CPU/interrupt/timer state, device queues, filesystem handles, immutable disk/memory generations, transport reconnection and activation ordering must agree. A normal OS fork of a multithreaded VMM process is not a substitute for this contract.

Clean memory sharing also depends on object identity. Canonical immutable RAM files privately mapped by multiple children provide a different host pagecache relationship from separate reflinked file inodes. Verify physical memory behavior, not just storage sharing. The native read-only descriptor contract requires the backing to remain unmodified by other writers throughout use. [S8]

Reauthorize child identity, CID, endpoints, credentials and external connections. Firmware generation/RNG/time hooks are prerequisites to test, not proof every application reinitializes safely. Reject unsupported graphics, passthrough, published-port or nested-device combinations rather than downgrade a requested live continuation to a disk boot.

Respect the newer stack's stated limitations, including disk-only incremental-export lineage and new baselines after compaction. Restoring execution never rolls back a remote Git push, payment or other external effect. Yggdrasil can use these primitives later without putting model-specific branching decisions inside Workestrate. [U3]

## 8. Proposed upward-facing contract

This section is a design sketch, not valid current Workestrate syntax. Final names must reuse existing types and compatibility conventions.

```toml
# PROPOSED ONLY. Do not paste into a current fleet expecting support.
[workloads.example.storage.root]
layout = "flat"            # alternative: existing layered representation
clone = "reflink"          # strict; auto may resolve to sparse copy

[workloads.example.memory_policy]
ksm = "off"                # proposed: off, prefer, require
```

Root capacity must integrate with the existing root_disk_mib declaration rather than silently define a competing value. `clone` is meaningful only for supported layouts. Image identity is resolved from the normal pinned image declaration; do not turn arbitrary host paths into trusted bases.

The effective record should carry these separately:

| Category | Proposed facts |
| :--- | :--- |
| Image/storage | Immutable image ID, materializer ABI, root layout, base/ancestor IDs, writable owner, requested/resolved clone method, capacity |
| Lifetime | Instance and launch IDs, operation ID, durable reference set, parent/checkpoint identity, capture scope and consistency |
| Memory | Boot/target/current/max, backing kind, KSM request/admission/enrolled ranges, scanner observation, sharing/reclaim measurements |
| Qualification | Exact runtime/firmware/tooling tuple, host support, policy refusal/degradation reason, test evidence generation |

Do not make `supports_cow = true` stand in for this model. A backend may support reflink provisioning but not flat snapshots, or KSM enrollment but not private-memory restore.

Persist declared topology and ownership; do not persist host pointers, reusable live descriptors or bearer secrets in a public plan. Decide configuration-hash membership explicitly. Workestrate's current nested policy hash exclusions are not automatically appropriate for disk format, writable ownership or device topology. [S1]

Use the existing launch-capability refusal mechanism for required native behavior. Old runtimes must refuse before interpreting an unsupported security/storage setting, rather than ignore a new optional JSON field. Desired/effective skew on reuse must remain visible and non-destructive. [S16]

## 9. Work packages and issue graph

Each issue includes implementation locations, specific changes and positive/negative tests. Lower-level work is coordinated in sketchbook because the Microsandbox and libkrun fork trackers are disabled; no repository settings were changed. Implementation ownership remains with those components.

| ID | Deliverable | Owner | Tracking |
| :--- | :--- | :--- | :--- |
| C01 | Inventory selected graph, formats and effective build identities | Microsandbox + Workestrate | [#23](https://github.com/rybskiworks/sketchbook/issues/23) |
| C02 | Expose existing layered/flat/clone policy | Workestrate adapter | [workestrate #40](https://github.com/rybskiworks/workestrate/issues/40) |
| C03 | Immutable closure, leases and conservative GC | Microsandbox cache/SDK | [#24](https://github.com/rybskiworks/sketchbook/issues/24) |
| C04 | Stopped disk checkpoints and private child volumes | Microsandbox + Workestrate | [#25](https://github.com/rybskiworks/sketchbook/issues/25) |
| C05 | Block-chain exposure, zero/discard/flush qualification | libkrun + imago + runtime | [#26](https://github.com/rybskiworks/sketchbook/issues/26) |
| C06 | New-generation compaction and growth recovery | Runtime/image + block backend | [#26](https://github.com/rybskiworks/sketchbook/issues/26), upstream #1533/#1537 |
| C07 | Selective KSM native enrollment and SDK/launch wiring | libkrun + Microsandbox | [#27](https://github.com/rybskiworks/sketchbook/issues/27) |
| C08 | KSM policy/admission/status and host-owner boundary | Workestrate + opt-in host module | [workestrate #41](https://github.com/rybskiworks/workestrate/issues/41) |
| C09 | Backing-aware release and bounded memory convergence | libkrun/runtime/firmware | [#28](https://github.com/rybskiworks/sketchbook/issues/28) |
| C10 | Upstream full-state CoW restoration adoption | Runtime and selected dependency graph | [#29](https://github.com/rybskiworks/sketchbook/issues/29) |
| C11 | Restore/branch identity and activation fencing | Runtime + Workestrate broker | [#29](https://github.com/rybskiworks/sketchbook/issues/29), workestrate #39 |
| C12 | Physical accounting, conformance and fault harness | Native tests -> SDK -> Workestrate | [#30](https://github.com/rybskiworks/sketchbook/issues/30) |

```text
C01 -> C02                              first usable storage-policy slice
C01 -> C03 -> C04 -> C05 -> C06          durable disk branching and compaction
C01 -> C07 -> C08                       optional KSM path, no snapshot dependency
C01 -> C09                             reclaim/pressure qualification
C03 + C04 + C05 + C09 -> C10 -> C11      later full execution-state branching
C12 runs alongside each slice          evidence is part of each acceptance gate
```

The early C04 scope can use existing stopped layered-root snapshots; advanced flat/block-chain capture is a later slice. This avoids a circular dependency between basic storage testing and complete block-chain integration.

Each accepted implementation slice should be represented in its owner's existing Beads graph with the issue URL and actual prerequisites. These GitHub links are not a claim that Beads has been updated. Do not migrate or initialize a tracker database as a side effect of planning.

Reuse #8 for shared-store lifetime, #7 for branching taxonomy, #17/#19 for broader compartment/confinement work and workestrate #39 for generic capabilities. None is closed by writing this document.

## 10. Qualification matrix and evidence protocol

Implement the harness in #30 with explicit already-built runtime and image inputs, sanitized private HOME/MSB_HOME and bounded scratch resources. Reuse nix-tooling's opt-in NixOS runner shape without adding a tooling-to-runtime dependency cycle. [S13]

| Experiment | Positive result | Required negative/control |
| :--- | :--- | :--- |
| Layered siblings | One base composition, private writes and correct restart | Whiteouts/renames do not affect sibling or lower |
| Flat clone modes | Effective mode equals request or documented auto resolution | Strict reflink fails on unsupported source/destination pair |
| Snapshot scope | Captured data and consistency match the manifest | Uncaptured binds/volumes are not reported as restored |
| Block chain | Parent reads, child writes/zeros/flushes behave correctly | Missing/malformed/implicit backing never admits a writable guest |
| Publication/GC | All live and durable references stay readable | Crash during publish/retire does not expose partial state or collect a required base |
| KSM | Touched matching nonzero guest pages share after observation | Off/unique/churn cohorts; later writes remain private |
| Reclaim | Actual touched RAM released and safely reused | Refused guest shrink, incompatible backing, zero-only false savings |
| Full memory branch | In-RAM counter continues, parent survives and child diverges | Disk-only child cold-boots; unsupported devices and stale authority refuse |

Measure more than logical sizes. Record provisioning/boot/application-ready latency, operation pause time, storage I/O, dirty growth and failures. For disk, use filesystem-specific exclusive/shared extent accounting or isolated whole-fixture allocation; summing per-file allocated blocks can double-count shared extents. For RAM, distinguish RSS, PSS, private/shared mappings, cgroup charges, host pressure and KSM observations. None alone is a universal measure of total physical cost. [S4][K1][K3]

Use matching nonzero data, unique data and real workload phases. Empty demand-paged RAM and sparse files are useful baselines but not evidence of useful application sharing. Do not count unrelated global KSM activity as this fleet's savings. Preserve unsupported/unavailable results, repetitions and raw bounded evidence instead of reporting a single favorable run.

Keep cold and warm cache conditions explicit. Do not clear global host caches, run destructive GC, enable KSM or create filesystems without an authorized disposable host fixture. Test ENOSPC/EIO, interrupted publication/compaction, simultaneous creators, failed thaw, stale grants, lost control and guest refusal to offline pages. No fixed density or performance target is justified before those workload-specific measurements.

## 11. First implementation milestone

The smallest useful code PR is **workestrate #40**, not a forked hypervisor rewrite: expose the already available root-storage/clone policy, retain current defaults, and produce a truthful requested/effective plan and runtime record. Pair it with bounded two-sibling tests. It can land without KSM or full-memory adoption.

Next, make storage-only checkpoints and immutable reference ownership operationally safe through #24/#25, then qualify advanced block chains/compaction via #26. In parallel, implement #27's selective native KSM contract and #41's host-policy boundary. Complete #28 before claiming safe dense private-memory restore. Adopt #29 only after reviewing the real upstream stack and preserving downstream contracts.

Changing a dependency pin, switching a host generation or migrating active VM state is a separate reviewed operation. This roadmap and its issues contain no implementation deployment, live tuning, benchmark result or guarantee that a particular workload reaches a target sharing ratio.

## Sources

Repository links below are pinned where source behavior was inspected. Upstream PR pages provide inspection-time status and revision-scoped author reports; their present status may change.

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
[U1]: https://github.com/superradcompany/microsandbox/pull/1503
[U2]: https://github.com/superradcompany/microsandbox/pull/1533
[U3]: https://github.com/superradcompany/microsandbox/pull/1537
[U4]: https://github.com/superradcompany/microsandbox/blob/df385fc6e4b4a7c11ba4907fa548a7056ee2b36d/sdk/rust/lib/snapshot/create.rs
[K1]: https://www.kernel.org/doc/html/latest/admin-guide/mm/ksm.html
[K2]: https://man7.org/linux/man-pages/man2/madvise.2.html
[K3]: https://docs.kernel.org/admin-guide/cgroup-v2.html
[K4]: https://www.kernel.org/doc/html/latest/filesystems/overlayfs.html

Additional inspected graph/API entries: [Workestrate flake](https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/flake.nix), [Microsandbox flake](https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/flake.nix), [native builders](https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/krun/src/api/builders.rs), and [QEMU memory-backend merge reference](https://www.qemu.org/docs/master/system/qemu-manpage.html).
