# CubeSandbox deep-dive (Workestrate fleet)

> Upstream: `tencentcloud/CubeSandbox` at pin `d4a93fa546223a5bde8abe14bda2d88153c982f7`.
> Method: GitHub API tree + file reads at the pin. No host was provisioned, no benchmark was run.
> All latency and size numbers below are upstream vendor claims, not reproduced results.
> Date: 2026-09-16.

Pin detail: commit `d4a93fa` (author DSH 2026-09-14, committer Like Xu 2026-09-16)
removes a vacuous/flaky `Test_HashCode` (`Cubelet/pkg/utils/strings_test.go`, 31 deletions).
Repo state at read time: `master` branch, ~12.5k stars,
description "Instant, Concurrent, Secure & Lightweight Sandbox for AI Agents", Apache-2.0 with third-party exceptions (LICENSE names additional components; GitHub API reports NOASSERTION).
Tree at pin: 3,793 blobs. Top layout: `CubeAPI`, `CubeEgress`, `CubeMaster`, `CubeNet`,
`CubeOps`, `CubeProxy`, `CubeS3lvol`, `CubeShim`, `CubeTemplateCenter`, `Cubelet`,
`cubecow`, `hypervisor`, `agent`, `sdk`, `examples`, `tests`, `deploy`, `docs`, `web`,
`configs`, `pkgs`, `docker`, `openapi.yml`.

Related sketch: `explorations/workestrate-k0s-cubesandbox-comparison.md` (fleet framing).

## 1. E2B-compatible API surface (CubeAPI, `openapi.yml` at pin)

CubeAPI calls itself the "E2B-compatible sandbox API server".
OpenAPI `3.1.0`, title `CubeAPI`, version `0.1.0`, server `/cubeapi/v1`.
26 paths at the pin:

- `/health`
- `/sandboxes` (GET list, POST create)
- `/sandboxes/{sandboxID}` (GET detail, DELETE kill)
- `/sandboxes/{sandboxID}/connect`, `/logs`, `/network`, `/pause`, `/refreshes`,
  `/resume`, `/rollback`, `/snapshots`, `/timeout`
- `/snapshots` (GET list)
- `/templates`, `/templates/aliases/{alias}`, `/templates/compat`,
  `/templates/compat/{templateID}/adopt-baseline`, `/templates/{templateID}`,
  `/templates/{templateID}/alias`, `/templates/{templateID}/builds/{buildID}`,
  `/templates/{templateID}/builds/{buildID}/logs`,
  `/templates/{templateID}/builds/{buildID}/status`
- `/v2/sandboxes`, `/v2/sandboxes/{sandboxID}/logs`
- `/volumes`, `/volumes/{volumeID}`

Create shape (`NewSandbox`): `templateID` is the one required field.
Field names match what the E2B SDK sends. ID abbreviations stay uppercase
(`templateID`, `sandboxID`, `envVars`). `envs` is accepted as an alias for `envVars`.
`allow_internet_access` keeps its snake_case SDK quirk. Other inputs:

- `timeout`: idle TTL in **seconds** (E2B uses `timeoutMs`; Cube uses seconds).
- `metadata`: free-form key/value stored on the sandbox.
- `distributionScope`: node IDs or host IPs allowed to run the sandbox; one entry pins it.
- `network`: `allowOut`, `denyOut`, `rules`, `maskRequestHost`, `allowPublicTraffic`.
- `lifecycle`: `onTimeout` (`kill` default, or `pause`) + `autoResume` bool.
- `volumeMounts`: path-keyed volume attachments.
- `secure`, `mcp`, plus flattened `autoPause`/`autoResume` for E2B wire compat.

Sandbox response (`Sandbox`): `sandboxID`, `templateID`, `clientID`, `envdVersion`,
`domain`, `envdAccessToken`, `trafficAccessToken`, `alias`.
Detail (`SandboxDetail`) adds `state` (`running`, `paused`, `pausing`, `unknown`),
`cpuCount` + `cpuMilli`, `memoryMB`, `startedAt`, `endAt`, `metadata`, `volumeMounts`.
`endAt` is the projected next-timeout instant; never-timeout sandboxes omit it.

Snapshots live beside templates, not under their own delete path:

- `POST /sandboxes/{id}/snapshots` -> `SnapshotInfo` (`snapshotID`, `names`).
- `GET /snapshots` -> paginated list, cursor in `x-next-token` header.
- Delete is `DELETE /templates/{id}` when the id is a snapshot id. There is
  intentionally no separate `DELETE /snapshots/{id}` (avoids divergent shapes).
- `POST /sandboxes/{id}/rollback` takes `snapshotID`, restores in place.

Lifecycle states: `running`, `pausing`, `paused`, `resuming`, `terminated`.
`timeout` values: omitted means server default; `NEVER_TIMEOUT` (`-1`) means never;
`0` means reclaim on first idle sweep; positive `N` means N idle seconds.
`on_timeout="kill"` (default) destroys; `"pause"` freezes VM memory to the snapshot
store with zero CPU/memory cost. `connect()` resumes a paused sandbox.
`kill()` always wins and is irreversible. Deleting a paused sandbox removes the
tombstone and snapshot without resuming. Delete returns `204` on success,
`503 + Retry-After: 2` when a pause/resume/delete holds the lock.

Python SDK (`cubesandbox` 0.7.0, Python 3.9+, `pip install cubesandbox`):

- `Sandbox.create(template, timeout, env_vars/envs, metadata, distribution_scope,`
  `allow_internet_access, network, lifecycle, volume_mounts)`.
- `Sandbox.connect(sandbox_id)` (resumes when paused), `sandbox.get_info()`,
  `Sandbox.list()`, `sandbox.kill()`, `sandbox.pause()`, `run_code`, `commands.run`,
  `files.read/write`, `pty`, `create_snapshot`, `Sandbox.list_snapshots`,
  `Sandbox.delete_snapshot`, `clone(n, concurrency)`, `rollback(snapshot_id)`,
  `set_timeout`, templates, volumes.
- When `user` is omitted the SDK sends as `root` for envd compat.
- Public URL shape: `{port}-{sandboxID}.cube.app` via `get_host(port)`.
- `Sandbox.create(template=snap.snapshot_id)` spawns from a snapshot as a template.
- `clone(n=N)` fans out N isolated sandboxes with inheritance, isolation,
  continuity; failures kill already-created clones (all or nothing); the temp
  snapshot is refcount-cleaned after all clones land.

E2B SDK interop is real: point `E2B_API_URL=http://127.0.0.1:3000` at Cube,
pass any placeholder `E2B_API_KEY`, set `CUBE_TEMPLATE_ID`, trust the mkcert CA.
Validated pairs recorded upstream: `e2b==2.21.0 + e2b-code-interpreter==2.8.1`
(needs constraint override, runs in production), `e2b==2.26.0`, `e2b==2.29.5`.
Ceiling candidate `e2b==2.37.1`; known bad `2.38.0` (drops `get_transport(http2=...)`).
Capability map: common (`lifecycle`, `commands`, `filesystem`, `filesystem_extended`,
`run_code`) on both; E2B adds `code_interpreter`, `pause_resume`, `set_timeout`,
`network_allow_deny`, `network_public_access`, `network_mask_request_host`;
Cube adds `rollback_clone`, `network_dns_allow`, `network_always_denied`,
`network_l7_egress`, `network_template_merge`, `network_dynamic_update`,
`platform_lifecycle`, `host_mount`, `volume_plugin`, `auth_simple_key`,
`network_l7_custom_port`.

## 2. Host requirements and root plus Docker posture

- CPU and virtualization: x86_64 Linux with KVM. Ordinary cloud VMs work
  through PVM. PVM host kernel is x86_64-only. ARM64 needs native KVM
  on bare metal. Self-build docs forbid nested virtualization.
- Check KVM with `ls -la /dev/kvm`. It must exist and be read/writable.
- User: run every install command as `root`. `install.sh` requires root.
- OS: binaries build on Ubuntu 20.04 (glibc 2.31). Host needs glibc >= 2.31.
  Best fit: OpenCloudOS 9 and TencentOS 4. Tested: Ubuntu 20.04, 22.04, 24.04.
  Other RPM, Debian, and WSL hosts must still meet glibc and XFS rules.
- Filesystem: `/data/cubelet` must sit on XFS with reflink. Ubuntu and Debian
  default to ext4, so they need a manual XFS mount. See upstream FAQ #311.
- Disk: at least 50 GB free on `/data/cubelet`. Use 200 GB or more
  for many templates or custom images.
- Size: 4 cores and 8 GB RAM can run it. Recommended: 32 cores, 64 GB RAM.
  Self-build guide asks for 8 or more cores and 16 or more GB RAM.
- Docker: required and running. MySQL and Redis run through Docker Compose.
  CubeProxy and CoreDNS use Compose templates. The builder runs in Docker.
  Guest image build needs `tar`, `python3`, `truncate`, `ldd`, `mkfs.ext4`.
- DNS: `systemd-resolved` is preferred. `NetworkManager + dnsmasq` also works.
- S3: MinIO ships by default as the S3 backend for volumes and cross-node
  pause and resume. Nodes that mount volumes still need `s3fs`.
- Install result: REST API on port 3000. CubeMaster, Cubelet with embedded
  network runtime, and CubeShim run as host processes. MySQL and Redis run
  in Compose. CubeProxy gives TLS through mkcert and `cube.app` routing
  through CoreDNS. WebUI listens on port 12088.
- No rootless path exists upstream. No NixOS package or module exists upstream.
  Treat Cube as a root-run service beside the Nix world, not inside it.

## 3. cubecow XFS reflink engine

- cubecow is a Copy-On-Write store on XFS reflink (`FICLONE`). It ships as a
  Rust library crate. It gives thin volumes plus O(1) snapshot and clone.
- Only backend at the pin: `ReflinkEngine`. All callers use the `Engine` trait
  through `dyn Engine`. A new backend needs no FFI or SDK change.
- `FICLONE` shares extents instead of copying bytes. Snapshots are metadata
  operations. Cost follows extent count, not file size.
- Model is flat. Each snapshot is its own file. A snapshot of a snapshot is
  flattened to the same origin volume. Delete of one snapshot never touches
  another snapshot. Delete is one `unlink`.
- Layout: `<root_dir>/volumes/<vol>/<vol>` is the main file. Snapshots sit
  beside it as `<snap-1>`, `<snap-2>`. The engine owns only `volumes/`.
- Crash recovery is a scan. Volumes and snapshots are files. Restart rebuilds
  the in-memory index from `readdir` plus `stat` plus `mtime`. No ledger file
  exists. The scanner drops orphan artefacts from crashed runs.
- Names share one process-wide namespace. A volume name and a snapshot name
  cannot collide. Names should be UTF-8 and non-empty. Leading `_` is reserved
  for backend use.
- Volume: the only usable unit. It has a unique `name`, a thin `size_bytes`
  upper bound, and a host `device_path` for block I/O. It is read-write.
  It can grow. It cannot shrink. Delete wipes it.
- Snapshot: a read-only copy of one volume at one time. It records
  `origin_volume` as the first volume, never another snapshot. It has an
  active state: active means `device_path` is set and readable; inactive means
  metadata only. Use `activate_volume` and `deactivate_volume` to switch.
  `create_volume` creates and activates in one step. `activate_volume` is
  idempotent. `deactivate_volume` drops the device, not the metadata. Delete
  drops the device first, then the metadata.
- To make a writable copy, use the cross-node `import_lvol` path. The base API
  has no direct derive-volume-from-snapshot call.
- Build needs Rust 1.93 or later. Production XFS needs
  `mkfs.xfs -m reflink=1,crc=1`. Unit tests need no root. The reflink bench
  needs root plus `xfsprogs` plus `losetup`.
- v0.7 adds `CubeS3lvol` COW on S3 for remote snapshots, cross-node pause and
  resume, and snapshot clone. MinIO is the default S3 target. Cross-node use
  is still preview.
- Deep-dive model: VM state is disk plus memory. Disk uses XFS reflink.
  Memory uses `/proc/self/pagemap` plus soft-dirty tracking for true
  incrementals. Result: disk snapshots return almost at once for tens of GiB.
  Memory writes cover only a fraction of guest RAM. Clones add almost no disk
  use, yet each copy reads and writes in isolation.

## 4. eBPF plus L7 egress model (CubeVS, CubeEgress, CubeProxy)

- CubeVS is the kernel data plane. Three eBPF programs share pinned BPF maps
  under `/sys/fs/bpf`. A Go library owns load, pins, TAP setup, and reaping.
- `from_cube` runs at TC ingress on each TAP device. It checks policy, reads
  DNS, applies SNAT, makes sessions, and answers ARP.
- `from_world` runs at TC ingress on the host NIC. It reverses NAT and serves
  port mappings for inbound traffic.
- `from_envoy` runs at TC egress on `cube-dev`. It returns proxy replies and
  host probes toward sandboxes.
- No shared bridge exists. Each sandbox gets its own TAP device straight into
  the kernel path.
- Control plane: `Init` loads and pins objects and sets host constants.
  `AddTAPDevice` and `DelTAPDevice` add and drop sandboxes. `AttachFilter`
  builds the `clsact` qdisc and filter. `SetSNATIPs` fills the SNAT pool.
  Port map calls update static NAT at run time. Two reapers drop dead NAT
  sessions and dead DNS-learned entries.
- Egress path: sandbox process, TAP, `from_cube`, then either direct SNAT to
  the host NIC, or marked TCP 80 and 443 to `cube-dev`, TPROXY, CubeEgress,
  and out. Ingress answers come back through `from_world`.
- User fields: `allow_internet_access`, `allow_out`, `deny_out`, `rules`,
  plus `mask_request_host` and public-traffic flags.
- Order: check `allow_out_v2` first. A hit allows. A hit with `L7_REQUIRED`
  sends TCP 80 and 443 to CubeEgress. Then check `deny_out`. A hit rejects.
  TCP gets RST when possible. Other traffic drops. Else allow by default,
  unless `allow_internet_access=false` installed a `0.0.0.0/0` deny.
- Priority is allow, then deny, then default allow.
- Guard rails: with public egress on, private and host ranges go to deny by
  default (`10/8`, `127/8`, `169.254/16`, `172.16/12`, `192.168/16`).
  With public egress off, `0.0.0.0/0` denies all, but explicit allows and L7
  targets can still open holes.
- Limits: 8192 allow keys, 8192 deny keys, 1024 DNS domain keys, 1024 inner
  trie entries. `198.51.100.1` and `198.51.100.1/32` count as one key. Domains
  are lowercased and lose one trailing dot. Over-limit calls fail back through
  Cubelet, CubeMaster, and CubeAPI to the create caller.
- DNS learning: domain targets in `allow_out` and `rules[].match.host/sni`
  enter `dns_allow`. Query and response tracking learns A records into timed
  IP allows. Exact and leading `*.` forms work.
- CubeEgress is the L7 proxy. It runs as a host-network container on OpenResty
  plus lua. It binds TPROXY listeners HTTP 8080 and HTTPS 8443 on the
  sandbox-facing IP. eBPF marks each SYN with HTTP or HTTPS. `iptables`
  mangle steers each mark to its listener.
- TLS: `ssl_certificate_by_lua` mints a leaf cert per SNI. It signs with the
  CubeEgress root CA. The template trusts that CA, so guest TLS clients see
  no error. The proxy can then read, allow, deny, inject, and audit.
- Rules: `match` plus `action`. All set fields must match. First match wins.
  No match means deny. Fields: `scheme`, `port`, `sni`, `host`, `method` list,
  `path` with exact or one trailing `*` prefix. `sni` and `host` allow leading
  `*.` for subdomains, not the apex. Matching is case-insensitive.
- Ports: no `port` means classic `{80/http, 443/https}`. `scheme` alone keeps
  one classic side. `port` plus `scheme` pins one `(host, port, scheme)` tuple.
  `port` needs `scheme`. Range is 1 to 65535. Subnet CIDRs cannot be L7 hosts.
  One `(host, port)` pair can only use one scheme. Max 8 `(port, scheme)`
  tuples per host. Uncovered ports stay in L3 and L4 policy and never reach
  the proxy.
- Timeouts: upstream read and send 2 hours. Connect 10 seconds.
- CubeProxy is the ingress side. It routes `{port}-{sandboxID}.cube.app`,
  serves TLS, forwards `Host` per `mask_request_host` (`${PORT}` expands),
  and checks `e2b-traffic-access-token` or `cube-traffic-access-token` when
  public traffic is locked down. Missing token means 403.
- Extras: live policy update on running sandboxes is supported. Optional
  `cube-router` mode sends egress through a dummy device into normal Linux
  routing plus MASQUERADE. That mode fits multi-NIC, GRE, VXLAN, WireGuard,
  and VPN paths. Port maps stay on the primary NIC.

## 5. Cold-start and density claims (vendor numbers, not reproduced)

- Headline: under 60 ms cold start, under 5 MB overhead per sandbox.
- README table: Docker 200 ms boot, low isolation; classic VM seconds, high
  isolation; Cube sub-ms label but under 60 ms in text, extreme isolation
  through dedicated kernel plus eBPF.
- Detail: 60 ms at single concurrency. At 50 concurrent creates: mean 67 ms,
  p95 90 ms, p99 137 ms, always sub-150 ms. Measured on bare metal.
- Memory: overhead stays under 5 MB for specs up to 32 GB. Larger specs may
  add a small rise. Density target is thousands of sandboxes per node through
  shared kernel paths and CoW.
- Mechanism cited: resource pooling plus snapshot clone skips cold boot.
  Aggressively stripped guest keeps the base small. Pause and resume lifts
  density further.
- Snapshot speed: disk snapshots return in about a split second for tens of
  GiB. Memory writes cover only dirty pages. Clone of 10 copies adds almost
  no disk. Rollback runs at hundred-ms scale. v0.3 adds event-level use.
- v0.7 notes: faster sandbox network setup. Network-agent merged into Cubelet.
  Fewer RPC calls on create. TAP lifecycle rework stops rule leaks. eBPF
  policy path tuned. Netlink dumps removed for high-concurrency TAP creates.
- Boundary: no host was provisioned here. Treat every number as a claim tied
  to bare-metal or PVM test rigs, not a fleet guarantee.

## 6. Identity and credential model (do not adopt as-is)

- Default: CubeAPI allows all requests with no auth. Auth only turns on when
  the server starts with `--auth-callback-url` or `AUTH_CALLBACK_URL`.
- Flow: server pulls `Authorization: Bearer` first, else `X-API-Key`. It posts
  to the callback with the credential plus `X-Request-Path` and
  `X-Request-Method`. Callback 200 means allow. Any other code means 401.
  Dead callback means 500. Missing credential means 401.
- Rule: check both path and method. One path serves GET, POST, PATCH, DELETE.
  Path-only checks let read-only keys delete or rebuild.
- SDK: E2B SDK sends `E2B_API_KEY` as Bearer. `cubesandbox` SDK sends
  `CUBE_API_KEY` as `X-API-Key`, and only when set. It warns when that key
  goes over plain HTTP to a non-loopback host.
- Sandbox traffic: `trafficAccessToken` is per sandbox when public traffic is
  restricted. Send `e2b-traffic-access-token` or `cube-traffic-access-token`.
  CubeProxy returns 403 without it. It arrives only on create.
- L7 secrets: CubeEgress injects headers such as `Authorization: Bearer ...`
  at the proxy. The workload never sees the raw secret. `Inject.secret` caps
  at 2048 bytes. Injection only counts on allowed HTTPS with matching SNI or
  Host. Audit levels are `full`, `metadata`, `none`.
- Volumes: plugin may issue a token. `VolumeInfo` carries it on create and
  get-single, never on list. SDK masks it in `repr`.
- Fleet rule: keep Workestrate as the custody point. Broker Cube creds behind
  the adapter. Do not copy Cube's default-open posture, its callback shape,
  or its token flow into Workestrate policy.

## 7. Versioned backend-contract adapter (proposal)

Pin the contract to the upstream pin. Example: `cubesandbox-backend v1`
tracks `d4a93fa`. A new upstream pin means a new contract version, plus
migration notes. The adapter owns five calls. Each call maps to Cube wires
below. No other Cube surface leaks through.

- `launch(spec) -> handle`
  Inputs: template ref, CPU and memory, env, metadata, network policy,
  lifecycle intent, volume mounts, placement scope.
  Cube wires: `POST /sandboxes` with `templateID`, `timeout`, `envVars`,
  `metadata`, `distributionScope`, `allow_internet_access`, `network`,
  `lifecycle`, `volumeMounts`. Snapshot spawn uses `template=snapshotID`.
  Output handle keeps `sandboxID`, `templateID`, `state`, node, and tokens.
- `observe(handle) -> state`
  Wires: `GET /sandboxes/{id}`, `GET /sandboxes/{id}/logs`,
  `GET /v2/sandboxes` for list sweeps. Normalize Cube `running`, `paused`,
  `pausing`, `unknown`, plus local `resuming` and `terminated`, into fleet
  states. Keep `startedAt`, `endAt`, `cpuMilli`, `memoryMB`, metadata.
- `stop(handle, mode) -> void`
  Modes: soft kill, hard kill, pause. Wires: `DELETE /sandboxes/{id}` for
  kill, `POST /sandboxes/{id}/pause` for freeze, `POST .../connect` or
  `.../resume` for wake. Handle `503 + Retry-After: 2` with backoff.
  Treat `kill()` as final. Treat paused delete as tombstone cleanup.
- `snapshot(handle, scope) -> snapshotRef`
  Scope: disk only or disk plus memory. Wires:
  `POST /sandboxes/{id}/snapshots`, `GET /snapshots` with cursor,
  `DELETE /templates/{snapshotID}` for retire,
  `POST /sandboxes/{id}/rollback` for restore. Keep `snapshotID`, `names`,
  origin sandbox, status, timestamps. Clone fan-out stays inside `launch`
  when the source is a snapshot or a live sandbox.
- `policyUpdate(handle, network) -> void`
  Wires: `PATCH /sandboxes/{id}/network` shape where present, else
  create-time `network` plus documented dynamic update path. Re-check live
  connections per Cube semantics.

Adapter rules:

- Validate `network` once: allow and deny caps, DNS key caps, L7 port and
  scheme checks, one scheme per `(host, port)`, max 8 tuples per host.
- Keep E2B wire compat at the edge (`envVars` and `envs`, snake and camel
  network keys, flattened `autoPause` and `autoResume`), but store one
  canonical form inside.
- Own timeouts: map `timeout`, `NEVER_TIMEOUT`, lifecycle `on_timeout` and
  `auto_resume`, idle sweeps, and `503` retry into fleet policy. Never let
  Cube defaults decide retention.
- Own placement: `distributionScope` is a hint. Fleet scheduler stays above it.
- Own secrets: inject through Cube L7 rules only as transport. Custody stays
  in Workestrate. Never log `trafficAccessToken`, volume tokens, or injected
  header values.
- Version gate: on startup, check CubeAPI `0.1.0` shape and template compat
  matrix. Refuse or quarantine on unknown fields, not silent pass-through.

## 8. Non-goals (explicit)

- No identity adoption. Do not take Cube's auth callback, default-open API,
  Bearer-or-key flow, or traffic token flow as Workestrate identity.
- No rootless claim. Upstream needs root, KVM, and Docker. No rootless path
  exists at this pin. Do not promise one.
- No Nix deployment. No NixOS package or module exists upstream. Do not claim
  Cube runs inside the Nix store. It runs beside it as an opaque service.
- No benchmark reproduction. Latency, overhead, and density numbers are vendor
  claims. No host was provisioned here.
- No control-plane merge. Keep k0s, k3s, Cube, and Workestrate versions apart.
  The adapter is the only joint.

## 9. Read list at the pin (all via GitHub contents API)

- `README.md`, `openapi.yml`, `AGENTS.md`, `Makefile`, `configs/single-node/*`
- `sdk/python/cubesandbox/sandbox.py`, `_models.py`, `_config.py`, `_policy.py`,
  `__init__.py`, `_transport.py`, `_volume.py`, `sdk/python/README.md`
- `CubeAPI/src/handlers/sandboxes.rs`, `snapshots.rs`, `volumes.rs`,
  `CubeAPI/src/services/snapshots.rs`
- `cubecow/README.md`, `cubecow/docs/cubecow-api.md`, `cubecow/Cargo.toml`,
  `cubecow/src/engine/reflink.rs`
- `docs/architecture/network.md`, `docs/guide/network-policy.md`,
  `docs/guide/security-proxy.md`, `docs/guide/lifecycle.md`,
  `docs/guide/authentication.md`, `docs/guide/network-hardening.md`,
  `docs/guide/route-aware-egress.md`, `docs/guide/snapshot-rollback-clone.md`,
  `docs/guide/quickstart.md`, `docs/guide/bare-metal-deploy.md`,
  `docs/guide/self-build-deploy.md`, `docs/guide/multi-node-deploy.md`
- `docs/blog/posts/2026-06-03-cubesandbox-v0.3.0-snapshot.md`,
  `2026-06-23-cubesandbox-network-deep-dive.md`,
  `2026-06-25-cubesandbox-snapshot-clone-rollback-deep-dive.md`,
  `docs/changelog/v0.7.0.md`
- `CubeEgress/nginx.conf`, `CubeEgress/lua/policy.lua`, `agent/src/network.rs`,
  `agent/README.md`, `hypervisor/README.md`
- `tests/e2e/sdk_compat/e2b-versions.txt`,
  `tests/e2e/sdk_compat/adapters/e2b_adapter.py`,
  `tests/e2e/sdk_compat/framework/capabilities.py`
- `examples/code-sandbox-quickstart/README.md`, `network_allowlist.py`,
  `examples/snapshot-rollback-clone/README.md`,
  `deploy/one-click/README.md`, `CubeNet/cubevs/egress_policy_test.go`
