# Pluggable backend architecture for the Workestrate fleet

One versioned backend contract sits between the fleet operator and every
sandbox backend. microsandbox-fork is backend #1. CubeSandbox is backend #2.
Firecracker and QEMU can follow. The k0s operator sees one interface only.

## 1. The contract

The contract already exists in prototype form inside
`control/agentctl/src/control_plane/`:

- `types.rs`: backend-neutral names (`WorkloadRef`, `InstanceRef`,
  `LaunchRef` = instance + `generation` as `OpaqueId`), `ControlRequest` /
  `ControlResponse` envelopes, `RuntimeCapabilities`, `LifecycleState`,
  the `ExecState` machine, `SshRequest` (Inspect / Reconcile / Revoke).
- `native.rs`: the narrow adapter traits `NativeControl` / `NativeExec`
  plus `MicrosandboxControl`, the first adapter.
- `dispatcher.rs` / `owner.rs`: one serializing owner, one host endpoint.

Promote this seam to the versioned **Backend Contract v1**:

```
launch(spec) -> LaunchRef          # create + bind one exact generation
observe(launch) -> ObservedState   # Running | Stopping | Stopped + health
exec(launch, command) -> stream    # launch-bound guest exec
stop(launch) -> Stopped            # generation-fenced stop, no name lookup
snapshot(launch) -> SnapshotRef    # OPTIONAL, capability-gated
restore(snapshot) -> LaunchRef     # OPTIONAL, pairs with snapshot
```

Rules, carried over from the existing code:

- Every mutating call takes a `LaunchRef` (instance + generation), never a
  reusable name. Replacement always changes `generation`.
- A launch ID is a public projection, not a bearer credential.
  Knowing it never authenticates a caller.
- No adapter reconnects by name, reuses a slot after a lease ends, or
  discovers resources. The trusted owner supplies workload plans and
  retained handles; adapters translate.
- Every native call has a fixed time budget (today 5 s in the dispatcher).
  Queues and replies stay bounded.
- The owner never stops an adopted VM when it exits.

## 2. Capability advertisement

Backends differ. The operator must not probe by trial and error.
Each adapter reports a capability set at register time, extending the
existing `RuntimeCapabilities` shape:

| Capability | microsandbox-fork | CubeSandbox | Firecracker? | QEMU? |
|---|---|---|---|---|
| launch / observe / stop | yes | yes | yes | yes |
| launch-bound exec + stdin/pty/cancel | yes | yes (envd) | via guest agent | via guest agent |
| snapshot / restore | no | yes (snapshot-as-template) | yes (mem+diff) | yes (qcow2/migration) |
| pause / resume | msb stop/start | yes (`/pause`) | yes | yes |
| clone N from snapshot | no | yes | manual | manual |
| nested virtualization | require-capable | no (KVM guest) | no | nested opt-in |

Unknown capabilities are denied by default. There is no wildcard grant:
like `ControlOperation` today, each new capability needs an explicit
permission-table entry. A workload that requests `snapshot` on a backend
without it fails closed at admission with `UnsupportedCapability`,
before any VM is touched.

## 3. Selection policy

Selection is data, not code. A workload (or fleet default) declares:

```toml
[backend]
preferred = ["microsandbox", "cubesandbox"]  # ordered
requires  = ["snapshot"]                     # hard gates
```

The operator resolves, per launch:

1. Drop backends that lack a `requires` entry. Fail closed if none remain.
2. Take the first surviving entry of `preferred`.
3. Pin the chosen backend + adapter version into the launch record
   (`LaunchRef` + `backend: { name, adapter_version }`). A launch never
   migrates mid-life; replacement creates a new generation.

Fleet default stays `microsandbox` until a backend passes conformance
(see §6). Per-workload overrides allow canary backends (e.g. run the
stateless linter on CubeSandbox first).

## 4. Per-backend adapters

One adapter = one crate (or one Go package, operator-side) implementing
the contract against one backend SDK. Nothing is shared except the
contract types.

- **microsandbox adapter** (exists): `MicrosandboxControl` in `native.rs`.
  Wraps the pinned SDK `=0.6.18` from fork
  `github:rybskiworks/microsandbox/251b368a868d578ead123071c3e6bc8eec013817`.
  Name encoding (`slots::msb_name_of_instance`) stays inside this adapter.
- **CubeSandbox adapter** (to build): talks to CubeAPI (`/cubeapi/v1`,
  see `openapi.yml`; E2B-compatible surface: create/list/get/pause
  sandboxes). Maps Cube sandbox IDs to `LaunchRef` generations at retain
  time, exactly like `retain()` does for msb names. Snapshot maps to the
  Cube snapshot-as-template API (`SnapshotID` doubles as template ID);
  clone-N maps to `CloneOptions`. Egress goes through CubeEgress policy,
  compiled from the same workload policy the msb adapter consumes.
- **Firecracker / QEMU adapters** (future): same trait. Snapshot maps to
  Firecracker mem-file + diff or QEMU qcow2 / migration streams. Guest
  exec needs a guest agent (vsock); until the agent is present the
  adapter advertises `launch_bound_exec = false` and exec workloads
  refuse to schedule there.

Adapter dependencies (SDKs, guest-agent binaries) live on the adapter,
never in the contract crate — the same fork-carries-compat policy as ADR 0011.

## 5. Backend-owned vs operator-owned

This is the hard line. Backends provide **mechanism**. Workestrate keeps
**identity, credentials, and policy**.

Operator-owned (never delegated):

- Identity: `OpaqueId` generations, `LaunchRef` bindings, CID→instance
  registry, epoch tokens (anti-replay / anti-fork).
- Credentials: sealed SOPS Ed25519 custody, per-launch SSH shim setup,
  `ssh_emit` compilation. Requests name registered resources and
  credential *names*, never raw keys or backend addresses.
- Secrets: the layering ladder (`bound = host | guest`, `allowed_hosts`
  deny-all default, `on_violation` ladder). Host-bound placeholders are
  substituted by the Workestrate egress proxy only toward allowed hosts.
- Policy: mount policy, egress/ingress allowlists, provenance, audit
  digests. A backend receives compiled enforcement input, not source policy.
- Desired state: the reconciler owner, generations, fencing, break-glass.

Backend-owned:

- VM/isolation mechanism (namespaces, KVM, microVM, snapshots).
- Guest image boot, pause/resume, clone, resource enforcement.
- Its own control-plane auth (CubeAPI tokens, etc.), scoped per host,
  held by the adapter — never minted from Workestrate credentials and
  never visible to guests.

Concretely: adopting CubeSandbox means adopting its API and its
snapshot/clone speed. It never means adopting a Cube identity model,
storing fleet secrets in Cube, or letting Cube policy decide what a
workload may reach. The sibling CubeSandbox deep-dive states the same
non-goals: no identity adoption, no Nix-deployment claim.

## 6. Conformance suite (both sides run)

One suite, two harnesses:

- **Contract harness** (operator side): spins each registered adapter
  through launch → observe → exec → stop, generation-fence checks
  (stale generation rejected), stop-by-wrong-generation rejected,
  budget-exceeded kills, owner-exit leaves VM untouched.
- **Capability harness** (per capability): snapshot → restore → verify
  content; pause → resume → verify liveness; clone-N → verify fan-out.
  Backends without the capability must return `UnsupportedCapability`,
  not a half-working emulation.

Gates:

- A backend enters `preferred` lists only after green contract harness.
- A capability enters `requires`-satisfying status only after green
  capability harness for that capability.
- The suite runs in CI per adapter-version bump and per backend pin
  bump (msb fork rev, CubeSandbox rev).

## 7. Adapter versioning

- The contract carries a semver major (`Backend Contract v1`).
  Breaking changes (new required method, changed `LaunchRef` shape)
  bump the major; adapters declare the majors they implement.
- Adapters version independently (`microsandbox-adapter 0.6.18.x`,
  `cubesandbox-adapter 0.1.x`). The launch record pins
  `(contract_major, adapter_name, adapter_version, backend_pin)`.
- Additive capabilities (e.g. `pause`) are minor additions: old
  adapters keep working, new workloads gate on advertisement.
- The operator refuses to load an adapter whose contract major it
  does not speak. Mixed-version fleets drain and re-launch; no
  in-place cross-version handoff of a live launch.

## 8. What the k0s operator sees

One interface. The operator reconciles `Workload` CRs and calls the
contract; backend choice is a resolved field on the launch, not a
branch in the reconciler:

```
Workload CR → resolve backend (policy §3) → contract.launch()
            → status holds LaunchRef + backend pin
            → contract.observe() feeds status
            → contract.stop() on delete / replace (finalizer)
```

Sibling notes own the details: `fleet-crd-design.md` (Workload/RuntimeHost/
WorkloadOperation/Checkpoint shapes, fencing, no silent revive),
`go-operator-patterns.md` (reconciler patterns), `broker-arc-runners.md`
(launch-bound tokens, ARC). Checkpoint CRs reference `SnapshotRef`s and are rejected
on backends without the snapshot capability.

## 9. Migration path between backends

Live migration across backends is **not supported by design**.
A launch is backend-pinned for life. Moving a workload means:

1. Register + conform the new backend (suite green, §6).
2. Add it to `preferred` behind the old one (canary) or for
   snapshot-capable workloads only (`requires = ["snapshot"]` routes
   them to CubeSandbox while the rest stay on msb).
3. Blue-green cutover per ADR 0021/0030 slots: bring the new-backend
   generation up on a parallel slot, smoke-test, then replace.
   State moves via workload-level export/import or snapshot→restore
   only where both sides advertise the capability with a compatible
   format — otherwise cold start with mounted `/data` state carried
   over (state lives on Workestrate mounts, not inside the backend).
4. Remove the old backend from `preferred` once all generations on it
   have drained. Stopped generations are never revived.

Rollback is the same path in reverse, with the same no-silent-revive
rule: a fenced (break-glass) launch stays fenced until explicit handoff.
