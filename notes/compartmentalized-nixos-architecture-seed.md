# Architecture Seed: A Compartmentalized, NixOS-Native Workstation

Status: exploratory architecture seed

Date: 2026-09-10

Scope: Linux-first, NixOS-derived system configuration / flake

This document is intentionally more ambitious than an implementation plan and less final than a specification. Its purpose is to preserve an architecture direction, make the boundaries explicit, identify plausible implementation stacks, and create a serious starting point for later SPEC, ADR, threat-model, and PRD work.

It is not a proposal to turn Workestrate into an operating system. Workestrate is one possible control-plane component that could be reused if its abstractions fit. The system described here should remain coherent without requiring Workestrate specifically.

Likewise, this does not require a fork of NixOS or nixpkgs. The implementation can remain a highly opinionated NixOS flake, module set, guest-image library, and small collection of runtime components and downstream forks. If the resulting operating model is different enough from ordinary NixOS, calling it a distro or proto-distribution may be useful shorthand, but that is not an architectural requirement.

## 1. Thesis

The physical host should be boring, durable, small, and rarely switched.

Most user software should not be installed into the physical host at all. Applications, development environments, agents, browsers, risky files, build environments, and potentially whole user contexts should run in isolated virtual-machine compartments whose configuration, policy, state, provenance, and lifecycle are managed declaratively.

The user should still experience one coherent desktop.

The target combines several ideas:

- Qubes-style security by compartmentalization.
- NixOS and Nix closures as the system construction and reproducibility substrate.
- Lightweight KVM microVMs as the ordinary application boundary.
- Shared immutable guest bases plus copy-on-write storage instead of full VM copies.
- Eventually, memory snapshot/fork and page sharing where the runtime can support it safely.
- A Wayland-first seamless GUI where windows from different VMs appear in one compositor.
- Explicit capability brokerage for clipboard, files, audio, camera, screen capture, USB, credentials, networking, and similar cross-domain operations.
- Agent assistance for proposing, testing, and evolving system configurations, while deterministic software remains the enforcement layer.
- Recursive testability: the system should be able to instantiate disposable copies of its own architecture and let agents exercise them as a systems laboratory.

A useful mental model is:

```text
Nix defines what machines are.
Policy defines what machines may do.
The VMM/hypervisor enforces machine isolation.
Brokers mediate intentional cross-domain capabilities.
The compositor makes isolated applications feel like one desktop.
Agents help author, test, and evolve the declarative model.
```

The core design objective is not merely an immutable host. It is to make most ordinary changes not be host changes in the first place.

## 2. Non-goals and constraints

The architecture should not begin by trying to replace all of NixOS, write a new hypervisor, or recreate every Qubes component.

Initial non-goals:

- No requirement to fork NixOS or nixpkgs.
- No requirement to use Xen.
- No requirement that every workload use one VMM backend.
- No requirement for Windows or macOS guests or hosts. Linux x86_64 is the primary target.
- No requirement to hide virtualization from software or anti-cheat systems.
- No claim that AI is a security boundary.
- No assumption that every device can be safely or efficiently virtualized.
- No requirement that the first version split networking, storage, GUI, USB, and administration into separate service domains.
- No requirement that existing Workestrate, Microsandbox, libkrun, or other projects remain unchanged.

The design should prefer standard Linux, Nix, Wayland, PipeWire, KVM, and virtio mechanisms where they are adequate. Forks should exist only where a missing primitive is important enough to justify carrying one.

## 3. Architectural principles

### 3.1 The host-host is infrastructure, not the user's workstation

The bare-metal NixOS generation should contain only what is necessary to boot, own hardware, enforce the top-level isolation boundary, construct the next layer, and recover the machine.

Typical L0 responsibilities:

- Linux kernel and KVM.
- IOMMU/VFIO setup.
- Disk and filesystem primitives needed to host VM artifacts.
- Minimal networking required to provision or recover higher layers.
- A small control surface for VM lifecycle and policy bootstrap.
- Attestation or measured-boot facilities if adopted later.
- Logging and recovery facilities that must survive higher-layer failure.

Things that should normally not require an L0 switch:

- Installing a browser or editor.
- Changing a project toolchain.
- Installing CUDA userland into a compute workload.
- Updating an agent harness.
- Changing Python, Node, Rust, Java, or project dependencies.
- Updating ordinary desktop applications.
- Creating a new untrusted inspection environment.
- Changing a workload's network or credential policy.

Host switches should feel consequential. Workload switches should feel routine.

### 3.2 Identity and policy are separate from implementation backends

A workload should have a stable identity and declared capabilities independent of whether it currently runs on Microsandbox/libkrun, Clone, crosvm, Cloud Hypervisor, QEMU, Firecracker, or a future backend.

The public model should describe intent such as:

```text
workload identity
base generation
persistent volumes
CPU/memory class
network policy
credential bindings
GUI capability
clipboard capability
screen-capture capability
device capability
persistence mode
nested-virtualization requirement
GPU mode
snapshot/fork policy
```

Backend-specific knobs can exist, but should not leak upward unless they represent a real semantic difference.

### 3.3 Capability mediation should be explicit

Cross-domain behavior should not emerge accidentally from ambient host access.

Capabilities that should eventually have explicit policy include:

- network egress and ingress
- DNS
- files and directory mounts
- clipboard import/export
- drag and drop
- explicit file transfer
- URL opening
- notifications
- audio output
- microphone
- camera
- screen capture
- remote input
- USB
- GPU
- GPU compute
- SSH agent access
- signing keys
- API credentials
- browser credential stores
- host or peer RPC
- inter-workload service access

The ideal model is deny-by-default for sensitive crossings, with narrow grants and clear provenance.

### 3.4 AI proposes, deterministic layers enforce

An agent may translate user intent into configuration, generate policy changes, build candidate generations, test them, and present a diff.

It should not be the authority deciding whether an operation is permitted at runtime.

```text
user intent
    |
    v
AI / tooling proposes configuration
    |
    v
deterministic config + policy evaluator
    |
    v
runtime/broker/kernel enforcement
```

This gives agents useful power without making model behavior part of the trusted computing base.

### 3.5 Provenance is a first-class desktop primitive

A visible application window should have a trusted origin that cannot be forged merely by copying an application name or icon.

The trusted side should know at least:

- workload identity
- workload generation
- base-image generation
- runtime backend
- trust/profile class
- whether the workload is ephemeral
- whether an agent owns or can mutate it
- relevant granted capabilities

The compositor or a trusted shell surface can expose this as a subtle border, titlebar treatment, badge, inspect action, or equivalent mechanism.

## 4. Relationship to Qubes OS

Qubes is the clearest existing reference architecture for the user experience and trust model. It uses Xen, isolates applications and system components into qubes, centralizes template updates, provides secure cross-domain RPC through qrexec, and implements GUI virtualization so applications from isolated VMs appear local.

The proposed system should borrow principles rather than blindly copy implementation choices.

Useful Qubes ideas to retain:

- security by compartmentalization
- explicit domain identity
- trusted GUI-side provenance
- narrow cross-domain RPC
- policy-gated inter-domain services
- disposable domains
- template/base separation from per-domain state
- moving risky network and device stacks out of the most privileged domain
- eventually separating GUI and administrative authority

Likely differences:

- NixOS and Nix closures are the primary construction and update model.
- KVM is the initial virtualization substrate.
- Lightweight microVM runtimes may be used instead of one general-purpose hypervisor stack.
- Wayland is the primary GUI protocol.
- Workloads may have much shorter lifetimes and much cheaper creation through storage and memory CoW.
- Backends may be heterogeneous.
- The system is designed to be unusually friendly to automated construction and black-box testing by agents.

This should be thought of as Qubes-inspired, not Qubes-compatible and not a Qubes replacement unless much later work demonstrates equivalent security properties.

## 5. Topology options

The architecture should not prematurely commit to one topology. Two configurations are especially useful.

### 5.1 Simpler topology: L0 owns the desktop

```text
+-------------------------------------------------------------+
| L0: NixOS host                                              |
|                                                             |
| KVM, compositor, PipeWire, brokers, policy, VM runtime      |
|                                                             |
|   +-----------+   +-----------+   +-----------+             |
|   | app VM A  |   | app VM B  |   | agent VM |             |
|   +-----------+   +-----------+   +-----------+             |
+-------------------------------------------------------------+
```

Advantages:

- Much easier to prototype.
- No nested virtualization requirement.
- Fewer layers in graphics and input paths.
- Easier debugging and hardware enablement.
- Good environment for proving the storage, policy, GUI, and portal model.

Disadvantages:

- The graphical desktop and VM runtime enlarge the L0 trusted computing base.
- Driver complexity lives directly in the physical host.
- Desktop changes may cause more frequent host generations.

This is a sensible first implementation even if it is not the desired final topology.

### 5.2 Nested topology: minimal L0, desktop/workload host in L1, apps in L2

```text
physical hardware
      |
      v
+-------------------------------------------------------------+
| L0: minimal NixOS host                                      |
|                                                             |
| kernel, KVM, IOMMU/VFIO, storage, bootstrap/control         |
|                                                             |
|             physical GPU passthrough                        |
|                        |                                    |
+------------------------|------------------------------------+
                         v
+-------------------------------------------------------------+
| L1: desktop / graphics / workload-host VM                   |
|                                                             |
| GPU driver, Wayland compositor, PipeWire, portals,          |
| capability brokers, nested KVM, VMM runtime                 |
|                                                             |
|   +-----------+   +-----------+   +-----------+             |
|   | L2 dev VM |   | browser   |   | agent VM  |             |
|   +-----------+   +-----------+   +-----------+             |
+-------------------------------------------------------------+
```

This topology is attractive because the physical host can remain almost appliance-like. GPU drivers, the desktop environment, user-facing services, and ordinary application stacks can change without rebuilding L0.

However, it must be treated as an experiment until measurements prove that nested KVM, virtio-gpu, suspend/resume, input, audio, screen sharing, and workload density are acceptable.

The important GPU rule is:

```text
physical GPU --VFIO--> L1
L1 GPU driver --virtio-gpu--> L2 workloads
```

Do not assume the physical device can or should be passed through again into arbitrary L2 guests.

### 5.3 Later topology: split service domains

If the system becomes security-oriented enough, L1 itself can be decomposed:

```text
L0
 |
 +-- admin/control domain
 +-- GUI domain
 +-- network domain
 +-- USB/device domain
 +-- storage/build domain
 +-- workload-host domain
       |
       +-- application VMs
```

This is closer to Qubes, but is intentionally not a first milestone. It increases the amount of cross-domain protocol design substantially.

## 6. Nix and storage model

The storage model is central to making VM-per-scope practical rather than theatrical.

A target workload should look approximately like:

```text
immutable guest base generation
        +
immutable/prepopulated Nix store lower
        +
workload or session Nix-store upper
        +
root filesystem CoW delta
        +
explicit persistent volumes
        +
ephemeral tmpfs/runtime state
```

### 6.1 Immutable base generation

A base generation should contain only broadly reusable guest state:

- kernel/firmware requirements
- init and guest integration
- Nix client/daemon if required
- certificates
- common libraries
- common diagnostics
- GUI proxy/guest portal pieces for graphical bases
- workload bootstrap protocol

Different bases can exist for minimal, development, browser, graphical, compute, and specialized workloads, but uncontrolled base proliferation should be avoided.

### 6.2 Shared Nix store lower

A major opportunity is to make `/nix/store` a shared immutable lower layer rather than baking repeated closures into every VM image.

Nix 2.34 includes the experimental `local-overlay` store, which combines a lower store and an upper almost-store through OverlayFS. Nix deliberately does not mount the OverlayFS itself, so the system configuration must own the mount lifecycle. The lower store must remain unchanged while it is being used.

This maps well to an immutable generation model, but the feature is still experimental and has had real GC correctness bugs. Therefore the public system schema should not promise `local-overlay` specifically.

Prefer an abstract semantic such as:

```text
store.strategy = layered
```

The implementation may initially be Nix local-overlay + OverlayFS, but can change without forcing every workload definition to change.

### 6.3 Disk-level CoW

Nix-store layering and virtual-disk layering solve different problems and can be composed.

Possible mechanisms:

- qcow2 backing chains
- runtime-native block layers
- Microsandbox writable root layers
- Clone overlay mode
- dm-thin or other host storage backends where appropriate

The ideal guest root is mostly disposable. Persistent state should be carved out deliberately.

```text
/
  mostly ephemeral
/nix/store
  layered, immutable lower + scoped upper
/home or /data
  explicit persistent volume when required
/work
  explicit workspace volume
/tmp
  tmpfs
/run
  tmpfs
secrets
  brokered, not stored in the image
```

### 6.4 Builder and binary-cache topology

Guest VMs should generally substitute rather than build expensive shared dependencies independently.

A dedicated Nix builder appliance is a natural role:

```text
                       +--------------------+
flake/config --------->| Nix builder VM     |
                       | large local store  |
                       +---------+----------+
                                 |
                           post-build push
                                 |
                                 v
                          binary cache
                                 |
                   +-------------+-------------+
                   |             |             |
                   v             v             v
                dev VM        app VM        image build
```

Nix already supports remote builders over SSH and advertises system features such as `kvm`. Cachix can consume newly built store paths through a post-build hook, `watch-store`, or `watch-exec`.

The exact cache product is replaceable. The architectural requirements are:

- immutable signed artifacts
- reproducible input pins
- garbage-collection policy
- base-generation pinning
- a way to prewarm common closures
- clear provenance between builder output and guest generation

### 6.5 Memory CoW and warm forks

Memory sharing is not required for correctness, but it can radically improve the economics of VM-per-workload.

Potential layers:

1. ordinary host overcommit
2. KSM for identical pages
3. ballooning/reclaim
4. full and incremental memory snapshots
5. warm-template fork using private CoW mappings

The current Microsandbox public snapshot contract is disk-only. Its resumable snapshot API is reserved but not yet implemented. However, the lower `msb_krun` API already contains memory-generation, incremental capture, execution-state, and block-layer primitives. Those pieces are useful substrate but do not yet constitute a finished safe VM-fork product.

`unixshells/clone` is particularly relevant here. Its stated design centers on a warm template VM and `MAP_PRIVATE` memory mappings for forked children, with KSM, ballooning, disk overlays, per-fork identity injection, fork-compatible userspace networking/vsock, snapshots, and live migration. It is young and should be evaluated rather than assumed production-ready, but its architecture closely matches the desired high-density L2 workload model.

A critical requirement for any memory-fork implementation is identity reconstitution. A child must not simply inherit every piece of parent identity. At minimum evaluate:

- vsock CID
- MAC/IP identity
- hostname/machine-id policy
- kernel randomness and VM generation IDs
- wall clock and monotonic-time semantics
- application-level connection state
- service recovery after fork
- credential/session state
- cryptographic RNG reseeding

The existing VM-generation work in the libkrun/libkrunfw lineage is especially relevant to this problem.

## 7. GUI model: one desktop, many machines

The target user experience is not a collection of VM consoles.

A graphical app running in a workload VM should appear as an ordinary top-level window in a trusted compositor.

```text
L2 application
    |
    | Wayland
    v
guest proxy
    |
    | virtio-gpu cross-domain / equivalent transport
    v
trusted compositor in L0 or L1
    |
    v
physical display
```

### 7.1 Candidate stack

The strongest existing candidate is the crosvm/Sommelier model:

- guest kernel with `CONFIG_DRM_VIRTIO_GPU`
- virtio-gpu cross-domain support in the VMM
- Sommelier or sommelier-rs inside the guest
- host Wayland compositor

`google/sommelier-rs` explicitly targets unmodified applications inside a VM displaying seamlessly on the host desktop, with native window management and clipboard sharing. It is Wayland-only by design.

Alternatives or supplements:

- classic Sommelier
- waypipe over vsock for simpler experiments
- a custom narrow Wayland proxy if stronger provenance/policy integration becomes necessary

The architecture should avoid implementing a new display protocol until existing Wayland virtualization is proven inadequate.

### 7.2 Trusted window provenance

The guest must not be able to claim arbitrary trust merely by choosing a title, icon, or app ID.

The trusted side should bind the incoming GUI connection to the VM identity that owns its transport. Window provenance should therefore be derived from the authenticated VM/channel, then augmented with guest metadata.

Possible trusted UI:

```text
Application: Firefox
Origin: personal-browser
Generation: workload 183 / base 42
Backend: libkrun
Persistence: profile volume only
Network: personal-vpn policy
Clipboard export: prompt
Agent control: none
```

The exact visual design can remain subtle. The important property is that trusted origin metadata cannot be spoofed by an untrusted workload.

### 7.3 X11 compatibility

The system should remain Wayland-first. X11 applications can initially run under Xwayland inside the workload if necessary. The host should not need an X11 security model to support legacy guests.

## 8. Desktop portals as a cross-VM capability API

`xdg-desktop-portal` already provides a useful shape for sensitive desktop operations. Rather than bypassing portals, the system can make them workload-aware.

Candidate mediated operations:

- file chooser and file transfer
- OpenURI
- notifications
- camera
- microphone/audio capture
- screen capture
- remote input
- clipboard
- printing
- secret storage

### 8.1 Screen capture

If a conferencing application runs in the same domain as the compositor, ordinary Wayland portal capture is straightforward.

The more interesting case is when the conferencing application itself runs in an isolated L2 VM and wants to share another L2 window or an L1 desktop surface.

A plausible path is:

```text
L2 conferencing app
    |
    | xdg portal request
    v
guest portal backend
    |
    | authenticated vsock/RPC
    v
trusted portal broker in L1
    |
    v
real compositor/portal source picker
    |
    v
PipeWire stream in L1
    |
    | cross-VM media transport
    v
local PipeWire source/remote in L2
    |
    v
conferencing app
```

The standard ScreenCast portal returns a restricted PipeWire remote file descriptor. File descriptors do not magically cross a VM boundary, so a broker must recreate an appropriate local endpoint in the requesting VM and transport the media stream explicitly.

### 8.2 Virtual presentation outputs

The ScreenCast portal supports virtual monitor sources. This suggests an unusually useful feature: a dedicated presentation desktop/output containing only windows explicitly added to it.

```text
share output: meeting
  - work-dev / editor
  - docs-browser / Firefox
  - work-dev / terminal
```

Private windows outside that virtual output cannot accidentally appear because the user alt-tabs or opens a notification.

This could make compartmentalized screen sharing safer and more usable than conventional whole-desktop capture.

### 8.3 Remote input

The RemoteDesktop portal already models pointer, keyboard, touchscreen, clipboard, and screen-capture integration. A workload-aware broker can further constrain remote control to one workload or presentation surface rather than the entire desktop.

## 9. Capability broker and inter-domain RPC

A Qubes-like system needs an equivalent of the role qrexec plays, even if the protocol and implementation are different.

The primitive should provide:

- authenticated VM identity
- service names rather than arbitrary implicit host access
- explicit source and target identity
- policy evaluation before connection
- bidirectional streams and request/response forms
- bounded framing and backpressure
- cancellation
- audit metadata
- optional user confirmation
- no requirement for guest network reachability

Virtio-vsock is an obvious transport for KVM microVMs. The transport is not the policy layer.

An illustrative service namespace:

```text
system.exec
system.shutdown
system.inspect
clipboard.import
clipboard.export
file.offer
file.receive
portal.screencast
portal.camera
portal.microphone
credential.ssh
credential.sign
network.open
notification.post
host.open-uri
```

The trusted broker must derive the caller identity from the VM transport and runtime registry, not from caller-provided strings.

The `msb_krun` lineage already exposes custom in-process vsock service backends. The rybskiworks libkrun fork also carries per-VM guest CID allocation/getter work. Those are useful lower-level ingredients for a typed broker.

## 10. Network architecture

The initial version can use per-workload virtual networking plus host-enforced policy. The long-term system should keep open the option of a Qubes-like network domain.

Possible modes:

```text
none
  no network device or external sockets

brokered
  only named services/proxies

restricted-net
  virtual NIC or TSI with domain/port policy

network-domain
  traffic routes through a dedicated gateway/VPN/firewall VM

exclusive-device
  special workload owns a physical NIC through VFIO
```

libkrun supports two notably different network models: virtio-vsock + Transparent Socket Impersonation, and virtio-net through passt/gvproxy. Microsandbox adds higher-level network policy and proxy machinery. Those mechanisms can be useful, but a security-oriented desktop must distinguish convenience networking from a strong network-domain boundary.

Network policy should be tied to workload identity, not merely IP address.

Potential policy dimensions:

- DNS names
- resolved IP ranges
- protocol/port
- proxy route
- VPN route
- ingress publication
- bandwidth/rate limit
- local peer access
- metadata/internal host access

## 11. Credentials and secrets

Guest images should not contain long-lived credentials.

The preferred model is to keep credentials outside untrusted workloads and lend narrowly scoped capabilities at use time.

Examples:

- SSH agent key only usable for selected hosts.
- Git signing key exposed through a signing service rather than copied into guest storage.
- API token injected only at an approved egress boundary.
- Browser/passkey capability granted to a specific browser workload.
- Short-lived cloud credentials minted for one task.

This is one area where Workestrate's existing direction around brokered SSH identities, egress-scoped credentials, and per-workload policy could be reused if Workestrate is selected as a control-plane component.

The system should not make an LLM responsible for deciding whether to release a secret.

## 12. GPU and device model

GPU design is one of the biggest architecture constraints.

### 12.1 L1 physical GPU ownership

For the nested topology, the preferred experiment is:

```text
physical GPU
    |
    | VFIO/IOMMU
    v
L1 desktop VM
    |
    | native driver
    v
virtio-gpu renderer
    |
    v
L2 graphical workloads
```

This allows the bare-metal L0 to avoid carrying the full graphical driver stack while still letting L1 own the display and virtualize graphics for L2.

### 12.2 Virtio-gpu paths

libkrun supports virtio-gpu with Venus and native-context. Its implementation uses virglrenderer/rutabaga-related graphics infrastructure. crosvm is another strong graphics backend because Sommelier and cross-domain Wayland are already established there.

Mesa's Venus documentation currently lists NVIDIA proprietary driver 570.86 or later among tested host drivers, alongside Intel and AMD implementations. Compatibility still depends on kernel, host driver, CPU/GPU pairing, and VMM behavior, so this should be measured on target hardware rather than assumed.

### 12.3 Compute is separate from graphics

Vulkan graphics virtualization does not automatically provide arbitrary native CUDA semantics to L2.

Possible compute strategies:

- run trusted CUDA workloads in L1
- dedicate a second physical GPU to a compute/gaming domain
- use direct VFIO for special workloads
- evaluate future mediated/vGPU support
- expose narrow compute services rather than the whole GPU

Do not design the desktop graphics path around the assumption that CUDA passthrough to every app VM will be solved at the same time.

### 12.4 Gaming

Gaming is a useful stress test but should be a workload class rather than a design center.

Potential modes:

```text
shared virtual GPU
  ordinary desktop apps, Vulkan workloads, some games

exclusive GPU
  physical GPU scheduled to one gaming/compute domain

L1 direct
  game runs in the GPU-owning desktop domain when compatibility wins
```

Anti-cheat systems may refuse to run in virtualized environments. The project should not attempt to conceal virtualization to bypass those policies.

### 12.5 Other devices

The same explicit capability philosophy should extend to:

- USB
- webcams
- microphones
- Bluetooth
- game controllers
- storage devices
- smart cards/security keys

Long term, physically risky device stacks can live in dedicated domains. Early versions can keep more of them in L0/L1 while preserving a schema that does not require that forever.

## 13. Candidate runtime stacks

No one backend currently dominates every desired property. A capability-oriented backend interface is preferable to betting the whole system on one VMM immediately.

### 13.1 Microsandbox -> msb_krun -> libkrun -> KVM

Candidate role: primary lightweight application/agent runtime if the stack can gain the required GUI, snapshot, and lifecycle semantics.

Strengths:

- already aligned with fast local microVM workloads
- Rust APIs
- network policy and higher-level sandbox lifecycle
- OCI-oriented image handling
- current disk snapshots/fork
- libkrun virtio device support
- existing rybskiworks forks and Nix packaging work
- `msb_krun` already exposes memory-generation/capture primitives, block-layer types, custom vsock services, metrics, and NUMA placement
- libkrun already exposes nested virtualization and virtio-gpu

Current architectural gaps for this system:

- Microsandbox's public snapshots are still disk-only
- resumable/live fork semantics are not yet a complete public runtime contract
- seamless Wayland app integration is not a Microsandbox product feature
- desktop portal brokerage is outside its current scope
- VM identity/provenance must be carried into GUI and portal layers
- the VMM process itself needs a clear host sandboxing story
- the guest image model must become genuinely Nix-native rather than only OCI-compatible

Important security note: upstream libkrun explicitly states that guest and VMM belong to the same security context and the VMM proxies host operations for the guest. A system that treats each microVM as a hard security compartment must therefore also isolate the VMM process appropriately with host namespaces, seccomp, cgroups, filesystem restrictions, or an enclosing VM/domain. The nested L1/L2 architecture naturally limits a compromised L2 VMM to L1 rather than L0, but L1 remains a major trust boundary.

### 13.2 Direct libkrun/msb_krun

Candidate role: lower-level backend when Microsandbox abstraction prevents required VM features.

Advantages:

- direct control over devices, memory capture, block layers, vsock, GPU, nested virtualization, and metrics
- smaller semantic gap between system policy and VMM configuration
- easier to experiment with unusual storage/memory primitives

Costs:

- must provide more lifecycle, persistence, image, process, policy, and observability machinery ourselves
- easier to accidentally couple high-level configuration to one VMM

This is especially useful as an experimental backend even if Microsandbox remains the normal productized path.

### 13.3 Clone

Candidate role: high-density warm-fork backend, especially for ephemeral L2 workloads and recursive test trees.

Project-stated capabilities include:

- KVM VMM in Rust
- warm-template VM fork using private CoW memory mappings
- overcommit + KSM + balloon reclaim
- incremental snapshots
- raw/qcow2 block support and overlay mode
- fork-compatible userspace networking and vsock
- virtio-fs
- VFIO passthrough
- live migration
- guest exec and identity injection

Why it is attractive:

- memory fork is a first-order architectural feature rather than an afterthought
- its template/fork model maps closely to disposable Nix workload generations
- potentially excellent for branching agent/test environments

Why it should not simply replace the stack immediately:

- young project and small ecosystem
- graphics/Wayland integration is not its center of gravity
- claims and benchmarks should be reproduced on target hardware
- integration quality, security review, and long-term maintenance matter more than raw fork latency

A useful outcome may be multiple specialized backends: Clone for fork-heavy headless/test workloads, another VMM for rich graphics.

### 13.4 microvm.nix

Candidate role: Nix-native orchestration/reference layer and possibly the first prototype environment.

microvm.nix already composes NixOS MicroVMs across multiple VMMs, including QEMU, Cloud Hypervisor, Firecracker, crosvm, kvmtool, stratovirt, alioth, and vfkit. It also has nested MicroVM examples and experimental graphics support.

This is important for two reasons:

1. It may solve enough NixOS guest construction and lifecycle plumbing that the project should integrate or adapt it rather than recreate all of it.
2. It gives a convenient backend matrix for evaluating VMMs under identical NixOS guest configurations.

Potential mismatch:

- the desired system has stronger runtime identity, capability, fork, provenance, broker, and agent-lab requirements than a generic NixOS MicroVM module necessarily wants to own.

Therefore microvm.nix should be evaluated as a substrate or adapter, not presumed to be either too high-level or sufficient.

### 13.5 crosvm

Candidate role: graphics-heavy backend or implementation reference.

Strengths:

- Rust VMM
- strong virtio-gpu support
- documented Wayland forwarding with Sommelier
- mature use in ChromeOS virtualization

It may fit graphical L2 workloads better than a smaller server-oriented VMM even if another backend remains preferable for headless workloads.

### 13.6 Cloud Hypervisor

Candidate role: general-purpose modern Rust VMM for richer VM features.

Strengths:

- broad virtio/device support
- active rust-vmm ecosystem
- good fit for Linux cloud workloads
- usable through microvm.nix

It is heavier than libkrun/Clone but may be a better fit where richer VM semantics matter more than minimalism.

### 13.7 Firecracker

Candidate role: headless server/agent workloads, not desktop graphics.

Firecracker is intentionally minimal and does not target a graphical device model. It is therefore a poor universal backend for this system, but remains a useful reference or specialized backend for headless workloads and VM snapshot/fork experiments such as forkd.

### 13.8 forkd

Candidate role: reference implementation for Firecracker-based warm agent branching.

forkd maps a warmed Firecracker parent memory image privately into children and is explicitly aimed at AI-agent fan-out. Its design is worth studying for branching semantics, even if Firecracker's device model is not a good fit for the graphical desktop path.

### 13.9 QEMU

Candidate role: compatibility and debugging backend.

QEMU is large, but feature breadth is valuable. It should remain available as a correctness/debugging escape hatch and may be the easiest place to validate obscure hardware or virtio behavior before reproducing it in a smaller VMM.

### 13.10 Xen/Qubes stack

Candidate role: later security-oriented architecture alternative.

Xen should not be introduced merely because Qubes uses it. It becomes interesting if the project eventually decides that driver domains, GUI/admin separation, Xen's architecture, or compatibility with Qubes components provides security value that outweighs abandoning or adapting the KVM-first stack.

The flake should avoid assumptions that make a future Xen experiment impossible, but KVM is the pragmatic starting point.

## 14. Existing rybskiworks substrate

The organization already contains useful pieces, but none should be confused with the new system's product boundary.

### 14.1 `rybskiworks/microsandbox`

The fork is useful as a controlled integration point for Nix packaging and any runtime capabilities that need to move upward. The current Workestrate integration branch already consumes fork-built Microsandbox artifacts rather than treating the runtime as an opaque external binary.

If used here, changes should generally be layered like:

```text
missing VMM primitive
    -> libkrun/msb_krun
    -> Microsandbox runtime/SDK
    -> system backend adapter
    -> public system capability
```

Do not implement low-level semantics only in the top-level flake when the runtime needs to understand them.

### 14.2 `rybskiworks/libkrun`

The fork already carries integration-oriented work including Nix packaging and per-VM vsock CID allocation/getter support. It is a natural place for low-level capabilities that are genuinely libkrun concerns.

Keep the delta from upstream/parent small and continuously rebased. Prefer upstreamable primitives over project-specific product policy.

### 14.3 `rybskiworks/libkrunfw`

The fork is especially relevant for this experiment because the guest kernel/firmware controls whether nested KVM, virtio, VM-generation, metrics, and other required guest-side facilities exist.

Current rybskiworks commits include:

- source-pinned Nix packaging for libkrunfw
- Intel/AMD KVM enabled in the guest configuration
- virtio-vsock and Microsandbox guest drivers
- a VM-generation guest driver that re-seeds fork randomness and reconciles guest time during activation
- x86 platform poweroff support

These are promising prerequisites, not proof that the full nested workload architecture is correct.

### 14.4 `rybskiworks/nix-tooling`

The shared tooling flake already contains runtime-neutral guest-image helpers and an opt-in NixOS-derived guest configuration. Those are useful construction primitives, but they should remain generic. The compartmentalized workstation should consume them rather than forcing desktop/runtime product policy back into `nix-tooling`.

### 14.5 Workestrate as an optional control plane

Workestrate should remain its own project with its own goals.

If reused here, the relevant value is not its current agent list. It is the direction toward:

- declarative workload identity
- runtime backend adapters
- scoped authorization
- brokered SSH/credentials
- egress policy
- desired/applied state separation
- VM lifecycle and native guest exec
- isolated workspaces
- automated black-box testing

To become genuinely useful as this system's control plane, Workestrate would need mature versions of the following abstractions:

1. Backend capability discovery rather than assuming all runtimes are equivalent.
2. Stable workload identity independent of VM instance identity.
3. First-class generations for base image, workload config, disk state, and memory state.
4. Explicit lifecycle state machine and reconciliation.
5. Typed inter-domain service/broker API.
6. Device and GPU scheduling.
7. GUI provenance registration.
8. Portal brokerage integration.
9. Snapshot/fork primitives with identity refresh hooks.
10. Nested-virtualization capabilities.
11. Persistent volume ownership and attachment rules.
12. Policy evaluation for peer/service access.
13. Auditable event stream.
14. Backend-neutral conformance tests.
15. Separation between user/agent mutation authority and host mutation authority.

If another component provides these better, the system should use it. The architecture must not exist merely to justify Workestrate.

## 15. What probably needs to be built

Even with aggressive reuse, several pieces are likely project-specific.

### 15.1 System flake and module schema

The top-level artifact should describe the machine topology, not merely one NixOS host.

An illustrative, non-existent API might look like:

```nix
{
  imports = [ inputs.compartmentalized.nixosModules.host ];

  compartmentalized = {
    host = {
      role = "l0";
      nestedDesktop = true;
    };

    desktop = {
      role = "l1";
      gpu = "primary";
      compositor = "wayland";
    };

    bases = {
      minimal = { /* ... */ };
      graphical = { /* ... */ };
      development = { /* ... */ };
    };

    workloads = {
      work-dev = {
        base = "development";
        gui.enable = true;
        persistence = [ "workspace" ];
        network.profile = "work";
        credentials = [ "github-work" ];
      };

      personal-browser = {
        base = "graphical";
        gui.enable = true;
        persistence = [ "browser-profile" ];
        network.profile = "personal";
      };
    };
  };
}
```

The final schema should be designed only after the system model and threat model are clearer.

### 15.2 Guest integration agent

A small guest-side component is likely required even if the VMM offers an exec primitive.

Responsibilities may include:

- lifecycle readiness
- application launch registration
- GUI proxy startup
- portal forwarding endpoint
- identity refresh after fork/restore
- shutdown coordination
- metrics/health
- optional exec/filesystem operations

It should not become an all-powerful daemon merely because it is convenient.

### 15.3 Trusted broker daemon

The broker mediates cross-domain services and should be treated as security-sensitive infrastructure.

It likely needs:

- authenticated transport registry
- workload identity mapping
- policy lookup
- user confirmation UI integration
- capability handles
- rate/bounds enforcement
- audit events
- revocation
- lifecycle cleanup

This can start with a tiny set of services and grow deliberately.

### 15.4 Portal backend/proxy

Rather than forking all of xdg-desktop-portal, implement a backend or proxy layer that translates guest portal calls into trusted host/L1 decisions and recreates local endpoints where necessary.

### 15.5 GUI provenance integration

Options include:

- compositor plugin/extension
- trusted shell/window-management integration
- Sommelier extensions carrying transport identity
- a separate trusted decoration surface

Avoid patching a compositor until the minimal mechanism is understood.

### 15.6 Backend adapters

Each backend must report capabilities honestly.

Example conceptual capability set:

```text
exec
vsock
network
network_policy
block_layers
disk_snapshot
live_snapshot
memory_snapshot
memory_incremental
memory_fork
nested_virt
virtio_gpu
wayland_cross_domain
vfio
virtio_fs
balloon
numa
live_migration
```

A workload requiring `memory_fork + nested_virt` must fail clearly on a backend that cannot provide them. Silent degradation is unacceptable for security or persistence semantics.

## 16. Fork strategy

Forking should be tactical.

### Strong candidates for carrying a fork when necessary

- libkrun / msb_krun: low-level VM primitives.
- libkrunfw: guest kernel and custom guest device support.
- Microsandbox: runtime/SDK semantics that need to expose those primitives.
- Clone: only if evaluation shows it is a strong fit and required integration cannot stay upstream-compatible.

### Components to avoid forking initially

- NixOS/nixpkgs.
- Nix itself, including local-overlay, unless an upstreamable correctness or required capability patch demands it.
- Wayland compositor.
- PipeWire.
- xdg-desktop-portal core.
- Mesa/virglrenderer.
- Sommelier-rs.

Prefer adapters, plugins, backends, and upstreamable protocol additions first.

A fork budget should be treated as a maintenance budget: every carried patch must justify the ongoing merge cost.

## 17. Security model and trust boundaries

The first formal document after this architecture seed should be a threat model.

At minimum, distinguish:

### L0 compromise

Catastrophic. L0 owns hardware and can subvert everything.

Goal: minimize L0 code and change rate.

### L1 desktop-domain compromise

Severe. L1 may own the GPU, displays, input presentation, compositor, portal broker, and L2 VMM processes.

In the nested topology, L1 compromise should not automatically imply L0 compromise, but it can observe or impersonate much of the user's interactive session.

Future work may split GUI, workload hosting, networking, and administration to reduce this blast radius.

### L2 workload compromise

Expected threat model. A compromised browser, editor plugin, agent, malicious repository, or document should remain contained by its declared capabilities and persistent mounts.

### VMM escape

A guest exploiting its VMM can compromise the domain hosting that VMM. This is why L1 placement and VMM process sandboxing matter.

### Broker compromise

Depends on broker scope. A monolithic broker holding every credential and capability would become an unacceptable high-value target. Sensitive services may need privilege separation.

### Build/cache compromise

Nix reproducibility does not remove supply-chain risk. Binary-cache trust, signatures, pinning, source provenance, and builder compromise must be part of the threat model.

### AI compromise or model error

Agents are untrusted configuration authors/operators. Their permissions should be explicit and revocable. A model deciding to edit a workload should be categorically different from being authorized to switch L0.

## 18. Agent-native systems laboratory

The architecture becomes much more compelling if it is also its own validation environment.

Because machine definitions are declarative and workloads are disposable, an agent can test system changes inside copies of the system itself.

```text
developer agent
      |
      v
candidate flake generation
      |
      v
isolated test topology
   /       |        \
backend   chaos   security
 tests    tests     tests
   \       |        /
      evidence
         |
         v
      evaluator
```

Examples:

- change a virtio-gpu setting, boot a candidate desktop tree, open applications, exercise resize/clipboard/audio, and compare behavior
- mutate network policy and prove forbidden paths fail
- kill brokers and VMMs and verify recovery semantics
- fork workloads repeatedly and test identity uniqueness
- test restore across base generations
- test storage GC under layered stores
- fuzz guest-to-broker protocols
- compare identical workload contracts across libkrun, Clone, crosvm, and Cloud Hypervisor

Properties worth testing:

```text
An ephemeral workload leaves no persistent state except declared volumes.

A workload cannot mutate another workload's store upper or persistent volume.

A workload without clipboard.export cannot export clipboard contents.

A workload without camera capability cannot acquire a camera stream.

A fork receives fresh VM identity and randomness.

A restored workload cannot silently receive capabilities that were revoked after snapshot.

A backend claiming capability X satisfies the same black-box contract as every other backend claiming X.

A guest cannot forge a more-trusted GUI identity.
```

This is where Workestrate's proposed backend-neutral black-box test harness could be particularly valuable without making Workestrate the product itself.

## 19. Update, rollback, and recovery model

Different layers should have independent generation cadences.

```text
L0 host generation
  rare, security/hardware/runtime substrate changes

L1 desktop generation
  desktop, GPU driver, compositor, brokers, VM-host runtime

base guest generation
  guest kernel/integration/common closure

workload generation
  application/toolchain/policy changes

runtime/session state
  frequent and often disposable
```

Rollback should operate at the smallest relevant layer.

Examples:

- broken Rust toolchain: roll back `work-dev`
- broken browser: roll back browser workload
- bad guest base: select previous base generation
- bad compositor/GPU update: roll back L1 desktop generation
- bad kernel/KVM/IOMMU update: roll back L0

An L2 failure should not require rolling back L1 or L0.

The control plane should retain enough provenance to answer:

```text
What exact flake input graph produced this VM?
What base generation is it using?
What mutable upper does it own?
Which persistent volumes are attached?
Which capabilities were granted?
Which snapshot or parent fork created it?
Which backend and backend version launched it?
```

## 20. Performance model

The architecture succeeds only if strong isolation becomes cheap enough to use by default.

Important measurements:

- L2 cold boot to exec
- warm fork to exec
- warm fork to GUI window
- incremental RAM per idle VM
- dirty RAM growth under representative workloads
- storage upper growth
- Nix substitution latency
- GUI frame latency
- input latency
- audio latency/glitches
- virtio-gpu throughput
- nested-KVM overhead
- context-switch cost with many VMs
- suspend/resume correctness
- battery/power cost where relevant
- builder/cache hit rates

A key goal is to make a microVM feel closer to a process/container lifecycle than to traditional VM administration.

That does not mean hiding the security boundary. It means reducing startup and storage costs enough that isolation can be the default unit of application organization.

## 21. Major risks and ugly edge cases

This architecture will fail if it hand-waves the desktop details.

Known hard areas include:

- proprietary GPU drivers
- nested virt + GPU memory mapping interactions
- CUDA and other vendor compute APIs
- suspend/resume with GPU passthrough
- input methods and accessibility
- screen capture across VMs
- PipeWire/media buffer transport
- clipboard semantics and large transfers
- drag-and-drop
- desktop notifications
- file picker semantics
- URL handlers
- browser credential/passkey integration
- USB hotplug
- Bluetooth
- smart cards/YubiKeys
- game controllers
- anti-cheat
- DRM/protected media
- hardware video encode/decode
- multiple monitors, HDR, VRR, color management
- power management
- VM clocks after fork/restore
- entropy after fork
- live migration of device-heavy workloads
- Nix layered-store GC
- base generation garbage collection while children still reference it
- debugging failures that cross L0/L1/L2

These are not reasons to abandon the idea. They are reasons to keep the architecture modular and to build proofs before making claims.

## 22. Prototype sequence

The project should be staged so every step is useful independently.

### P0: System-model repository/flake

Deliverables:

- flake skeleton
- NixOS module namespace
- architecture docs
- threat-model skeleton
- backend capability schema draft
- CI for pure evaluation/build checks

Exit criterion: topology and terminology are coherent without running a VM.

### P1: Nix-native guest base and storage layering

Deliverables:

- reproducible NixOS guest image
- immutable base generation
- shared/layered Nix-store experiment
- per-workload writable upper
- explicit persistent workspace/data volume
- remote builder + cache path
- GC/rollback tests

Exit criterion: two independent VMs share a base but persist only their declared deltas, and a fresh VM can substitute the common closure without rebuilding it.

### P2: Backend conformance baseline

Deliverables:

- one backend adapter, probably Microsandbox/libkrun or microvm.nix/libkrun/crosvm
- stable workload identity
- exec, shutdown, logs, mounts, network, vsock
- capability reporting
- black-box conformance harness

Exit criterion: a workload can be created/destroyed repeatedly and all declared isolation/storage invariants are tested on a KVM host.

### P3: Seamless single-VM GUI

Deliverables:

- graphical guest base
- virtio-gpu path
- Sommelier/sommelier-rs or equivalent
- one guest application as a host compositor window
- trusted workload provenance attached to the window connection

Exit criterion: launching a graphical workload does not expose a VM console and the trusted side can prove which VM owns the window.

### P4: Cross-VM desktop capabilities

Deliverables:

- clipboard broker
- file transfer
- notifications
- minimal portal proxy
- policy prompts/audit

Exit criterion: two VMs can intentionally exchange allowed data and cannot use the same mechanisms when policy denies them.

### P5: L0 -> L1 desktop VM

Deliverables:

- minimal L0 profile
- VFIO GPU passthrough to L1
- L1 NixOS desktop
- nested KVM verified inside L1
- L2 headless VM launched from L1

Exit criterion: L0 remains graphical-driver-light and an L2 workload can run under nested KVM with acceptable stability.

### P6: Nested graphical L2

Deliverables:

- virtio-gpu from L1 to L2
- seamless Wayland application into L1 compositor
- audio
- input
- screen capture proof

Exit criterion: ordinary desktop use across multiple L2 workloads is tolerable for a real work session.

### P7: Warm fork / memory sharing

Deliverables:

- evaluate Clone and msb_krun memory-state path
- full/incremental snapshot tests
- CoW fork
- VM-generation/entropy/time reset
- page-sharing measurements
- persistent-volume correctness

Exit criterion: a warmed base can create many isolated children with substantially lower latency/RAM than cold independent VMs, without identity duplication.

### P8: Agent laboratory

Deliverables:

- agent-controlled candidate topologies
- property tests
- fault injection
- backend differential tests
- reproducible evidence bundles

Exit criterion: an agent can propose a runtime/config change, test it in an isolated copy of the system, and return evidence without authority to switch L0.

### P9: Hardening

Potential work:

- split GUI/admin/workload-host domains
- USB/network domains
- measured boot
- signed policy/config generations
- privilege-separated brokers
- stronger VMM sandboxing
- security audit/fuzzing

Only after this stage would it be reasonable to compare the security posture seriously with Qubes rather than merely citing Qubes as inspiration.

## 23. Decision records that should exist before implementation hardens

The eventual ADR set should include at least:

1. Why KVM is the initial substrate rather than Xen.
2. Whether L0 or L1 owns the compositor in the first usable system.
3. Whether nested L2 VMs are default, optional, or experimental.
4. Runtime backend interface and capability semantics.
5. Primary VMM selection for headless workloads.
6. Primary VMM selection for graphical workloads.
7. Guest exec/control protocol.
8. Inter-domain RPC transport and authentication.
9. Nix store layering implementation.
10. Disk CoW format and lifecycle.
11. Memory snapshot/fork semantics.
12. Workload identity and generation model.
13. Persistent volume ownership model.
14. GUI provenance mechanism.
15. Portal brokerage model.
16. Clipboard/file-transfer policy.
17. Network-domain model.
18. Credential broker model.
19. GPU virtualization and exclusive-device scheduling.
20. Agent authority boundaries.
21. Update/rollback/GC policy.
22. Build/cache trust model.
23. VMM process isolation model.
24. Logging/audit data model.

Each ADR should state security implications, rollback strategy, and which layer owns the implementation.

## 24. PRD questions

A PRD should be written after several architecture experiments, not before them. It should focus on concrete user workflows such as:

- Open an untrusted repository without giving it ambient host credentials.
- Launch a work browser and personal browser that look native but cannot read each other's state.
- Give an agent a disposable environment with scoped GitHub and network access.
- Install a development tool without switching the physical host.
- Roll back one workload without rolling back the desktop.
- Open an untrusted document in a disposable graphical VM.
- Share only selected cross-VM windows in a meeting.
- Attach a USB device to exactly one workload.
- Run a GPU-heavy workload with an explicit virtual or exclusive GPU policy.
- Fork a warmed development environment for parallel agents.
- Reproduce a system bug in an isolated copy of the topology.

The PRD should include measurable latency and reliability targets rather than only architecture aspirations.

## 25. Open questions

The following should remain deliberately unresolved until prototypes provide evidence:

- Is nested L0/L1/L2 actually worth the complexity for daily use?
- Should the L1 compositor and L2 VMM host be the same domain?
- Is Microsandbox the right primary runtime once GUI and memory-fork requirements are considered?
- Should Clone be adopted, mined for ideas, or used only for specialized fork-heavy workloads?
- Can crosvm be cleanly adapted behind the same workload identity model?
- Is microvm.nix the right Nix-level substrate, or does the system need a distinct topology module from day one?
- Is Nix `local-overlay` reliable enough, or should another store-sharing approach be primary?
- How should store/base GC account for running and snapshotted descendants?
- What is the smallest safe guest agent?
- How much of xdg-desktop-portal can be reused unchanged?
- Can window provenance be implemented without compositor-specific patches?
- What is the correct cross-VM zero-copy path for PipeWire/video?
- Which GPU APIs work acceptably through virtio-gpu on the actual hardware?
- How should CUDA be exposed, if at all?
- What does suspend/resume mean when L1 owns a passed-through GPU and L2 VMs are nested?
- How should hardware failure/rebind be recovered?
- Which capabilities can be safely delegated to agents automatically?
- Which changes must always require explicit human confirmation?
- What level of security claim is realistic without Xen/Qubes-style driver-domain maturity?

## 26. Architectural success criteria

The idea is worth pursuing if the system can eventually demonstrate all of the following:

1. The bare-metal NixOS host changes rarely during normal desktop/software use.
2. Most applications can live in isolated workloads without feeling like remote desktops.
3. Creating a new workload is cheap in storage, RAM, and latency.
4. Shared base state remains immutable and independently verifiable.
5. Persistent state is explicit and inspectable.
6. Cross-workload data flow is policy-controlled.
7. Window provenance is trusted.
8. Individual workloads can be updated and rolled back independently.
9. Agents can build and test candidate environments without ambient host authority.
10. Multiple VMM backends can be tested against the same capability contracts.
11. The whole topology is reproducible from a flake and associated state artifacts.
12. Failure of an ordinary workload does not require treating the physical host as contaminated.
13. The system can test meaningful portions of itself recursively.

If those hold, the implementation may technically still be "just a NixOS flake" while behaving enough unlike a conventional NixOS workstation that a distro-like identity becomes a reasonable description.

## 27. Suggested next documents

This architecture seed should eventually split into four classes of documents:

### System specification

Normative terms, object model, identities, state machines, capabilities, lifecycle, and backend contracts.

### Threat model

Assets, attackers, trust boundaries, TCB, guest/VMM/broker escape assumptions, supply-chain risks, and security invariants.

### ADRs

One decision per irreversible or costly architectural choice, with alternatives and consequences.

### PRD

Concrete user workflows, latency/reliability targets, supported hardware scope, operational expectations, and staged product milestones.

The architecture seed should remain broader and more exploratory than all four. Its job is to preserve the idealized shape while keeping implementation choices replaceable.

## 28. References and candidate projects

Qubes OS:

- Architecture: https://doc.qubes-os.org/en/r4.3/developer/system/architecture.html
- qrexec: https://doc.qubes-os.org/en/r4.3/developer/services/qrexec.html
- GUI domain discussion: https://www.qubes-os.org/news/2020/03/18/gui-domain/

Nix/NixOS:

- Nix experimental local-overlay store: https://nix.dev/manual/nix/2.34/store/types/experimental-local-overlay-store
- Current local-overlay GC issue example: https://github.com/NixOS/nix/issues/16269
- Nix remote builds: https://nix.dev/manual/nix/2.25/advanced-topics/distributed-builds
- Distributed builds on NixOS: https://nix.dev/tutorials/nixos/distributed-builds-setup.html
- Cachix push/watch mechanisms: https://docs.cachix.org/pushing
- Cachix post-build-hook example: https://docs.cachix.org/continuous-integration-setup/hydra

VM/runtime candidates:

- microvm.nix: https://github.com/microvm-nix/microvm.nix
- libkrun: https://github.com/libkrun/libkrun
- Microsandbox: https://github.com/superradcompany/microsandbox
- msb_krun API: https://docs.rs/msb_krun/latest/msb_krun/
- Clone: https://github.com/unixshells/clone
- Clone SPEC: https://github.com/unixshells/clone/blob/master/docs/SPEC.md
- forkd: https://github.com/deeplethe/forkd
- crosvm Wayland: https://chromium.googlesource.com/chromiumos/platform/crosvm/+/refs/heads/main/docs/book/src/devices/wayland.md

Graphics/desktop:

- sommelier-rs: https://github.com/google/sommelier-rs
- Mesa Venus: https://docs.mesa3d.org/drivers/venus.html
- XDG ScreenCast portal: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html
- XDG RemoteDesktop portal: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html
- XDG portal PipeWire integration: https://flatpak.github.io/xdg-desktop-portal/docs/pipewire.html

rybskiworks integration points:

- https://github.com/rybskiworks/microsandbox
- https://github.com/rybskiworks/libkrun
- https://github.com/rybskiworks/libkrunfw
- https://github.com/rybskiworks/nix-tooling

## 29. Final framing

The most useful framing is deliberately modest about implementation and ambitious about system behavior:

> A NixOS-derived, declaratively composed compartmentalized workstation in which the physical host is a minimal and durable substrate, most applications execute in cheap isolated microVM workloads, a trusted Wayland desktop presents those workloads seamlessly, cross-domain behavior is capability-brokered, and agents can construct and test disposable copies of the system without becoming part of its enforcement boundary.

Implementation-wise, this can remain a flake.

Operationally, if it works, it will feel like a different operating system.
