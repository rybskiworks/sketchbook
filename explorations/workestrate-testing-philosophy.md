# Testing Workestrate as a Stateful System

## Properties, black-box exploration, fault injection, replay, and a path toward a Workestrate-native testing platform

> **Status:** architecture exploration / testing doctrine proposal  
> **Date:** 2026-09-11  
> **Scope:** reusable testing philosophy and practices for Workestrate. This is intentionally not an Antithesis product integration plan.  
> **Primary influences:** Antithesis, FoundationDB simulation, Jepsen-style opaque-box checking, property-based/state-machine testing, and Workestrate's existing Rust/property-testing work.

---

## Executive recommendation

Workestrate should adopt a large part of the *testing philosophy* behind Antithesis without making Antithesis, its SDK, its container model, or a deterministic hypervisor a prerequisite.

The central idea is:

> Treat Workestrate as a stateful system whose correctness is described by durable properties, then autonomously generate and compose operations, concurrency, failures, and recovery paths against the real public Workestrate boundary while an independent model and set of observers continuously check those properties.

That suggests a testing stack with several complementary layers:

1. **Pure property tests** for configuration, plans, state transitions, parsers, authorization, ownership logic, protocol types, and other deterministic pieces.
2. **Model-based/state-machine tests** for lifecycle and control-plane logic, where generated actions are applied to both a small reference model and the implementation.
3. **Backend conformance tests** for the internal backend contract and capability declarations.
4. **Opaque-box real-VM tests** that drive Workestrate only through its public CLI/API/control surface and observe real host/guest effects.
5. **Generated concurrent scenarios** composed from small typed actions instead of handwritten monolithic E2E scripts.
6. **Fault campaigns** in which failures are first-class generated inputs, constrained by backend and host capabilities.
7. **Recovery and final-state checks** that deliberately distinguish "the system eventually recovers" from "the final state is exactly correct."
8. **Replay and minimization** so every autonomous failure becomes a small, durable regression case rather than an irreproducible anecdote.
9. **Harness self-testing** with known bugs, negative controls, and mutation testing, because a testing system that cannot rediscover intentionally seeded defects should not be trusted simply because it reports green.
10. **Eventually, feedback-guided branching exploration** that can exploit Workestrate backend snapshot/fork/CoW capabilities when available, moving closer to the useful parts of Antithesis's multiverse model without requiring that capability on day one.

The most important architectural choice is that the **main E2E correctness harness should live outside the Workestrate process it is testing**. It can be shipped in the same repository and share schemas/types where appropriate, but its authoritative observations should come from public behavior and independent probes. Otherwise, the harness risks validating Workestrate by asking Workestrate whether Workestrate is correct.

The goal is not "more random tests." The goal is a **searchable state space with explicit correctness oracles**.

---

## 1. Why this is a particularly good fit for Workestrate

Workestrate has unusually rich system-level state and failure boundaries:

- configuration compilation and provenance,
- workload identity and launch generations,
- backend capability negotiation,
- VM creation and teardown,
- guest execution and streaming I/O,
- persistent and disposable state,
- mounts and ownership,
- control sockets and transports,
- network and egress policy,
- secret/credential custody,
- retries, cancellation, deadlines, recovery, and reconciliation,
- multiple workloads running concurrently,
- future backend diversity.

These are exactly the areas where example-based testing tends to leave gaps. A handwritten test might prove that:

```text
create -> exec -> destroy
```

works once. It says much less about:

```text
create A
create B concurrently
cancel A halfway through
kill B's guest control path
retry A
recreate B
send a stale operation from B generation 1
rotate a policy
exec both
restart A
recover host-side control state
destroy both in the opposite order
```

The second sequence is not exotic. It is a composition of individually ordinary operations. Most difficult infrastructure bugs live in exactly those compositions.

Recent Workestrate work already points in the right direction. For example, PR #25 reports 256-case lifecycle/permission properties and several explicit recovery/fencing regressions, while also correctly stating that those tests are not real-VM, multi-workload, or resident-agent acceptance. PR #21 describes compiled negative controls that intentionally remove important timeout/expiry guards and must cause the tests to fail. Those are good instincts. The missing piece is to generalize them into a systematic whole-system exploration framework.

References:

- Workestrate testing baseline: https://github.com/rybskiworks/workestrate/blob/main/docs/testing.md
- Existing Workestrate PBT corpus: https://github.com/rybskiworks/workestrate/tree/main/docs/testing/property-based-testing
- Stateful PBT reference already in Workestrate: https://github.com/rybskiworks/workestrate/blob/main/docs/testing/property-based-testing/rust/proptest-state-machine.md
- Workestrate PR #25: https://github.com/rybskiworks/workestrate/pull/25
- Workestrate PR #21: https://github.com/rybskiworks/workestrate/pull/21

---

# 2. The reusable Antithesis philosophy

Antithesis is useful here less as a product to copy and more as a concentrated set of testing ideas.

The important reusable ideas are below.

## 2.1 Start with a workload, then deepen the oracle

Antithesis's "Writing tests" guidance starts with a driver/workload that actually exercises the software. Assertions, coverage guidance, and tuned faults are layered on afterward.

That is a useful ordering for Workestrate:

1. make the test harness capable of driving real Workestrate operations,
2. make those operations composable and repeatable,
3. add explicit system properties,
4. add fault dimensions,
5. add search guidance and coverage feedback.

This avoids a common failure mode where a very sophisticated test framework exists before it can perform enough realistic work to find anything.

Reference: https://antithesis.com/docs/product/writing_tests/

## 2.2 Prefer small compatible commands over giant scenarios

Antithesis test templates are collections of compatible commands. The platform composes them in different orders, parallelism levels, and fault conditions. Their documentation explicitly points out that more granular commands give the search system more steering choices.

For Workestrate, this suggests defining a typed vocabulary such as:

```text
ValidateConfig
Plan
Create
EnsureRunning
Exec
SendStdin
SignalExec
Stop
Restart
Recreate
Destroy
Reconcile
RotatePolicy
CancelOperation
ProbeGuest
ProbeHostState
```

A conventional E2E suite can still express a fixed scenario by listing commands. The autonomous harness can instead generate thousands of valid compositions from the same vocabulary.

This is far more reusable than having separate scripts named after specific historical bugs.

References:

- https://antithesis.com/docs/product/writing_tests/test_templates/
- https://antithesis.com/docs/product/writing_tests/test_templates/first_test/
- https://antithesis.com/docs/product/writing_tests/test_templates/test_composer_reference/
- Example implementation: https://github.com/antithesishq/etcd-test-composer

## 2.3 Separate correctness properties from test-adequacy properties

One of the most valuable Antithesis concepts is the distinction between assertions such as:

- **always:** a bad encounter disproves a guarantee,
- **sometimes:** a good encounter proves that a state/path was actually reached,
- **reachable/unreachable:** whether a code or scenario location was exercised at all.

This should become a first-class Workestrate concept, even if the syntax is different.

A correctness assertion might be:

```text
ALWAYS: a stale launch handle cannot affect a newer launch generation.
```

A test-adequacy assertion might be:

```text
SOMETIMES: a stale launch operation was actually attempted and rejected.
```

If the first passes but the second never occurs, confidence should be low. The suite may simply never have tested the interesting state.

This is much more informative than code coverage alone.

References:

- https://antithesis.com/docs/product/writing_tests/assertions/
- https://antithesis.com/docs/best_practices/sometimes_assertions/

## 2.4 Treat safety and liveness as different species of property

The Antithesis KV property catalog is a good example of writing down whole-system guarantees before implementing workloads. It separates safety properties such as "no data corruption" from liveness such as clients eventually being able to make progress.

Workestrate needs the same separation.

Safety asks:

> Did anything happen that must never happen?

Liveness asks:

> Did something that should eventually happen fail to make progress for too long?

This prevents a system from appearing "correct" merely because it deadlocked before it could violate a safety assertion.

Reference: https://antithesis.com/docs/resources/kv_property_catalog/

Reference workload: https://github.com/antithesishq/workloads-for-kv-datastores

## 2.5 Validate during the run, not only at the end

The most informative autonomous tests continuously alternate work and validation. If correctness is checked only after teardown, transient illegal states can disappear before they are observed.

For Workestrate, many invariants should be checked after every action or at frequent barriers:

- unique ownership,
- active generation identity,
- process/socket/resource cardinality,
- mount visibility,
- credential exposure boundaries,
- state-file validity,
- backend-reported capability consistency,
- expected guest liveness.

Then use special quiet-period checks for properties that only become meaningful after faults and concurrent activity stop.

## 2.6 Distinguish recovery checks from final-state checks

Antithesis's `eventually` versus `finally` distinction is extremely reusable:

- **Recovery check:** stop injecting faults and concurrent operations, then ask whether the system converges back to a healthy state.
- **Final-state check:** only after the workload completed naturally, ask whether the final state is exactly what the completed operations imply.

For Workestrate:

```text
RECOVERY:
  After killing or pausing a guest/backend/control path and then removing the fault,
  can Workestrate reconcile to a valid declared state within the liveness bound?

FINAL:
  After every started operation completed naturally,
  are the exact expected workloads, generations, sockets, reservations,
  mounts, persistent artifacts, and owned resources present, with nothing leaked?
```

These are not interchangeable.

Reference: https://antithesis.com/docs/product/writing_tests/test_templates/test_composer_reference/

## 2.7 Make randomness structured and record the choices

Antithesis recommends structured random decisions because they are more useful to a search system than opaque random bytes.

The generic lesson is strong even outside their platform.

Prefer:

```rust
Choice::Action(Action::Restart)
Choice::Target(WorkloadId(2))
Choice::ConcurrencyWidth(3)
Choice::Fault(Fault::ControlDisconnect)
Choice::DelayClass(DelayClass::Short)
```

over:

```rust
rng.next_u64()
```

Every decision should be serializable into the run artifact. This improves:

- replay,
- minimization,
- search scoring,
- coverage accounting,
- human debugging.

Reference: https://antithesis.com/docs/reference/sdk/generate_randomness/

## 2.8 Faults are inputs, not a separate test suite

Antithesis treats network, node, clock, CPU, and other faults as dimensions of execution. Faults can overlap.

Workestrate should adopt the same mental model:

```text
scenario = action trace + schedule + fault trace + parameters
```

not:

```text
normal tests
chaos tests
```

Fault support should be capability-driven. A backend that cannot implement a particular fault primitive must report that clearly. The scenario generator can then target the intersection of supported capabilities or intentionally test that unsupported requests are rejected correctly.

Reference: https://antithesis.com/docs/product/writing_tests/controlling_faults/fault_types/

## 2.9 Optimize the test environment to reach rare states quickly

Antithesis recommends shortening production-scale timers and thresholds in test environments so rare maintenance/recovery paths occur frequently.

This is relevant to Workestrate for:

- lease/expiry windows,
- retry backoff,
- reconciliation intervals,
- rotation intervals,
- cleanup TTLs,
- stale-generation windows,
- health/recovery polling,
- failure-detection thresholds.

The rule should be:

> Change the scale, not the semantics.

A test configuration may make a 5-minute expiry occur in 500 ms, but it should execute the same state transition and policy path as production.

Reference: https://antithesis.com/docs/best_practices/optimizing/

## 2.10 Hermetic test packaging is valuable independently of Antithesis

Their setup model requires software and dependencies to be packaged into a hermetic environment. The specific Docker/Kubernetes mechanics are not relevant to Workestrate, but the philosophy is.

A Workestrate system test should be describable by immutable inputs:

- Workestrate revision,
- backend revision,
- guest/base image digest,
- workload fixture digest,
- configuration digest,
- test-harness revision,
- seed/decision trace,
- host capability report.

Nix is particularly well suited to making these inputs explicit.

Reference: https://antithesis.com/docs/setup/overview/

## 2.11 Search should preserve progress instead of repeatedly starting from zero

The small `rand-tree-search` Antithesis repository demonstrates a deeper point: naive random testing loses probability exponentially when interesting states require a long sequence of favorable decisions. A search system that remembers useful intermediate states can keep making progress.

Reference: https://github.com/antithesishq/rand-tree-search

This has an obvious long-term Workestrate analogue once backend snapshot/fork support exists:

```text
interesting state
      |
      +-- snapshot/checkpoint
             |
             +-- branch A: inject network/control fault
             +-- branch B: recreate workload
             +-- branch C: race destroy vs exec
             +-- branch D: rotate policy then retry stale operation
```

Without snapshot support, the harness can replay the prefix to reconstruct an interesting state. With cheap CoW disk/memory snapshots, it can fork directly from the state and explore much more efficiently.

This is where Workestrate's virtualization layer can eventually become a genuine testing advantage, not merely something being tested.

## 2.12 Determinism is enormously useful, but it can be adopted incrementally

Antithesis and FoundationDB demonstrate the debugging value of deterministic execution and replay. FoundationDB's simulation runs whole logical clusters deterministically in a single process; Antithesis takes the alternate route of controlling regular software inside a deterministic hypervisor.

Workestrate does not need to solve full deterministic virtualization before getting most of the other benefits.

A practical ladder is:

```text
L0  immutable build/config/image inputs
L1  seeded structured action generation
L2  persisted decision + fault trace
L3  event/barrier-triggered fault injection
L4  injectable clocks/RNG in pure Workestrate control-plane components
L5  deterministic concurrency tests for selected Rust components
L6  deterministic network/filesystem simulation for selected subsystems
L7  backend snapshot/fork branching with replayable prefixes
L8  deterministic hypervisor execution, if eventually justified
```

Each rung improves reproducibility without making the next rung a prerequisite.

References:

- https://antithesis.com/docs/resources/deterministic_simulation_testing/
- https://antithesis.com/docs/introduction/how_antithesis_works/
- https://apple.github.io/foundationdb/testing.html
- https://apple.github.io/foundationdb/engineering.html

## 2.13 Fast branch tests plus longer continuous exploration

Antithesis recommends shorter development-cycle tests and longer nightly tests. This is generic good practice for an autonomous exploration harness because state-space search has a natural time-budget dimension.

Workestrate should have the same test *program* at multiple budgets rather than unrelated suites.

Reference: https://antithesis.com/docs/workflows/

---

# 3. Property discovery: use algebra before inventing examples

Scott Wlaschin's property-based testing article gives seven useful ways to discover properties. These map unusually well to infrastructure orchestration.

Reference: https://fsharpforfunandprofit.com/posts/property-based-testing-2/

| Property pattern | Workestrate interpretation | Example |
|---|---|---|
| Different paths, same destination | Commutativity / convergence | Starting independent workloads A then B should produce the same externally relevant state as B then A. |
| There and back again | Inverse / round trip | Create then destroy should return the owned host state to the same baseline, modulo explicitly persistent state. |
| Some things never change | Invariant | A workload may never gain ownership of another workload's mounts, sockets, credentials, or generation. |
| The more things change, the more they stay the same | Idempotence | Repeating `down`, `destroy`, or a reconciled desired state should converge without duplicate resources or new side effects. |
| Solve a smaller problem first | Decomposition | Prove the generic backend lifecycle contract against a canary workload before validating a complex coding agent. |
| Hard to prove, easy to verify | Cheap oracle | It may be hard to prove cleanup code, but easy to assert that the disposable state root contains exactly the expected files/sockets/processes afterward. |
| The test oracle | Model/differential testing | Apply the same action trace to a pure lifecycle model and the real Workestrate system, or to two backends implementing the same capability contract. |

These patterns should be part of design review. When a new Workestrate feature is proposed, ask:

1. What must always remain invariant?
2. What is the inverse operation?
3. What should be idempotent?
4. Which independent operations should commute?
5. Is there a simpler model we can run beside the implementation?
6. What evidence proves the path was actually exercised?

---

# 4. A proposed Workestrate property catalog

The Antithesis KV catalog is valuable because it starts from a small, named list of guarantees and then builds workloads that can falsify them. Workestrate should maintain a similar catalog.

Property IDs should be stable and human-readable. Reports, regression traces, and issues can then refer to the same property over time even if implementation details change.

The examples below are a starting point, not a finalized specification.

## 4.1 Safety properties

### `SAFE-OWN-001` - ownership is disjoint

A workload must never mutate, clean up, attach to, or inherit another workload's owned resources unless a declared shared-resource contract explicitly permits it.

Relevant resources include:

- VM/runtime identity,
- persistent state,
- workspace mounts,
- control sockets,
- CIDs/ports/leases,
- credential grants,
- generated artifacts.

### `SAFE-GEN-001` - stale generations have no authority

An operation scoped to launch generation `g` must never affect generation `g+1` of the same logical workload.

This should be attacked continuously by intentionally delaying and replaying old handles, acknowledgements, receipts, and control messages.

### `SAFE-ID-001` - live identities are unique

No two simultaneously live workload launches may own an identity/resource that the model declares exclusive.

### `SAFE-CLEAN-001` - cleanup is exact

Teardown removes everything owned by the target launch that is designated disposable, and removes nothing owned by another launch or designated persistent.

### `SAFE-ISO-001` - isolation policy is enforced at the real boundary

A guest must not observe or modify host paths, peer-workload resources, network destinations, or control interfaces outside its effective policy.

This property belongs in real-VM acceptance, not only plan serialization tests.

### `SAFE-SECRET-001` - credential/secret custody follows effective policy

A secret must not appear in plans, logs, guest environments, files, or egress paths where its declared binding/policy says it should not exist.

This should be checked using synthetic canary secrets, never production secrets.

### `SAFE-CAP-001` - unsupported capabilities fail explicitly

If a scenario requests a semantic capability the selected backend does not implement, Workestrate must reject or report it at the defined boundary rather than silently degrade to weaker behavior.

### `SAFE-PLAN-001` - planning is stable

Given identical immutable inputs, normalized plans and provenance digests should be identical. Reordering semantically unordered input should not change the normalized result.

### `SAFE-PERSIST-001` - persistent control state is never silently reinterpreted

After partial writes, corruption, incompatible versions, rollback, or missing components, state must either be validly recovered/migrated or fail closed. It must not be treated as clean/free authority merely because parsing failed.

### `SAFE-EXEC-001` - guest execution belongs to the exact requested launch

Stdout, stderr, stdin, signals, exit status, and cancellation must be bound to the expected workload and launch generation.

### `SAFE-PROTO-001` - malformed control input cannot gain authority

Truncated frames, oversized frames, duplicate/replayed messages, invalid identities, malformed serialized state, and out-of-order acknowledgements must fail without causing cross-launch state changes.

### `SAFE-RECON-001` - reconciliation converges without ownership bleed

A reconciler may repair declared state, but may not adopt or delete resources that it cannot prove belong to its scope.

## 4.2 Liveness properties

Liveness needs explicit bounds. "Eventually" without a bound is easy to satisfy by waiting forever.

### `LIVE-LAUNCH-001`

A valid launch on a healthy supported backend reaches its ready/running state within the configured test bound or returns a typed terminal failure.

### `LIVE-EXEC-001`

A finite guest command either completes or returns a bounded failure/cancellation. It must not become an unowned zombie operation.

### `LIVE-STOP-001`

Stop/destroy eventually releases all disposable owned resources.

### `LIVE-RECOVER-001`

After a removable fault ends, a workload whose desired state remains runnable either returns to a valid running state or reports a terminal condition requiring operator action.

### `LIVE-RETRY-001`

A retry after a transient failure does not become permanently blocked by stale locks, stale generations, stale sockets, orphan reservations, or abandoned control tasks.

### `LIVE-HARNESS-001`

The test workload itself continues to make meaningful progress often enough that safety properties are being exercised rather than "passing" behind a dead driver.

## 4.3 Metamorphic properties

Metamorphic properties are powerful when there is no single expected output.

### `META-IDEMP-001`

Applying an already-converged desired state again must not create duplicate resources or change semantics.

### `META-INVERSE-001`

Create followed by destroy returns disposable host/guest state to baseline.

### `META-COMMUTE-001`

Independent operations on workloads with disjoint resources commute in their externally visible result.

### `META-REORDER-001`

Reordering declarations that are semantically unordered does not change the effective plan.

### `META-BACKEND-001`

For capabilities shared by two backends, the same abstract action trace produces equivalent canonical observations, ignoring explicitly backend-specific metadata and timing.

### `META-RESTART-001`

Restart/recreate preserves exactly the state declared persistent and discards exactly the state declared ephemeral.

## 4.4 Test-adequacy / coverage properties

These properties say whether the harness actually reached meaningful conditions.

Examples:

```text
SOMETIMES concurrent creates overlap.
SOMETIMES an operation is cancelled while in flight.
SOMETIMES a stale generation is presented and rejected.
SOMETIMES a guest is killed during an active exec.
SOMETIMES a backend/control connection fails mid-operation.
SOMETIMES recovery succeeds after a removable fault.
SOMETIMES cleanup follows a partially completed launch.
SOMETIMES two workloads execute simultaneously.
SOMETIMES an unsupported capability path is exercised.
SOMETIMES persistent-state recovery is exercised.
```

A run that violates none of the safety properties but hits none of the difficult adequacy properties should be reported as **low exploration confidence**, not simply green.

---

# 5. The core harness architecture

The black-box harness should be structurally independent from the implementation it judges.

```text
                    +------------------------+
                    | Scenario / trace search|
                    +-----------+------------+
                                |
                          typed Action
                                |
                                v
+------------------+   +--------+---------+       +---------------------+
| Reference model  |<--| Harness executor |------>| public Workestrate   |
| expected state   |   | + barriers       |       | CLI/API/control     |
+--------+---------+   +---+------------+-+       +----------+----------+
         ^                 |            |                    |
         |                 |            |                    v
         |                 |            |             backend adapter
         |                 |            |                    |
         |                 |            |                    v
         |                 |            |                real VM(s)
         |                 |            |
         |                 |            +------ fault injector
         |                 |
         |                 +------------------- recorder
         |
         +----------- canonical observations
                           ^
                           |
                +----------+-----------+
                | independent observers|
                | host + canary guest  |
                +----------------------+
```

The system has six conceptual components.

## 5.1 Scenario generator / search engine

Produces valid action sequences based on:

- current model state,
- action preconditions,
- backend capabilities,
- desired concurrency,
- fault budget,
- exploration feedback.

Initially this can be ordinary seeded PBT. Later it can become corpus/frontier based.

## 5.2 Reference model

A deliberately smaller state machine describing *what should be true*, not how Workestrate implements it.

A simplified model might track:

```rust
struct Model {
    workloads: BTreeMap<WorkloadId, WorkloadModel>,
}

struct WorkloadModel {
    desired: DesiredState,
    live_generation: Option<Generation>,
    persistence: PersistenceExpectation,
    owned_resources: BTreeSet<ResourceKey>,
    pending_ops: BTreeMap<OperationId, ExpectedOperation>,
}
```

The model should not encode Microsandbox internals, libkrun structs, socket implementation details, or current source layout. If it does, it stops being an independent oracle.

## 5.3 Black-box executor

Drives the public product boundary.

For product-level claims, prefer:

- installed `workestrate` binary,
- stable control API,
- public config files,
- normal workload lifecycle operations.

Do not call private Rust implementation methods merely because it is convenient. Private-path tests are useful, but they belong to the lower layers.

## 5.4 Independent observers

Observers collect enough evidence to canonicalize the real state:

- CLI/API results,
- guest canary responses,
- process liveness,
- control socket existence and ownership,
- disposable state-root contents,
- declared persistent volume content,
- network reachability probes,
- synthetic credential visibility,
- backend metadata that is explicitly part of the contract.

The oracle should avoid reading internal in-memory state from the Workestrate process.

## 5.5 Fault injector

Applies a typed fault vocabulary and reports capabilities.

## 5.6 Recorder + minimizer

Records every decision and observation, then minimizes failures into durable regression traces.

---

# 6. Actions should form a grammar, not a bag of shell commands

A generated scenario should be model-aware. Actions have:

- preconditions,
- parameters,
- expected abstract state transitions,
- observable success/failure classes,
- concurrency class,
- whether they are safe during faults,
- possible shrink strategies.

For example:

```rust
enum Action {
    ValidateConfig,
    Plan { workload: WorkloadId },
    Create { workload: WorkloadId },
    Exec { workload: WorkloadId, command: CanaryCommand },
    Signal { operation: OperationId, signal: SignalKind },
    Stop { workload: WorkloadId },
    Restart { workload: WorkloadId },
    Recreate { workload: WorkloadId },
    Destroy { workload: WorkloadId },
    Reconcile,
    Cancel { operation: OperationId },
    Probe { probe: ProbeKind },
}
```

And actions can be classified as:

```rust
enum SchedulingClass {
    Parallel,
    Exclusive,
    Observation,
    RecoveryCheck,
    FinalCheck,
}
```

This mirrors the useful idea behind Antithesis test-command classes without importing their exact product convention.

A scenario is then a serializable object:

```text
step 0001  Create(A)
step 0002  Create(B) || Probe(HostOwnership)
step 0003  Exec(A, WriteEphemeralToken(17))
step 0004  Fault(KillGuest(A))
step 0005  Restart(A)
step 0006  Probe(Persistence(A))
step 0007  ReplayStaleExec(A, generation=1)
step 0008  Destroy(B) || Exec(A, Echo("alive"))
step 0009  RecoveryCheck
step 0010  Destroy(A)
step 0011  FinalCheck
```

That trace can be saved, diffed, replayed, minimized, and promoted to regression data.

---

# 7. Record a complete run manifest

A seed alone is not enough for real KVM/system testing. Host scheduling, kernel behavior, backend timing, and external process timing can change the exact execution even with the same PRNG seed.

Every run should therefore persist both the seed and the actual decisions made.

Example conceptual manifest:

```toml
schema = 1
run_id = "01J..."
seed = 1844674407
workestrate_revision = "..."
testkit_revision = "..."
config_digest = "sha256:..."
backend = "microsandbox"
backend_revision = "..."
guest_image_digest = "sha256:..."
canary_digest = "sha256:..."
host_kernel = "..."
host_arch = "x86_64"

[host_capabilities]
kvm = true
nested_virtualization = true
snapshot = false
network_faults = true

[[decision]]
index = 1
kind = "action"
value = "create"
target = "a"

[[decision]]
index = 2
kind = "fault"
value = "guest-kill"
target = "a"
trigger = "after:exec-started"
```

For exact or high-quality replay, event-relative triggers are preferable to wall-clock sleeps:

```text
bad:   sleep 137 ms, then kill VM
better: after guest exec is accepted but before completion, kill VM
```

Barriers make generated failures more reproducible even without a deterministic scheduler.

---

# 8. Fault injection should be a capability-negotiated API

A portable Workestrate test platform should define faults semantically, then let each backend/host implementation report which ones it can provide.

For example:

```rust
bitflags! {
    struct FaultCapabilities: u64 {
        const GUEST_TERMINATE       = 1 << 0;
        const GUEST_PAUSE           = 1 << 1;
        const BACKEND_TERMINATE     = 1 << 2;
        const CONTROL_DISCONNECT    = 1 << 3;
        const NETWORK_PARTITION     = 1 << 4;
        const NETWORK_DELAY         = 1 << 5;
        const DNS_FAILURE           = 1 << 6;
        const STATE_CORRUPTION      = 1 << 7;
        const DISK_QUOTA_EXHAUSTION = 1 << 8;
        const CLOCK_CONTROL         = 1 << 9;
        const CPU_THROTTLE          = 1 << 10;
        const SNAPSHOT_FORK         = 1 << 11;
    }
}
```

The initial set should favor faults that are easy to implement safely and deterministically on disposable test resources.

## 8.1 Good first fault primitives

### Controller cancellation

Cancel the caller while create/exec/destroy/reconcile is in flight.

This is cheap, backend-independent, and likely to expose resource ownership bugs.

### Guest termination

Kill the disposable guest at meaningful lifecycle barriers.

### Backend/runtime termination

Terminate the backend process or control connection while Workestrate owns an operation.

### Control transport disconnect / truncated frame

Exercise reconnect, stale receipt, retry, and timeout behavior.

### Network partition/delay for test VMs

Limit this to disposable test namespaces/interfaces. Do not alter arbitrary host networking.

### Disposable state corruption

Create partial/truncated/malformed state under an isolated test root and verify fail-closed/recovery semantics.

### Resource pressure

Use explicit cgroup/quota/test-VM limits rather than globally exhausting the development host.

## 8.2 Backend-specific faults are acceptable

Not every fault must exist on every backend.

The contract should make this explicit:

```text
scenario requires: {guest_terminate, control_disconnect}
backend A supports: yes
backend B supports: guest_terminate only

result:
  run scenario on A
  skip/rewrite B with an explicit unsupported-capability record
```

Silent weakening is the failure mode to avoid.

---

# 9. Purpose-built canary workloads are more valuable than complex apps at first

Antithesis's `glitch-grid` is intentionally a toy system with obvious invariants. The ring test and Chain of Blocks similarly use simple state so the correctness oracle is cheap and strong.

That is exactly what Workestrate needs for infrastructure validation.

Reference: https://github.com/antithesishq/glitch-grid

## 9.1 `echo-canary`

A tiny static binary that:

- reports PID/boot ID/workload-provided identity,
- echoes stdin/stdout/stderr,
- exits with requested status,
- handles signals predictably,
- can block on a barrier.

Tests:

- exec routing,
- stream separation,
- cancellation,
- signal delivery,
- stale-operation fencing,
- concurrent exec.

## 9.2 `persistence-canary`

Maintains two counters:

```text
/persistent/counter
/ephemeral/counter
```

and a rolling hash over commands.

Tests:

- restart/recreate semantics,
- correct volume attachment,
- no cross-workload volume swap,
- cleanup exactness,
- partial-write recovery.

## 9.3 `mount-canary`

Receives a set of expected readable/writable/denied paths and probes them.

Tests:

- read-only enforcement,
- traversal denial,
- path alias/symlink behavior,
- host data isolation,
- mount identity after recreate.

## 9.4 `network-canary`

A pair or small set of guests that can expose/listen/connect through explicit ports and report connection identity.

Tests:

- permitted peer communication,
- denied egress,
- DNS behavior,
- partition/recovery,
- identity after restart.

## 9.5 `credential-canary`

Uses synthetic credentials with unique random fingerprints.

Tests:

- broker-bound material never enters guest environment/files,
- guest-bound material appears only where declared,
- destination restrictions,
- stale generation cannot reuse authority,
- logs/provenance never contain raw secret material.

## 9.6 `lifecycle-chain` - inspired by Chain of Blocks

Antithesis's Chain of Blocks encodes replicated state as `(count, rolling_hash)`, making reordering, skipping, duplication, or corruption easy to detect.

Workestrate can use the same information-dense idea without pretending Workestrate is a consensus system.

For a canary workload, each successful lifecycle-visible command can evolve:

```text
state = (generation, sequence, rolling_hash)
rolling_hash[n+1] = H(rolling_hash[n], generation, command, payload)
```

The harness stores the expected sequence and polls/execs the guest to retrieve the observed digest.

This catches:

- wrong persistent volume attached,
- operation delivered to wrong generation,
- duplicate command delivery,
- lost command after a declared durable acknowledgement,
- unexpected persistence across recreation.

Reference: https://antithesis.com/docs/resources/chain-of-blocks/

## 9.7 `ownership-ring` - inspired by the ring-test principle

The database ring test succeeds because a simple global invariant survives many concurrent transformations and is cheap to verify.

A literal DB ring is not appropriate for Workestrate, but the principle is.

One possible Workestrate canary:

1. create N disposable workloads,
2. assign each a unique host-owned token/volume and expected neighbor identity,
3. perform concurrent restart/recreate/exec operations,
4. repeatedly verify:
   - exactly N unique tokens exist,
   - no token is mounted into two exclusive owners,
   - every workload observes only its expected token,
   - the ownership graph remains a single closed ring,
   - final teardown leaves exactly the declared persistent subset.

The test need not become a product feature. It is a deliberately synthetic invariant-rich workload for stressing identity, mount, lifecycle, and ownership behavior.

Reference: https://antithesis.com/docs/resources/ring_test/

---

# 10. Stateful PBT is the right lower-level model for lifecycle logic

Workestrate already contains a strong property-testing reference corpus. That should be used rather than duplicated.

The natural lifecycle testing pattern is:

```text
reference model state
        +
valid generated transition
        |
        +----> update model
        |
        +----> perform operation against SUT
                     |
                     +----> canonical observation
                                  |
                                  +----> compare/check invariants
```

For pure/semi-pure lifecycle logic, `proptest` and `proptest-state-machine` are a good fit. The important limitation is that the current Rust state-machine support is sequential. Parallel race exploration must come from a separate mechanism.

References:

- Workestrate corpus: https://github.com/rybskiworks/workestrate/tree/main/docs/testing/property-based-testing/rust
- Proptest: https://github.com/proptest-rs/proptest
- Antithesis fork: https://github.com/antithesishq/proptest

Do not force the real-VM harness *inside* a proptest macro. Instead, reuse the same concepts:

- strategies/generators,
- preconditions,
- reference model,
- shrinking,
- failure persistence.

The system-level runner will need its own asynchronous/concurrent execution and minimization machinery.

---

# 11. Concurrency testing below the VM layer

Whole-system VM tests are necessary, but they are expensive and nondeterministic. Concurrency bugs in individual Rust control-plane components can often be found much faster with scheduler-aware tools.

These tools are complementary, not replacements for E2E.

## 11.1 Loom for small concurrency-critical components

Loom explores possible schedules for code that uses Loom's modeled synchronization primitives. It is a good fit for small ownership/locking/state-machine components where exhaustive schedule exploration remains tractable.

Potential Workestrate targets:

- operation-handle ownership,
- cancellation/acknowledgement state,
- launch-generation publication,
- lock-free/shared-state components,
- small broker/reconciler concurrency primitives.

Reference: https://docs.rs/loom/latest/loom/

## 11.2 Shuttle for larger randomized schedule exploration

Shuttle trades exhaustive soundness for scalable randomized schedule control with deterministic replay of the chosen schedule.

It may fit larger async/concurrent control-plane tests where Loom's state space explodes.

Reference: https://github.com/awslabs/shuttle

## 11.3 Turmoil where subsystems can use simulated I/O

Turmoil provides deterministic simulated hosts, network behavior, filesystem behavior, partitions, crashes, latency, drops, and torn writes for Tokio-oriented systems.

It is attractive for *selected Workestrate subsystems* if their network/filesystem dependencies can be abstracted cleanly. It should not become a requirement to rewrite the entire product around a simulator.

Reference: https://github.com/tokio-rs/turmoil

---

# 12. Jepsen contributes the right black-box discipline

Jepsen's most relevant lesson is not a particular database consistency model. It is the architecture:

1. run real binaries,
2. generate concurrent operations,
3. inject failures,
4. record a history of invocation/completion,
5. feed that history to an independent checker/model.

Jepsen explicitly describes its niche as opaque-box systems testing under distributed-system faults with generated operations and history checking.

That maps almost directly onto the proposed Workestrate E2E layer.

References:

- https://jepsen.io/analyses
- https://jepsen.io/consistency/models
- https://jepsen.io/consistency/models/linearizable

Workestrate does not need to use Jepsen itself, and most Workestrate properties are not linearizability properties. The useful import is **history as evidence**.

A Workestrate history event might look like:

```json
{
  "op_id": "op-17",
  "workload": "alpha",
  "generation": 4,
  "type": "exec",
  "phase": "invoke",
  "logical_step": 83
}
```

followed later by:

```json
{
  "op_id": "op-17",
  "type": "exec",
  "phase": "complete",
  "result": "cancelled",
  "logical_step": 91
}
```

The checker can reason about concurrency from the intervals and model state instead of relying on log-text ordering.

---

# 13. Backend conformance and differential testing

Backend abstraction creates an unusual opportunity: the abstract Workestrate contract can itself become an oracle.

Two separate suites are needed.

## 13.1 Backend conformance suite

This is a focused adapter-level suite that verifies each backend honestly implements the semantics it advertises.

For every capability:

```text
capability: guest_exec
precondition: workload running
contract:
  request is launch-generation scoped
  stdout/stderr separation preserved
  exit status returned
  cancellation has bounded behavior
  stale launch rejected
```

The backend should pass the same conformance fixture or explicitly report unsupported behavior.

## 13.2 Cross-backend differential suite

For the intersection of two backends' semantic capabilities:

```text
trace T
  -> backend A
  -> canonical observation A

trace T
  -> backend B
  -> canonical observation B

assert equivalent(A, B)
```

Canonicalization must strip irrelevant backend-specific data such as:

- runtime-assigned IDs,
- exact timing,
- log formatting,
- implementation-specific process trees.

Compare contract-level facts:

- operation result class,
- guest-visible state,
- persistence,
- isolation,
- ownership,
- cleanup,
- recovery.

This becomes increasingly valuable if Workestrate supports multiple microVM/runtime backends. A new backend can be measured against the mature one using generated traces instead of only a checklist.

---

# 14. Failure minimization is not optional

A 600-step randomized failure is useful for discovery but miserable for engineering.

The harness should treat minimization as part of producing the result.

## 14.1 Trace shrinking

Given a failing action/fault trace:

1. remove contiguous chunks of steps (`ddmin` style),
2. remove individual actions,
3. remove faults,
4. reduce number of workloads,
5. reduce concurrency width,
6. shrink parameters/payloads/timeouts,
7. simplify action variants,
8. move fault triggers toward simpler barriers,
9. re-run the property after every candidate shrink.

The state-machine precondition checker rejects invalid candidates before expensive execution.

## 14.2 Preserve causality, not exact timestamps

If a failure requires:

```text
kill guest after exec accepted but before reply
```

then the minimized case should store that relation, not "kill after 83.4 ms."

## 14.3 Every minimized failure becomes a regression fixture

For example:

```text
tests/system/regressions/
  SAFE-GEN-001-stale-exec-after-recreate.toml
  SAFE-CLEAN-001-cancel-create-leaks-cid.toml
  LIVE-RETRY-001-stale-socket-blocks-retry.toml
```

Generated test failures should enrich the deterministic suite over time.

Proptest's failure persistence is the small-scale precedent for this idea.

---

# 15. Test the test system

A sophisticated autonomous harness can fail silently by never reaching useful states or by having weak oracles.

The harness needs explicit negative controls.

## 15.1 Maintain a known-bug corpus

Keep small intentionally buggy fixture implementations or historical bug revisions where safe and practical.

The harness should reliably rediscover them within a bounded budget.

Examples:

```text
mutant: ignore launch generation when dispatching exec
expected property: SAFE-GEN-001

mutant: skip one cleanup path after cancellation
expected property: SAFE-CLEAN-001

mutant: attach workload B's persistent path to workload A
expected property: SAFE-OWN-001 / META-RESTART-001

mutant: silently accept unsupported backend capability
expected property: SAFE-CAP-001

mutant: remove operation deadline
expected property: LIVE-EXEC-001
```

## 15.2 Mutation testing for ordinary Rust tests

`cargo-mutants` is useful because code coverage only proves code was executed, while mutation testing asks whether changing behavior causes a test to fail.

Reference: https://github.com/sourcefrog/cargo-mutants

It should be targeted first at correctness-critical modules rather than run indiscriminately over enormous generated/vendor trees.

## 15.3 Semantic negative controls for E2E

Source mutation alone is not enough for the black-box harness. Maintain a small set of semantic mutants or old known-bad binaries/images and score whether the E2E search discovers them.

## 15.4 Harness confidence metrics

Track at least:

- known mutants rediscovered / total,
- median search budget to rediscovery,
- replay success rate,
- minimization success rate,
- adequacy-property hit rate,
- unique abstract state/transition coverage,
- action/fault pair coverage.

This is a much stronger answer to "is the testing platform working?" than a green dashboard.

---

# 16. Coverage should mean semantic exploration first

Code coverage is useful, especially as feedback for search, but it is not the principal goal.

Workestrate should track several forms of coverage.

## 16.1 Property encounter coverage

Did each property's precondition actually occur?

## 16.2 Abstract state coverage

Which model states were reached?

Examples:

```text
Absent
Creating
Running
ExecInFlight
Stopping
FailedRecoverable
Recreating
Destroying
Recovered
```

## 16.3 Transition coverage

Which state transitions and transition pairs/triples occurred?

Rare bugs often require sequences such as:

```text
Running -> ExecInFlight -> Recreate -> stale completion
```

## 16.4 Concurrency coverage

- maximum overlapping operations,
- action pairs observed concurrently,
- same-workload vs cross-workload overlap.

## 16.5 Fault/action cross-product coverage

Did each supported fault interact with the interesting actions?

```text
fault x action
---------------------------
guest kill x exec        hit
controller cancel x create hit
control disconnect x destroy miss
```

## 16.6 Backend capability coverage

For each backend capability, do we have:

- positive path,
- negative/unsupported path,
- faulted path,
- recovery path,
- cross-backend comparison where applicable?

## 16.7 Code coverage

Use it as an additional feedback signal, especially for pure/control-plane code, not as proof of correctness.

Antithesis's search examples are a useful demonstration of why feedback can outperform naive random sampling.

References:

- https://antithesis.com/docs/product/writing_tests/instrumentation/coverage_instrumentation/
- https://github.com/antithesishq/rand-tree-search

---

# 17. A future Workestrate exploration engine

A first implementation can simply generate random valid traces. A mature implementation can become a state-space search engine.

## 17.1 Corpus/frontier model

Maintain a corpus of interesting run prefixes scored by novelty:

```text
score += new model state
score += new state transition
score += new action/fault pair
score += new property precondition
score += new code-coverage edge
score += greater lifecycle depth
score += new concurrency shape
score += proximity to unsatisfied adequacy goal
```

Select promising prefixes, mutate/extend them, and retain ones that discover new state.

## 17.2 Checkpoint provider abstraction

Add a test-only capability contract such as:

```rust
trait CheckpointProvider {
    fn checkpoint(&self, scope: ScenarioScope) -> Checkpoint;
    fn restore(&self, checkpoint: &Checkpoint) -> Result<()>;
    fn fork(&self, checkpoint: &Checkpoint, branches: usize) -> Result<Vec<Fork>>;
}
```

Backends can implement:

- no checkpointing,
- disk-only snapshots,
- VM snapshot/restore,
- disk + memory CoW fork.

The exploration engine uses whatever is available.

Without snapshots:

```text
replay prefix from clean environment -> branch
```

With snapshots:

```text
restore/fork prefix checkpoint -> branch cheaply
```

This is the natural bridge between ordinary PBT today and multiverse-like exploration later.

## 17.3 Do not make snapshot semantics part of correctness unless declared

Snapshot/fork is initially a harness optimization. The harness must be able to run its core correctness suite without it.

When Workestrate exposes snapshot/fork as a product feature, those operations receive their own explicit properties.

---

# 18. Reproducibility expectations need levels

It is important not to promise perfect replay before the underlying system can provide it.

Define replay classes:

## R0 - artifact reproducible

Same source/config/backend/image inputs are available.

## R1 - decision reproducible

Same generated actions, parameters, and fault intentions can be replayed.

## R2 - barrier reproducible

Faults/actions can be synchronized to the same semantic lifecycle events.

## R3 - schedule reproducible

Relevant thread/task/network scheduling is controlled for the subsystem under test.

## R4 - machine execution reproducible

The VM/hypervisor environment can replay effectively the same execution timeline.

The initial E2E system can target R1/R2. Pure state-machine tests and Loom/Shuttle/Turmoil components can reach R3 locally. A future deterministic hypervisor could approach R4.

This nomenclature prevents a deterministic seed from being misrepresented as deterministic execution.

---

# 19. CI and campaign tiers

The same property catalog should run at different budgets.

| Tier | Intended loop | Typical contents | VM required? |
|---|---|---|---|
| T0 | every edit / pre-push | unit, schema, serialization, pure PBT, deterministic regressions | no |
| T1 | PR | model/state-machine tests, Loom/Shuttle selected modules, backend contract with fakes | mostly no |
| T2 | PR on KVM runner | fixed-seed black-box smoke + minimized historical regressions + canary VM tests | yes |
| T3 | PR or merge queue | short generated real-VM campaign with several seeds/fault combinations | yes |
| T4 | nightly | longer autonomous exploration per supported backend | yes |
| T5 | scheduled/weekly | cross-backend differential, long fault campaigns, mutation/known-bug rediscovery, snapshot/fork exploration | yes |

The exact minutes are infrastructure-dependent. The principle is more important:

> Short tests should be a time-bounded slice of the same model/property system used by long campaigns.

This gives fast feedback without maintaining two unrelated notions of correctness.

---

# 20. What a useful failure report should contain

A generated failure should be issue-ready.

Minimum artifact set:

```text
property ID + version
one-sentence violation
expected model state
canonical observed state
minimal action trace
minimal fault trace
original run seed
actual structured decision trace
Workestrate revision
backend name + revision
image/workload digests
host capability snapshot
relevant event history
stdout/stderr/log slices
replay classification (R0-R4)
replay attempts / success rate
```

An ideal summary looks like:

```text
SAFE-GEN-001 violated

Minimal trace:
  1. Create(alpha) -> generation 1
  2. Exec(alpha, block_on_barrier) -> op 9 accepted
  3. Recreate(alpha) -> generation 2
  4. ReleaseBarrier(op 9)
  5. old op 9 wrote to generation 2 stdout stream

Reproduced: 10/10 with barrier replay
Backend: microsandbox @ <rev>
Workestrate: <rev>
```

That is much more actionable than "nightly fuzz test failed."

---

# 21. Proposed repository shape

The exact names can change, but keeping the layers explicit will help prevent the system test framework from becoming a pile of scripts.

```text
workestrate/
  crates/
    test-model/             # pure abstract lifecycle/reference model
    test-properties/        # property registry + checkers
    test-trace/             # action/fault/history/run-manifest schema
    test-canary-protocol/   # tiny protocol shared with canary binaries
    test-runner/            # black-box orchestrator, recorder, minimizer

  tests/
    system/
      scenarios/            # curated fixed traces
      regressions/          # minimized discovered failures
      mutations/            # semantic negative controls / known bug metadata
      fixtures/

  test-workloads/
    echo-canary/
    persistence-canary/
    mount-canary/
    network-canary/
    credential-canary/

  docs/
    testing/
      philosophy.md
      property-catalog.md
      trace-format.md
      backend-conformance.md
      fault-model.md
      replay.md
```

An alternative is a single `workestrate-testkit` crate at first, split only when its interfaces stabilize.

The important boundary is logical, not the initial crate count.

---

# 22. Suggested implementation sequence

## Phase 0 - write the property catalog first

Deliverables:

- stable property IDs,
- safety/liveness/adequacy taxonomy,
- definitions of observable state,
- first 10-15 properties.

Do not start with fault injection.

## Phase 1 - build a single-backend, no-fault black-box runner

Deliverables:

- one canary guest image,
- typed action trace,
- pure model,
- installed Workestrate binary execution,
- independent observation,
- run manifest,
- fixed seed and decision replay.

Initial generated actions:

```text
Create
Exec
Stop
Restart
Destroy
Probe
```

Prove:

- inverse cleanup,
- idempotence,
- exact persistence,
- ownership isolation.

## Phase 2 - add concurrency

Add:

- multiple workloads,
- overlapping exec/create/destroy,
- model-aware action preconditions,
- invocation/completion history,
- concurrency coverage.

## Phase 3 - add the first fault primitives

Start with:

- caller cancellation,
- guest kill,
- control disconnect,
- disposable state corruption,
- safe network partition/delay.

Add recovery checks distinct from final-state checks.

## Phase 4 - minimization and regression promotion

A failing random run is not considered "finished" until the harness can produce a substantially reduced trace or explicitly report why it cannot.

## Phase 5 - harness self-tests

Add:

- historical bad revisions or fixture mutants,
- semantic negative controls,
- `cargo-mutants` on critical Rust modules,
- rediscovery metrics.

## Phase 6 - backend conformance + differential execution

Run shared traces against every backend that advertises the required semantics.

## Phase 7 - feedback-guided exploration

Add:

- abstract-state coverage,
- action/fault novelty,
- corpus/frontier search,
- targeted generation toward unmet adequacy properties.

## Phase 8 - exploit snapshot/fork/CoW capabilities

Use backend checkpointing to branch from interesting states rather than replaying every prefix.

At this stage the harness begins to resemble a Workestrate-native multiverse explorer.

## Phase 9 - deeper deterministic simulation where ROI is proven

Only then decide whether to invest in:

- broader pluggable time/randomness,
- deterministic network/filesystem simulation,
- hypervisor-level determinism,
- controlled CPU/scheduler execution.

The architecture above remains useful whether or not this phase ever exists.

---

# 23. What not to copy from Antithesis

The goal is to steal the strongest general ideas, not cargo-cult their product architecture.

## 23.1 Do not require their SDK assertion API

Workestrate should have its own property/event schema. An adapter to Antithesis could exist later if useful.

## 23.2 Do not require Docker or Kubernetes

Their setup mechanics exist because that is how software is packaged into their product. Workestrate's own Nix/microVM packaging should remain native.

## 23.3 Do not make a deterministic hypervisor a prerequisite

That would postpone valuable black-box generative testing unnecessarily.

## 23.4 Do not confuse random activity with exploration

A chaos monkey that kills random processes and checks only for crashes is not enough.

Every campaign should have:

- a model or oracle,
- named properties,
- adequacy goals,
- replay artifacts,
- minimization.

## 23.5 Do not rely on end-of-run assertions only

Transient ownership/security failures can disappear by final cleanup.

## 23.6 Do not use code coverage as the correctness metric

Coverage is a search signal. Properties are the correctness contract.

## 23.7 Do not hide expected crashes/failures from the harness

If a workload is supposed to exit on a failed connection or a guest is intentionally killed, record that as an explicit expected transition. Unexpected and expected failures must remain distinguishable.

## 23.8 Do not couple the reference model to backend implementation details

If the model needs to know Microsandbox's internal task graph to decide whether Workestrate is correct, it is no longer an independent model.

---

# 24. FoundationDB lessons worth importing

FoundationDB is the other major reference point because deterministic simulation is deeply integrated into its engineering process.

The reusable lessons are:

1. **Design for failure injection.** Systems become easier to test when time, randomness, I/O, and failure boundaries are explicit.
2. **Deterministic replay has enormous debugging value.** Exact or near-exact replay converts rare concurrency failures into ordinary engineering work.
3. **Compress time.** Simulation can execute much more logical time than wall time.
4. **Use invariant-rich synthetic workloads.** FoundationDB's own testing documentation cites cycle/ring-like workloads for transactional isolation.
5. **Keep real-cluster/hardware testing too.** Simulation does not replace production-like validation.

References:

- https://apple.github.io/foundationdb/testing.html
- https://apple.github.io/foundationdb/client-testing.html
- https://apple.github.io/foundationdb/engineering.html
- https://github.com/apple/foundationdb

This is another reason for Workestrate to keep both:

```text
simulation/scheduler-aware subsystem tests
                 +
real KVM black-box acceptance
```

rather than choosing one.

---

# 25. A concise doctrine for Workestrate

If this proposal is reduced to a set of rules, they would be:

1. **Specify properties, not only examples.**
2. **Drive the real public boundary for product-level claims.**
3. **Keep the reference model simpler than the implementation.**
4. **Build scenarios from small typed actions.**
5. **Generate valid stateful sequences, not arbitrary command soup.**
6. **Treat concurrency as an input dimension.**
7. **Treat faults as an input dimension.**
8. **Check invariants continuously.**
9. **Separate safety, liveness, and adequacy.**
10. **Separate recovery checks from final-state checks.**
11. **Use synthetic canary workloads with very strong, cheap oracles.**
12. **Record decisions and semantic barriers, not just random seeds.**
13. **Minimize every discovered failure.**
14. **Promote minimized failures to permanent regressions.**
15. **Measure whether hard states were actually reached.**
16. **Test the harness with known bugs and mutants.**
17. **Make backend fault/test capabilities explicit.**
18. **Differential-test backends over their shared semantic contract.**
19. **Adopt determinism incrementally.**
20. **Exploit snapshots/CoW to preserve interesting states when backends make it cheap.**

That would make Workestrate's testing platform more than "an E2E test suite." It would be a system for *searching for counterexamples to the Workestrate contract*.

---

# 26. Recommended near-term design decision

The most useful first architectural commitment is:

> Define a stable, serializable `ActionTrace + FaultTrace + History + PropertyResult + RunManifest` model before adding many system-test scripts.

Why this first?

Because it gives every later capability a common substrate:

- property-based generation emits traces,
- curated scenarios are traces,
- historical regressions are traces,
- retries/replay consume traces,
- minimization rewrites traces,
- differential backend testing reuses traces,
- a future snapshot/fork search engine branches traces,
- reports cite traces,
- AI agents can reason about and synthesize traces,
- CI can archive traces as ordinary text artifacts.

The trace schema is therefore more foundational than any particular fuzzing library.

A minimal first schema could contain:

```rust
struct TestTrace {
    schema_version: u32,
    seed: u64,
    requirements: CapabilitySet,
    steps: Vec<Step>,
}

enum Step {
    Action(Action),
    Concurrent(Vec<Action>),
    Fault(FaultAction),
    Barrier(Barrier),
    Check(PropertySet),
}
```

Everything else can evolve behind it.

---

# 27. Sources and further reading

## Antithesis documentation supplied for this review

- Writing tests: https://antithesis.com/docs/product/writing_tests/
- KV reliability property catalog: https://antithesis.com/docs/resources/kv_property_catalog/
- Ring test: https://antithesis.com/docs/resources/ring_test/
- Chain of Blocks: https://antithesis.com/docs/resources/chain-of-blocks/
- How Antithesis works: https://antithesis.com/docs/introduction/how_antithesis_works/
- Setup overview: https://antithesis.com/docs/setup/overview/

## Additional Antithesis documentation that is particularly relevant

- Test templates / compositional scenarios: https://antithesis.com/docs/product/writing_tests/test_templates/
- Creating test templates: https://antithesis.com/docs/product/writing_tests/test_templates/first_test/
- Test command types, including recovery/final checks: https://antithesis.com/docs/product/writing_tests/test_templates/test_composer_reference/
- Assertions / properties: https://antithesis.com/docs/product/writing_tests/assertions/
- Sometimes assertions: https://antithesis.com/docs/best_practices/sometimes_assertions/
- Structured randomness: https://antithesis.com/docs/reference/sdk/generate_randomness/
- Coverage instrumentation: https://antithesis.com/docs/product/writing_tests/instrumentation/coverage_instrumentation/
- Controlling faults: https://antithesis.com/docs/product/writing_tests/controlling_faults/
- Fault types: https://antithesis.com/docs/product/writing_tests/controlling_faults/fault_types/
- Optimizing systems for testing: https://antithesis.com/docs/best_practices/optimizing/
- Deterministic simulation testing: https://antithesis.com/docs/resources/deterministic_simulation_testing/
- Developer workflow cadence: https://antithesis.com/docs/workflows/

## Antithesis repositories worth studying for generic ideas

- Organization: https://github.com/antithesishq
- Repository index: https://github.com/orgs/antithesishq/repositories
- `etcd-test-composer`, granular generated scenarios: https://github.com/antithesishq/etcd-test-composer
- `workloads-for-kv-datastores`, property catalog made executable: https://github.com/antithesishq/workloads-for-kv-datastores
- `glitch-grid`, deliberately simple buggy distributed-system fixture: https://github.com/antithesishq/glitch-grid
- `rand-tree-search`, demonstration of preserving progress in deep state-space search: https://github.com/antithesishq/rand-tree-search
- `bombadil`, property/state-machine-style autonomous UI testing: https://github.com/antithesishq/bombadil
- `proptest` fork: https://github.com/antithesishq/proptest

Not every repository in the organization is relevant. For example, tools such as `fluke` and `madness` are interesting infrastructure projects but do not materially change the core testing doctrine proposed here.

## Property-based testing

- Scott Wlaschin, choosing properties: https://fsharpforfunandprofit.com/posts/property-based-testing-2/
- Proptest: https://github.com/proptest-rs/proptest
- Proptest book: https://proptest-rs.github.io/proptest/
- Workestrate's existing PBT corpus: https://github.com/rybskiworks/workestrate/tree/main/docs/testing/property-based-testing

## Deterministic/scheduler-aware testing

- FoundationDB simulation and testing: https://apple.github.io/foundationdb/testing.html
- FoundationDB engineering/simulation: https://apple.github.io/foundationdb/engineering.html
- FoundationDB client workloads and seed replay: https://apple.github.io/foundationdb/client-testing.html
- Loom: https://docs.rs/loom/latest/loom/
- Shuttle: https://github.com/awslabs/shuttle
- Turmoil: https://github.com/tokio-rs/turmoil

## Opaque-box system testing and history checking

- Jepsen analyses and testing philosophy: https://jepsen.io/analyses
- Jepsen consistency-model/history explanation: https://jepsen.io/consistency/models

## Mutation testing / harness validation

- cargo-mutants: https://github.com/sourcefrog/cargo-mutants
- cargo-mutants docs: https://mutants.rs/

---

# 28. Bottom line

The strongest idea to take from Antithesis is not "put Workestrate in a deterministic hypervisor."

It is this:

> Stop treating tests as a finite list of scenarios. Define the truths Workestrate promises, define small actions that can compose into many histories, actively perturb the environment, search for histories that falsify those truths, and preserve every counterexample as a reproducible artifact.

Workestrate is in a good position to go further than a typical application because it already owns a virtualization/orchestration boundary. If the test harness is designed around properties, traces, independent observation, backend capabilities, and replay from the beginning, future snapshot/fork/CoW support can turn that same harness into a much more aggressive branching state-space explorer without changing the testing contract.

That is the architecture worth adopting.