# Shared Nix Store Fabric for Dense MicroVM Fleets

> Status: design exploration
>
> Scope: Linux-first, Nix-heavy microVM hosts, with NixOS as the reference host and Workestrate as a potential orchestration layer.

## 1. Purpose

A host running many development, agent, CI, or other short-lived microVMs tends to reproduce the same data repeatedly:

- the same Nix store paths,
- the same base userspace and toolchains,
- the same VM root image blocks,
- the same executable and library pages,
- and large portions of identical guest memory.

The objective of this design is to make each workload behave like an independent machine while allowing the physical host to share immutable state as aggressively as the isolation model permits.

The target is not a single shared writable environment. The target is a composition of independent sharing mechanisms:

- a dedicated **Cachix VM** acting as the fleet's build/cache infrastructure VM, with a builder either colocated in it or delegated to a separate builder VM;
- an immutable, locally published Nix store base shared by many workload VMs;
- a private writable Nix overlay for each workload;
- copy-on-write VM root/image storage;
- shared file-backed memory where the VMM/filesystem path permits it;
- KSM for identical anonymous guest memory;
- and, eventually, true warm-template memory copy-on-write where a backend supports VM snapshot/fork semantics.

The core principle is simple:

> **Share immutable state, isolate mutable state.**

The architecture should make that principle explicit at every layer rather than relying on convention.

---

## 2. Goals

The system should:

1. build common Nix derivations once and reuse them across host and guest workloads;
2. avoid copying the same Nix closures into every VM;
3. allow each VM to install/build additional Nix paths without affecting any other VM;
4. preserve workload isolation even when most of the underlying bytes are physically shared;
5. use storage CoW for VM images and roots wherever the backend supports it;
6. use memory deduplication or memory CoW where safe and measurable;
7. allow a dedicated infrastructure VM to centralize Cachix credentials and build capacity;
8. work cleanly on NixOS while remaining expressible on generic Linux;
9. expose capabilities through Workestrate without baking one VMM's implementation details into the workload model;
10. support deterministic generation pinning, rollback, garbage collection, and testing.

## 3. Non-goals

This design does not require:

- a shared writable `/nix/store` across workload VMs;
- making the NixOS host boot from the same overlay store as workloads;
- implementing VM memory forking before the storage architecture is useful;
- forcing Cachix, the builder, publication, and local binary-cache roles into separate VMs;
- making Workestrate itself a Nix cache server;
- treating one virtualization backend as the permanent implementation.

The architecture defines roles and invariants. Placement and backend implementation remain flexible.

---

## 4. Architecture overview

A reference deployment has four logical planes:

1. **build/cache plane**
2. **store publication plane**
3. **workload runtime plane**
4. **host storage and memory-sharing plane**

```text
                              remote cache
                         +------------------+
                         |      Cachix      |
                         +--------^---------+
                                  |
                             push / pull
                                  |
+------------------------------------------------------------------------+
| NixOS / Linux host                                                     |
|                                                                        |
|   +---------------------------------------------------------------+    |
|   | Cachix VM                                                     |    |
|   |                                                               |    |
|   | Cachix client/uploader                                        |    |
|   | Nix daemon                                                    |    |
|   | remote builder endpoint, optional colocated builder           |    |
|   | durable build store                                           |    |
|   +-----------------------------+---------------------------------+    |
|                                 |                                      |
|                                 | publish selected closures             |
|                                 v                                      |
|   +---------------------------------------------------------------+    |
|   | store publication plane                                       |    |
|   |                                                               |    |
|   | mutable staging store                                         |    |
|   |       |                                                       |    |
|   |       +--> immutable generation G42                           |    |
|   |       +--> immutable generation G43                           |    |
|   +-----------------------------+---------------------------------+    |
|                                 |                                      |
|                           read-only attachment                          |
|                +----------------+----------------+                     |
|                |                |                |                     |
|          +-----v------+   +-----v------+   +-----v------+              |
|          | workload A |   | workload B |   | workload C |              |
|          |            |   |            |   |            |              |
|          | lower: G42 |   | lower: G42 |   | lower: G42 |              |
|          | upper: A   |   | upper: B   |   | upper: C   |              |
|          +------------+   +------------+   +------------+              |
|                                                                        |
|   VM roots/images: shared base + storage CoW                           |
|   guest memory: KSM initially, template-memory CoW later               |
+------------------------------------------------------------------------+
```

The planes are logical. A small deployment may place the builder, Cachix client, local cache endpoint, and publisher-related tooling in one infrastructure VM. A larger deployment may split them.

The correctness model must not depend on that placement.

---

## 5. The Cachix VM

The Cachix VM is the fleet's trusted Nix build/cache infrastructure workload.

Its responsibilities may include:

- running `nix-daemon`;
- exposing a Nix remote-builder endpoint;
- building derivations requested by the host and workload VMs;
- consuming upstream substituters such as `cache.nixos.org`;
- pushing selected build outputs to Cachix;
- holding Cachix write credentials;
- maintaining a durable build store;
- optionally serving a local binary cache;
- staging or initiating publication of selected closures into the shared local store.

The builder does not have to be colocated. Two valid arrangements are:

```text
Cachix VM
  +-- builder
  +-- uploader
  +-- local cache
```

or:

```text
Cachix VM
  +-- uploader/cache gateway
          ^
          |
   separate builder VM
```

The first is simpler. The second may be useful when build workloads need different resource, trust, or nested-virtualization policy.

### 5.1 Why centralize building

Without a shared builder, every VM can end up paying for:

- duplicate compiler/toolchain installations;
- duplicate build inputs;
- duplicate CPU work;
- duplicate build caches;
- duplicate network downloads.

Nix already supports distributed/remote builds. The architecture should use that instead of inventing another build protocol. See [Nix distributed builds][nix-distributed-builds].

### 5.2 Host use of the builder

The NixOS host can also delegate builds to the Cachix VM or its builder.

A reasonable host policy is:

```nix
{
  nix.distributedBuilds = true;

  nix.settings = {
    builders-use-substitutes = true;
    # Optional if local host builds should be avoided entirely:
    # max-jobs = 0;
  };

  nix.buildMachines = [
    {
      hostName = "nix-builder";
      protocol = "ssh-ng";
      system = "x86_64-linux";
      maxJobs = 16;
      supportedFeatures = [ "big-parallel" ];
    }
  ];
}
```

The host should still keep its normal local `/nix/store` for boot, recovery, and NixOS generation management. There is little benefit in making the host itself depend on the guest overlay design in the first implementation.

---

## 6. Shared Nix store model

Nix's experimental [`local-overlay` store][nix-local-overlay] is a natural fit for a fleet of VMs that need a common immutable base plus per-VM writable state.

A local overlay store combines:

- a lower Nix store;
- an OverlayFS upper layer;
- an OverlayFS work directory;
- a merged store view.

Nix does not create the OverlayFS mount itself, but it verifies that the expected lower and upper are mounted correctly by default. The documented store URI has the form:

```text
local-overlay://?root=<merged-root>&lower-store=<lower-store-root>&upper-layer=<upper-dir>
```

The Linux [OverlayFS documentation][overlayfs] requires the work directory to live on the same filesystem as the upper layer.

### 6.1 Per-workload layout

Conceptually, every VM receives:

```text
read-only lower generation:
  /run/workestrate/nix-lower/nix/store

private writable state:
  /var/lib/workestrate/nix-overlay/upper
  /var/lib/workestrate/nix-overlay/work
  /var/lib/workestrate/nix-overlay/state

merged logical store:
  /nix/store
```

The mount is equivalent to:

```bash
mount -t overlay overlay \
  -o lowerdir=/run/workestrate/nix-lower/nix/store \
  -o upperdir=/var/lib/workestrate/nix-overlay/upper \
  -o workdir=/var/lib/workestrate/nix-overlay/work \
  /nix/store
```

The VM can then build, copy, or substitute additional paths into its own upper layer while reading the shared lower paths directly.

### 6.2 Required invariants

The runtime must guarantee:

- the lower store is read-only at the host/VMM boundary;
- a workload cannot remount the host export writable;
- every workload gets a distinct upper layer;
- every workload gets distinct upper-layer Nix state;
- lower generations are not modified while mounted by workloads;
- Workestrate pins the exact lower generation for the workload lifetime;
- workload destruction can delete an ephemeral upper without affecting any other workload;
- lower-generation GC is a host control-plane operation, never a guest operation.

---

## 7. Immutable store generations

The shared lower should be modeled as an immutable **store generation**, not as the Cachix VM's live mutable `/nix/store`.

This provides a stable filesystem and metadata view for every running workload and creates a clean lifecycle boundary.

```text
publication staging store
        |
        | publish/freeze
        v
 immutable generation G42
    /        |        \
   /         |         \
VM A       VM B       VM C

staging store continues toward G43 independently
```

A new generation never mutates the previous one.

### 7.1 Generation contents

The generation should represent a coherent Nix store root, including the data required by the selected lower-store implementation, rather than only copying arbitrary `/nix/store` paths without metadata.

A physical layout might be:

```text
/var/lib/workestrate/nix-publisher/
  live/
    nix/
      store/
      var/nix/
  generations/
    G42/
    G43/
```

The exact physical layout is implementation-specific. The workload-facing logical store remains `/nix/store`.

### 7.2 Generation manifest

Each generation should have a machine-readable manifest:

```toml
schema = 1
id = "sha256-..."
system = "x86_64-linux"
nix_version = "2.34.9"
created_at = "2026-09-11T00:00:00Z"

[top_level]
paths = [
  "/nix/store/...-workestrate",
  "/nix/store/...-rust-toolchain",
  "/nix/store/...-nodejs",
]

[store]
logical = "/nix/store"
```

The manifest gives Workestrate a stable object to pin in:

- workload plans;
- checkpoints;
- snapshots;
- rollback state;
- GC leases;
- metrics;
- debugging output.

### 7.3 Generation leases

A simple lifecycle is:

```text
G41  refs=0   old
G42  refs=17  current
G43  refs=0   publishing
```

Rules:

1. publication creates a new immutable object;
2. `current` is a pointer/default, not a mutable generation;
3. launching a workload takes a lease on a generation;
4. a running workload never silently moves to another generation;
5. a generation with live leases cannot be deleted;
6. destroying a workload releases its lease;
7. old unleased generations are eligible for GC.

This is also compatible with future checkpoint/fork systems: a checkpoint records the exact store generation it depends on.

---

## 8. Publication strategies

Two publication models are useful.

### 8.1 Isolation-first publication

The Cachix VM or builder keeps a private mutable build store. Selected closures are copied into a host-owned publication store, then frozen into a generation.

```text
Cachix VM / builder store
          |
          | nix copy selected closure
          v
host publication staging store
          |
          | snapshot/freeze
          v
immutable generation
```

Advantages:

- builder compromise does not imply arbitrary host publication-store writes;
- promotion is explicit;
- only high-value reusable closures are shared fleet-wide;
- validation and signing can occur at the publication boundary;
- the builder VM can use ordinary private VM storage.

The cost is one additional local copy between the builder store and publication staging store.

### 8.2 Host-backed publication store

A more aggressive design gives the trusted Cachix VM or builder writable access to a dedicated host-backed store/subvolume and lets the host snapshot it directly.

```text
host-backed mutable publication subvolume
             ^
             |
      trusted Cachix VM

host:
  live -> read-only G42
  live -> read-only G43
```

This removes the builder-to-publication copy and is attractive on Btrfs, but it increases the trust placed in the infrastructure VM and requires careful snapshot coordination.

The first implementation should prefer the isolation-first path unless benchmarks demonstrate that publication copying is a meaningful bottleneck.

---

## 9. Host filesystem and physical storage

For the NixOS reference implementation, Btrfs is a strong candidate for Workestrate's VM/state storage area.

Relevant properties include:

- copy-on-write data and metadata;
- cheap subvolume snapshots;
- read-only snapshots;
- reflink-style sharing between logically independent files;
- a natural representation for immutable store generations.

See the [Btrfs subvolume documentation][btrfs-subvolume].

XFS with reflink support is also viable for root/image cloning and shared extents. The architecture should not require Btrfs globally.

Immutable store generations could also eventually be materialized as read-only filesystem images such as EROFS or SquashFS. That is attractive when portability and hard immutability matter more than publication latency.

---

## 10. Root image copy-on-write

The Nix overlay does not replace VM root-image sharing. The two mechanisms solve different duplication problems.

A workload ideally gets:

```text
base VM image
     |
     +--> CoW clone A
     +--> CoW clone B
     +--> CoW clone C
```

The VM root then contains only the minimal operating environment and private changes, while large reusable Nix closures live in the shared lower store.

Current Microsandbox already has useful storage primitives in this direction, including image-layer sharing and reflink-based cloning paths. Workestrate should expose the semantic requirement, such as `reflink-preferred` or `copy-on-write-required`, and let the backend satisfy it using its native mechanism.

This makes it possible to combine:

```text
shared Nix bytes
+ shared root/image blocks
+ private changed root blocks
+ private Nix upper
```

rather than choosing only one sharing layer.

---

## 11. Memory sharing

Storage sharing does not automatically produce RAM sharing. Memory should be treated as its own capability domain.

### 11.1 File-backed sharing

A large shared read-only Nix tree creates opportunities for host page-cache reuse, and possibly for more direct sharing through virtio-fs/DAX depending on backend implementation.

Upstream libkrun exposes virtio-fs APIs with configurable DAX window sizing. A large immutable Nix lower store is a good benchmark target for determining whether DAX materially reduces duplicate guest file-backed memory.

This should be measured rather than assumed.

### 11.2 KSM

Linux [Kernel Samepage Merging][linux-ksm] deduplicates identical anonymous memory pages that userspace marks with `MADV_MERGEABLE`.

For many nearly identical VMs this can recover memory occupied by identical guest RAM after boot.

The VMM must participate. Enabling KSM on the host is not sufficient if guest RAM mappings are never marked mergeable.

The relevant VMM operation is conceptually:

```c
madvise(addr, len, MADV_MERGEABLE);
```

KSM should be an explicit workload/backend policy:

```toml
[vm.memory]
sharing = "ksm"
trust_domain = "local-agent-fleet"
```

It should not silently deduplicate memory across unrelated trust domains.

KSM also has operational tradeoffs:

- `ksmd` consumes CPU while scanning;
- convergence is not immediate;
- memory churn reduces benefit;
- swapping merged pages breaks sharing until KSM finds identical pages again, as documented by the kernel;
- side-channel considerations make cross-tenant use a policy decision.

Useful metrics include:

- `pages_shared`;
- `pages_sharing`;
- `pages_unshared`;
- `full_scans`;
- VMM RSS/PSS;
- time to convergence;
- `ksmd` CPU cost.

### 11.3 True template-memory CoW

The longer-term density target is to start several VMs from one initialized parent state and share its memory pages immediately:

```text
              initialized parent VM
                       |
               pause / snapshot
                       |
           +-----------+-----------+
           |           |           |
        child A     child B     child C
           |           |           |
      private-on-write divergence
```

This requires substantially more than KSM:

- VM pause/quiesce;
- guest RAM snapshotting;
- vCPU state capture;
- device state capture;
- consistent disk state;
- restore/fork semantics;
- child identity regeneration;
- network/vsock reattachment;
- entropy and clock handling;
- private-on-write memory mapping or equivalent backend support.

It should therefore be modeled as a distinct backend capability, not as an extension of KSM.

Possible future backends may provide this through libkrun changes, Clone-like semantics, Firecracker-derived mechanisms, forkd-like approaches, or another VMM entirely.

---

## 12. Build and cache resolution path

A workload should resolve a required Nix path in an ordered way:

```text
1. pinned shared lower generation
          |
          v miss
2. local host/infrastructure binary cache, optional
          |
          v miss
3. Cachix / upstream substituters
          |
          v miss
4. remote builder in Cachix VM or dedicated builder VM
          |
          v
5. result copied into workload-private upper
```

A successful output can later be promoted into a new shared generation if it is expected to have fleet-wide reuse.

This separates immediate workload correctness from long-term cache optimization.

---

## 13. Promotion policy

A store path appearing in one workload's upper should not automatically become shared fleet state.

Promotion should be explicit and trusted.

Possible policies:

1. **rebuild and publish**: the trusted builder reproduces the derivation, then publishes its closure;
2. **verified import**: a result is imported into publication staging after signature/provenance validation;
3. **usage-driven promotion**: Workestrate records repeated cache misses or repeated upper-layer paths and recommends or automatically schedules promotion according to policy.

The published lower should remain curated enough that it does not become a permanent dumping ground for every one-off derivation.

---

## 14. Security boundaries

### 14.1 Shared lower

The lower generation must be read-only at the host/VMM attachment boundary. A guest root user or compromised guest kernel must not be able to mutate it.

### 14.2 Workload uppers

Each workload upper is private. Workload A must not be able to inspect or modify workload B's upper.

### 14.3 Cachix credentials

A useful default is:

```text
Cachix write authority
    -> Cachix VM / trusted builder only

Cachix read authority, if private cache
    -> selected consumers

publication authority
    -> host publisher / trusted infrastructure path

shared store generation
    -> all consumers read-only
```

### 14.4 Host path containment

If a VMM exports host directories through virtio-fs, its host-visible namespace should contain only the paths needed for that workload.

A reasonable defense-in-depth chain is:

```text
workload VM
   -> virtio-fs device
      -> restricted VMM mount namespace
         -> exact immutable store generation
```

The backend should fail closed if it cannot provide the requested read-only semantics.

---

## 15. NixOS reference host

NixOS is a particularly good control-plane host for this architecture because the entire setup can be represented declaratively.

A host module or flake can own:

- KVM configuration;
- nested-virtualization policy;
- Btrfs/XFS layout;
- KSM enablement and tuning;
- remote-builder configuration;
- Cachix substituters and trusted keys;
- SOPS-backed infrastructure credentials;
- Workestrate services;
- generation publisher services;
- generation GC;
- local cache endpoint;
- metrics/exporters;
- pinned Microsandbox/libkrun/libkrunfw builds.

Generic Linux remains viable as long as it provides equivalent kernel, filesystem, Nix, and VMM capabilities.

---

## 16. Workestrate model

Workestrate should model desired semantics, not Microsandbox-specific command-line switches.

A workload configuration might eventually express:

```toml
[store]
mode = "overlay"
generation = "current-compatible"

[store.upper]
lifecycle = "ephemeral"
size = "20GiB"

[store.builder]
name = "nix-builder"
strategy = "remote-first"

[store.cache]
local = true
cachix = "rybskiworks"

[vm.root]
sharing = "cow-preferred"

[vm.memory]
sharing = "ksm"
```

Internally, Workestrate can resolve this into something like:

```rust
struct StorePlan {
    generation: StoreGenerationId,
    lower: ReadOnlyStoreAttachment,
    upper: UpperStorePlan,
    builder: Option<BuilderEndpoint>,
    substituters: Vec<Substituter>,
}

struct BackendCapabilities {
    readonly_directory_mount: bool,
    reflink_root_clone: bool,
    block_cow_root: bool,
    nested_virtualization: bool,
    mergeable_guest_memory: bool,
    virtiofs_dax: bool,
    vm_snapshot_restore: bool,
    template_memory_cow: bool,
}
```

A backend that cannot satisfy a required capability should reject the plan before launch.

This keeps the workload model valid if Workestrate later supports Microsandbox, direct libkrun, Clone, Firecracker, forkd, or another backend.

---

## 17. Workload lifecycle

A launch path becomes:

1. resolve the requested store generation;
2. acquire a generation lease;
3. resolve backend capabilities;
4. create or clone the VM root;
5. allocate the workload's private Nix upper;
6. attach the lower generation read-only;
7. boot the guest;
8. mount OverlayFS and initialize the local-overlay store;
9. configure substituters and remote builder access;
10. start the workload;
11. collect store/image/memory-sharing metrics;
12. on destruction, remove ephemeral upper/root deltas and release the generation lease.

This lifecycle should be visible through `plan`, `inspect`, or equivalent commands so operators can see exactly which sharing mechanisms are active.

---

## 18. Implementation baseline and remaining capability work

This section separates an immutable source baseline from the proposed architecture. Branch names and package versions are not evidence that a deployment has these capabilities. Resolve the selected Workestrate flake and Cargo locks, then test the resulting runtime and guest image. The examples in this document are proposed configuration, not accepted Workestrate syntax.

### 18.1 Workestrate

Workestrate revision [`6c0672ef`][workestrate-source-baseline] pins the `rybskiworks/microsandbox` fork at `8ae14c22963c0680b231f61280f43db364693a5c` in its flake, with runtime packages and SDK patches selected from that same source. This supersedes the older upstream `0.5.6` release-artifact packaging; it is not a claim about which revision a particular fleet currently selects.

That source integration does not implement the shared-store generation, publication, or memory-sharing design proposed here.

Work for this design includes:

- retain coherent, reproducibly pinned runtime, SDK, and guest-kernel inputs;
- extend capability reporting for the store and memory semantics required here;
- add store-generation objects and leases;
- add shared-lower/private-upper lifecycle management;
- add guest initialization for OverlayFS + Nix `local-overlay`;
- model Cachix VM / builder infrastructure workloads;
- model store publication and promotion;
- expose root-storage sharing policy;
- expose memory-sharing policy;
- integrate the invariants with Workestrate's black-box/property-based E2E testing plans.

### 18.2 Microsandbox

The pinned Microsandbox source baseline [`8ae14c22`][rybskiworks-msb-cargo] identifies itself as `0.6.18`. Inspect that revision's Cargo and Nix dependencies rather than assuming an update in another repository is already consumed.

Changes made only in `rybskiworks/libkrun` or `libkrunfw` do not automatically appear in a selected Microsandbox build. Preserve the dependency chain and verify the actual built artifacts.

Assess and, where absent, implement generic backend capabilities for:

- hard read-only directory export;
- root reflink/CoW cloning;
- nested virtualization declaration;
- mergeable guest memory once libkrun exposes it;
- optional virtio-fs DAX controls;
- future full snapshot/restore if supported by the VMM.

The Nix-generation concept should remain in Workestrate. Microsandbox only needs to expose the underlying generic virtualization/storage primitives.

### 18.3 libkrun

The selected libkrun [`API header`][rybskiworks-libkrun-header] and implementation must be checked together with the caller's dependency pin.

A Workestrate lower-store attachment must rely on an actual read-only export rather than guest convention. An available header declaration alone does not prove that the deployed VMM uses that path or enforces the requested mode.

For KSM, libkrun needs an opt-in API that marks only eligible guest RAM mappings `MADV_MERGEABLE` and reports whether the requested mode is effective.

Requirements include:

- disabled by default;
- Linux/KVM capability detection;
- explicit error/reporting when unsupported;
- no accidental marking of unrelated mappings;
- observability suitable for integration tests;
- tests against host KSM counters.

Full memory snapshot/fork support is a later concern and should not block the store architecture.

### 18.4 libkrunfw

The guest kernel must provide the filesystem and virtualization features used by the design, including:

- virtio-fs;
- OverlayFS;
- the filesystem used for private upper/root storage;
- nested KVM only for profiles that explicitly require it.

KSM itself is a host/VMM mechanism, not a guest-kernel feature for this purpose.

The exact `libkrunfw` build used by Workestrate should be tested for required kernel features rather than relying on assumptions.

### 18.5 Nix

`local-overlay` remains an experimental Nix store type and should be pinned deliberately.

The implementation should include tests for:

- mount validation;
- query behavior;
- substitutions into the upper;
- builds into the upper;
- daemon restart;
- GC;
- remount behavior;
- lower-only paths remaining immutable.

Nix issue [`#16269`][nix-overlay-gc-issue] reports a finite-limit/automatic-GC problem relevant to `local-overlay`. Check the selected Nix revision against the reported defect and any fix, and carry a regression test rather than assuming that a newer version resolves it.

---

## 19. Nested virtualization and builder placement

Some Nix derivations require the `kvm` system feature.

If the builder runs inside the Cachix VM, Workestrate should explicitly decide whether that VM receives nested virtualization.

A useful policy shape is:

```toml
[infra.cachix_vm]
nested_virtualization = "require" # require | allow | disable
```

If nested virtualization is disabled, the builder must not advertise `kvm` and KVM-dependent derivations should route to another capable builder.

This is another reason to keep the logical roles separable even when they are colocated by default.

---

## 20. Failure behavior

### Cachix unavailable

Existing shared generations remain usable. The builder may still build from available sources and local inputs. Upload can resume later.

### Cachix VM / builder unavailable

Existing workloads whose dependencies are already in the lower or accessible substituters remain usable. New source builds are delayed or fail according to policy.

### Publisher unavailable

Running workloads are unaffected because they hold immutable pinned generations. New publication is blocked, but existing generations remain usable.

### Bad generation

The generation is marked unavailable for new leases. The default pointer can roll back. Existing workloads can either continue if the generation is safe enough to retain for diagnosis or be explicitly recycled according to policy. The generation itself is never edited in place.

---

## 21. Testing strategy

The architecture should be proven through black-box tests from outside the workload, not merely by inspecting configuration.

### 21.1 Store isolation

- launch two VMs from the same generation;
- verify both resolve lower paths;
- add/build a path in VM A;
- verify only A's upper changes;
- verify VM B cannot see it;
- verify neither can mutate the lower;
- destroy A and verify B remains unaffected.

### 21.2 Generation stability

- launch workloads on G42;
- publish G43;
- verify G42 workloads remain on G42;
- launch new workload on G43;
- verify G42 cannot be GC'd while leased;
- release leases and verify eventual cleanup.

### 21.3 Builder/cache behavior

- disable local workload builds;
- build through remote builder;
- verify builder uses substitutes;
- verify result appears in workload upper;
- push result to Cachix;
- publish selected closure into a future generation.

### 21.4 Root CoW

Measure allocated blocks, not apparent file size:

- clone N VMs from one base;
- mutate one VM;
- verify only changed extents allocate;
- compare reflink/CoW mode with full-copy fallback.

### 21.5 KSM

- launch N equivalent guests;
- verify VMM memory is marked mergeable;
- measure KSM counters and PSS over time;
- dirty memory in one guest and verify isolation;
- verify workloads with sharing disabled are not mergeable;
- measure convergence time and `ksmd` CPU cost.

---

## 22. Observability

The design should expose whether sharing is actually producing density improvements.

Example metrics:

```text
workestrate_store_generation_bytes{generation=...}
workestrate_store_generation_leases{generation=...}
workestrate_store_upper_bytes{workload=...}
workestrate_nix_resolution_total{source="lower|local-cache|cachix|builder"}
workestrate_builder_queue_depth
workestrate_root_physical_bytes{workload=...}
workestrate_vm_rss_bytes{workload=...}
workestrate_vm_pss_bytes{workload=...}
workestrate_ksm_pages_shared
workestrate_ksm_pages_sharing
workestrate_ksm_full_scans
```

The physical-cost model is roughly:

```text
storage ~= shared store generations
        + shared VM image bases
        + private changed root extents
        + private Nix uppers

memory ~= VMM/device overhead
       + unique guest working sets
       + shared file-backed pages
       + KSM-shared anonymous pages
       + future template-shared memory
```

The architecture is successful only if these values improve materially at fleet scale.

---

## 23. Implementation sequence

### Phase 1: prove the overlay-store primitive

- pin a suitable Nix version;
- create an immutable lower store;
- export it read-only into two microVMs;
- create independent uppers;
- verify query, substitution, build, and GC behavior.

### Phase 2: introduce store generations

- publication staging store;
- immutable generation snapshots/images;
- manifests;
- leases;
- atomic default pointer;
- generation GC.

### Phase 3: Cachix VM and remote builder

- persistent infrastructure VM;
- Nix remote builder endpoint;
- Cachix write credentials;
- host and workload builder configuration;
- explicit closure promotion into publication staging.

### Phase 4: Workestrate integration

- `StorePlan` and capability model;
- generation lifecycle;
- guest initialization;
- CLI planning/inspection;
- failure handling;
- black-box tests.

### Phase 5: root/image density

- validate the selected Microsandbox fork's root-storage behavior;
- use reflink/CoW root cloning where available;
- shrink base images by moving reusable closures into the shared Nix lower;
- add physical-allocation metrics.

### Phase 6: KSM

- libkrun mergeable-RAM API;
- Microsandbox capability/configuration;
- Workestrate policy;
- NixOS KSM tuning;
- density and CPU-cost benchmarks.

### Phase 7: warm-template memory research

Evaluate backend-specific VM snapshot/fork implementations only after the simpler storage and KSM mechanisms are measured.

---

## 24. Initial reference stack

A practical first implementation would use:

| Layer | Initial choice |
| --- | --- |
| Host | NixOS |
| Host state/storage | Btrfs |
| Build/cache infrastructure | dedicated Cachix VM, builder colocated initially |
| Remote binary cache | Cachix |
| Publication source | explicit `nix copy` from builder/Cachix VM store |
| Store generations | read-only Btrfs snapshots |
| Guest lower attachment | hard read-only virtio-fs |
| Guest store | pinned Nix `local-overlay` |
| Guest upper | private per workload, ephemeral by default for agents |
| Root sharing | backend-native reflink/CoW |
| Memory sharing | none initially, then KSM |
| Warm-memory CoW | deferred backend research |
| Host `/nix/store` | ordinary local host store |

This reaches the majority of the likely storage-density benefit without making the first milestone depend on VM memory snapshot/fork support.

---

## 25. Open questions and benchmarks

1. How does virtio-fs perform under Nix's metadata-heavy workload with tens or hundreds of guests?
2. Does virtio-fs DAX materially reduce physical memory consumption for shared Nix executables and libraries?
3. What is the KSM convergence curve at 10, 50, and 100 near-identical agent VMs?
4. How much CPU does `ksmd` consume at those densities?
5. How much does zram/swap reduce sustained KSM benefit?
6. Is explicit `nix copy` into publication staging materially expensive compared with a host-backed publication subvolume?
7. Should generations be fleet-wide, fleet-specific, project-specific, or eventually layered/composable?
8. What promotion heuristic best identifies upper-layer paths worth adding to the shared base?
9. Should the Cachix VM also serve a local Harmonia endpoint, or is the lower-store plus Cachix path sufficient?
10. At what density does maintaining true template-memory CoW become worth the VMM complexity?
11. Which backend gives the best combination of fast root cloning, hard read-only shared mounts, nested virtualization, KSM, and eventual memory snapshot/fork?

---

## 26. Summary

The target system gives every workload the semantics of an independent Nix machine while sharing the expensive immutable parts underneath it:

```text
                 Cachix
                   ^
                   |
         Cachix VM / builder
                   |
              publish
                   v
          immutable store G42
             /      |      \
            /       |       \
       VM A        VM B      VM C
       upper A     upper B   upper C

root disks:   shared base + CoW divergence
Nix stores:   shared lower + private overlay
RAM:          KSM, then optional template CoW
```

The architecture does not depend on one monolithic cache VM, one filesystem, or one hypervisor. It depends on a small set of explicit semantics: immutable shared generations, private mutable state, capability-aware backends, trusted publication, and measurable sharing.

That is the level Workestrate should orchestrate.

---

## References

### Nix

- [Nix 2.34.9: Experimental Local Overlay Store][nix-local-overlay]
- [Nix 2.34.9: Store types and settings][nix-store-types]
- [Nix: Distributed builds setup][nix-distributed-builds]
- [Nix issue #16269: local-overlay GC with finite `max-freed`][nix-overlay-gc-issue]

### Linux storage and memory

- [Linux kernel: OverlayFS][overlayfs]
- [Linux kernel: Kernel Samepage Merging][linux-ksm]
- [Btrfs documentation: subvolumes and snapshots][btrfs-subvolume]

### Cachix and local cache options

- [Cachix documentation][cachix-docs]
- [Harmonia][harmonia]
- [Attic][attic]

### Virtualization stack

- [Microsandbox][microsandbox]
- [libkrun][libkrun]
- [libkrun API header][libkrun-header]

### Rybskiworks source and integration references

- [Workestrate][workestrate]
- [Workestrate immutable source baseline][workestrate-source-baseline]
- [rybskiworks/microsandbox][rybskiworks-msb]
- [rybskiworks/microsandbox `Cargo.toml`][rybskiworks-msb-cargo]
- [rybskiworks/libkrun][rybskiworks-libkrun]
- [rybskiworks/libkrun header][rybskiworks-libkrun-header]
- [rybskiworks/libkrunfw][rybskiworks-libkrunfw]

[nix-local-overlay]: https://nix.dev/manual/nix/2.34/store/types/experimental-local-overlay-store
[nix-store-types]: https://nix.dev/manual/nix/2.34/command-ref/new-cli/nix3-help-stores
[nix-distributed-builds]: https://nix.dev/tutorials/nixos/distributed-builds-setup.html
[nix-overlay-gc-issue]: https://github.com/NixOS/nix/issues/16269
[overlayfs]: https://docs.kernel.org/filesystems/overlayfs.html
[linux-ksm]: https://docs.kernel.org/admin-guide/mm/ksm.html
[btrfs-subvolume]: https://btrfs.readthedocs.io/en/latest/Subvolumes.html
[cachix-docs]: https://docs.cachix.org/
[harmonia]: https://github.com/nix-community/harmonia
[attic]: https://github.com/zhaofengli/attic
[microsandbox]: https://github.com/superradcompany/microsandbox
[libkrun]: https://github.com/containers/libkrun
[libkrun-header]: https://github.com/containers/libkrun/blob/main/include/libkrun.h
[workestrate]: https://github.com/rybskiworks/workestrate
[workestrate-source-baseline]: https://github.com/rybskiworks/workestrate/blob/6c0672efb376ceb860a0a5a339bf6b550a94fea2/flake.nix
[rybskiworks-msb]: https://github.com/rybskiworks/microsandbox
[rybskiworks-msb-cargo]: https://github.com/rybskiworks/microsandbox/blob/8ae14c22963c0680b231f61280f43db364693a5c/Cargo.toml
[rybskiworks-libkrun]: https://github.com/rybskiworks/libkrun
[rybskiworks-libkrun-header]: https://github.com/rybskiworks/libkrun/blob/krun/include/libkrun.h
[rybskiworks-libkrunfw]: https://github.com/rybskiworks/libkrunfw
