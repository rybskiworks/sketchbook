# Yggdrasil: an agent that can revisit its execution history

> Status: draft specification / architecture exploration, not an accepted design or implemented API.
>
> Date: 2026-09-11. Scope: Linux-first, agent-directed experimentation over explicitly resettable environments.
>
> Tracks [issue #6](https://github.com/rybskiworks/sketchbook/issues/6). Runtime capability, store retention, recursive laboratory and knowledge work continue in [#7](https://github.com/rybskiworks/sketchbook/issues/7), [#8](https://github.com/rybskiworks/sketchbook/issues/8), [#9](https://github.com/rybskiworks/sketchbook/issues/9) and [#10](https://github.com/rybskiworks/sketchbook/issues/10).

**Remember outcomes. Rewind execution. Keep authority moving forward.**

## 1. The idea

Yggdrasil is a harness in which an agent can deliberately checkpoint an experiment, fork alternative futures, learn from their outcomes and revisit an earlier environment without forgetting everything it learned afterward. Branches are continuations of one problem-solving effort, not unrelated workers handed the same prompt.

The agent itself should be able to ask: "Save this state; let two versions of me test different explanations; retain their evidence; return me to the earlier state with that evidence; continue along the more promising path." The harness makes these requests real within declared capabilities and resource limits. It does not need to choose every branch on the agent's behalf.

The originating Satella/Subaru analogy is useful as a design mnemonic: the harness preserves the return points and continuity; the agent experiences attempts and carries useful lessons between them. This is not a claim about fictional canon or a requirement to model it literally. The operational requirement is an asymmetric reset: an explicitly bounded execution world can go backward while selected knowledge and the supervisory record continue forward.

A failed branch can be valuable. Its environment may be discarded while its observation becomes a scoped warning for siblings. A successful branch can become the basis for another round rather than an immediate final answer. The result is an inspectable evolutionary history of hypotheses, actions, evaluations and selected continuations.

"Evolutionary" describes that history, not a requirement for a genetic algorithm, model fine-tuning or a particular search policy. Sequential retry, branching search, bounded parallel sampling and population-style exploration are alternatives above the same runtime contract.

## 2. Goals, useful problems and non-goals

The first useful setting is an application and its synthetic dataset entirely inside a disposable VM: debugging a stateful failure, trying a migration, evaluating a configuration, exploring a workflow or minimizing a regression. Returning to a known state is valuable because the attempted operation changes the conditions of the next experiment.

Later consumers can include development-environment exploration and authorized hypervisor testing in a separate systems laboratory. A branch might contain a whole test deployment rather than only a shell. The boundary must describe all state needed to make its results interpretable.

The proposal aims to make agent-directed branching explicit, preserve useful failed-attempt evidence, prevent branch interference, explain what was actually reset, and produce reviewable artifacts with provenance. It should work with one agent and a cold, storage-only reset before requiring parallelism or live-memory forks.

Non-goals include universal undo, automatic reconciliation of arbitrary VM memory or filesystems, guaranteed deterministic LLM behavior, an autonomous right to publish results, a new mandatory guest daemon, or making Workestrate own model-specific planning. Neither a NixOS distribution nor an entire agent framework is a prerequisite. A thin tool adapter around an existing harness is a plausible first implementation.

A workload whose important state lives in uncontrolled external services is not automatically a good candidate. Checkpointing its client does not checkpoint those services. Either bring a simulation or owned fixture inside the reset boundary, provide a coordinated reset contract, or admit that this experiment is only partially reversible.

## 3. Separate five kinds of state

The essential split remains execution state **S** and retained knowledge **K**. Three additional records make the split operational rather than metaphorical.

| State | Examples | Treatment on rewind |
| --- | --- | --- |
| **S: execution world** | Workspace, application data, captured volumes, supported guest RAM/register/device state, image and store-generation bindings. | Restore only the resources and consistency level named in the checkpoint. |
| **A: agent continuation** | Task, selected conversation prefix, tool-result references, strategy, model/harness configuration, branch brief. | Start a new continuation from an explicit checkpoint or reconstructed session, then import an explicit K view. |
| **K: retained knowledge** | Observations, failed hypotheses, constraints, summaries, evaluations and their provenance. | Retain eligible records outside the reset domain; retrieval remains scoped and versioned. |
| **L: supervisory ledger** | Identities, authorization epochs, consumed budgets, operation IDs, effect receipts, promotion decisions, retention references. | Never restore from a workload checkpoint. Its accepted history remains forward-moving. |
| **E: external world** | Remote Git state, API charges, messages, external databases, other users and wall-clock time. | Unchanged unless a separately declared external protocol actually changes it. |

A useful transition is:

```text
attempt a: (S0, A0, K0) -> (S1, A1, K1)
attempt b: (S0, A0, K0) -> (S2, A2, K2) -> failure
continue: (S0, A3, view(K1, K2)) -> another experiment

L records all three attempts and their real cost.
E is not reset by the third line.
```

K is not VM RAM. Sharing physical pages through memory CoW is not sharing semantic knowledge. Likewise, preserving a transcript is not sufficient to make every statement in that transcript valid after the environment changes.

A checkpoint of S does not automatically capture A: the model may be a remote service, the harness may run outside the VM, or a tool call may be in flight. The baseline checkpoints at a completed tool/turn boundary and records a reconstructable continuation. It makes no promise to restore a remote provider's hidden state or reproduce the next completion exactly.

## 4. Proposed ownership and trust boundaries

```text
                       human / mission owner
                  goals, authority, limits, publication grants
                                  |
             +--------------------v-----------------------+
             | Yggdrasil supervisory harness              |
             | durable L; branch registry; effect broker  |
             | checkpoint/continuation coordinator        |
             +----------+------------------+--------------+
                        |                  |
             scoped tools/results         | candidate evidence
                        |                  v
             +----------v-------+   +---------------------+
             | agent family     |<->| K: evidence + views |
             | root and siblings|   | outside reset world |
             +----------+-------+   +----------^----------+
                        |                      |
                  experiment actions       evaluations
                        |                      |
             +----------v----------------------+----------+
             | generic runtime adapter / Workestrate      |
             | lifecycle, capability checks, identity,    |
             | policy, resource reservations and fencing  |
             +----------+------------------+--------------+
                        |                  |
                +-------v-------+  +-------v-------+
                | world branch a|  | world branch b|
                | private S_a   |  | private S_b   |
                +---------------+  +---------------+
                        ^                  ^
                        +-- independent ---+
                            validators

External publication: branch proposal -> effect broker -> E
Never: arbitrary guest access to host administration or shared mutable S.
```

Yggdrasil owns exploration coordination, continuation construction, branch briefs, knowledge views and evaluation policy. The agent can propose or initiate the allowed exploration actions. A deterministic supervisor enforces mission scope, admission limits and cancellation. Resource pressure may delay or reject a fork; it must not silently turn a requested fork into a different operation.

Workestrate is a candidate provider of generic lifecycle, policy, identity and backend adaptation, consistent with its documented workload-oriented positioning [W1]. This draft does not assert that its current public API already exposes Yggdrasil's operations. Backend-native guest execution should remain usable; a universal replacement for each backend's agent/control channel is not assumed.

The preferred first placement keeps the harness, ledger and knowledge store outside the resettable target VM. An agent can still run inside a workload and invoke a narrow authenticated bridge. A later all-in-guest arrangement must place authoritative continuity outside the state it rewinds, or it risks forgetting accepted effects, charging decisions and its own pending rewind.

The model is not the security boundary. Guest output, retrieved knowledge and proposed patches are untrusted inputs. Independent validators run with their own immutable test definitions and authority. A score can inform selection without granting permission to change a policy or publish an artifact.

## 5. Identity and the two graphs

Use distinct identifiers for the mission, logical agent family, agent instance, execution branch, attempt, checkpoint, operation, evaluation and artifact. A launch generation identifies one live runtime incarnation; it is not the checkpoint format version or the mission identity.

Execution ancestry is a forest of immutable checkpoints with branches originating from one execution parent. A branch can produce another checkpoint and grandchildren. A rewind is represented as a new attempt from an earlier checkpoint, not erasing or rewriting the intervening history.

Knowledge and artifact provenance form separate DAGs. A new continuation may read evidence from multiple siblings without claiming multiple physical execution parents. Combining two patches creates a new artifact with explicit inputs and validation; it does not invent a merge of their VM memories.

Every authenticated mutation carries the caller's mission, branch and live generation, an operation ID, an expected resource version and a payload digest. Reusing an operation ID with the same payload returns the recorded operation; a different payload is a conflict. Authorization uses the current ledger and policy, never a guest-restored counter or a snapshot's old credentials.

Children inherit the permitted task context and the requested knowledge view, but receive fresh live identities and leases. They cannot impersonate the source, control a sibling by knowing its ID, or acquire more privileges from an old checkpoint. An old attempt may submit late evidence through an explicitly allowed ingestion path, labeled as late; it cannot regain runtime control.

## 6. Capabilities describe semantics, not names

A single `supports_snapshot: true` is insufficient. The proposed adapter reports a capability vector with supported operations, consistency guarantees, capture scope, compatibility constraints and relevant limits. Unknown is distinct from unsupported, and neither is admission to a capability-dependent experiment.

| Proposed field | Questions it must answer |
| --- | --- |
| `checkpoint.storage` | Stopped disk, crash-consistent or application-quiesced? Which volumes, mount types and backing chains? |
| `checkpoint.memory_devices` | Which RAM, vCPU and device state is captured consistently? What remains excluded? |
| `fork.storage_isolation` | Full copy, reflink, overlay or another private-write mechanism? Are every child's writable attachments independent? |
| `fork.memory_sharing` | Private mapping from an immutable snapshot, live-source CoW, or no sharing? |
| `checkpoint.async` | Can a result be preparing/writing? When is it durable and safe to fork? |
| `restore.compatibility` | Host architecture, CPU features, kernel, VMM/build, snapshot format, device layout and backing artifacts required. |
| `restore.identity_reset` | Which identity, transport, entropy and authorization repairs are supported before guest access is released? |
| `exec` and `observe` | Command lifecycle, reconnect behavior, signals, streams and independent host observations actually exposed. |
| `nested_virtualization` | Allowed, required or unavailable, including whether active nested state can be captured. |

Convenient experimental stages are cold reconstruction, stopped-storage branching, full VM-state restore, and warm/live branching. They are not a universal total order: one backend can support a memory mechanism while lacking the necessary writable-volume isolation or application quiescing.

A cold restart must return `mode: cold` and its capture scope, even if it was requested as a fallback. Explicit opt-in is required for a downgrade. KSM may reduce duplicate physical pages, but is a deduplication mechanism, not a checkpoint, replay guarantee or replacement for a memory-fork contract [K1].

### Source-pinned candidate matrix

Inspection date: 2026-09-11. This table distinguishes inspected documentation/configuration from runtime qualification. **No VM, memory-sharing benchmark or security acceptance test was executed for this draft.**

| Candidate and inspected revision | Evidence available here | What remains proposed or unqualified |
| --- | --- | --- |
| Workestrate `migration/tool-model` at `09e63162e856541f59fe011c24864bc3845a6ebc` | README describes a generic workload orchestrator; `flake.lock` pins `rybskiworks/microsandbox` to `8ae14c22963c0680b231f61280f43db364693a5c` and `libkrunfw` to `3017d504988971bd84dcc5935c96aa4a81227d1e` [W1][W2]. | This inspection is not a source audit of the full runtime or its libkrun dependency chain. Generic checkpoint/fork capability reporting and the Yggdrasil adapter are proposals, not established current APIs. |
| Microsandbox/libkrun path selected by that pin | The consumer's actual selected fork revision is known from its lockfile [W2]. | Storage and warm-memory fork semantics, guest preparation, exported operations and nested-state capture need source inspection and conformance tests at the complete dependency pins. A fork in Git is not evidence of runtime VM forking. |
| Clone, `unixshells/clone` master at `a9525154846e709bd46a7aeb64ceb1fb43547ee2` | Pinned README documents snapshot/fork, private snapshot memory mappings, guest identity injection and exec. Its status section also says persistent qcow2 per-fork disk overlay needs work [C1]. | The snapshot commands alone do not establish coordinated persistent-disk rollback, all-device coverage or safe application identity renewal. Qualify the exact disk/guest path before using it as a resettable world. No headline performance/security claim is adopted here. |
| forkd, `deeplethe/forkd` dev at `07a1ffb1543c0f7e12719064c881ae769cf4dcec` | Pinned README documents Firecracker-based snapshot memory CoW and v0.4 live branching, including asynchronous writing/ready behavior and a modified Firecracker/userfaultfd setup [F1]. | Prove rootfs/volume capture, API/CLI composition, branch readiness, crash recovery and identity repair in the chosen mode. The older v0.2 design at the same revision says volume bindings inherit and contains historical non-goals; it is not a current capability oracle [F2]. |

These are candidates, not a winner selection. The first implementation can use an owned stopped-image copy adapter with no warm-fork claim. Clone and forkd become optimization or richer-state candidates only after their adapters satisfy the same observable contract. Benchmark publications are leads for experiments, not portable latency or density promises.

## 7. Checkpoint manifest and capture protocol

A checkpoint is an immutable manifest plus reachable captured artifacts, not just an opaque file path. Separate the immutable content from the ledger's mutable preparation, availability and retention status.

An illustrative manifest, not an implemented schema:

```json
{
  "schema_version": 1,
  "checkpoint_id": "cp-0007",
  "execution_parent": "cp-0002",
  "mission_id": "mission-demo",
  "source_attempt": "attempt-0011",
  "source_generation": 4,
  "source_pins": {"repository_revision": "example-revision", "config_digest": "example-digest"},
  "runtime": {"adapter": "stopped-image-copy", "adapter_revision": "example-revision"},
  "capture": {
    "consistency": "stopped-disks",
    "volumes": [{"name": "world", "artifact": "artifact-world-7", "private_writes_required": true}],
    "memory_devices": null,
    "excluded": ["remote-model-state", "external-services", "supervisory-ledger"]
  },
  "dependencies": {"image_base": "image-3", "store_generation": "store-42"},
  "continuation_ref": "continuation-11",
  "knowledge_view_at_capture": "knowledge-view-19",
  "effect_watermark": "effect-ledger-31"
}
```

Real fields need canonical encoding, content digests, ownership and schema validation. Manifest references are not authorization tokens. The knowledge view at capture records history; a new continuation may explicitly request a later eligible view. The effect watermark records what was known, not a promise that E can return to that point.

The proposed capture protocol is:

1. Authenticate, validate the expected generation and capability requirements, reserve space, establish retention references and record a durable preparing operation.
2. Reach the declared barrier. Drain or record in-flight tools; quiesce/stop the application and all captured writable resources as required. Pausing vCPUs alone is not a claim of application consistency or frozen external mounts.
3. Capture all resources in the declared consistency group. Partial disk-plus-memory combinations never become ready checkpoints. Detect unsupported mounts/devices before admitting the operation where possible.
4. Verify the artifact inventory and integrity, persist the manifest and required dependencies, then atomically publish readiness in the authoritative registry.
5. Resume the source where requested and record its outcome independently. A valid checkpoint can coexist with a source that failed to resume.

Suggested states are `preparing -> ready`, `preparing -> failed`, `ready -> retiring -> collected`, with `quarantined` for corrupted or untrusted artifacts. Asynchronous creation returns an operation handle. A writing/preparing checkpoint cannot be restored just because its ID or memory file exists.

Durability acknowledgements name their scope: controller-process recovery, host-reboot recovery with durable storage, or explicitly replicated storage. Host disk loss is not covered by a local fsync. A partial capture can leave the source paused or unknown; recovery queries the backend rather than claiming it is still running because a timeout occurred.

## 8. Agent-facing tools and continuation semantics

All names below are proposed. The protocol could be exposed through typed tools, a local API or an existing harness adapter. These are not commands to run against today's Workestrate.

| Tool | Intent and important result |
| --- | --- |
| `world.inspect` | Read the caller's branch, capabilities, checkpoints, effects, budget and operation status. |
| `world.checkpoint` | Request a capture with explicit scope/consistency; return an operation and later a ready checkpoint. |
| `world.fork` | Spawn bounded child continuations from a ready checkpoint with hypotheses, authority subsets and knowledge views. Return child handles and granted budgets. |
| `world.rewind` | Fence/end the current attempt as requested and start a fresh incarnation at an earlier checkpoint, with an explicit retained-knowledge view. |
| `world.wait` / `world.cancel` | Observe or cancel owned operations/children; cancellation is a request with an eventual terminal outcome, not retroactive undo. |
| `knowledge.publish` / `knowledge.query` | Append candidate evidence and retrieve an identified, scope-filtered view. Publication is not automatic endorsement. |
| `evaluation.request` | Run a named, versioned validator against a specified immutable candidate or branch generation. |
| `artifact.propose` | Export a narrow candidate with ancestry, expected target base and validation evidence. |
| `branch.discard` | End a branch and release execution retention according to policy, without automatically deleting useful evidence. |

An agent may decide where to checkpoint, how many alternatives are worth trying, which hypotheses to allocate, when to ask siblings for evidence and when to stop. A parent can delegate bounded branching authority to a child. The supervisor may impose global depth/concurrency limits, but cannot replenish a child's exhausted budget by accepting its rewind.

A fork copies an explicit A baseline, not an unspecified live mind. Each child receives its own identity, branch brief, permitted tools, remaining grant, world description and selected K view. The source can continue, wait or suspend. Child responses are branch events with evidence references, not uncontrolled writes into the parent's conversation.

Rewind is particularly easy to implement incorrectly: replaying the old conversation up to the checkpoint can simply cause the same tool call again. The new continuation therefore receives an explicit resume envelope: which attempt ended, which world state was restored, which operation caused it, which lessons were retained, and which external effects still stand. The old generation is fenced. The envelope does not depend on the discarded guest remembering that it asked to rewind.

A restored in-guest agent must complete a generation/identity handshake before receiving privileged tools or egress. A paused process may contain stale tokens or old connection state; an outer identity rename does not sanitize its memory. The safer first design brokers secrets outside the captured world and starts a clean agent continuation outside the restored target.

## 9. Retained and shared knowledge

Use at least three scopes: branch-local scratch work, mission-shared candidate evidence, and promoted reusable knowledge. A successful runtime branch does not automatically promote its statements to the last scope. A failed runtime branch can contribute evidence without being preserved as a running VM.

A knowledge record should name the producing attempt and operation, observation versus interpretation, artifact/test references, applicable source/image/config/policy/input versions, causal preconditions, trust classification, visibility, and contradiction or supersession links. Model confidence can be recorded, but independent verification status must be separate.

For example, "the migration loses a row under fixture F at source revision R when interrupted after step 2" is an observation with conditions. "All migrations lose rows" is not a valid consolidation of it. A sibling's result after altering its schema is not evidence about the untouched ancestor unless that dependence is made explicit.

Append records with idempotent IDs and durable acknowledgements. Preserve raw evidence references and emit revised summaries rather than silently replacing the past. A later retraction changes current retrieval eligibility; it does not pretend that earlier agents never read the claim. Sensitive data must be redacted or access-controlled before sharing, with a retention/deletion mechanism outside ordinary workload rewind.

For comparable experiments, pin a knowledge view at each decision boundary and record its digest or sequence cut. For adaptive collaboration, allow explicit polling or notifications that create a new view. Siblings must not see silently changing shared context and then be described as independent samples. If a knowledge service is unavailable, continue only under a declared branch-local mode, or stop; never claim a publish is durable before acknowledgement.

Treat branch findings as untrusted data, including adversarial text produced by the target. Constrain ingestion size and cost. Validate applicability at query time, retain contradictions, avoid counting repeated copies of one observation as independent confirmations, and isolate tenants/missions. A vector similarity result or Git merge is not semantic validation. These mechanisms need a dedicated evaluation set and continue in #10.

## 10. Reversibility and external effects

Classify effects before allowing the experiment to execute them.

| Class | Example | Proposed handling |
| --- | --- | --- |
| Captured local state | Files and database entirely on captured private disks. | Reset with the declared consistency contract; validate restoration. |
| Owned simulated service | Fake payment endpoint or mail sink within the test world. | Capture/reset together or use a coordinated fixture protocol. |
| Read-only external interaction | Package download, model call, remote read. | Record inputs/results and real cost; acknowledge time dependence, data disclosure and rate limits. |
| External mutation | Git push, message, remote deployment, persistent remote database write. | Default deny during exploration; explicit effect/publication broker and current authorization. |

A network call that looks read-only can still consume money, leak data or modify provider-side logs. Its cost and authorization belong in L. Rewinding S does not issue a refund or remove that disclosure.

The effect broker records a durable intent before dispatch, uses a service-supported idempotency key where available, and records the external receipt. If dispatch may have succeeded but no receipt is available, the operation is `outcome_unknown`. Query the service or reconcile explicitly; do not blindly retry a non-idempotent action or claim exactly-once behavior across an arbitrary service boundary.

An effect barrier is a point after which prior checkpoints cannot be described as returning the whole mission to its old world. It can block rewind, or permit a local rewind with an explicit diverged-E warning and restricted continuation. The policy must choose; silently ignoring the barrier is invalid. Compensation is a new external action, not erasing the original effect.

No agent-controlled snapshot can restore a revoked grant, roll back a consumed budget, or modify the ledger to hide a publication. An agent can propose exporting results, but whether publication requires human review, a deterministic gate or a preapproved narrow grant belongs to the mission owner.

## 11. Promotion is a new generation, not arbitrary merge

Distinguish four operations commonly hidden behind "keep the winner":

**Select a continuation:** choose a branch to explore next. This is search policy and need not publish anything.

**Seal an execution result:** quiesce/capture a branch into a new immutable checkpoint. Change a named mission head using compare-and-swap against its expected old version. Existing siblings keep their original immutable dependencies.

**Promote an artifact:** export a patch, dataset or configuration against an explicit base. Apply it to a clean target generation, run independent validation and request authorized publication. A target-base mismatch requires reapplication and revalidation, not rewriting the declared ancestry.

**Promote knowledge:** consolidate evidence into a wider knowledge scope using a separate policy, with provenance and a retraction path.

There is no proposed operation that generically three-way-merges divergent RAM, device state or databases. Combining complementary ideas means constructing a new branch with explicit input artifacts and testing the combination. A passing score on one child cannot establish correctness of a different combined candidate.

Promotion records an intent, immutable candidate, validator version/result, expected target version and terminal receipt. If the head change committed but the caller lost the response, operation lookup resolves it. A crash between local acceptance and external publication is not a single atomic transaction; the effect broker records and reconciles the boundary.

## 12. Budgets, retention and recovery

Admission is controlled by a mission-wide ledger outside S and A. Limits can include total tokens/cost, CPU time, live RAM, concurrency, branch depth, number of checkpoints, snapshot bytes, retained evidence and wall-clock deadline. Per-branch grants reserve from this envelope; recursive children spend from delegated capacity, not new unlimited accounts.

Reserve resources before creating children, reconcile actual usage, and release reservations only when terminal state is known. A lost response is not evidence that no VM was created. Memory CoW is an optimization, not permission to ignore worst-case divergence; dirty pages and storage layers can consume real capacity later. Limits require enforceable host/runtime mechanisms where advertised, not just an agent's promise.

Checkpoint reachability includes base images, Nix store generations, writable layers, memory snapshots, continuations and evidence needed for retained provenance. Runtime-layer GC, Nix-store GC and knowledge retention have separate responsibilities. Pin dependencies before a checkpoint becomes visible and before a restore can race their collection.

A proposed two-phase collector first marks an eligible object retiring under a versioned lease/reference check, then removes its artifacts and records completion. A concurrent restore must acquire a valid reference or fail cleanly, never use partly deleted backing state. Interrupted collection resumes from durable intents. Shared backing data cannot be deleted merely because one child was discarded. Retain an evidence tombstone when policy removes bulky execution state.

| Failure | Required observable behavior in the draft |
| --- | --- |
| Controller dies after backend creation, before response | Reconcile by operation/branch/generation identity; attach to the existing operation or clean a confirmed orphan. Avoid duplicate children. |
| Capture runs out of disk | No ready partial checkpoint. Report source state separately, clean or quarantine partial artifacts, account for reserved space. |
| Snapshot succeeds but source resume fails | Preserve the valid checkpoint and expose the source failure as a separate outcome. |
| Stale request arrives after rewind | Reject runtime mutation using the ledger's current generation, even if the guest believes it is current. |
| Source checkpoint is incompatible or corrupt | Reject/quarantine before releasing guest authority; no automatic downgrade to an unrequested cold state. |
| Knowledge service fails | Bound any local spool and expose its unacknowledged status; no false durable/shared-memory acknowledgement. |
| Rewind races revocation or deadline | Current authority and real deadline win; restored state does not reopen the grant. |
| Pruning races fork/restore | Leases/references keep dependencies alive, or the admission fails before launch. |
| Promotion response is lost | Query durable operation/head state; do not publish a second artifact blindly. |
| Host or storage is lost | Report the actual acknowledged durability class and missing artifacts; do not invent recoverability. |

## 13. Observable properties and negative controls

These are proposed acceptance properties, not claims of an existing proof. Safety should hold even for a malicious or confused agent. Liveness is conditional on an available backend, remaining budget, fair scheduling and the chosen durability model.

| Property | Independent observation or negative control |
| --- | --- |
| Private branch mutation never changes an ancestor or sibling. | Place distinct canaries in captured volumes, mutate one branch, compare sibling and sealed-parent hashes. Deliberately share a writable layer to prove the test detects it. |
| Restore matches its declared scope, not a stronger imaginary one. | Verify app fixture identity and captured data; for live-state tiers also verify memory/process/device continuity. Fail a live-state test if a cold restart is substituted. |
| Revocation, budgets and effects cannot be rewound. | Revoke a grant and exhaust a token reservation after a checkpoint, then restore and submit an old operation. |
| Knowledge survives only with provenance and eligibility. | Retain a failed-branch finding, change its precondition in a sibling, and verify it is marked inapplicable rather than silently treated as truth. |
| Operations and publication are idempotent within their stated contracts. | Lose responses at controlled boundaries, retry the same ID, and count real children/effects using a separate observer. |
| No ready checkpoint references incomplete or collected state. | Inject crashes across preparation/publication/collection and inspect the artifact registry independently. |
| A promoted artifact is the artifact that was validated. | Change the candidate or target base between scoring and promotion; require a digest/version conflict and revalidation. |
| Cancellation terminates or reports an unresolved state within a bound. | Interrupt a child during capture/exec; verify backend processes and resource reservations, not only a green harness log. |

Also test prompt injection in target output, malicious knowledge records, duplicated evidence, resource exhaustion and denied cross-mission access. The harness must rediscover deliberately introduced defects before a clean run is credible. The broader independent-oracle and negative-control philosophy is developed in [Workestrate testing](workestrate-testing-philosophy.md).

A trace should preserve operations, public actions, concise decision summaries, knowledge-view IDs, pins, generations, effect receipts, validator results, artifacts and resource use. It need not expose private model chain-of-thought to be useful or reproducible. Exact replay requires control of nondeterminism; otherwise report a reproducible setup and recorded history, not deterministic execution.

## 14. Worked example: two rounds, one useful failure

Consider an intentionally seeded failure in a local application migration, with synthetic records and all application state on one captured disk. The desired property is that interrupted migration never loses accepted records. A separate validator owns the expected fixture and restart/interruption tests. This is a hypothetical experiment, not a reported result.

```text
cp0: stopped pristine application + synthetic dataset, continuation A0
 |
 +-- attempt a: hypothesis "transaction boundary is wrong"
 |      changes migration -> ordinary tests pass
 |      interruption probe fails -> evidence e1
 |
 +-- attempt b: hypothesis "startup retry is wrong"
        changes retry -> duplicate application observed -> evidence e2

cp0 + knowledge view containing e1 and e2
 |
 +-- attempt c: agent combines scoped lessons into a new hypothesis
        introduces candidate fix -> independent probes pass
        seals cp1, still unpublished
         |
         +-- attempt d: tests a second interruption location -> failure e3
         |
         +-- attempt e: tests a different input shape -> passes

cp1 + eligible view containing e3
 |
 +-- attempt f: revised candidate -> clean-base validation
        -> artifact proposal, explicit promotion/publication gate
```

Neither c nor f inherits a sibling's mutated database. The agent asks to revisit a checkpoint, supplies the lessons to retain and chooses its next hypothesis. The harness supplies fresh attempt identity, the declared world state and a recorded knowledge view.

The failure e3 is retained with the interruption location and candidate revision. It does not invalidate all possible solutions or count as evidence against the original source without qualification. The mission history shows why f exists, which failed attempts informed it, which tests selected it and the total cost of every discarded attempt.

Selecting f does not alter cp0 or cp1 beneath other branches. Publishing its patch requires a clean application to the intended source base and independent validation. The hypothetical pass in the diagram is not evidence that the actual implementation satisfies the property.

## 15. Smallest useful experiment

Start with one host-side agent harness, one ledger/knowledge directory outside the target, one disposable Linux VM and one private application disk. Networking is denied except for an explicitly brokered model endpoint outside the target's reset domain. Use synthetic data, a fixed seeded defect and an independent validator.

Shut down the VM, confirm its process is stopped and capture the owned disk and pinned configuration. For the first prototype, an ordinary full copy is acceptable: it avoids assuming reflink, snapshot or warm-fork support. Start each attempt from a fresh private copy. Name the guarantee `stopped-disks/cold`, not process continuation. Require all meaningful application state to be on that disk, with no writable host mounts or uncontrolled external services.

Give the agent a small fixed mission envelope, for example four attempts, depth two, one live target at a time and explicit token/disk/deadline limits. These are experimental parameters, not recommended universal defaults. The agent must choose at least one checkpoint/rewind itself, publish a useful failed-attempt observation, retrieve it after the reset and produce a candidate that the independent validator can accept or reject.

Success requires more than a plausible final explanation: the restored fixture matches its expected state; an acknowledged lesson survives the reset; the new attempt has a fresh identity; prior cost remains charged; unauthorized external effects remain denied; and the exported artifact passes the unchanged validator on a clean base. A deliberately shared writable-disk negative control must fail isolation. A deliberate ledger rewind must fail the budget/revocation checks.

Run a bounded comparison with the same task fixtures and cost accounting: sequential reset without retained K, sequential reset with K, and then optional bounded parallel forks with K. Record trial count, model identifier/provider configuration, task and fixture revisions, budget, success criterion and uncertainty. Do not hide failures or report only the best branch. Separate wall-clock speedup from better success per token/cost; shared information makes sibling samples correlated.

Only after this semantic loop works should an adapter replace full copies with storage CoW, then consider full VM-state or warm forks. Measure pause time, ready-to-exec time, snapshot size, peak and steady host memory, dirty-page divergence, backing-state retention and restore correctness separately. RSS sums alone can misrepresent shared memory; record an appropriate host accounting method. Do not trade away branch isolation to achieve a density target.

This draft proposes the experiment. It does not contain a runnable prototype, experimental data or a claim that Clone/forkd has passed it.

## 16. Richer application worlds and hypervisor laboratories

A multi-service application needs a consistency group covering its databases, queues, clocks and inter-service state. Coordinated stop/capture may be a practical first method. A snapshot of one VM is not a distributed checkpoint of every peer; outstanding connections and shared writable volumes are explicit exclusions unless handled.

For an authorized hypervisor-security investigation, do not place the authoritative harness and only evidence store inside the hypervisor being tested. A candidate arrangement is an independent outer controller/observer, a disposable test host or L1 VM running the hypervisor under test, and L2 guest fixtures. Credentials, management interfaces and retained evidence belong outside the SUT's authority.

Nested virtualization availability and checkpointing of active nested virtualization are different capabilities. Do not assume that snapshotting an L1 VM can safely preserve its running L2 VMs. Begin by shutting down the inner SUT and rebuilding its fixtures, or use separately resettable lab hardware. Qualify active nested-state restore only through explicit backend support and independent experiments.

A guest escape or compromised VMM can invalidate the integrity of evidence collected solely through that VMM. Keep an out-of-band observer, quarantine untrusted snapshots and exported artifacts, constrain the lab's network and device access, and use a clean restore path. A reset is not proof that a host compromise or external effect has been undone. This is an authorized-laboratory architecture, not an exploit procedure or permission to test unrelated systems.

The same distinction matters for recursive Workestrate development: testing its lifecycle through a narrow development bridge need not give a workload unrestricted host control. Record which observations come from the outer runtime, and keep generic runtime capability work separate from Yggdrasil's search decisions. The detailed laboratory boundary belongs in #9.

## 17. Decisions left open and ownership

The strongest initial recommendation is the asymmetric state model and a storage-first semantic experiment. The backend, memory product and exploration algorithm remain open.

| Decision | Alternatives and next evidence | Likely owning layer |
| --- | --- | --- |
| Agent placement | External continuation controller first; in-guest agent with external continuity later. Test stale-session and recovery behavior. | Yggdrasil harness and its adapter. |
| Knowledge persistence | Append-only local evidence plus materialized views; shared service; Git-backed consolidation. Compare acknowledgement, scope, contradiction and poisoning behavior. | Knowledge integration, #10. |
| Search policy | Sequential agent-directed retry; adaptive branching; population search; independent judge. Compare success per budget, not rhetoric. | Yggdrasil policy. |
| Capture implementation | Stopped owned image copy; filesystem CoW; Clone; forkd; extended Microsandbox backend. Qualify exact resource capture and failure semantics. | Generic runtime adapter, #7. |
| Consistency groups | Stop all owned resources; application-specific barrier; richer coordinated snapshot protocol. Test multi-volume interruption. | Runtime plus workload-specific hooks. |
| Promotion authorization | Human review, deterministic release gate, or narrow preapproved effect. Define target/version/receipt contract first. | Mission owner and effect broker. |
| Retention and replication | Local durability first; remote evidence/artifact replication later. Measure GC races and acknowledged-loss boundaries. | Storage/ledger, #8. |

Follow-on documents should include a Yggdrasil SPEC for state, tools and operations; an ADR for continuation placement and the first capture adapter; an ADR for knowledge-view/retention semantics; a threat model for authority and external effects; and a small experiment PRD with measurable acceptance and stop criteria. Runtime API changes belong in the implementing runtime repository. Sketchbook retains the exploration and links to those decisions instead of claiming it accepted them.

The [shared-store exploration](shared-nix-store-microvm-fabric.md) supplies related questions about immutable generations and private mutable state. The [workstation exploration](compartmentalized-nixos-architecture-seed.md) is a possible independent consumer, not Yggdrasil's purpose or a redefinition of Workestrate.

## 18. References and evidence limits

The pinned sources below are a starting evidence set. Source claims are not independent benchmark results or conformance certification. This draft inspected selected repository documentation and Workestrate's lockfile; it did not audit complete VMM implementations, verify all transitive pins, run a microVM or assess production safety.

[W1]: https://github.com/rybskiworks/workestrate/blob/09e63162e856541f59fe011c24864bc3845a6ebc/README.md
[W2]: https://github.com/rybskiworks/workestrate/blob/09e63162e856541f59fe011c24864bc3845a6ebc/flake.lock
[C1]: https://github.com/unixshells/clone/blob/a9525154846e709bd46a7aeb64ceb1fb43547ee2/README.md
[F1]: https://github.com/deeplethe/forkd/blob/07a1ffb1543c0f7e12719064c881ae769cf4dcec/README.md
[F2]: https://github.com/deeplethe/forkd/blob/07a1ffb1543c0f7e12719064c881ae769cf4dcec/docs/design/branching.md
[K1]: https://docs.kernel.org/admin-guide/mm/ksm.html

- [W1: Workestrate positioning and documented baseline][W1], inspected on `migration/tool-model` at the pinned revision, not assumed from `main`.
- [W2: Workestrate's actual selected dependency pins][W2], particularly `microsandbox-fork` and `libkrunfw`.
- [C1: Clone's documented snapshot/fork model and explicit status limitations][C1], including the distinction between advertised overlay operation and unfinished persistent per-fork disk overlay.
- [F1: forkd's current pinned README][F1], including asynchronous live-branch prerequisites and mode-specific integration caveats.
- [F2: forkd's older branching design][F2], useful for historical protocol questions but not a substitute for the newer implementation or current-mode tests.
- [K1: Linux kernel KSM documentation][K1], a primary explanation of deduplication, distinct from temporal checkpoint semantics.
