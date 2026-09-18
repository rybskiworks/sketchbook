# Compartmentalized NixOS: lower-level enablement roadmap

[Exploration catalogue](README.md) | [Architecture seed](compartmentalized-nixos-architecture-seed.md) | [Implementation tracker #17](https://github.com/rybskiworks/sketchbook/issues/17)

**Status:** exploratory implementation roadmap, not an accepted specification or a claim that this workstation already works.

**Audit date:** 2026-09-13. **Initial target:** Linux x86_64. **Method:** inspect the consumed repositories, dependency declarations, selected implementation paths, and relevant upstream proposals. No VM, GPU, firmware, Nix build, or performance test was run for this assessment. Existing project test claims and upstream author reports are identified separately from observations made here.

## 1. Recommendation

Build the first experiment around the existing Microsandbox/native-libkrun stack, but do not treat enabling its GPU feature as completing desktop isolation. The lower layers already contain substantially more than their currently exposed product interfaces: virtio-gpu, Rutabaga CrossDomain, sound, input-device machinery, guest-init handoff, and NixOS image construction. The immediate work is selective integration, missing native display/input bindings, renderer compatibility, explicit endpoint authorization, and end-to-end qualification. [S2], [S3], [S4], [S5], [S6], [S7], [S8], [S14].

Keep three graphics outcomes separate:

| Outcome | Required building blocks | What it does not establish |
| :--- | :--- | :--- |
| Render-only acceleration | virtio-gpu, selected renderer/capsets, compatible host and guest drivers, working blob mappings and fences | A visible window, a full guest desktop, CUDA, or device passthrough |
| Seamless individual windows | Guest Wayland proxy, CrossDomain transport or another qualified transport, trusted host compositor/proxy boundary | Full guest scanout, raw host input access, authorized clipboard/media sharing |
| Whole-desktop display | Virtual scanouts, display backend/viewer, input-device bindings, cursor/resize lifecycle | Native per-application host windows or per-application provenance |

For the first implementation milestone, keep the physical NixOS host's existing desktop, run two isolated application VMs, and prove correct Wayland connection attribution with all convenience sharing disabled. Add explicit text/file transfer next. Qualify accelerated rendering independently. Full outer-desktop virtualization, VFIO ownership, and live memory forks should not block that experiment.

Workestrate is a plausible optional configuration and runtime-adapter layer. It should own declarative intent, resolution, admission, lifecycle and provenance, not become the compositor, host OS, generic driver distribution, or personal fleet. Its current structure already supports that boundary. [S8], [S9].

## 2. Exact dependency baseline

These are the inspected source identities, not a promise that a future default branch or an already installed binary has the same capabilities.

| Component | Inspected or consumed identity | Why it matters |
| :--- | :--- | :--- |
| Architecture seed / sketchbook | `main` at `3c75279220bfc123048ad076065adbda86be0e49` | Consumer requirements and existing research tracks |
| Workestrate | `main` at `beaab036fe9fb59f132c83bdb81d443863914d9f` | Integration branch, not an obsolete migration branch |
| Microsandbox | `251b368a868d578ead123071c3e6bc8eec013817`, version 0.6.18 | Exactly the source selected by Workestrate's flake |
| Native libkrun fork | `9c0c8b517d5685672a89a7bf6810ef9a114ec07b`, `msb_krun` 0.1.34, branch `krun` | The runtime consumes native Rust crates from this fork |
| Nix firmware input | `d575b13e79368b23246be3d93d7935899dec5a3b`, branch `krunfw` | The downstream Nix build's guest kernel/firmware source |
| Effective tooling under Workestrate | `a403c2c111e24db64feb5748bbba939308048c07` | Workestrate makes the Microsandbox input's tooling follow its own |
| Standalone Microsandbox tooling | `1120aa22cddf4a9a3424f38aadbebadd8a963c4b` | A different declared supplier snapshot from the composed build |
| Shared guest-memory crate patch | `superradcompany/rust-vmm` at `f798d4f274db22a3c458ba756900db2cd03e6fe9` | `msb-vm-memory` crate identity must agree across direct/transitive consumers |
| Block-image library | `msb-imago` 0.1.5 | Registry dependency in libkrun's devices crate; do not invent a consumed Git revision from an upstream default branch |
| Rutabaga/display/input | In-tree `msb_krun_*` crates at the libkrun pin | These are not independent, automatically updated upstream components |

Sources: Workestrate's [flake](https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/flake.nix), Microsandbox's [flake](https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/flake.nix) and [Cargo workspace](https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/Cargo.toml), and libkrun's [devices crate](https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/devices/Cargo.toml).

Two easily missed boundaries:

1. **The native Rust VMM and firmware DSO are different interfaces.** Microsandbox calls the `msb_krun` Rust API. Enabling an option only in the C API or Makefile does not expose it to this runtime. The bundled kernel remains a separate firmware artifact.
2. **The vendor and Nix firmware paths differ.** Microsandbox's `.gitmodules` points `vendor/libkrunfw` at `superradcompany/libkrunfw`, while the downstream flake selects the rybskiworks firmware pin. An upstream/prebuilt workflow and the downstream Nix build must not be treated as one tested dependency tuple. [S1], [S2].

The first capability report should record source revisions, Cargo features, registry checksums, firmware ABI/config/patch digests, exact renderer library and server, host driver/kernel, guest Mesa and image closure. A shared Microsandbox source SHA alone does not prove identical composed artifacts when `follows` changes the package set. Cargo workspace patches also need reconciliation at the consuming root; dependency workspaces do not automatically supply a consumer's root patches. [S2], [S8].

## 3. What is already there, and what remains

| Building block | Evidence in the inspected stack | Remaining work |
| :--- | :--- | :--- |
| GPU renderer flags / shared-memory size | Native `ConsoleBuilder::gpu_virgl_flags` and `gpu_shm_size` | Runtime feature/config plumbing, compatibility qualification and explicit capability policy |
| virtio-gpu CrossDomain | GPU device constructs Wayland/X11/PipeWire channels; Rutabaga registers CrossDomain | Explicit authorized channels, qualified guest proxy and host provenance boundary |
| Sound | Native `ConsoleBuilder::sound`; devices crate has PipeWire integration | Default-off runtime exposure, restricted playback/capture policy and session lifecycle |
| Scanouts and input | Lower display/input types exist; current Rust console builder lacks proposed display/backend/input methods | Evaluate upstream libkrun #118 and the scanout/cursor fixes, only for paths needing them |
| Guest graphics drivers | Firmware enables virtio-gpu/KMS, virtio-input, virtio-snd, virtio DMA shared buffers | Built-config manifest, role-specific userspace and real device/render tests |
| NixOS userspace boot | Tooling constructs NixOS OCI base/leaves; Workestrate forwards explicit init | Desktop/session profile, role qualification, explicit engine selection and application readiness |
| Guest control | Existing named virtio-console `agent` protocol and bootstrap handshake | Preserve it; do not replace it with a generic vsock broker by accident |
| vsock listeners and CIDs | Existing transient host-listener and host-reserved guest-CID launch contracts | Generation-bound authorization, revocation and broker lifecycle above transport |
| Resource/capability control | Runtime already has live-control discovery for its supported operations | Extend capability scope rather than create a second incompatible discovery mechanism |
| Nested virtualization policy | Workestrate already models require/prefer/degraded/frozen states | Qualify actual L2 KVM execution, topology and lifecycle; policy fields are not hardware proof |
| Disk snapshots | SDK creates snapshots of supported stopped OCI-backed sandboxes | Explicit scope, disk consistency, volume/store lifetime and restore contracts |
| Resumable memory snapshots | Native memory/control types exist, but SDK rejects `resumable` | Complete capture/restore/device/identity qualification, separately from disk snapshots |

Evidence: [S3], [S4], [S5], [S6], [S7], [S8], [S9], [S10], [S11], [S14]. None of these rows means that enabling every available device is appropriate for every workload.

### A concrete graphics-policy problem

In `VirtioGpu::create_rutabaga`, the current fork constructs a Wayland path from `XDG_RUNTIME_DIR` and `WAYLAND_DISPLAY`, with a fallback under `/run/user/1000`. It optionally adds X11 from `DISPLAY` and PipeWire from ambient runtime variables. The Wayland string concatenation also needs an explicit contract for absolute socket paths. The call uses capset mask zero and passes no explicitly supplied renderer-server descriptor. [S5]

Rutabaga already supports channel selection and capset masks internally, and initializes CrossDomain alongside a rendering component. The default zero mask follows the legacy broad capset-advertisement path. Therefore the task is **not** "invent CrossDomain". It is to expose selected channels and capability sets through the actual native Rust/runtime interface, remove ambient authorization in strict mode, and demonstrate that unavailable required capabilities fail early. The absence of an explicit server descriptor in this caller does not prove that renderer flags cannot start a server by another mechanism. [S6]

This is a source-level policy mismatch, not proof of an exploited vulnerability. It becomes especially important when adding the currently absent product GPU feature.

### NixOS support is ahead of the seed's open questions

The inspected tooling contract already provides generated stage-2 `/init`, a required volatile `/run`, guest-owned store registration and database, base/leaf registration, and documented opt-in Microsandbox tests covering fresh activation, untrusted builds, two boots and normal poweroff. Those are project-reported results, not tests rerun here. Workestrate already passes the explicit init block to the runtime. [S7], [S8].

The next work is a graphical non-root session, correct DBus/logind/runtime directories, proxy/driver configuration, role readiness, and isolation of mutable state. The current common example base is Determinate-specific. That is neither a requirement of the architecture nor permission to replace the physical host's Nix daemon. A Lix or upstream-Nix image profile should be an explicit alternative with its own qualification.

## 4. Upstream work worth integrating or tracking

Status is as checked on 2026-09-13. PR descriptions are author reports, not independent verification. Only libkrun #118's patch was additionally inspected during this assessment; all candidates still require patch-level review against the consumed fork before adoption. An open PR can also have equivalent changes elsewhere, so compare code rather than using PR status as a complete feature detector.

| Proposal | Verified status / inspected head | Relevance and adoption boundary |
| :--- | :--- | :--- |
| [superradcompany/microsandbox #1194](https://github.com/superradcompany/microsandbox/pull/1194) | Open, not merged; `d97eeaf0b42638990aef046fd03408a8704e5bbf` | SDK/CLI/runtime `--gpu` Venus plumbing; asynchronous fences and render-server flags. Starting point, not an authorization design or seamless desktop. |
| [superradcompany/libkrun #91](https://github.com/superradcompany/libkrun/pull/91) | Open, not merged; `eefd5d99995b242920dfd146e400d023c767531c` | Linux fixed blob-mapping API and feature propagation, plus macOS alignment. Review Linux-relevant changes against the actual renderer ABI. |
| [libkrun/libkrun #789](https://github.com/libkrun/libkrun/pull/789) | Open, not merged; `ef0e54a793b16db4d0983d5841c19f018b1b9f8c`; targets `stable-1.19.x` | Finalized `virgl_renderer_resource_map_fixed` and runtime detection. Compare with #91; do not blindly stack two approaches to the same mapping boundary. |
| [superradcompany/libkrun #118](https://github.com/superradcompany/libkrun/pull/118) | Open, not merged; `a496f45f17ad29aafd5a79f7e063ce3b25a126f5` | Adds Rust `gpu_display`, `gpu_display_backend`, `input_device`, and backend re-exports. Directly addresses the missing native binding for full scanout/input. |
| [superradcompany/libkrun #117](https://github.com/superradcompany/libkrun/pull/117) | Open, not merged; `2292f4ac0be1a8fe8f752ccff35a9c8070e51d5d` | Explicit 2D-only mode and safe scanout rectangle/stride handling. Do not advertise working 3D when selecting software-only display. |
| [superradcompany/microsandbox #1482](https://github.com/superradcompany/microsandbox/pull/1482) | Open draft; `229c071a238cba022cd6849fb9d9f4ff481b1a3b` | Whole-guest framebuffer viewer and input, currently macOS-only viewer and temporary environment switches. Useful reference, not a Linux seamless-window implementation. |
| [libkrun/libkrun #822](https://github.com/libkrun/libkrun/pull/822) | Open draft; `3819ce5fc090a890dec7dc4fbba50bee5c805b17` | Zero-copy `wl_shm` guest-handle path involving guest and host udmabuf, kernel/protocol and proxy changes. Optimization research, not required for the first proof. |

Additional candidates surfaced in upstream search, **not individually status-qualified here**:

- [superradcompany/libkrun #119](https://github.com/superradcompany/libkrun/pull/119): cursor-plane handling and display-backend ABI compatibility, related to #117.
- [libkrun/libkrun #816](https://github.com/libkrun/libkrun/pull/816): vhost-user GPU software scanout; its description explicitly distinguishes that from a pending DMABUF scanout path.
- [libkrun/libkrun #811](https://github.com/libkrun/libkrun/pull/811): vhost-user media/shared-memory plumbing, a potential specialized camera/media path, not portal authorization.
- [libkrun/libkrun #762](https://github.com/libkrun/libkrun/pull/762): HVF-first snapshot/restore proposal, with Linux/KVM and other limitations in its description. It is not evidence that this Linux Microsandbox SDK can resume graphical guests.
- [libkrun/libkrun #718](https://github.com/libkrun/libkrun/pull/718): native Rust API/C API reorganization. Do not confuse that upstream API work with the already consumed `msb_krun` native API or assume an ABI-compatible update.

Maintain a small patch ledger: consumed base, candidate head, superseding work, local adaptation, tests and upstreaming destination. For an inherited bug, contribute to the component that owns it; keep fleet/Nix packaging changes out of an unrelated upstream kernel/VMM patch.

## 5. Desktop architecture and the actual crossings

### Initial topology

```text
physical NixOS host
  trusted supervisor / optional Workestrate adapter
    | per-instance identity, launch epoch, explicit grants
    +-- isolated VMM A -- NixOS app guest A -- Wayland proxy A
    +-- isolated VMM B -- NixOS app guest B -- Wayland proxy B
              | selected CrossDomain channels only
              v
       trusted host-side proxy / compositor integration
              | provenance, focus, consent UI
              v
       physical desktop / selected host render device
```

The topology is a proposal. A host compositor sees host-side proxy clients; it must receive a trustworthy association to the originating VM. Guest-provided `app_id`, titles, environment variables and client-side decorations are not identity. If the chosen compositor cannot produce trusted labels or accept verified per-connection attribution, that is a real compositor/proxy integration gap, not something fixed inside libkrun.

**Seamless Wayland route.** Crosvm documents a guest Sommelier path over virtio-gpu CrossDomain. Sommelier-rs describes a guest-side Rust rewrite with VM mode and local debugging mode, and explicitly does not target X support. Use these as reference integrations, pin the proxy, and verify libkrun interoperability. Local proxy mode is not a VM test. Ordinary focused input in this route travels through Wayland; it does not require giving each app VM raw host evdev devices. [P1], [P2].

**Whole-desktop route.** A guest compositor drives virtual scanouts and consumes virtual input devices; the host displays a window or another presentation endpoint. This is where native display/input bindings, stride/resize/cursor handling and a Linux viewer matter. A full desktop window is a useful fallback or specialized workspace, not equivalent to seamless app windows. The macOS draft is a reference, not a Linux deliverable. [U1482], [U118].

**Alternative transport.** Waypipe-like remoting can be evaluated as a fallback, but an ordinary vsock byte stream cannot transmit Unix file descriptors by merely relaying their numeric values. Select a transport implementation that reconstructs its resources across the VM boundary and qualify it. Do not assume binding the host Wayland socket through virtiofs provides working or authorized Wayland FD semantics.

### Capability-by-capability crossing model

| Interaction | Proposed minimum boundary | Negative condition |
| :--- | :--- | :--- |
| Window creation | Per-instance proxy connection and trusted surface attribution | Spoofed title/app ID cannot change trusted identity |
| Clipboard / primary selection / drag-drop | Explicit source/destination transfer, MIME and size limits, cancellation and staging | Focus change or replacement cannot revive an old grant |
| Files | Broker-selected object or disposable copy, constrained path/descriptor translation | Guest paths cannot select arbitrary host files or other guests' mounts |
| URI opening / notifications | Named broker operations with validated payload and trusted origin | No arbitrary host command or unlabelled authority-bearing notification |
| Audio playback | Restricted sink/session with bounded lifetime | Playback grant does not authorize microphone or the full host graph |
| Microphone / camera / screen capture | Trusted consent and source selection, restricted media endpoint, explicit stop/revocation | Recording ends on revoke/exit; no broad host PipeWire exposure |
| Remote input | Separate narrowly scoped grant bound to focus/session | A background guest cannot inject into the host desktop |
| Signing / SSH | Named request through an external broker, policy and fresh instance binding | Guest cannot extract a key or reuse authority from a replaced instance |

The existing libkrun CrossDomain PipeWire channel is a useful mechanism to investigate. It is not sufficient to grant every guest the ambient host PipeWire socket. Likewise, the ScreenCast portal's `OpenPipeWireRemote` returns a local FD: a cross-VM implementation needs a guest-local portal/session endpoint, brokered host consent, a restricted stream transport, and recreated guest resources. Reuse existing CrossDomain support where it actually carries the needed resource types; do not claim that either a generic vsock stream or a host session-bus mount solves this. [S5], [P3].

Continue [interaction research #11](https://github.com/rybskiworks/sketchbook/issues/11) for the threat model. [Integration #21](https://github.com/rybskiworks/sketchbook/issues/21) supplies the bounded two-VM acceptance task.

## 6. Host isolation must include the VMM and renderer

The fork's README explicitly puts the guest and VMM in the same security context and assigns VMM confinement to the host. Treat that as a deployment requirement. KVM isolates guest execution, but a compromised device backend must not inherit the operator's home directory, signing keys, every workload disk, or unrestricted network authority. [S12]

The runtime entry point also participates in management: configuration includes database paths, runtime state, resource leases and relay/control endpoints. A host confinement design therefore needs an ownership audit, not just a `ProtectHome` flag. Identify which management writes genuinely belong in each VMM and move or constrain any access that would let one compromised runtime tamper with unrelated instances. [S13]

For the workstation profile, define and test a minimal launch environment: mount/process/network isolation, restricted descriptors and device access, dropped capabilities, applicable syscall restrictions, resource limits and fresh private runtime paths. Preserve only the image and mutable volumes belonging to that instance, required agent/control endpoints, `/dev/kvm`, selected rendering resources and explicitly granted channels. A shared desktop user UID is not automatically a boundary between mutually untrusted helpers.

Renderer-server separation is worth evaluating, including the existing Rutabaga descriptor interface and upstream render-server configuration. It is not itself a sandbox. The renderer's filesystem, IPC, network and GPU authority must be constrained separately; the host kernel GPU driver remains in the trusted computing base. A render node does not imply robust per-workload GPU memory/time quotas.

Gate untrusted graphics on [#19](https://github.com/rybskiworks/sketchbook/issues/19). Test the host policy against an intentionally malicious stand-in VMM process with the same launch credentials, not only against cooperative guest applications.

## 7. Images, shared storage, identity and lifecycle

### Guest roles instead of one ever-growing kernel

The consumed firmware already includes virtual graphics/sound/input support. It omits physical USB/media and guest VFIO/IOMMU support in the inspected generic configuration. Keep host kernel requirements, an optional outer GPU-owning guest kernel, and ordinary application-guest requirements separate. A virtual camera/media broker can be evaluated without first enabling physical USB drivers in every application VM. The firmware README's x86 CPU-limit table and actual config differ; derive capabilities from built artifacts and probes, not the prose table. [S4], [S15].

The NixOS image is userspace under a runtime-supplied kernel. Adding a NixOS `boot.kernelPackages` choice to that userspace does not automatically replace libkrunfw. If a role needs a different kernel or firmware contract, select and qualify that boot mode explicitly.

### Sharing immutable bytes is not sharing mutable authority

Use the existing base/leaf constructors and guest registration service for the first experiment. Their archive-layer inheritance and per-guest Nix database are useful starting points. The tooling documentation explicitly distinguishes archive deduplication from physical deduplication after runtime import. [S7]

The shared-store work should define immutable published generations, per-instance writable state, leases held by live VMs and retained snapshots, and crash-safe collection. Keep a guest's mutable Nix database and the store paths it knows about consistent across reboot/rollback. Never expose an unrestricted host Nix daemon socket as a shortcut. Keep signing secrets out of images and public flakes. The generic recipe is a supplier component; application choice and operator policy belong in the workstation/fleet repository. Continue [#8](https://github.com/rybskiworks/sketchbook/issues/8), not a second competing storage design.

### Several identities, not one overloaded generation

Keep at least the following concepts distinct in the design: runtime build identity, immutable image/store generation, persistent workload identity, concrete instance identity, and fresh launch/grant epoch. Workestrate's binary-keyed MSB_HOME generation and instance slots already solve narrower problems; they must not silently become authority for every other lifetime. [S8], [S9].

Microsandbox already distinguishes transient host-vsock listeners from durable guest-to-host routes, reserves guest CIDs, and requires launch capabilities for security-sensitive additions. Preserve those mechanisms. The guest-agent control path is the named virtio-console `agent` protocol, not this new desktop broker. CID is transport attribution, not a complete authenticated workload/grant identity. Fresh listeners, broker grants, cancellation and revocation still need a supervisor-owned lifetime. [S10]

The downstream README explicitly says generation-bound multi-instance SSH authorization, managed host certificates and shared broker-VM lifecycle are not fully integrated. Reuse the existing transport work without calling the entire credential architecture complete. [S1]

### Snapshots must state exactly what they capture

The consumed SDK's `create_snapshot` immediately rejects `resumable`; it also rejects Running, Draining and Paused states and limits creation to supported OCI-rooted storage with its managed writable layer. This is decisive evidence that its current public snapshot path is not a live-memory fork API. [S11]

Native memory-control/capture types are useful groundwork, not proof of a resumable graphical guest. A complete restore contract must cover vCPU/device state, queue quiescence, timers, guest memory, root/extra-volume consistency, external streams, renderer resources, identity and authority. A framebuffer, GPU context, DMA-BUF, broker connection or open network session must not be assumed portable across a fork.

Start with cleanly stopped disk snapshots and explicit scope. For later memory work, classify devices as capturable, reconnectable, discardable or blocking, with precise semantics. Renew identity/entropy and reauthorize external grants where appropriate; never rewind external effects or broker revocation state with guest RAM. KSM, shared page cache, private memory mappings, restored RAM and true execution-state CoW are separate mechanisms and require separate measurements. Continue [#7](https://github.com/rybskiworks/sketchbook/issues/7) and [Yggdrasil](yggdrasil.md).

## 8. Optional outer desktop and physical GPU ownership

The nested topology in the seed is a later experiment, not a reason to make every application microVM a general-purpose PC:

```text
L0 minimal physical NixOS host
  physical GPU -- qualified VFIO ownership --> L1 NixOS desktop domain
                                                host driver / compositor
                                                nested KVM + app VMMs
                                                   |
                                                   +--> L2 app guests
                                                        virtual GPU / CrossDomain
```

The same physical device is not casually assigned twice. A physical display cable terminates at the GPU that owns scanout; rendering on another device/domain requires an explicit buffer or remote-display path. A shared virtual Vulkan device is not transparent NVIDIA CUDA or physical GPU passthrough. Venus is a Vulkan command-serialization protocol, and Mesa documents additional driver/mapping constraints; validate the actual machine rather than promising compatibility from a GPU vendor name. [P4]

A full outer VFIO role can use QEMU or another qualified backend even if the ordinary app guests use Microsandbox. Evaluate whole IOMMU groups, reset behavior, GPU companion functions, DMA isolation, guest drivers, firmware, input/audio ownership, recovery when the desktop domain fails, and nested KVM availability. A Nix declaration does not prove a safe IOMMU group or successful device reset. No hardware topology or passthrough test was performed here.

microvm.nix is a useful reference for NixOS guest generation, shares/volumes and hypervisor-specific device options. It is not evidence that every backend has the same graphics, passthrough or snapshot contract. Select per-role backends through capabilities rather than trying to make one global `gpu = true` cover all these topologies. [P5]

## 9. Workestrate integration contract

The current `SandboxPlan` already includes init, managed root capacity, credential grants, mounts/network, instance policy and nested virtualization provenance. The adapter already has separate modules for plans, runtime, slots, generation, broker, provenance and dependency handling. Extend those seams. [S9]

A proposed capability report should distinguish:

```text
capability identifier and semantic version
  compiled support
  host/device probe result
  required guest/firmware features
  requested policy and its declaring source
  admission result, with a structured refusal reason
  effective active-instance state
  restart / snapshot / revoke constraints
```

This is a design sketch, not an accepted configuration schema or a currently available CLI.

For graphics, use independent axes such as renderer, presentation transport, scanout/input, playback/capture and physical-device ownership. Requested strict isolation must not fall back to a weaker backend or broad host socket. Optional performance acceleration may fall back only when the workload explicitly permits that outcome, and the plan must report it as degraded.

Add provenance for desired versus active capabilities and specify which changes require recreation. Device topology, image generation and transient socket handles do not have identical hashing/persistence rules. Do not blindly copy the nested-policy field's existing config-hash exclusion to new GPU devices.

Expose store-ready, session-ready, broker-ready and application-ready checks separately. The current TCP readiness budget is not a desktop-session health check. Reuse the existing dependency graph, but reject cycles and clean up grants on dependency/startup failure. Keep a stable lower-level interface so an initial experiment can run without Workestrate and be incorporated later. Track the generic adapter work in [workestrate #39](https://github.com/rybskiworks/workestrate/issues/39).

## 10. Actionable work packages

Priority reflects dependency order, not an estimate. The named code paths are integration points to inspect and change; the list is not a claim that every implementation detail has already been designed.

| ID | Priority / owner | Concrete work and acceptance gate | Dependencies / tracking |
| :--- | :--- | :--- | :--- |
| E01 | P0, Microsandbox + tooling | Emit the resolved dependency/feature/firmware/renderer manifest. Verify native crate identity and composed `follows` inputs. Refuse a required feature absent from the actual runtime. | #17, #18, #20 |
| E02 | P0, libkrun | Reconcile Linux blob mapping and feature propagation against #91/#789. Exercise actual mapped Vulkan buffers and fence completion, not enumeration alone. | E01; #18 |
| E03 | P0, libkrun | Add strict explicit CrossDomain endpoints and capset selection to the native builder/device boundary. Hostile environment must not add X11/PipeWire or select another workload's endpoint. | E01; #19 |
| E04 | P0, Microsandbox + host module | Constrain VMM/renderer authority and separate management state where necessary. Malicious stand-in VMM cannot access other workloads, operator credentials or ungranted networks. | E01; #19 |
| E05 | P0, Microsandbox | Carry typed graphics requirements through Cargo/Nix, SDK spec/builder, launch/spawn and runtime VmConfig. Old runtimes reject required settings before mutation. Preserve CPU-only behavior. | E02/E03; #18 |
| E06 | P0, libkrunfw + tooling | Add role manifests and verify already-present drivers with built config and real guests. Keep generic, graphics-session and outer-device roles separate. | E01; #20 |
| E07 | P0, tooling + workstation fleet | Compose a non-root NixOS Wayland session and proxy using existing init/store registration. Prove independent mutable state, service readiness and clean poweroff on two boots. | E06; #20 |
| E08 | P1, workstation proxy/compositor | Prove CrossDomain interoperability, trusted surface identity, focus and protocol-global policy for two guest applications. No guest-controlled provenance labels. | E03/E04/E05/E07; #21 and existing #11 |
| E09 | P1, broker + workstation | Add one explicit file/text transfer workflow with bounded staging, trusted endpoints, cancellation and revocation. Wrong-destination and replay tests must fail. | E08; #21 and existing #11 |
| E10 | P1, libkrun + runtime + broker | Qualify restricted audio/media transport, including existing CrossDomain PW support. Playback, mic and capture remain separate; revoked streams stop. | E03/E04/E08; #21 |
| E11 | P1, workstation portal integration | Implement guest-local portal requests and brokered host consent/resource translation. No unrestricted host DBus or PipeWire socket shortcuts. | E09/E10; #21 and existing #11 |
| E12 | P1, Workestrate | Extend plan/admission/provenance and fresh launch/grant lifecycle; preserve existing init/nested/slot semantics. Test stale grants and desired-versus-active drift. | E01/E03; workestrate#39 |
| E13 | P1, storage runtime + tooling | Qualify immutable generation publication, lease roots, overlay/DB coherence and GC under crashes. Measure runtime physical storage sharing separately from archive prefixes. | Existing #8; #20 |
| E14 | P2, libkrun + Microsandbox | Integrate native display/input bindings and qualified 2D/stride/cursor work for whole-desktop scanout. Linux viewer, resize/reconnect and bounded input are explicit deliverables. | E04/E05/E06; #18 |
| E15 | P2, workstation + specialized backend | Qualify outer VFIO domain and nested app VMs with actual host hardware, recovery and resource ownership tests. No unsupported backend fallback. | E12; #17 |
| E16 | P3, libkrun + rust-vmm + storage + runtime | Define and implement supported memory/device restore and fork scopes, reject unsupported devices, refresh identities/grants and prove isolation/consistency. Graphics is not assumed capturable. | E12/E13 and existing #7/#6 |

### Exact edit seams

**libkrun:** `src/krun/src/api/builders.rs`, `src/krun/src/api/builder.rs`, `src/krun/src/lib.rs`, `src/krun/Cargo.toml`, `src/devices/Cargo.toml`, `src/devices/src/virtio/gpu/virtio_gpu.rs`, related `device.rs`/`worker.rs`, and the in-tree Rutabaga/display/input implementations. Native bindings, capsets/channel configuration, mapping and display behavior belong here. Do not add unrelated policy vocabulary to the guest kernel. [S3], [S5], [S6].

**Microsandbox:** `crates/runtime/Cargo.toml`, `crates/runtime/lib/launch.rs`, `crates/runtime/lib/vm.rs`, `crates/runtime/lib/control.rs`, `sdk/rust/lib/sandbox/builder.rs`, `sdk/rust/lib/sandbox/config.rs`, `sdk/rust/lib/runtime/spawn.rs`, and the authoritative shared types/schema/CLI definitions identified by those paths. Update generated consumers through the repository's actual generation workflow. Preserve the bootstrap protocol, canonical durable representations and launch refusal conventions in `COMPATIBILITY.md`. For snapshots start from `sdk/rust/lib/snapshot/create.rs`, not an invented new snapshot subsystem. [S2], [S10], [S11], [S13], [S14].

**libkrunfw:** `config-libkrunfw_x86_64`, kernel patch/build selection and installed provenance/checks. Add a requirement only when the selected role needs it, verify the resulting config after kernel configuration resolution, and keep libkrun-specific poweroff behavior out of a physical-PC kernel. [S4], [S15].

**nix-tooling:** `lib.guest`/`nixosModules` exports, documented NixOS image constructors, registration and opt-in smoke contracts. Keep runtime-neutral construction and engine choice separate from operator fleet policy. A runtime test receives the runtime as an explicit input rather than introducing a tooling-to-runtime dependency cycle. [S7]

**Workestrate:** `control/agentctl/src/microsandbox/plan.rs` and its existing `runtime`, `nested`, `broker`, `generation`, `provenance`, `slots` and `depgraph` module seams; then authoritative config/schema and Nix dependency composition. Workstation-specific UI/portal/policy choices belong in a separate consumer. [S8], [S9].

### Dependency shape

```text
E01 manifest / capability truth
 +--> E02 mapping + E03 explicit channels --> E05 runtime plumbing
 +--> E04 host confinement
 +--> E06 role/firmware evidence --> E07 guest session
                   E03/E04/E05/E07 --> E08 two seamless guests
                                        +--> E09 bounded transfer
                                        +--> E10 media --> E11 portals
E01/E03 --> E12 optional Workestrate adapter
E13 immutable storage + E12 authority --> E16 memory/device forks
E04/E05/E06 --> E14 full-desktop viewer (separate branch of work)
E12 + hardware qualification --> E15 outer VFIO/nested topology
```

## 11. Tests that decide whether the design works

Every accepted work package should specify independent observations and negative controls, not just a happy-path screenshot or a successful Cargo build.

| Test group | Required evidence |
| :--- | :--- |
| Source/build | Exact manifests, CPU-only build without graphics dependencies, graphics profile link/ABI checks, generated-schema compatibility |
| Firmware/boot | Actual required guest devices, successful stage-2/session activation, coherent store state after two boots, clean flush and VMM exit distinct from timeout kill |
| GPU | Selected renderer identity, nonzero usable capsets, buffer mapping/read-write, submitted work and completed fences, intentional software mode reported correctly |
| Wayland | Two separate VMs and proxy connections; resize/scale/popups/focus; guest-supplied labels cannot alter trusted provenance |
| Authority | Hostile environment, old runtime, stale CID/socket/grant, unauthorized channel, wrong file destination, capture after revoke, and extra inherited FD all rejected |
| Host confinement | Malicious helper cannot read/write other instances, host credentials or unrelated supervisor state, and cannot bypass egress policy |
| Failure | Independent guest/proxy/renderer/broker crash and restart; bounded cancellation; no unbounded stalled client blocking unrelated workloads |
| Storage/forks | Exact captured scope, lease/GC crash cases, no shared writable lower, unsupported resume rejected before mutation, identity/grants handled independently from restored memory |
| Hardware-only | Actual driver/kernel/GPU/CPU tuple, outer IOMMU group/reset validation and L2 KVM execution where requested; do not infer support from config fields |

For the first release gate, choose one host compositor, one pinned proxy, two small NixOS app guests and one representative browser. Broaden the matrix only after the basic authority and lifecycle tests pass. Explicitly report untested platforms and protocols rather than implicitly claiming all desktops, GPUs or distributions.

## 12. Tracking and open decisions

Created for this assessment:

| Tracker | Responsibility |
| :--- | :--- |
| [sketchbook #17](https://github.com/rybskiworks/sketchbook/issues/17) | Cross-repository milestones and dependency map |
| [sketchbook #18](https://github.com/rybskiworks/sketchbook/issues/18) | GPU mapping/runtime integration and separate display/input work |
| [sketchbook #19](https://github.com/rybskiworks/sketchbook/issues/19) | Explicit channels, endpoint policy and VMM/renderer confinement |
| [sketchbook #20](https://github.com/rybskiworks/sketchbook/issues/20) | NixOS guest roles and firmware qualification without duplicating boot support |
| [sketchbook #21](https://github.com/rybskiworks/sketchbook/issues/21) | Two seamless compartments, provenance and revocable interactions |
| [workestrate #39](https://github.com/rybskiworks/workestrate/issues/39) | Generic capability-qualified plans and generation-bound grants |

The libkrun fork rejected issue creation because Issues is disabled. Its work is explicitly assigned an implementation owner in the central tracking issues; no repository setting was changed and no upstream implementation issue is falsely claimed. Existing #11, #8 and #7 remain the authorities for their broader explorations. Accepted runtime work should be reflected in the existing Beads dependency graph, preserving these issue links, not by initializing or migrating tracker databases during planning.

Decisions still requiring evidence: the first compositor/proxy pair; exact renderer ABI/backport choice; host-side provenance mechanism; narrow PipeWire/media protocol coverage; whether to split runtime management writes for stronger confinement; per-role Nix engine; acceptable performance degradation; and the actual hardware topology for an outer GPU-owning domain. The preferred default remains a narrow, measured app-VM experiment, not enabling every optional device or promising universal snapshot support.

## Source map

Pinned repository sources are the authority for observations above. External documentation is a reference implementation or protocol contract; upstream proposal reports are candidates, not local test results.

[S1]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/DOWNSTREAM.md
[S2]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/Cargo.toml
[S3]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/krun/src/api/builders.rs#L1138-L1260
[S4]: https://github.com/rybskiworks/libkrunfw/blob/d575b13e79368b23246be3d93d7935899dec5a3b/config-libkrunfw_x86_64
[S5]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/devices/src/virtio/gpu/virtio_gpu.rs#L220-L280
[S6]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/src/rutabaga_gfx/src/rutabaga_core.rs#L1177-L1320
[S7]: https://github.com/rybskiworks/nix-tooling/blob/a403c2c111e24db64feb5748bbba939308048c07/docs/nixos-oci-images.md
[S8]: https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/docs/runtime-provisioning.md
[S9]: https://github.com/rybskiworks/workestrate/blob/beaab036fe9fb59f132c83bdb81d443863914d9f/control/agentctl/src/microsandbox/plan.rs#L77-L148
[S10]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/COMPATIBILITY.md
[S11]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/sdk/rust/lib/snapshot/create.rs#L25-L97
[S12]: https://github.com/rybskiworks/libkrun/blob/9c0c8b517d5685672a89a7bf6810ef9a114ec07b/README.md
[S13]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/crates/runtime/lib/vm.rs#L1-L210
[S14]: https://github.com/rybskiworks/microsandbox/blob/251b368a868d578ead123071c3e6bc8eec013817/crates/runtime/Cargo.toml
[S15]: https://github.com/rybskiworks/libkrunfw/blob/d575b13e79368b23246be3d93d7935899dec5a3b/README.md
[P1]: https://doc.crosvm.dev/book/devices/wayland.html
[P2]: https://github.com/google/sommelier-rs/blob/main/README.md
[P3]: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html
[P4]: https://docs.mesa3d.org/drivers/venus.html
[P5]: https://microvm-nix.github.io/microvm.nix/options.html
[U1482]: https://github.com/superradcompany/microsandbox/pull/1482
[U118]: https://github.com/superradcompany/libkrun/pull/118
