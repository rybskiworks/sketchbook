# Shared Nix Store and MicroVM Density Fabric

## Cachix, `local-overlay`, remote builders, storage CoW, KSM, and Workestrate integration

> Status: architecture exploration / design note.
>
> This is intentionally not an ADR and not a statement that this is the purpose of Workestrate. It is an idealized systems design for a Nix-heavy microVM host, with a concrete section on what Workestrate and the current `rybskiworks` virtualization forks would need in order to orchestrate it cleanly.

## 1. Core idea

The target is a Linux, preferably NixOS, host that can run many microVMs while paying for common state as close to once as practical.

The common state is split into several independent layers:

1. **Nix build/cache plane**: a dedicated infrastructure microVM acts as the trusted Nix builder and Cachix uploader/client.
2. **Shared Nix store plane**: selected reusable closures are published into immutable local store generations that can be shared read-only by many VMs.
3. **Per-VM Nix overlay**: every VM gets the shared store generation as its lower layer and its own writable upper layer through Nix's experimental `local-overlay` store.
4. **VM image CoW**: root disks/images are cloned from common bases using reflinks, block-level CoW, shared OCI layers, or equivalent backend-native mechanisms.
5. **RAM sharing**: start with KSM, Kernel Samepage Merging, for identical anonymous guest RAM pages. Treat true warm-template memory CoW as a separate, later VMM feature.
6. **Centralized building**: the host and ordinary workload VMs can delegate expensive builds to the trusted builder VM instead of each maintaining an independent build environment.

The important architectural rule is:

> **Share immutable state aggressively. Do not share one writable Nix store among independent workloads.**

A useful high-level picture is:

```text
                              remote durability
                         +-----------------------+
                         |        Cachix         |
                         +-----------^-----------+
                                     |
                              push / substitute
                                     |
+--------------------------------------------------------------------------+
| Linux / NixOS host                                                       |
|                                                                          |
|   +----------------------------+                                         |
|   | builder + cache microVM    |                                         |
|   |                            |                                         |
|   | nix-daemon                 |                                         |
|   | remote builder endpoint    |                                         |
|   | Cachix uploader/client     |                                         |
|   | private mutable build store|                                         |
|   +-------------+--------------+                                         |
|                 |                                                        |
|                 | publish selected closures                              |
|                 v                                                        |
|   +---------------------------------------------------------------+      |
|   | local store publication plane                                 |      |
|   |                                                               |      |
|   | mutable staging store                                         |      |
|   |      |                                                        |      |
|   |      +-- freeze --> immutable generation G41                   |      |
|   |      +-- freeze --> immutable generation G42                   |      |
|   |      +-- freeze --> immutable generation G43                   |      |
|   +-----------------------------+---------------------------------+      |
|                                 |                                        |
|                           read-only export                                |
|                                 |                                        |
|           +---------------------+---------------------+                   |
|           |                     |                     |                   |
|     +-----v------+        +-----v------+        +-----v------+            |
|     | workload A |        | workload B |        | workload C |            |
|     |             |        |             |        |             |            |
|     | lower: G42  |        | lower: G42  |        | lower: G42  |            |
|     | upper: A    |        | upper: B    |        | upper: C    |            |
|     | merged /nix|        | merged /nix|        | merged /nix|            |
|     +-------------+        +-------------+        +-------------+            |
|                                                                          |
|   roots/images: shared base + storage CoW                                |
|   RAM: KSM initially, template-memory CoW later                          |
+--------------------------------------------------------------------------+
```

## 2. First correction: "Cachix VM" is not literally a Cachix server

Cachix is primarily a hosted binary cache service. A machine runs the Cachix client/daemon or post-build hooks and pushes store outputs to the hosted cache.

So the infrastructure VM described here is better thought of as a **Nix builder/cache gateway**:

- Nix remote builder,
- Cachix uploader/client,
- trusted holder of cache write credentials,
- optional local cache server,
- optional publisher/stager for the shared local store.

If a completely local binary-cache HTTP endpoint is wanted, that is another component. Harmonia is a good fit for serving an existing Nix store. Attic is another possible architecture, but it is not required for the shared lower-store design.

Cachix and the shared local store solve different problems:

- **Cachix**: durable, off-host, network-visible distribution of Nix outputs.
- **shared local store generation**: avoid downloading/copying the same already-present closure into every VM on one physical host.

The ideal system uses both.

## 3. Second correction: KSM, not KMS

The Linux RAM deduplication primitive is **KSM, Kernel Samepage Merging**.

KSM scans anonymous memory regions that a userspace process has marked with `MADV_MERGEABLE`, detects identical pages, replaces them with a shared write-protected page, and splits the page again when one participant writes.

That is useful for many near-identical VMs, but it is not the same thing as starting N VMs from one warm parent memory snapshot.

### KSM

```text
VM A boots independently ----+
VM B boots independently ----+--> ksmd later finds identical pages
VM C boots independently ----+             |
                                            v
                                    shared physical page
                                            |
                                      write -> copy
```

### True template-memory CoW

```text
                warm parent VM snapshot
                         |
              +----------+----------+
              |          |          |
            child A    child B    child C
              |          |          |
          private-on-write mappings from the start
```

KSM is the realistic first step for the libkrun/Microsandbox stack. True memory CoW needs pause/snapshot/restore or explicit fork semantics in the VMM.

Also note that KSM sharing is not permanent across swap. Linux documents that when merged pages are swapped out and later swapped back in, the sharing is broken until `ksmd` rediscovers and merges them again. This matters if the host uses aggressive swap or zram.

## 4. There are several independent CoW/sharing layers

These mechanisms should not be conflated:

| Layer | Likely mechanism | Shared object | Divergence behavior |
| --- | --- | --- | --- |
| Nix store | Nix `local-overlay` + Linux OverlayFS | immutable store generation | new guest paths land in private upper |
| VM root/image | reflink, shared OCI layers, qcow2 backing, snapshot | filesystem/block base | changed blocks become private |
| Read-only file pages | host page cache / optionally virtio-fs DAX | executable/library/file pages | normally immutable/read-only |
| Guest anonymous RAM | KSM | identical anonymous pages | private page on write |
| Warm guest memory | snapshot/fork + private mapping | parent VM RAM image | private page on write |

The density target comes from composing them.

## 5. Why the shared Nix store should be immutable generations

Nix 2.34.9 documents the experimental `local-overlay` store.

The lower store is logically immutable from the overlay consumer's point of view. Nix allows the lower store to grow in some abstract cases, but Linux OverlayFS imposes the stronger restriction that the lower store directory **cannot change at all while it is mounted as a lower layer**.

That immediately rules out the naive design:

```text
builder continuously mutates one live /nix/store
             |
             +--> VM A OverlayFS lowerdir
             +--> VM B OverlayFS lowerdir
             +--> VM C OverlayFS lowerdir
```

Even adding new paths changes the lower directory.

The correct primitive is therefore a **published store generation**:

```text
mutable store / staging area
          |
          | freeze / publish
          v
     immutable G42
       /    |    \
      /     |     \
    VM A   VM B   VM C

builder and publisher continue preparing G43 elsewhere
```

When G43 is ready:

- new workloads can use G43,
- existing G42 workloads remain on G42,
- G42 is retained until no workload has a lease/reference to it,
- no running guest sees its lower store mutate underneath it.

This is a much better lifecycle model anyway because it gives deterministic planning, rollbacks, auditability, and safe GC.

## 6. Where should the shared store physically live?

This is the most important topology distinction.

If the only copy of the store physically lives inside the builder/cache VM, other VMs cannot use it as a low-overhead local OverlayFS lower layer without introducing another network/filesystem export layer.

So the most useful design is:

- **builder/cache VM owns build authority**, credentials, and mutable build activity,
- **host owns the published immutable store generations** that are directly attachable to workload VMs.

There are two reasonable publication strategies.

### 6.1 Isolation-first topology

The builder has a private mutable Nix store. It publishes selected closures to a separate host-owned local store.

```text
builder VM private /nix/store
          |
          | nix copy selected closures
          v
host publication staging store
          |
          | freeze
          v
read-only generation G42
```

Pros:

- the builder never receives general write access to the host's publication tree,
- publication is an explicit policy boundary,
- only useful closures need to become fleet-wide shared state,
- easier to validate/sign/test before promotion,
- easiest design to secure first.

Cost:

- one extra local copy exists between builder-private storage and the publication store.

For dozens of VMs that is still dramatically better than dozens of duplicated stores.

### 6.2 Density-first topology

A later optimization is to expose a dedicated host filesystem/subvolume writable to the trusted builder VM. The builder uses that as a publication/staging store and the host creates immutable snapshots directly from it.

On a Btrfs host:

```text
host Btrfs subvolume: /var/lib/.../nix-publisher/live
                  ^
                  |
          writable to trusted builder only
                  |
             builder VM

host snapshots:
  live -> generations/G42 (ro)
  live -> generations/G43 (ro)
```

Pros:

- avoids the builder-private -> publication-store copy,
- Btrfs snapshots are naturally CoW,
- publication is nearly instantaneous regardless of logical store size.

Cons:

- the trusted infrastructure VM now has a direct writable host-backed path,
- the host and guest must coordinate a coherent snapshot boundary,
- the VMM process must be strongly contained to only that path.

I would implement isolation-first and benchmark before optimizing this.

## 7. Host filesystem

For a NixOS/Linux reference implementation, **Btrfs** is an attractive default for Workestrate's state/published-store area because:

- read-only subvolume snapshots naturally model immutable generations,
- reflink/CoW semantics are native,
- generation publication can be cheap,
- the same filesystem can also support CoW clones for suitable VM disk artifacts.

XFS with reflink is also viable for many of the same storage-density goals, but generation snapshots are less directly represented as subvolumes.

Another direction is to materialize immutable lower stores as:

- EROFS images,
- SquashFS images,
- read-only ext4 images.

Those can be attractive for portability and hard immutability, but they require image generation. A read-only Btrfs snapshot plus virtio-fs is the simplest Linux-first prototype.

## 8. What a store generation contains

A generation is not merely a random directory of `/nix/store` objects.

The lower store has filesystem content plus Nix metadata. The generation should represent a coherent local store root, for example:

```text
/var/lib/workestrate/store-publisher/live/
  nix/
    store/
    var/nix/
      db/
      ...
```

A publisher can maintain this using a separate local Nix store root and `nix copy` selected closures into it.

Then snapshot/freeze the entire coherent store root.

Each generation should have a manifest, conceptually:

```toml
schema = 1
id = "sha256-..."
system = "x86_64-linux"
nix_version = "2.34.9"
created_at = "2026-09-10T00:00:00Z"

[top_level]
paths = [
  "/nix/store/...-workestrate",
  "/nix/store/...-rust-toolchain",
  "/nix/store/...-nodejs",
]

[store]
logical_store = "/nix/store"
physical_root = "/var/lib/workestrate/store-publisher/generations/<id>"

[cache]
cachix = "..."
```

This manifest becomes useful for:

- workload plans,
- generation leases,
- GC,
- rollback,
- reproducibility,
- explaining why a store path exists,
- checkpoint compatibility,
- measuring physical/logical sharing,
- grouping VMs into compatible warm-template families later.

### What should be published?

Not necessarily the builder's entire store.

Good shared-generation candidates are closures with high reuse:

- base Nix/NixOS userspace,
- Workestrate runtime,
- agent runtimes,
- common compilers/toolchains,
- language runtimes,
- common CLI/dev tools,
- browser/runtime dependencies,
- common project toolchains,
- dependencies known to recur across a fleet.

Highly specific temporary derivations can remain in a VM upper and/or Cachix until there is evidence they deserve promotion.

## 9. Guest store layout with Nix `local-overlay`

Each consumer VM receives:

1. a pinned read-only generation,
2. a private writable upper,
3. a private Nix state database for upper-layer metadata,
4. an OverlayFS workdir on the same filesystem as the upper.

Conceptually:

```text
read-only lower:
  /run/workestrate/nix-lower/nix/store

private writable VM state:
  /var/lib/workestrate/nix-upper/store
  /var/lib/workestrate/nix-upper/work
  /var/lib/workestrate/nix-upper/state

merged:
  /nix/store
```

The guest mounts:

```bash
mount -t overlay overlay \
  -o lowerdir=/run/workestrate/nix-lower/nix/store \
  -o upperdir=/var/lib/workestrate/nix-upper/store \
  -o workdir=/var/lib/workestrate/nix-upper/work \
  /nix/store
```

And Nix is configured using the experimental `local-overlay` store, with a shape like:

```text
local-overlay://?root=<merged-root>&lower-store=<lower-store-root>&upper-layer=<upper-dir>
```

Nix should keep `check-mount = true` unless there is a very specific reason not to.

### Invariants

- lower generation is immutable for the full VM lifetime,
- lower is exported read-only by the host/VMM, not merely mounted `ro` by guest convention,
- every VM gets a separate upper,
- one VM cannot see another VM's upper,
- upper and OverlayFS workdir satisfy the same-filesystem constraint,
- host publisher owns lower-generation GC,
- guest GC only deals with guest upper semantics,
- new published generations never silently replace a running VM's lower.

## 10. Current `local-overlay` GC caveat

As of September 2026, Nix issue `NixOS/nix#16269` is still open.

The bug affects finite-limit GC paths for `local-overlay`, including automatic `min-free` / `max-free` behavior. Lower-only paths can leave `bytesFreed` effectively wrong/uninitialized, causing collection to stop early without reclaiming the intended upper-store garbage.

For this architecture, do not casually enable automatic space-triggered GC and assume it bounds a persistent overlay upper.

For the first implementation:

- pin a known Nix version,
- carry the small fix if upstream has not released it,
- add a regression test specifically for finite-limit/automatic GC,
- implement and test the `remount-hook` behavior Nix documents for overlay deletion/remount cases,
- for ephemeral agents, deleting the entire private upper on VM destruction is a clean lifecycle anyway.

This is exactly the kind of low-level behavior Workestrate's planned black-box/property-based runtime tests should hammer continuously.

## 11. Build and substitution flow

A normal agent/workload can resolve a needed store path through a hierarchy:

```text
1. already present in pinned lower generation
              |
              v miss
2. local host binary-cache endpoint, optional
              |
              v miss
3. Cachix / cache.nixos.org substituters
              |
              v miss
4. trusted remote builder VM
              |
              v
5. result copied into workload's private upper
```

The trusted builder can then push reusable successful outputs to Cachix, and selected closures can be promoted into a future shared generation.

### Ordinary agent policy

- no Cachix write credential,
- preferably no unrestricted local builds,
- remote builder allowed,
- private upper usually ephemeral,
- persistent project workspace is separate from Nix store lifetime.

### Development VM policy

- same shared lower,
- upper may be persistent,
- local builds may be allowed,
- remote builder still preferred for expensive/common derivations,
- promotion of outputs to fleet-wide state is explicit.

### Builder policy

- infrastructure-trusted,
- owns Cachix write authority,
- can build for host and guests,
- can use upstream substituters itself,
- `builders-use-substitutes = true` so clients do not need to upload every build input manually.

## 12. Should the NixOS host also build through this VM?

Yes, that makes sense.

The host can keep its normal boot-critical `/nix/store` while delegating builds to the builder VM through Nix's remote/distributed builder mechanism.

Conceptually on NixOS:

```nix
{
  nix.distributedBuilds = true;

  nix.settings = {
    builders-use-substitutes = true;
    max-jobs = 0; # optional: force normal host builds away from the host
  };

  nix.buildMachines = [
    {
      hostName = "workestrate-builder";
      sshUser = "nixbuilder";
      sshKey = "/run/secrets/workestrate-builder-key";
      protocol = "ssh-ng";
      system = "x86_64-linux";
      maxJobs = 16;
      supportedFeatures = [ "big-parallel" ];
      # Add "kvm" only when nested virtualization is intentionally supported.
    }
  ];
}
```

This provides most of the operational benefit without making the running host dependent on an experimental overlay store.

### Should the host itself use the same `local-overlay` store?

Possible, but not a first milestone.

It introduces unnecessary coupling into:

- NixOS boot and recovery,
- host generation switching,
- `nixos-rebuild`,
- host GC,
- failure recovery when the publisher/builder is unavailable.

There is only one host but potentially tens or hundreds of workload VMs, so the multiplicative win is in the workload fleet.

The ideal first design is:

- host normal local store,
- host remote-builds through builder VM when desired,
- host also consumes Cachix,
- workload VMs receive shared immutable lower generations.

## 13. Optional local HTTP binary cache

Even with Cachix, it can be wasteful to send a miss out to the network and back when the same artifact already exists locally but is not in the pinned lower generation.

An optional host-local or infrastructure-local binary-cache endpoint can sit before Cachix in substituter priority.

Harmonia is attractive because it can serve a Nix store directly.

This is an optimization, not a prerequisite. The most important local fast path remains the shared lower generation itself.

## 14. Root disk and image CoW

Nix-store sharing only fixes one source of duplication. VM root filesystems should also share storage.

Current Microsandbox already has useful mechanisms:

- shared content-addressed read-only OCI layers,
- per-sandbox writable upper layers,
- flat OCI root disks,
- `clone=auto`, which prefers native CoW cloning and falls back to copying,
- `clone=reflink`, which requires native clone support,
- native `FICLONE` on Linux for flat root-disk cloning.

So the first Workestrate implementation should consume those primitives rather than inventing another root-disk layer immediately.

A more optimized Nix-oriented guest image can eventually become fairly small:

```text
root/image base:
  init / systemd or minimal init
  mount tooling
  Nix client/daemon plumbing
  certs
  Workestrate guest glue
  SSH/agentd/control-plane glue if needed

shared Nix generation:
  large reusable packages/toolchains/runtimes

private Nix upper:
  workload-specific additions
```

This is much better than baking the same large Nix-built agent closure into every VM image.

## 15. KSM implementation path

KSM requires cooperation at two levels.

### Host

- Linux kernel with `CONFIG_KSM=y`,
- `ksmd` enabled/tuned via `/sys/kernel/mm/ksm/*`,
- metrics and CPU-cost monitoring.

### VMM

The VMM must call:

```c
madvise(addr, length, MADV_MERGEABLE)
```

on eligible anonymous guest RAM mappings.

That means simply enabling KSM globally on the host is not enough if libkrun never marks guest RAM mergeable.

The desired Workestrate-level policy should look conceptually like:

```toml
[vm.memory]
sharing = "ksm" # none | ksm | future template-cow
trust_domain = "local-agents"
```

KSM should not silently be enabled for arbitrary mutually untrusted tenants. Memory deduplication has historically created side-channel concerns. For Workestrate's local single-owner agent fleets, it is much more reasonable, but it should still be an explicit policy/capability.

### Metrics

At minimum observe:

- `/sys/kernel/mm/ksm/pages_shared`,
- `pages_sharing`,
- `pages_unshared`,
- `full_scans`,
- per-VMM RSS and PSS,
- CPU time consumed by `ksmd`,
- convergence time after boot,
- effect of guest memory churn.

The real question is empirical: how much does KSM recover after 10, 50, 100 near-identical agent VMs?

## 16. virtio-fs DAX as another memory-sharing experiment

Upstream libkrun exposes configurable virtio-fs DAX window sizing.

A read-only Nix store is a particularly interesting candidate because its files are immutable and read-heavy. If executable/library/file pages can be mapped more directly instead of being repeatedly copied into independent guest page caches, the system may reduce memory duplication before KSM even scans anonymous RAM.

This should be benchmarked, not assumed.

Workestrate should model it as an optional backend capability rather than making the whole design depend on it.

## 17. True warm-template memory CoW

The eventual ideal is closer to VM forking:

```text
boot base VM
install/mount shared generation
initialize common userspace
start common guest services
pause at a clean point
             |
             v
      memory + device snapshot
        /       |       \
       /        |        \
 child A     child B     child C
```

Children should initially share parent memory and diverge on write.

That requires considerably more than KSM:

- VM pause/quiesce,
- vCPU state capture,
- device state capture,
- guest RAM capture,
- restore into multiple children,
- private-on-write memory mapping or an equivalent mechanism,
- consistent disk snapshot/fork point,
- new per-child identity,
- safe vsock/network reconnection,
- entropy/clock handling,
- process/socket semantics inside the guest,
- potentially VMGenID-like behavior.

This is why it should be treated as a later backend capability such as:

```text
memory_snapshot_restore
memory_template_cow
```

rather than pretending KSM and VM-fork memory are the same feature.

If a Clone/forkd/Firecracker-style backend eventually implements this more naturally than libkrun, Workestrate should be able to use that backend without changing the workload-level contract.

## 18. NixOS as reference host

NixOS is the cleanest host for this design because the entire fabric can become a flake/module rather than a sequence of imperative setup commands.

A NixOS module can own:

- KVM and nested virtualization policy,
- Btrfs/XFS layout,
- KSM service/tuning,
- remote builder registration,
- Cachix substituter/trusted key configuration,
- SOPS secrets,
- Workestrate services,
- store publication services/timers,
- generation GC,
- local cache endpoint,
- metrics/exporters,
- libkrun/Microsandbox fork pins.

This does not mean the architecture only works on NixOS.

## 19. Generic Linux host

A normal Linux host can provide the same runtime semantics if it has:

- KVM,
- Nix,
- OverlayFS support in guests,
- a suitable VMM/backend,
- a CoW/reflink-capable filesystem if storage sharing is desired,
- service supervision,
- KSM if RAM dedup is desired.

The main loss is declarative integration and reproducibility, not the core virtualization primitives.

Workestrate should therefore expose capabilities rather than hard-code `Btrfs + KSM + FICLONE` into its universal API.

## 20. Security model

Density is not worth collapsing trust boundaries.

### Shared lower is truly read-only

The generation should be read-only at the host/VMM export layer, not only mounted `ro` by guest convention.

A compromised guest kernel should not be able to remount the shared generation writable.

### Builder credentials

Default credential model:

- Cachix write token/key: builder/cache VM only,
- private-cache read credential: only consumers that need it,
- ordinary agent VM: no cache write authority,
- promotion into the shared generation: privileged action.

### Promotion boundary

A guest building `/nix/store/foo` does not mean `foo` automatically becomes trusted fleet-wide state.

Promotion should either:

1. ask the trusted builder to reproduce the derivation and publish the result, or
2. import into a trusted staging store and perform whatever verification/signing policy Workestrate defines before publication.

### Host path containment

A virtio-fs broker serving the lower generation sees a host path. The VMM/process should run in a host mount namespace where it can see only the exact paths it needs.

Defense in depth should resemble:

```text
guest
  -> virtio-fs implementation
      -> restricted VMM mount namespace
          -> one immutable generation
```

## 21. Workestrate should model semantics, not Microsandbox flags

This is where the architecture becomes valuable beyond one backend.

Workestrate should resolve a high-level store/runtime policy into a backend plan.

Conceptual workload configuration:

```toml
[store]
mode = "overlay"
generation = "latest-compatible"

[store.upper]
lifecycle = "ephemeral"
size = "20GiB"

[store.builder]
name = "nix-builder"
strategy = "remote-first"

[store.cache]
cachix = "rybskiworks"
local_cache = true

[vm.root]
clone = "reflink-preferred"

[vm.memory]
sharing = "ksm"
```

Conceptual internal plan:

```rust
struct StorePlan {
    generation: StoreGenerationId,
    lower: ReadOnlyStoreMount,
    upper: UpperStorePlan,
    builder: Option<BuilderEndpoint>,
    substituters: Vec<Substituter>,
}

struct BackendCapabilities {
    readonly_directory_mount: bool,
    reflink_root_clone: bool,
    block_cow_root: bool,
    nested_kvm: bool,
    mergeable_guest_memory: bool,
    vm_snapshot_restore: bool,
    template_memory_cow: bool,
    virtiofs_dax: bool,
}
```

Then `workestrate plan` could report:

```text
workload: ganymede
backend: microsandbox
store generation: sha256:...
lower: read-only virtio-fs
upper: ephemeral 20 GiB
builder: nix-builder
cache: local -> Cachix -> cache.nixos.org
root clone: reflink
memory sharing: KSM
nested virtualization: disabled
```

This is the right abstraction boundary because another backend may implement the same semantics differently.

## 22. Store generation lifecycle in Workestrate

A workload launch becomes roughly:

1. resolve the desired generation,
2. pin/lease that generation,
3. create the VM root clone,
4. create the VM's private Nix upper volume,
5. attach the shared lower generation read-only,
6. boot the guest,
7. mount OverlayFS / initialize the Nix `local-overlay` store,
8. configure builder/substituters,
9. start the workload,
10. on VM destroy, remove ephemeral upper and release generation lease.

Generation registry example:

```text
G40 refs=0 old
G41 refs=3
G42 refs=11 current
G43 publishing
```

Rules:

- published generation is never mutated,
- generation with live leases is never deleted,
- `current` is only a pointer/default selection,
- existing VMs do not silently follow `current`,
- failed publication never changes `current`,
- publisher GC and guest-upper GC are separate.

This also composes nicely with future checkpoint/Yggdrasil semantics because a checkpoint can record the exact store generation it depends on.

# 23. Current `rybskiworks` stack: concrete gaps

This is the section that matters for implementing the design with today's repositories.

## 23.1 `rybskiworks/workestrate`

The current default branch is still wired to an old upstream Microsandbox release in `nix/packages/microsandbox.nix`:

```nix
pname = "microsandbox";
version = "0.5.6";

url = "https://github.com/superradcompany/microsandbox/releases/download/v${version}/...";
```

So Workestrate is not currently consuming the much newer `rybskiworks/microsandbox` fork at all through that package.

Before this store fabric can sensibly land, Workestrate needs a lower-layer dependency strategy first.

Needed Workestrate work:

- move off the old 0.5.6 upstream binary packaging,
- pin/build the intended `rybskiworks/microsandbox` fork reproducibly,
- introduce backend capabilities instead of assuming one Microsandbox feature set,
- add store-generation registry and leases,
- add shared-lower + private-upper planning,
- add guest bootstrap for OverlayFS and Nix `local-overlay`,
- add builder/cache infrastructure workload type/profile,
- add promotion/publication orchestration,
- expose root clone policy,
- expose memory-sharing policy,
- expose nested-virtualization requirements for builder workloads,
- integrate all of this with the planned black-box/property-based E2E test system.

The older workaround of baking Nix-built tools into each image because `/nix/store` could not be safely shared should become unnecessary for closures that can live in the shared generation.

## 23.2 `rybskiworks/microsandbox`

The current fork identifies itself as Microsandbox `0.6.17`, which is substantially ahead of the `0.5.6` Workestrate package.

It already has useful storage primitives in this direction, including:

- read-only mount semantics at the Microsandbox surface,
- shared OCI image layers,
- per-sandbox writable state,
- flat root disks,
- reflink-preferred cloning,
- disk-oriented snapshots/fork primitives.

However, its root `Cargo.toml` currently pins:

```toml
msb_krun = "=0.1.32"
msb_krun_utils = "=0.1.32"
```

That is a crucial integration fact.

A feature implemented only in `rybskiworks/libkrun` does **not** automatically bubble into `rybskiworks/microsandbox`.

A reproducible fork dependency path is needed, for example:

- publish/version the forked `msb_krun` crates,
- use a Git dependency/patch pinned to the rybskiworks fork,
- or have the Nix build apply a deterministic Cargo source override.

Do not depend on a local developer-only Cargo patch.

Microsandbox work needed for this architecture:

- guarantee an end-to-end hard read-only directory export for the Nix lower store,
- expose backend capability reporting for that guarantee,
- expose root clone/reflink capability cleanly,
- expose nested-KVM capability for builder profiles,
- expose KSM/mergeable-memory mode once libkrun supports it,
- optionally expose per-mount virtio-fs DAX sizing for experiments,
- eventually expose resumable/full VM snapshots if libkrun gains real memory/device restore,
- keep the runtime process in a restricted host mount namespace around shared store paths.

Workestrate can own the higher-level concept of a "Nix shared generation". Microsandbox only needs to expose strong generic primitives.

## 23.3 `rybskiworks/libkrun`

There is a concrete divergence from current upstream relevant to this design.

Upstream libkrun exposes:

```c
krun_add_virtiofs3(..., uint64_t shm_size, bool read_only)
```

which explicitly supports a read-only virtio-fs export.

The current `rybskiworks/libkrun` `krun` branch header exposes `krun_add_virtiofs` and `krun_add_virtiofs2`, but not `krun_add_virtiofs3`.

For a shared Nix lower store, reconcile/port that functionality into the fork and ensure Microsandbox actually uses it where appropriate.

That should come **before** optimization work because the immutable lower store needs a fail-closed read-only boundary.

### libkrun KSM feature

Add an explicit Linux/KVM guest-memory sharing option that applies `MADV_MERGEABLE` to the actual anonymous guest RAM mapping.

Requirements:

- off by default,
- clear unsupported error on non-Linux/non-KSM environments,
- observable effective state,
- do not accidentally mark unrelated mappings or DAX/device regions,
- test interaction with NUMA/hugepage choices,
- native KVM integration tests that verify host KSM counters actually move.

The API should probably express a memory-sharing policy rather than expose a raw `madvise` boolean, because future template-memory CoW is a distinct mode.

### libkrun snapshot/restore later

Do not block the shared-store project on this.

True warm-template memory CoW needs a coherent Linux/KVM VM-state snapshot/restore story, including device state. Upstream libkrun snapshot/restore work is still an active area rather than a mature primitive that this design can simply assume.

## 23.4 `rybskiworks/libkrunfw`

KSM is a host/VMM memory feature, so it does not belong in the guest kernel firmware.

The firmware does need the filesystem and virtualization features required by this topology:

- virtio-fs,
- OverlayFS,
- ext4 if used for private uppers/root disks,
- EROFS/SquashFS only if those immutable image directions are adopted,
- nested KVM support for builder guest profiles only when intentionally required.

`CONFIG_OVERLAY_FS` should be verified in the exact firmware build rather than assumed.

## 23.5 Nix version

This architecture depends on an experimental Nix store type.

Therefore the guest Nix version should be pinned intentionally rather than inherited accidentally from whatever environment built the image.

The Workestrate/NixOS flake should carry:

- a known-good Nix version,
- `local-overlay-store` experimental feature enabled,
- the #16269 fix/patch while needed,
- tests for GC,
- tests for daemon restart,
- tests for copy/substitution/build into upper,
- tests that lower-only store paths are never mutated/deleted.

## 24. Nested virtualization and the builder

Some Nix derivations need the `kvm` system feature.

If the builder itself runs in a microVM, there are two choices:

1. builder does not advertise `kvm`, and KVM-requiring derivations route elsewhere,
2. Workestrate launches that infrastructure VM with nested virtualization enabled and the backend reports it as a supported capability.

This should be explicit configuration, not an accidental consequence of host CPU flags leaking into a guest.

Conceptually:

```toml
[infra.builder]
nested_virtualization = "require" # require | disable | allow
```

That matches the broader Workestrate idea of requirements/capabilities rather than backend-specific guessing.

## 25. Builder/cache VM image

The builder itself is a good candidate for a NixOS-based or otherwise Nix-built guest image.

It should contain:

- `nix-daemon`,
- build users,
- remote-builder transport,
- Cachix client/uploader,
- SOPS or Workestrate secret injection integration,
- durable build-store volume,
- egress policy to source/cache endpoints,
- optional nested KVM,
- metrics.

The host does not need to expose the builder as a general LAN SSH server. Workestrate could eventually bridge the Nix remote-builder protocol over its scoped broker/vsock/SSH control plane.

## 26. Secrets

The clean model is:

```text
Cachix write authority
      -> infrastructure builder only

Cachix read authority, if private
      -> consumers as required

store-generation write authority
      -> publisher only

shared generation
      -> workload VMs read-only
```

This fits Workestrate's broader secret-at-egress/brokered identity direction very well.

## 27. Failure behavior

### Cachix unavailable

- existing lower generation still works,
- local cache may still work,
- builder can build if sources are reachable,
- cache push can retry later,
- new remote substitutions may fail.

### Builder unavailable

- existing lower generation works,
- Cachix substitutions work,
- already-satisfied workloads keep running,
- local builds only happen where policy allows them.

### Publisher unavailable

- existing VMs keep their mounted pinned generation,
- new VMs can use already-published generations,
- only creation/promotion of new shared generations is blocked.

### Bad generation

- mark generation invalid,
- stop new leases,
- roll default pointer back,
- retain enough state for diagnosis,
- never mutate the bad generation in place.

## 28. Testing

The architecture is only worthwhile if the sharing/isolation properties are tested from outside the guest.

### Store tests

- launch VM A and B from one generation,
- both resolve lower paths through Nix,
- A builds/adds a path and only A's upper changes,
- B cannot see A's upper,
- neither can mutate lower,
- destroying A leaves B/lower untouched,
- publishing G43 does not change running G42 guests,
- finite-limit GC actually reclaims upper garbage,
- lower-only paths are never deleted.

### Publication tests

- import a closure,
- verify closure metadata,
- freeze generation,
- crash publisher at each publication phase,
- prove default generation pointer is atomic,
- prove generation with live lease cannot be deleted.

### Remote builder tests

- host with local builds disabled builds through builder,
- workload VM builds through builder,
- builder uses substitutes itself,
- returned path lands in workload upper,
- builder pushes to Cachix,
- a later generation can promote the closure.

### Storage CoW tests

Measure allocated physical blocks, not apparent image size:

- N VM clones from same root base,
- divergence in one VM,
- only changed extents allocate,
- compare reflink vs forced full-copy behavior.

### KSM tests

- launch N identical guests,
- confirm libkrun marks guest RAM mergeable,
- wait for KSM convergence,
- measure PSS/RSS and KSM counters,
- dirty pages in one guest and verify isolation,
- verify non-KSM workloads are not marked mergeable,
- measure CPU cost and convergence latency.

## 29. Observability

The whole point is measurable density.

Useful metrics:

```text
workestrate_store_generation_bytes{generation=...}
workestrate_store_generation_leases{generation=...}
workestrate_store_upper_bytes{workload=...}
workestrate_nix_resolution_total{source=lower|local_cache|cachix|builder}
workestrate_builder_queue_depth
workestrate_builder_seconds
workestrate_root_allocated_bytes{workload=...}
workestrate_vm_rss_bytes{workload=...}
workestrate_vm_pss_bytes{workload=...}
workestrate_ksm_pages_shared
workestrate_ksm_pages_sharing
workestrate_ksm_full_scans
```

The useful density model becomes:

```text
physical storage ~= shared store generations
                 + shared image/root bases
                 + sum(private changed root blocks)
                 + sum(private Nix uppers)

physical RAM ~= VMM/device overhead
             + unique guest working sets
             + shared file-backed pages
             + KSM-shared anonymous pages
             + future template-shared pages
```

## 30. Staged implementation

### Stage 0: prove Nix `local-overlay` inside one backend

No Cachix and no KSM yet.

- create a lower local store,
- freeze it,
- export it read-only,
- boot two VMs,
- give each a private upper,
- test Nix query/build/copy/GC behavior.

### Stage 1: generation publisher

- host publication store,
- immutable Btrfs snapshots or equivalent,
- generation manifests,
- leases,
- atomic default pointer,
- publisher GC.

### Stage 2: builder/cache VM

- trusted remote Nix builder,
- Cachix uploader,
- host remote-builder configuration,
- workload remote-builder configuration,
- explicit promotion into publication store.

### Stage 3: Workestrate first-class model

- `StorePlan`,
- backend capability reporting,
- config schema,
- guest bootstrap,
- generation lifecycle,
- CLI `plan/status/publish/gc`,
- black-box tests.

### Stage 4: maximize storage sharing

- migrate Workestrate from Microsandbox 0.5.6 packaging to current fork,
- consume flat/reflink root-disk primitives,
- remove unnecessary baked Nix closures from VM images,
- optionally add local Harmonia,
- benchmark builder-private vs host-backed publisher store.

### Stage 5: KSM

- libkrun mergeable guest-RAM option,
- Microsandbox surface/capability,
- Workestrate policy/trust-domain model,
- NixOS KSM tuning module,
- metrics and benchmarks.

### Stage 6: warm-template VM memory research

Only after the simpler layers are measured.

Compare:

- extending libkrun snapshot/restore,
- Clone-like VM fork semantics,
- Firecracker/forkd-style backend,
- userfaultfd/lazy-restore approaches,
- backend-specific snapshot primitives.

Do not force every backend to implement memory CoW the same way.

## 31. Practical dependency order for the current rybskiworks stack

The lower-layer work should happen approximately in this order:

```text
1. Pin/fix Nix local-overlay behavior
2. Reconcile hard read-only virtio-fs in rybskiworks/libkrun
3. Verify libkrunfw OverlayFS support
4. Make rybskiworks/microsandbox consume the intended libkrun fork reproducibly
5. Expose/verify read-only mount capability in Microsandbox
6. Move Workestrate off the old upstream Microsandbox 0.5.6 binary
7. Implement Workestrate store generations + private uppers
8. Add builder/cache infrastructure workload + publication path
9. Integrate Microsandbox root-disk CoW/reflink primitives
10. Add libkrun KSM
11. Bubble KSM through Microsandbox capability/config
12. Bubble KSM through Workestrate policy/config
13. Research full memory snapshot/fork only later
```

The shared-store work should not be blocked on true VM-memory CoW.

## 32. Reference implementation choices I would use first

For a serious first prototype:

- **host**: NixOS,
- **host state filesystem**: Btrfs,
- **builder**: dedicated Workestrate-managed infrastructure microVM,
- **builder store**: private initially,
- **Cachix**: durable off-host binary cache, builder is the only writer,
- **publication store**: separate host local-store root populated through `nix copy`,
- **generation mechanism**: read-only Btrfs snapshots,
- **VM lower attachment**: hard read-only virtio-fs,
- **VM Nix**: pinned Nix 2.34.x+ with `local-overlay-store` and the GC bug fixed/patched,
- **VM upper**: private per workload, ephemeral by default for agents,
- **root image**: Microsandbox flat/reflink where appropriate,
- **host Nix**: normal host store, optional `max-jobs = 0` to force builds into builder VM,
- **local HTTP cache**: optional Harmonia later,
- **RAM sharing**: KSM after the store/image path is working,
- **true warm-memory CoW**: explicitly deferred.

That gets most of the likely storage win and a meaningful fraction of the RAM win without making the first version depend on immature VM-state cloning.

## 33. Open benchmark questions

1. virtio-fs vs read-only block image for a very large Nix lower store under metadata-heavy agent workloads?
2. Does virtio-fs DAX materially reduce host RSS for common Nix executables/libraries?
3. How much memory does KSM actually save at 10, 50, 100 similar agent VMs?
4. How long does KSM take to converge, and what CPU cost does it impose?
5. How badly do zram/swap-heavy workloads reduce sustained KSM benefit?
6. Is the additional builder-private -> publication-store copy expensive enough to justify a trusted host-backed publication subvolume?
7. Should store generations be one broad fleet base, project-specific bases, or composable layers?
8. At what point should frequently recurring upper-layer paths be promoted automatically?
9. How does Microsandbox virtio-fs behave under high-concurrency Nix metadata/stat workloads?
10. At what VM density does true warm-template memory CoW justify maintaining deeper VMM changes?

## 34. References

### Nix

- Experimental `local-overlay` store, Nix 2.34.9: https://nix.dev/manual/nix/2.34/store/types/experimental-local-overlay-store
- Distributed builds: https://nix.dev/tutorials/nixos/distributed-builds-setup.html
- Current `local-overlay` finite-limit GC bug: https://github.com/NixOS/nix/issues/16269

### Cachix and local cache

- Cachix: https://www.cachix.org/
- Cachix docs: https://docs.cachix.org/
- Harmonia: https://github.com/nix-community/harmonia
- Attic: https://github.com/zhaofengli/attic

### Linux memory

- KSM documentation: https://docs.kernel.org/admin-guide/mm/ksm.html

### Microsandbox / libkrun

- Microsandbox: https://github.com/superradcompany/microsandbox
- Microsandbox root-disk clone docs: https://github.com/superradcompany/microsandbox/blob/main/docs/cli/sandbox-commands.mdx
- Microsandbox filesystem security model: https://github.com/superradcompany/microsandbox/blob/main/docs/security/filesystem.mdx
- libkrun API: https://github.com/libkrun/libkrun/blob/main/include/libkrun.h

### rybskiworks integration targets

- https://github.com/rybskiworks/workestrate
- https://github.com/rybskiworks/microsandbox
- https://github.com/rybskiworks/libkrun
- https://github.com/rybskiworks/libkrunfw

## 35. Bottom line

The ideal system is not:

```text
one mutable /nix/store shared writable by every VM
```

It is:

```text
trusted builder builds once
        |
        +--> pushes durable output to Cachix
        |
        +--> promotes useful closure into publication store
                                  |
                                  v
                         immutable generation G
                                  |
                    shared read-only across many VMs
                      /            |            \
                     /             |             \
             private upper A  private upper B  private upper C

shared root/image base -> storage CoW per VM
shared anonymous RAM   -> KSM
warm parent RAM        -> true VM/template CoW later
```

The goal is that each workload can **behave as though it owns a complete independent Nix machine**, while the physical host pays for immutable common state, common image blocks, and eventually common memory pages as close to once as the isolation layers safely permit.
