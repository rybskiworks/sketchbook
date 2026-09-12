# A continual RLM built on DeepSeek Harness

> Status: exploratory specification, not an accepted architecture or an implemented product.
>
> Evidence snapshot: 2026-09-12 UTC. Scope: a Linux-first, DeepSeek Harness-native equivalent of Prime Agent's recursive execution and continual harness, with explicit boundaries for durable knowledge, tools, authority and recovery.
>
> Related exploration: [Yggdrasil](yggdrasil.md). The integration discussed here is proposed, not an assertion that either runtime already implements the other's interfaces.

## Reading routes

| Start here | Continue with |
| --- | --- |
| [The answer and evidence](#1-the-question-and-the-proposed-answer) | Sections 1-6: source pins, implementation correspondence, equivalence criteria and alternatives. |
| [Architecture and execution](#7-proposed-composition-and-ownership) | Sections 7-11: composition, persistent Python, the host bridge, recursive children and budgets. |
| [Continual artifacts](#12-the-continual-artifact-domain) | Sections 12-16: knowledge scopes, persistence, promotion, refinement, prompt projection and skills. |
| [Recovery and authority](#17-durable-history-and-recovery-semantics) | Sections 17-20: state domains, security, lifecycle, Workestrate and Yggdrasil. |
| [Implementation and migration](#21-existing-continual-harness-plugin-reuse-without-overclaiming) | Sections 21-23: existing community code, concrete integration locations and Prime workflow migration. |
| [Experiments and decision criteria](#24-smallest-useful-experiment) | Sections 24-27: baselines, fault injection, implementation stages and reasons to change direction. |
| [Pinned references](#28-references-and-evidence-map) | Source inventory and the evidence behind each implementation claim. |

## 1. The question and the proposed answer

Prime Agent is built on Pi. What would the equivalent look like if DeepSeek Harness, rather than Pi, supplied its foundation?

The useful answer is not "Prime Agent using a DeepSeek model." The underlying model, the agent runtime and the surrounding product are different choices. It is also not merely launching Prime as a DSH subagent: that composes two products but leaves Prime's execution and persistence semantics inside Prime.

The proposed equivalent is **a DSH-native continual RLM distribution**: a profile and bundle that retain DSH's agent loop, model adapters, session history, tool execution and client interfaces, while adding a session-owned persistent Python environment, host-mediated recursive delegation, and a versioned continual-artifact plane. The artifact plane contains supplemental instructions, memories, skill references and reusable delegation specifications. It can propose and validate changes to those artifacts without acquiring the authority to rewrite deployment policy.

For discussion, this note calls that distribution **Continual RLM on DSH**, and uses names such as `dsh-rlm-runtime` for proposed packages. These are design labels, not claims that packages with those names exist or should be installed.

There are two particularly important implementation findings:

1. **DSH already supplies more of the foundation than a superficial comparison suggests.** Its programmatic tool calling, continuable subagents, scoped registrations, dynamic prompt context and durable session log provide concrete integration points. A community `dsh-continual-harness` plugin also implements a substantial part of the continual-artifact idea. [D1], [D2], [D3], [D4], [C1]
2. **DSH's existing code runtime is deliberately not a persistent REPL.** Its contract isolates individual runs and does not own sessions. Hiding cross-cell state inside an ordinary `CodeRuntime` provider would break that contract. Faithful Prime-style execution needs a separate stateful capability, or an explicit upstream contract change, rather than a misleading backend swap. [D5]

The recommended first direction is therefore **native composition plus a new stateful capability**, not a wholesale fork of the DSH loop and not a compatibility layer that reproduces every Pi internal class.

## 2. Evidence, terminology and limits

### 2.1 Inspected baselines

The implementation discussion is pinned to the following public repository revisions. A branch label is context; the full commit is the reproducible reference.

| System | Inspected branch | Commit |
| --- | --- | --- |
| Prime Agent | `PrimeIntellect-ai/prime-agent`, `main` | `46c60b7500923be9e77022cb85c731241f35e2ac` |
| Pi | `earendil-works/pi`, `main` | `71dca871bc80b6bc97be37f0ca3189399d651fff` |
| DeepSeek Harness | `deepseek-ai/deepseek-harness`, `master` | `c291e7961a515f6d7af9304e7fd1d257929aef26` |
| Community continual-harness plugin | `jasen215/dsh-continual-harness`, `main` | `d4e336a907d47a7e03562bd1710d1529480dadde` |

These are comparison snapshots, not an assertion that Pi's current head is Prime's exact fork point. Package names, source ancestry and similarly named methods do not establish binary or semantic compatibility. Prime's inspected package manifest reports version `0.9.4` and builds the TUI, AI, agent and coding-agent workspaces together. Its README explicitly acknowledges Pi. That supports treating Prime as a source-integrated, Pi-derived product rather than assuming it is only an external Pi extension. [P1], [P2]

DSH describes itself as a developer preview with breaking changes. The design should therefore qualify a complete composition at exact revisions, rather than target an unspecified "latest DSH." [D1]

### 2.2 Evidence classes

**Observed implementation** means a named source file was inspected. **Documented capability** means the pinned project documentation describes a behavior, without this note independently exercising it. **Inference** means an architectural consequence drawn from those sources. **Proposal** means a desired contract for the new system.

No end-to-end Prime, Pi, DSH, Python-kernel or microVM runtime experiment was executed for this exploration. Source inspection establishes useful seams and potential incompatibilities, not performance, security certification or drop-in compatibility. In particular, the community plugin observations below are source-level review findings, not reproduced bug reports.

All interfaces introduced in this note are proposed unless explicitly attributed to an inspected source. Configuration examples describe desired deployment policy; they are not copy-and-paste DSH configuration.

### 2.3 Terms that need to stay separate

An **RLM execution environment** lets an agent operate on context programmatically and delegate to other model-driven agents. A **continual harness** stores and refines reusable operating artifacts. Neither implies model-weight updates. A **profile** composes runtime capabilities. A **skill** may be executable code or a description pointing to code; those are not interchangeable installation units. A **session fork** copies a conversational starting point, while an **execution-world fork** requires a separate storage or VM capability.

A persistent Python variable is working state, not automatically durable knowledge. A fact written to a memory store is not automatically true, authorized for another tenant, or still applicable after the environment changes.

## 3. What Prime adds to its Pi foundation

Pi's inspected SDK exposes `createAgentSession`, configurable tools, a resource loader, a session manager, settings and model/auth runtime selection. The integration point is already richer than a raw model API: a caller can choose a tool surface and participate in session lifecycle without writing its own provider loop. [I1]

Prime adds a particular operating model on top of that foundation. Its architecture separates clients, daemon supervision, session workers, agent sessions and Python kernels. The Python side is the model-facing control environment; TypeScript retains ownership of child execution, model access, persistence and accounting. A typed host-request bridge crosses that boundary. [P3], [P4]

That ownership split is the important thing to transplant. Copying the Python syntax while allowing the Python process to launch arbitrary untracked model clients would reproduce the appearance of an RLM while losing the accounting and lifecycle properties that make it manageable.

### 3.1 The current delegation API is not the older API

At the inspected Prime revision, the public Python call is:

```python
handle = await rlm.spawn("Inspect the API boundary", name="api-reviewer")
```

The returned handle confirms admission and contains child identity and metadata. It does **not** contain the child's answer. Results arrive through explicit agent messages or files. The Python namespace is not callable, and its older `rlm.run` attribute has been removed, even though the internal host-request operation is still named `rlm.run`. [P4]

A port must distinguish all three layers: the model-facing Python API, the bridge protocol and the host implementation. Preserving an internal operation name is not a reason to teach the model a removed public method. An older blocking-result compatibility mode would be a separate adapter with its own scheduling semantics, not the default meaning of `spawn`.

### 3.2 The continual layer is supplemental state

Prime's inspected Python store has four entry kinds: `prompt`, `memory`, `skill` and `subagent`, with local and global scopes. Its TypeScript refinement subsystem emits create/update/delete proposals, records before/after values and supports rollback records. The base prompt remains outside the editable artifact set. Python skill references require an import and callable or call pattern; a descriptive skill entry is not the same operation as installing arbitrary source code. [P5], [P6]

This suggests a portable semantic core: **small, reviewable changes to explicitly scoped artifacts, attached to evidence and an expected improvement**. The exact file format, UI command and planner implementation can change without losing that core.

## 4. Implementation correspondence across all three systems

The table distinguishes a correspondence from a claim of identical behavior.

| Concern | Pi foundation | Prime's inspected behavior | DSH-native counterpart or gap |
| --- | --- | --- | --- |
| Agent construction | `createAgentSession` with tools, model runtime and session manager. [I1] | Root and child `AgentSession` instances coordinated by Prime's runtime. [P3], [P4] | `ctx.agents` and the default agent-loop plugin; keep their lifecycle rather than introduce a competing loop. [D2] |
| Model access | Provider-independent agent core plus SDK model/runtime integration. [I1] | TypeScript host resolves providers and child model selection. [P4] | `ctx.llm`, request preparation and adapter seams. [D2] |
| Product composition | SDK options, custom tools and resource loading. [I1] | Source-integrated workspaces and additional daemon/kernel machinery. [P2], [P3] | Named profiles, ordered bundles and Cordis plugins. [D2] |
| Model-facing code | SDK allows changing the tool set; this alone does not imply a persistent Python environment. [I1] | Persistent Python REPL is the principal built-in control tool. [P1], [P4] | PTC exists, but its code-runtime contract is per-run. Add a distinct stateful service. [D5], [D6] |
| Tool execution | Configurable built-in and custom tools. [I1] | Python operations and typed host requests reach host-owned behavior. [P4] | Registered canonical-JSON tools, monotonic guards and nested dispatch. [D7] |
| Recursive delegation | An application can build on agent/session construction. [I1] | `rlm.spawn`, host-owned children, retained registry and later replies. [P4] | Continuable subagents are the nearest semantic match; one-shot providers are a different mode. [D3] |
| Child communication | Application-specific orchestration is needed for the comparison. | Prime documents explicit parent/child messages and retained agents. [P4] | DSH authorizes adjacent parent/continuable-child messages through the exact live sender. [D3] |
| Editable artifacts | Resources can be loaded into a session. [I1] | Four-kind local/global ledger and dedicated refinement. [P5], [P6] | Community plugin is an existing partial implementation; qualify or adapt it. [C1], [C2] |
| Prompt updates | Session/resource integration surface. [I1] | Host integrates supplemental harness state. [P4], [P6] | Ordered sections and cache-safe `PromptContext`, materialized into logged history. [D4] |
| Transcript | Session manager participates in resume and branch context. [I1] | Transcript plus kernel artifacts and child-usage attribution. [P4] | Append-only session events, surface projection and versioned persistence. [D2] |
| Kernel revival | Not established by the inspected Pi SDK. | Optional namespace snapshots and runtime artifacts. [P4] | New stateful capability must specify cold reconstruction versus snapshot restore. |
| Long-running work | Do not infer a supervisor contract from SDK construction alone. | Daemon supervisor, per-root worker, scheduling and reconnect. [P3] | Reuse DSH client/agent seams, then qualify process ownership and durable admission separately. [D2], [D3] |
| Security boundary | Tool choice alone is not OS confinement. | Prime explicitly says workers and kernels are not security sandboxes. [P1], [P4] | Cordis scopes and tool restrictions are not an OS boundary; confinement remains an external execution-world concern. [D5], [D7] |

This comparison intentionally does not claim that stock Pi lacks every feature not examined here. It identifies the specific sources needed to explain Prime's design and a DSH replacement.

## 5. What counts as an equivalent

A useful successor should satisfy behavioral criteria rather than reproduce Prime's class names.

**Execution equivalence:** a model can keep useful program state across cells, process a large artifact without injecting all of it into the conversational context, invoke capabilities programmatically, and delegate to real child agents. The host, not a mutable Python object, remains authoritative for permissions, identity, lifecycle and cost.

**Continual equivalence:** lessons and reusable operating patterns can survive conversational compaction and, when explicitly promoted, future sessions. Refinements are scoped, attributable and reversible as artifact changes. They do not silently rewrite the immutable base or elevate privilege.

**Operational equivalence:** a detached client need not kill accepted work, children have inspectable identities, failed operations are distinguishable from completed ones, and the session can explain what state survived a restart. Achieving these properties requires qualifying the chosen DSH deployment, not merely finding similarly named APIs.

**Integration equivalence:** a headless orchestrator can create work, observe admission and settlement, cancel within a stated contract, retrieve artifacts and reconcile usage. Pixel-identical TUI behavior is not required. DSH's existing clients can remain the product surface.

Non-goals for the initial implementation are complete Prime/Pi extension compatibility, arbitrary Python heap migration, universal undo, distributed consensus inside every guest, a new model gateway, support for every host OS, or a promise that self-refinement improves benchmark performance.

## 6. Candidate approaches and the preferred baseline

| Approach | What it preserves | Main limitation | Appropriate role |
| --- | --- | --- | --- |
| Keep Prime and use a different model/provider | Prime's existing execution and continual behavior. | Does not answer the foundation change. | Control baseline for evaluation. |
| Launch Prime through a DSH subagent adapter | Existing Prime runtime behind a DSH delegation surface. | Two lifecycle, persistence and accounting domains remain. | Transitional integration, not the native equivalent. |
| DSH PTC plus continual artifacts | Native tool transport, persistence and refinement composition. | No faithful cross-cell namespace under the existing code-runtime contract. | Smallest baseline when programmatic tools matter more than Python continuity. |
| New DSH persistent-kernel capability plus continual plugins | RLM semantics with DSH owning agent execution. | Requires careful bridge, durability and lifecycle work. | Preferred direction for a genuine equivalent. |
| Port Prime's internals wholesale onto DSH | Potentially broad feature correspondence. | Competing queues, stores and ownership models; difficult upgrades. | Only if experiments show native seams cannot express required behavior. |
| Change DSH `CodeRuntime` into a session runtime | One apparent code abstraction. | Breaks the existing per-run semantics unless explicitly redesigned upstream. | An upstream proposal, not a local implementation trick. |

The first experiment should compare the PTC-plus-artifacts baseline with the persistent-kernel variant. Persistent Python is not free: it adds recovery state, attack surface and serialization constraints. It should earn its place through workloads where reusing variables or processing context outside the prompt is materially useful.

## 7. Proposed composition and ownership

DSH's documented launch path is a named profile composed from bundles and patch layers. Shipped headless and SDK profiles apply their layers at startup rather than live-replacing dependencies during accepted work. The proposed distribution should follow that model, not create an undocumented alternative application launcher. [D2]

A conceptual composition is:

```text
DSH profile: continual-rlm
  existing DSH base capabilities
    agent + agent-loop + session + session persistence
    model adapters + request preparation
    tools + policy guards + filesystem/subprocess capabilities
    subagent service + selected providers
    prompt assembly + selected client/SDK application

  proposed continual-RLM bundle
    rlm-runtime definition + kernel provider
    model-facing Python tool + host-request dispatcher
    recursive-delegation adapter
    artifact store + projection + refinement coordinator
    capability/budget policy + lifecycle observations

  deployment-owned composition
    execution-world provider
    model gateway configuration
    immutable profile and skill pins
    knowledge-promotion authority
```

The layer order and exact plugin identifiers must be derived from the pinned DSH configuration, not guessed from this diagram. DSH patches replace a row's whole configuration; an overlay author must not assume that partial fields are automatically deep-merged. [D2]

### 7.1 Proposed packages

`dsh-rlm-runtime` defines stateful kernel handles, cell execution, lifecycle and recovery capabilities. A provider implements that contract, initially with a managed CPython process or an explicitly isolated execution world.

`dsh-tool-python` registers the model-facing entry point, shapes bounded canonical output and binds each call to its DSH session. It is a consumer, not the owner of provider credentials or a second agent loop.

`dsh-rlm-delegation` maps a small Python API to DSH's continuable-subagent service. It normalizes handles and errors while retaining DSH's authorization and scheduling semantics.

`dsh-continual-artifacts` owns the versioned artifact domain and its projections. It may incorporate or adapt the existing community plugin rather than start from nothing. `dsh-continual-refine` coordinates planning, validation and application. Separating storage from the planner makes it possible to change the planner without changing every reader.

`dsh-continual-rlm-bundle` supplies the selected composition and protocol instructions. Package boundaries can initially be folders inside one package; the architectural ownership matters more than publishing many packages.

### 7.2 Trusted control and untrusted execution

The trusted control plane owns the live DSH `Agent`, policy, session log, credentials or credential broker, artifact mutations and child admission. The Python execution world receives a narrow bridge for operations it is allowed to request.

A local same-user process provider can be useful for trusted development, but it must report that trust model explicitly. Running a process separately does not stop it reading files accessible to its OS identity. A hardened deployment places model-generated Python and project commands behind an OS isolation boundary and keeps the control plane's secrets outside that boundary.

Cordis scoping solves registration and lifecycle composition. It does not make mutually hostile JavaScript plugins safe inside the same process. Installing a plugin is a deployment-trust decision.

## 8. The persistent Python capability

### 8.1 Why this is not another `CodeRuntime` provider

The inspected DSH `CodeRuntime` exposes `language`, an informational `isolation` descriptor and `run(request)`. Its source says the runtime does not know about tools or sessions and that implementations isolate runs from each other. The Python backend mentioned there is experimental and not published. [D5]

PTC already supplies useful transport machinery: a `run_code` surface, generated language-specific tool instructions, curated output and logged nested tool dispatches. Those features should inform the bridge design, but they do not establish persistent variables or Python-package continuity. [D6]

The new capability should make persistence visible in its type and lifetime. A simplified proposed interface is:

```typescript
// Proposed domain sketch, not an existing DSH API.
type KernelRef = Readonly<{
  sessionId: string;
  kernelId: string;
  generation: number;
}>;

type KernelCapabilities = Readonly<{
  language: "python";
  state: "session-persistent";
  recovery: "cold-only" | "allowlisted-values" | "trusted-snapshot";
  executionBoundary: "same-user-process" | "isolated-world";
}>;

interface PersistentKernelService {
  acquire(owner: AuthorizedSession): Promise<KernelRef>;
  execute(ref: KernelRef, cell: CellRequest): Promise<CellOutcome>;
  inspect(ref: KernelRef): Promise<KernelInventory>;
  interrupt(ref: KernelRef, cellId: string): Promise<InterruptReceipt>;
  checkpoint(ref: KernelRef, request: CheckpointRequest): Promise<CheckpointReceipt>;
  close(ref: KernelRef): Promise<void>;
}
```

`AuthorizedSession`, the cell schema and receipts would be defined by the new service. The caller cannot manufacture them merely by supplying a session ID. The host derives the owner from the live tool execution and authenticates any cross-process transport.

### 8.2 Kernel lifetime

The baseline owns one namespace per logical agent session and serializes ordinary cells within it. Two cells that mutate the same namespace do not execute concurrently. Child agents can run concurrently because they have separate sessions and separate kernels. This mirrors Prime's documented serialization and child ownership without requiring its exact `ReplKernelManager` implementation. [P4]

A kernel generation increases whenever the namespace is recreated. Handles returned by an earlier generation are stale, even if the session ID is unchanged. The service must reject delayed cell results, bridge replies and checkpoint requests from stale generations.

The first implementation should not support arbitrary detached Python tasks continuing after a cell returns. That is a deliberate reduction from the richer background behavior described by Prime. Add detached tasks only after their ownership, output attribution, cancellation and budget charging can be demonstrated. Otherwise an apparently completed cell can continue changing the world with no active tool call.

### 8.3 Context as data rather than repeated prompt text

The model can load a permitted source artifact into a variable, extract a subset and print a bounded result. The host logs the cell source, artifact references and returned observation. It need not turn every byte of the loaded artifact into a model-visible message.

A large context object should have a content digest, provenance, access scope and explicit lifetime. An artifact handle is preferable to an unrestricted host path. On restart, the agent can determine whether the variable still exists, whether the source artifact is available and which reconstruction step is safe.

The prompt should include a compact namespace inventory, not the entire heap. At minimum, expose names, coarse types, generation and whether a value is recoverable. Avoid evaluating arbitrary `repr` implementations simply to render that inventory, since user-defined objects can execute code during representation.

### 8.4 Cell outcomes and output budgets

A proposed cell outcome distinguishes successful completion, a Python exception, policy denial, timeout, cancellation, kernel loss, output-limit failure and stale generation. It includes bounded stdout/stderr, transferable values or artifact references, and structured failure metadata.

Truncation is visible. A large log can be stored as a scoped artifact with a bounded excerpt; the system must not make "truncated" look like "empty." Canonical JSON output is validated before DSH renders model-visible content, following the existing tool pipeline's separation between canonical values and presentation. [D7]

Cancellation acknowledges a request, not necessarily quiescence. The host must expose when the process and its owned work have actually stopped. A timed-out kernel that might still be mutating state is tainted and cannot simply accept the next cell.

## 9. Host requests and tool mediation

Prime's Python shim delegates authoritative operations through typed requests to the TypeScript host. The DSH equivalent should retain that separation while binding requests to DSH's tool and agent identities. [P4]

### 9.1 Bridge envelope

A proposed request envelope carries a protocol version, kernel generation, cell ID, request ID, operation and JSON payload. The transport binds the session, permitted operation set and current authority epoch. Python-provided claims about identity, cost or privilege are not authoritative.

Use a dedicated framed channel, or a rigorously separated protocol stream, rather than trusting arbitrary user stdout as control messages. Bound frame sizes, pending requests and result sizes. A compromised kernel can still invoke its allowed bridge operations, so the bridge must remain safe when the caller intentionally sends malformed or adversarial requests.

Protocol errors should be distinct from ordinary tool failures. Unknown fields and unsupported options are rejected, not silently ignored. Capability negotiation is versioned, and a mismatch fails before the model receives instructions for an unavailable operation.

### 9.2 Do not bypass DSH's tool pipeline

A Python `tools.read(...)` call must reach DSH's registered tool execution path rather than invoking a captured implementation function directly. That retains guards, cancellation, canonical output validation and observation hooks. DSH's tool filters affect inherited registrations, while a scope's own registrations have special treatment; this is another reason to keep authorization in the host rather than infer it from what the model can see. [D7]

Nested execution needs special care. DSH PTC already carries root-call identity and an opaque parent execution token. A Python bridge must use a supported nested-dispatch mechanism with equivalent provenance. It must not let the guest invent parent tokens or disguise a direct native call as an authorized nested call. [D6], [D7]

There is also a scheduler hazard: an exclusive outer Python tool cannot hold a lock that its own nested tool calls need to acquire. Reuse or extend DSH's nested execution machinery instead of implementing a second queue that deadlocks under the outer call. A minimal integration test must execute a guarded nested read and an exclusive nested write from one Python cell and prove both ordering and cancellation.

### 9.3 Direct Python I/O is a separate authority path

Unrestricted CPython can import modules and perform filesystem, subprocess or network operations without using `tools.*`. A prompt telling it not to do so is not enforcement. A bridge-only API does not make ordinary Python safe if the interpreter still has ambient OS access.

The design therefore supports two explicit deployment modes. A trusted local mode accepts the Python process's OS permissions and labels observations accordingly. An isolated mode constrains the execution world's mounts, process privileges and egress independently of the bridge. DSH tools and direct Python I/O must not accidentally target different copies of the workspace.

For an isolated deployment, file operations, shell execution, Python and child workload operations should resolve the same declared execution-world identity. DSH's existing filesystem/subprocess capability split provides a documented integration direction, but a specific microVM provider still needs implementation and conformance tests. [D2]

## 10. Recursive delegation without a second agent system

### 10.1 Use continuable children for Prime-style spawn

DSH has both one-shot and continuable subagents. Its continuable service reserves a child identity, creates an activation, submits the initial message and returns `{ childId, messageId }` when the inbox accepts that message. That is much closer to Prime's current admission-only `rlm.spawn` than a wrapper that waits for a completed result. [D3], [P4]

The proposed Python-facing adapter can preserve the recognizable name while returning a DSH-specific handle:

```python
# Proposed adapter API, not currently supplied by DSH.
child = await rlm.spawn(
    "Inspect the API boundary and send the findings to the parent",
    name="api-reviewer",
)
print(child.id, child.message_id, child.state)
```

The adapter should not fabricate a Prime `session_dir` when the DSH storage backend has no meaningful local directory. Expose portable artifact references and capability-dependent locations instead. A compatibility export can map old fields only when their semantics genuinely exist.

### 10.2 Admission, durability and completion are distinct

DSH's documented acceptance point precedes the message entering the durable session log. It also documents best-effort final flush behavior during activation disposal. Therefore the proposed wrapper must not advertise the returned handle as proof that a child ran, persisted its input or completed successfully. [D3]

A stronger deployment may add a durable operation journal before scheduling and a reconciliation process afterward. That is additional behavior, not something to attribute to `startContinuable` itself. Status should distinguish at least requested, accepted, durably recorded, running, settled and failed. Some states may be observations over multiple DSH events rather than new execution states.

Do not build a second FIFO queue. DSH's agent inbox remains the turn-ordering authority. A journal records accepted intentions and receipts; it does not compete with the inbox for execution ordering.

### 10.3 Parent-child messaging

The baseline maps Python message requests onto DSH's existing adjacent-agent authorization. A parent can address its direct continuable child, and that child can address its parent. A remembered ID is not sufficient authority. Sibling messaging and communication across arbitrary ancestors require a separately authorized coordinator rather than silently weakening DSH's rule. [D3]

The parent should end its current cell or turn after admitting independent work and consume later replies. Waiting inside a parent tool for a result that requires that same parent to process a message is a deadlock risk. A future `join` primitive would need an explicit event-delivery and cancellation contract; it should not be smuggled into `spawn`.

A reply is data from another agent, not an instruction with the parent's authority. Preserve sender provenance and treat embedded commands, approval claims and suggested policy changes as untrusted content.

### 10.4 Lifecycle and cancellation

DSH's continuable activation manager owns children independently after message acceptance. Later cancellation of the admission caller does not cancel accepted work. Its interrupt operation also differs from recursive teardown: it requests cancellation while retaining pending inbox work and does not automatically dispose descendants. [D3]

The adapter must expose those distinctions. Suggested user-level operations are `interrupt_turn`, `close_child` and `cancel_subtree`, with only the operations actually supported by the chosen integration enabled. Unsupported operations fail loudly; they do not all alias to a generic "cancel" button.

On root shutdown, new child admissions stop first. The owner waits for accepted materializations, cancels work according to policy, drains descendants and only then destroys their bridge and kernel resources. Stale completion messages carry their original generation and cannot revive a closed child.

## 11. Model selection, cache locality and shared budgets

### 11.1 Model selection is not quota management

The host resolves a child model from a deployment allowlist. An exact requested route that is unavailable fails explicitly unless the caller selected a documented fallback policy. This preserves the intent behind Prime's current exact child-model selection without assuming DSH's provider capability flags are identical. [P4], [D3]

Quota pooling and provider-account selection should remain below the agent, for example in a deployment-managed model gateway. The agent chooses a permitted capability or model policy, not credentials. A runtime must not manufacture fallback claims such as "equivalent reasoning" when a provider exposes no such equivalence.

Route stickiness should be a deployment policy at session or subtree granularity. Preserve a stable model/configuration and prompt prefix where possible, but record any route change and its reason. This is a proposed locality strategy, not a claim of measured cache savings.

### 11.2 One root budget, attributable spending

A root mission budget includes parent requests, child requests, refinement planning, evaluators and retries. Spawning children does not create free budgets. Reserve capacity before admitting work, charge settled usage when known, and retain a conservative reservation for an in-flight request whose final usage is unknown.

Prime's documented `child_usage_attributed` records distinguish a parent's aggregate accounting from its own context usage. The DSH successor should preserve that distinction even if its event representation differs. Child tokens count toward billable work; they do not become parent-context tokens merely because the parent owns the child. [P4]

Proposed accounting identities include mission, session, provider request, delegation operation and attribution edge. A request is charged once. Aggregates are derived views, not additional charges. Retries and cancelled requests remain visible, and a process restart must not reset spent budget.

### 11.3 Bound breadth as well as depth

An example deployment may set the root depth to zero and cap child depth at three. This is a proposed limit, not Prime's default: Prime's inspected documentation reports a default maximum depth of two. DSH's one-shot `maxDepth` is an absolute child-depth cap, and continuable admission has a distinct capability path. A wrapper must normalize and enforce its own declared semantics rather than pass an integer to unrelated APIs and assume equivalence. [P4], [D3]

Depth alone does not bound exponential fan-out. Also limit live children per parent, live descendants per mission, total spawned children, queued work, Python cells, tool dispatches, wall-clock duration and refinement frequency. Admission should return a typed limit failure or an explicit queued status, never an invisible downgrade from parallel to serial work.

## 12. The continual-artifact domain

### 12.1 Preserve the useful four-kind model

Prime's four kinds are a good starting vocabulary. A `memory` records a scoped assertion and its evidence. A `prompt` supplies a narrow behavioral addendum. A `skill` describes or references a reusable capability. A `subagent` describes a delegation role. Their shared storage shape does not mean they have identical trust or promotion rules. [P5], [P6]

A proposed artifact record is:

```json
{
  "schema_version": 1,
  "id": "memory:parser-test-command",
  "kind": "memory",
  "revision": 4,
  "scope": {"kind": "session", "id": "session-demo"},
  "title": "Parser tests require the fixture generator",
  "content": "Generate the synthetic parser fixtures before this test target.",
  "applicability": {
    "workspace": "example-project",
    "source_revision": "example-source-revision",
    "profile_digest": "example-profile-digest"
  },
  "evidence": [
    {"session": "session-demo", "event": "example-event", "artifact": "example-log-digest"}
  ],
  "status": "candidate",
  "supersedes": [],
  "executable_ref": null
}
```

This is an illustrative new schema, not an upstream format. Real records should use stable opaque identities, bounded fields and canonical serialization. A title is not an identity; renaming a lesson must not create an accidental duplicate history.

### 12.2 Scope is part of the identity

Start with session-local mutable artifacts. Optionally add project, fleet and personal/global scopes behind explicit deployment policy. A session cannot update a global record merely because it can read it. The destination scope participates in authorization and revision checks.

A useful lookup result is a **knowledge view**: an immutable manifest naming the selected artifact revisions, their provenance and the filtering policy. It is not a mutable global directory copied into every prompt. A run can therefore explain which lessons influenced it, and a held-out evaluation can pin a baseline rather than read a moving target.

Overrides should be explicit relationships, not accidental last-writer-wins ordering. A session-specific exception may shadow a project lesson in its view without editing the project record. Contradictory facts can coexist as claims pending resolution; the system should not merge them into a confident synthetic statement merely to make the store look tidy.

### 12.3 Memory and executable skills have different authority

A memory saying "run this command" is still untrusted content. A skill reference names installed code plus its input contract, dependency lock, capability requirements and version. Editing the reference does not install or grant access to the code.

A subagent specification is a reusable role, not an active child and not a credential. Its requested model, tools and budget are intersected with deployment policy at admission. A prompt addendum cannot override bridge protocol requirements, mandatory safety checks or the immutable base policy.

The artifact plane records confidence and evidence; the authority plane decides permitted actions. Keeping those planes distinct prevents a successful refinement from becoming an implicit privilege-escalation path.

## 13. Persistence, concurrency and promotion

### 13.1 One authoritative writer per mutable scope

Prime's Python store reloads on detected file modification and writes through an atomic replacement path. Those are useful local-file properties. They do not by themselves provide serializable multi-process read-modify-write transactions: two writers can both read one version before either replaces it. This is an inference about the mechanism, not a reproduced lost-update result. [P5]

The proposed successor uses a host-owned mutation service. Python receives a proxy that submits proposals with an expected revision. A mutation either commits against that revision or returns a conflict; it does not silently overwrite another agent's update. In a distributed deployment, ownership, fencing and durable transaction semantics belong in the service or backing store, not in a convention that every guest remembers to follow.

A scope's state can be represented by immutable artifact blobs plus an append-only mutation journal and a current revision pointer. A derived JSON snapshot is a cache, not a second authority. The minimum implementation can use one process and ordinary files, provided crash consistency and single-writer ownership are explicit and tested.

### 13.2 Corruption must not silently become an empty memory

The inspected Prime Python loader treats malformed or unreadable JSON as an empty state that a later save can rewrite. That is a permissive availability choice in the source. For a shared artifact service, the proposed policy is different: quarantine the corrupted generation, retain the last validated revision and refuse writes whose expected base cannot be established. [P5]

Reading an empty store and failing to read a store are different outcomes. The model should be told which happened. Recovery should never require trusting arbitrary Python serialization from another agent.

### 13.3 Git is suitable for promotion, not automatically for every hot mutation

A Git-backed promoted knowledge repository is a useful option because artifacts, schemas and review history are inspectable. Store one stable record per file or another merge-friendly representation, pin a tree or commit in the run's knowledge view, and promote changes through reviewed commits.

Git alone does not provide semantic conflict resolution. Two edits to different files can still contradict each other, and textual merge success does not validate a lesson. Similarly, a successful push is not an execution lease unless a separate protocol defines ownership, expiry, fencing and recovery.

The initial design should avoid committing every Python cell or hot local mutation. Use the session journal for working state and deliberate commits for durable cross-session promotion. A fully Git-backed local store remains an alternative to test, especially for low write volume; it should not be rejected solely because it is unconventional or adopted solely because Git is already present.

### 13.4 Promotion is an external effect

Promotion changes the knowledge future sessions consume. It needs a destination, expected base, candidate digest, evidence, approval policy and result receipt. Promotion can be rejected because the destination changed, the evidence is missing or the requested scope is unauthorized.

Rollback of a refinement is a new compensating artifact mutation. It does not erase the evaluation history, remove already incurred costs or undo actions that another session took while the lesson was active. Revocation should prevent future selection and mark affected views for inspection where practical.

## 14. Refinement as a bounded, reviewable transaction

Prime's dedicated refinement code provides a concrete parallel: a planner receives the trajectory and current artifact state, emits structured edits and expected outcomes, and applies them with recorded before/after values. The new implementation can preserve that workflow without importing Pi's model types or Prime's file-writing paths. [P6]

### 14.1 Proposed phases

A refinement starts by capturing a bounded, immutable view of the trajectory and the exact artifact revisions being reviewed. Sensitive material is filtered according to destination scope before a planner receives it. A project-local failure log is not automatically eligible for a fleet-global lesson.

The planner emits a proposal, not a direct store write. Deterministic validation checks the schema, target kinds, scope, expected revisions, evidence references, size limits and executable-reference rules. A policy gate then determines whether local application is allowed, explicit approval is required or the candidate must remain staged.

Application creates a new revision and a durable receipt. Optional evaluation compares that revision with its baseline. Promotion to broader scopes is a separate decision. The same coordinator owns manual, model-initiated and automatic refinement, so these entry points cannot bypass each other's checks.

A useful lifecycle is:

```text
captured evidence
  -> proposal
  -> schema and policy validation
  -> staged candidate
  -> local application or rejection
  -> evaluation record
  -> optional promotion

Any rollback is a later mutation referencing the original receipt.
```

### 14.2 Triggers and recursion prevention

Manual refinement is the first supported trigger. Later triggers may include a bounded turn interval, pre-compaction review or a mission wrap-up. Prime documents turn-interval and compaction-triggered review; the community DSH plugin also has an automatic gate. Their existence is evidence for the integration pattern, not proof that frequent refinement is beneficial. [P6], [C1]

Planner and evaluator sessions must not recursively trigger the same automatic refinement policy by default. Use an explicit session role and host policy, not a prompt request to "avoid refining." Charge their usage to the mission and impose separate caps so a refinement storm cannot consume the entire work budget.

A cooldown limits frequency but does not establish idempotence. An operation key derived from the reviewed evidence boundary and base revision can prevent accidental duplicate applications after reconnect or retry.

### 14.3 Evaluation does not prove a general lesson

A candidate can pass structural checks and still be wrong. A local success may reflect a changed workspace, a lucky model sample or leakage from the evaluated task. Keep the planner's rationale, deterministic checks and empirical evaluation results as distinct fields.

Do not let the candidate rewrite its own evaluator, held-out task definitions or acceptance thresholds. Report negative results and regressions rather than only the best sample. A useful expected outcome is falsifiable, for example fewer repeated invalid tool calls at the same task-success rate, not "the agent becomes smarter."

## 15. Prompt assembly, compaction and cache behavior

DSH's prompt system already separates relatively stable `PromptSection` contributions from dynamic `PromptContext`. The latter is documented as a cache-safe user-role snapshot materialized after retained history when it changes or when compaction removes it. This is a better starting point for a current artifact overview than untracked prompt mutation. [D4]

### 15.1 Three kinds of prompt material

Keep the immutable RLM protocol and bridge usage instructions in deployment-owned sections. Put the selected knowledge view's compact, changing overview in dynamic context. Retrieve detailed evidence or full skill descriptions through permitted tools when needed.

Each overview should identify its view revision and distinguish facts, hypotheses and procedures. A short index is useful; indiscriminately injecting every stored lesson recreates a context-growth problem under a different name.

DSH supports a `complete` prompt section that becomes the sole effective prompt section. Using it casually could suppress required instructions from other contributors. The first implementation should use ordinary scoped contributions and explicit ordering, not a complete replacement that assumes knowledge of every other plugin. [D4]

### 15.2 Model-visible content must be reconstructable

DSH's documented invariant is that model-visible input is represented in the session log. The artifact plugin must materialize the exact selected text or a reconstructable immutable representation before the request, not substitute live mutable store contents while replaying an old session. [D2]

A content digest alone is insufficient if its blob can disappear or change. Retain the referenced artifact revision for the session's retention period, or record the bounded rendered text in the durable message. Replay should not issue fresh network retrievals merely to reconstruct what a past model saw.

### 15.3 Compaction is not kernel reset or knowledge promotion

Compaction changes the conversational surface. It does not by itself destroy Python variables, reset an execution world or authorize promotion of local observations. Conversely, a surviving kernel is not proof that the model remembers its current contents after compaction.

After compaction, rematerialize the active artifact view and a bounded kernel inventory. Include any interrupted or unresolved operation status that would make blind retries unsafe. Do not restore a misleadingly clean transcript while leaving side effects and live child tasks unaccounted for.

### 15.4 Existing plugin compatibility questions

The community plugin's inspected `src/projection.ts` is a useful, concrete starting point. It injects a digest-tracked overview through `agent/pre-step`, uses a plugin-source user message and replaces a previous visible block through a session surface operation. [C2]

Two details need targeted tests against the pinned DSH revision. The first-injection path returns a new `{ kind: 'enter', messages: ... }` object rather than spreading the incoming decision; DSH documents `startsRequestSeries` as a declaration wrapping listeners must preserve. Also, the plugin returns early when its in-memory digest is unchanged, before looking for the overview on the current surface. A compaction that removes that surface node may therefore require an explicit reset or a different projection path. [C2], [D2]

These are source-level compatibility risks, not measured failures. Test the actual composition, including any other hook that changes the digest state. The proposed default is to evaluate DSH's normal dynamic-context mechanism first; retain a custom pre-step implementation only when its additional behavior is necessary and covered by conformance tests.

Replacing an older surface node and appending changed context at the tail also have different prefix-cache implications. Measure request-prefix reuse at the actual provider route rather than assert a universal caching improvement.

## 16. Skills, tools and reusable delegation roles

Prime's skill model includes importable Python packages. The community DSH continual plugin instead materializes skill entries as DSH `SKILL.md` bundles under a configured skills directory. This is a meaningful implementation difference: a useful description migration is not executable Python compatibility. [P1], [P5], [C1]

A skill import pipeline should distinguish three cases. A descriptive lesson can become an artifact directly after validation. A Python skill reference can be imported as an inactive reference if its package is not installed. An executable package requires a separately reviewed, pinned installation transaction with its capabilities and dependencies recorded.

The initial Python environment should be immutable for a run. Adding a dependency produces a new environment revision and usually a new kernel generation. Avoid installing arbitrary packages into a shared mutable interpreter while other agents are executing against it.

A reusable delegation role should contain task instructions, output expectations, applicability and requested capabilities. At spawn time, the host intersects those requests with the parent's permitted scope and current deployment policy. The stored role cannot make an unsupported provider suddenly accept tool filters, schema constraints or model overrides.

DSH's subagent providers advertise capabilities for one-shot requests, while continuable support is discovered through a different provider method. A role compiler must validate the selected path specifically. "Subagents are supported" is too coarse a capability statement. [D3]

## 17. Durable history and recovery semantics

### 17.1 Five state domains

The following split aligns the proposal with the existing [Yggdrasil exploration](yggdrasil.md), without requiring Yggdrasil to implement the core RLM.

| Domain | Examples | Recovery treatment |
| --- | --- | --- |
| Conversational continuation | DSH session events, current surface, queued intentions and child descriptors. | Replay through DSH's supported persistence and migration path. |
| Kernel working state | Variables, loaded modules and in-flight cells. | Cold reconstruction or a specifically supported checkpoint mode. |
| Execution world | Workspace files, application state, processes and selected volumes. | Reset only through the declared world provider. |
| Retained knowledge | Artifact revisions, evidence and selected views. | Restore or retain according to scope policy, independently of a world rewind. |
| Supervisory authority | Generations, spent budget, accepted effects, leases and promotion receipts. | Remains forward-moving; never restore it from guest state. |

The external world, including remote Git state, API charges and delivered messages, is outside all of these local reset mechanisms unless a separate protocol says otherwise.

### 17.2 The event log remains the conversational authority

DSH already derives model history from its session log and has explicit semantics for settled assistant messages, failed attempts and persistence generations. The new plugins should extend supported event vocabulary and projections rather than invent a parallel transcript that occasionally synchronizes with DSH. [D2]

Proposed additional facts might include kernel generation changes, cell lifecycle, artifact mutation receipts, knowledge-view selection and effect reconciliation. Their names and payloads require DSH event registration and migration review; this note does not claim those events exist today.

An artifact store can be a separate durable domain, but the session must reference exact artifact revisions and operation receipts. A commit that succeeds in one domain and fails in the other requires reconciliation, not silent best-effort success.

### 17.3 Recovery levels

**Transcript-only recovery** restores the conversation and declares the kernel lost. **Cold reconstruction** creates a fresh kernel and reloads allowed data artifacts through explicit steps. **Allowlisted-value restore** restores values with constrained, versioned codecs. **Trusted snapshot restore** may restore richer interpreter state but requires compatibility checks and a trusted snapshot source.

Arbitrary Python serialization is not a safe interchange format for untrusted agents. A snapshot can encode executable behavior, contain stale resource handles or depend on exact package versions. It should not be promoted as shared knowledge or automatically deserialized into a more privileged process.

The first implementation should choose cold reconstruction and selected data artifacts. Prime's documented snapshot files are a useful comparison, but their existence is not evidence that a DSH deployment can restore an arbitrary Python heap or that a file snapshot captures external processes. [P4]

### 17.4 No blind re-execution after crash

A crash after an external write but before its tool result is durable creates an uncertain outcome. Replaying the cell may duplicate the write. The recovery record needs an operation identity and an external receipt or reconciliation strategy; otherwise the system should report uncertainty and stop that automatic retry path.

Exactly-once effects require cooperation from the destination or an equivalent reconciliation protocol. Local event logging alone cannot provide them. Retryable reads, idempotent writes and non-idempotent writes should therefore have distinct policies.

## 18. Security and policy boundaries

The threat model includes malicious repository content, poisoned retrieved memories, prompt injection in child replies, compromised Python code, stale handles after restore and a faulty or malicious refinement proposal. It also includes ordinary mistakes: a permissive plugin default, an incompatible hook or a supposedly read-only helper that mutates parent state.

The proposed invariants are:

- A model-visible tool name, artifact, child ID or kernel variable never grants authority by itself.
- Host policy cannot be weakened by editing a prompt, memory, skill description or subagent role.
- Python and project code cannot read host-held model credentials, signing keys or the authoritative mutation store in the isolated deployment.
- A restored guest cannot roll back current authorization epochs, consumed budgets or accepted-effect records.
- Tool calls, nested bridge calls and imported skills remain subject to the declared execution-world and egress policy.
- Cross-scope promotion filters private data and requires the destination's authority, not merely the source session's enthusiasm.

These are requirements to prove, not guarantees supplied by a plugin architecture. Prime warns that its process boundaries are not security sandboxes, and DSH's code-runtime `isolation` string is explicitly informational rather than a security promise. [P1], [D5]

### 18.1 Authority must not be learned

A stored lesson may recommend a more efficient command or a useful test. It cannot declare that a domain is now allowed, a secret can be exposed, a required approval is unnecessary or a branch is safe to push. Such changes belong to deployment-owned policy and have a separate review path.

Immutable protocol text helps prevent accidental drift, but the enforcement must exist outside the prompt. A compromised model can still request an operation; the host must reject it based on current authority.

### 18.2 Observability must not become a leak

Logs should record the information needed to reconstruct decisions and failures without dumping credentials, entire private files or unrestricted interpreter heaps. Redaction applies before exporting evidence to broader scopes. Artifact retention and access checks need to remain effective after a child has settled.

A public knowledge repository must never receive private traces simply because a local artifact references them. Promotion can preserve a sanitized summary plus an access-controlled evidence reference, or reject the promotion when adequate evidence cannot be safely shared.

## 19. Process lifecycle, clients and hot reload

Prime's supervisor and per-root worker architecture provide an explicit example of keeping terminal lifetime separate from accepted work. A DSH-native design should preserve that property at the deployment level without assuming that every DSH launcher is a daemon with equivalent guarantees. [P3], [D2]

The headless integration should expose accepted operation IDs, observation streams, final receipts and reconnect cursors. An SDK client disconnect is not automatically a cancellation request. A one-shot launcher can intentionally own its work until exit, but then its contract must say so.

Use one lifecycle owner for each resource. The DSH agent owns conversational work, the continuation manager owns continuable activations, the kernel service owns interpreter processes, and the artifact service owns mutable knowledge revisions. A supervisor coordinates teardown; it should not duplicate each component's internal execution state machine.

Hot reload is especially risky for a persistent kernel. A tool schema or bridge implementation can change while Python retains references to the previous version. The initial profile should freeze its code and configuration for the run. A future reload protocol must drain cells and admissions, resolve or cancel pending bridge calls, publish a new generation and explicitly decide whether the old namespace is compatible.

Disposing a Cordis effect removes its registrations; it does not undo completed filesystem writes or published knowledge. A replacement plugin must not infer a clean world merely because the old plugin's effects have unwound.

## 20. Relationship to Workestrate and Yggdrasil

The core distribution should work without a microVM orchestrator. A separately owned test process can establish the first API and lifecycle contracts in a trusted synthetic environment; that process separation does not itself provide security isolation. Workestrate is a possible later provider of workload execution, image/configuration pins and policy-bound environments; that adapter is proposed here, not described as an existing API.

The existing Yggdrasil note separates execution state, agent continuation, retained knowledge, supervisory history and external effects. The continual-RLM design fits that split: DSH owns conversational continuation, the kernel/world providers own resettable working state, the artifact plane owns retained knowledge, and the supervisory ledger stays outside the rewind boundary. [Y1]

A Python helper could eventually request a checkpoint or branch through an authenticated host operation. That operation would need a capability vector: stopped-storage copy, application-quiesced snapshot and live-memory fork are different guarantees. Do not implement a single `fork()` that quietly downgrades between them.

Sharing retained knowledge between sibling attempts is not sharing interpreter RAM. A sibling may receive an explicit evidence view while starting with a fresh kernel and independent workspace. Conversely, a memory-CoW VM fork may share physical pages while retaining no semantic knowledge-merging policy at all.

Promotion also splits into distinct decisions: promote a code artifact, select an execution branch, promote a lesson, and publish an external result. One successful test should not automatically perform all four.

For deployment packaging, a pinned Nix environment is a plausible Linux-first option for the DSH bundle and Python dependencies. The specification requires reproducible environment identities, not Nix specifically. Snapshot compatibility still depends on the actual interpreter, packages, architecture and execution substrate; a shared package definition does not make arbitrary runtime state portable.

## 21. Existing continual-harness plugin: reuse without overclaiming

The inspected community plugin is not just a README idea. Its `src/index.ts` mounts a store, model-facing refinement tools, a projection, an automatic driver and a shared coordinator. It also exposes approval, diagnostic, budget and benchmark configuration. That is substantial prior implementation work and should be evaluated before building an independent replacement. [C1]

The source also makes deployment choices visible. `defaultGlobal` is required rather than implicitly local; `requireGlobalApproval` defaults to false in the inspected configuration schema; automatic refinement is enabled by default there; and skill materialization targets a DSH skills directory. These defaults are not necessarily wrong for its intended use, but they are not the conservative session-local, explicit-promotion defaults proposed in this note. [C1]

A reuse assessment should answer four questions. Can its store be made the single mutation authority without bypass paths? Can its planner/coordinator operate against immutable revisioned views? Does its projection preserve the current DSH request-series and compaction semantics? Can its skill-writing behavior be separated from executable installation and broader-scope promotion?

The preferred outcome is a small adapter or upstream contribution that retains the existing implementation. A fork is justified only by concrete incompatible requirements or an unmaintainable coupling, not by a desire to rename the same mechanism.

The plugin does not, merely by implementing continual artifacts, provide Prime's persistent Python environment or full daemon/kernel/subagent semantics. Conversely, adding persistent Python without a versioned refinement layer would not reproduce the continual half of Prime. These are complementary pieces, not competing definitions of an agent harness.

## 22. Implementation work mapped to actual seams

The following is a proposed work breakdown. The evidence column distinguishes inspected sources from component locations identified by their documentation; the final column gives proposed integration ownership.

| Work area | Existing implementation parallel | Proposed change or adapter |
| --- | --- | --- |
| Composition | DSH `docs/architecture.md`: profiles, bundles and startup-frozen SDK/headless trees. [D2] | Create a qualified bundle/profile without a new launcher. |
| Stateful kernel | Prime `packages/coding-agent/docs/rlm-runtime.md`: `ReplKernelManager`, lazy kernel, serialized execution and bridge ownership. [P4] | Define `dsh-rlm-runtime`, first provider and generation fencing. |
| Model-facing Python | Prime's runtime documentation identifies `packages/coding-agent/src/core/tools/ipython.ts`; DSH's tool contract is documented in `docs/subsystems/tools.md` and implemented under `packages/core/tools`. [P4], [D7] | Register a new canonical-output tool; do not copy Pi tool-result types. |
| Nested tool calls | DSH `packages/core/tools/src/ptc.ts` and `ToolExecutionInput` in tools documentation. [D6], [D7] | Reuse supported root/parent execution identity and scheduler integration. |
| Delegation | DSH `packages/subagent/subagent/src/{types,index,continuation}.ts`, as indexed by its subsystem documentation. [D3] | Adapt Python spawn/list/message operations to continuable service semantics. |
| Artifact domain | Prime `prime-agent-runtime/src/rlm/harness.py`. [P5] | Import concepts and validated records, not concurrent file-writer behavior. |
| Refinement | Prime `packages/coding-agent/src/core/refinement/refinement.ts`; community coordinator wiring. [P6], [C1] | Shared proposal/validation/application coordinator with revision checks. |
| Prompt projection | DSH's system-prompt documentation describes `packages/core/system-prompt/src/index.ts`; community `src/projection.ts` supplies a concrete plugin implementation. [D4], [C2] | Prefer native dynamic context; test request-series preservation and compaction. |
| Recovery | DSH session log/persistence architecture and Prime kernel artifact documentation. [D2], [P4] | Declare recovery levels and reconcile cross-domain receipts. |
| External world | DSH filesystem/subprocess seams and Yggdrasil state separation. [D2], [Y1] | Add an execution-world adapter only after the local contract works. |

The first source modification to DSH should be justified by a missing seam demonstrated in a minimal test. If nested tool execution cannot safely be reused by an external stateful consumer, an upstream adapter API may be better than importing an internal scheduler symbol. Internal symbols used by PTC are evidence of an implementation strategy, not automatically a supported external-plugin ABI.

## 23. Migration from existing Prime workflows

Migration should be capability-by-capability, not a promise that a session file can be renamed and opened in DSH.

First, preserve the original Prime export as an immutable source artifact. Import selected memories and descriptive roles into a candidate scope with their original provenance. Validate executable Python references against the new environment; unavailable packages remain inactive rather than disappearing or being installed automatically.

Second, translate a small set of workflow conventions: current `rlm.spawn` admission handles, explicit replies, model-selection policy and bounded artifact access. Document older `rlm(...)` or `rlm.run` usage as historical input requiring adaptation. The internal Prime wire operation name must not leak into the new public API by accident. [P4]

Third, run a fresh DSH session with an imported brief and selected knowledge view. This is a new continuation, not a bit-exact resume of Prime's agent, Python heap or daemon worker. Preserve links to the original transcript so uncertainty and past evidence remain inspectable.

Finally, compare outcomes and operational behavior against Prime at the pinned revision. Only expand the compatibility surface when a real workflow needs it. A compatibility shim that silently accepts unsupported arguments is worse than an explicit migration error.

## 24. Smallest useful experiment

### 24.1 Hypothesis

A DSH-native persistent Python capability plus a scoped continual-artifact service can reproduce the important RLM and refinement behaviors without replacing DSH's agent loop or bypassing its tool policy.

This is primarily a semantic and integration hypothesis. A separate experiment is needed to show that the added complexity improves task outcomes or cost.

### 24.2 Bounded setup

Use one pinned Linux environment, one pinned DSH profile, a fixed Python environment and a synthetic repository. Use a deterministic mock model/transport for lifecycle tests and a separately budgeted real-model run for behavioral evaluation. Keep all mutable application data inside the declared test workspace. External publishing is disabled.

The synthetic task should contain enough source material to make programmatic filtering useful, a test failure with a discoverable prerequisite and two independent review subtasks. The prerequisite creates an opportunity for a small evidence-backed lesson, but held-out variants must prevent the experiment from merely measuring memorization of one fixture.

### 24.3 Required demonstration

The parent loads a permitted source artifact into a Python variable, transforms it in a later cell and emits only a bounded summary. It spawns two named children, receives admission handles and later consumes their explicit replies. The host attributes their requests to the root budget without adding those requests to parent-context usage.

A guarded nested tool call succeeds, and a denied operation remains denied when attempted through Python, a child role and a stored skill reference. A local refinement proposes the discovered prerequisite, records evidence and creates a new local artifact revision. A fresh continuation with the promoted test view can retrieve that lesson, while an unrelated scope cannot.

Then compact the conversation, recreate the Python kernel, restart the host at a controlled point and replay the session independently. Each transition must report what survived and what was reconstructed. The experiment does not require heap snapshots or VM memory forks.

### 24.4 Comparisons

| Variant | Purpose |
| --- | --- |
| DSH native tools, no continual layer | Basic task and operational baseline. |
| DSH PTC, no persistent kernel | Isolate the value of programmatic tool calling. |
| DSH PTC plus continual artifacts | Test whether persistent Python is actually necessary. |
| DSH persistent Python without refinement | Isolate cross-cell state and recursive execution. |
| DSH persistent Python plus continual artifacts | Test the combined design. |
| Pinned Prime Agent | Behavioral reference, not assumed performance winner. |

Use the same model route, task revisions, tool permissions and total budget where the products permit it. Record unavoidable differences rather than bury them in a score. Repeat stochastic runs and report the distribution, failures and consumed budget, not just the best result.

### 24.5 Observable measurements

Measure task success, invalid tool requests, duplicated external-effect attempts, parent and child usage, refinement overhead, context volume, artifact retrieval volume, restart outcomes, orphaned resources and maximum live fan-out. For real providers, separate reported cache usage from inferred prefix similarity.

A successful first experiment establishes that the integration can express the desired behavior with explicit ownership. It does not establish general intelligence improvement, production hardening, safe arbitrary-code execution or an economic advantage over Prime.

## 25. Conformance and failure-injection plan

The test suite should distinguish deterministic protocol tests, integration tests, adversarial policy tests and model evaluations. A model benchmark cannot substitute for a cancellation test, and a passing typecheck cannot establish crash consistency.

| Property | Failure or adversarial case | Required observation |
| --- | --- | --- |
| Namespace isolation | Two sessions use the same variable names and artifact labels. | No values or unauthorized artifacts cross the session boundary. |
| Serial cell execution | Submit overlapping cells that mutate shared variables. | A declared deterministic order or explicit rejection, not a race. |
| Generation fencing | Deliver an old kernel result after restart. | Stale result rejected and recorded without affecting current state. |
| Bridge robustness | Malformed, oversized and duplicate frames. | Bounded failure; no identity or privilege confusion. |
| Nested tools | Outer Python call invokes exclusive and parallel-safe tools. | No self-deadlock; DSH policy and output validation remain active. |
| Cancellation | Abort during a nested tool, kernel cell or child admission. | Receipt distinguishes request, acceptance and actual quiescence. |
| Spawn semantics | Disconnect immediately after child admission. | Accepted work is either owned or explicitly reconciled; no fabricated completion. |
| Messaging authority | Child addresses a sibling, grandparent or stale parent object. | Current authorization rules reject unsupported relationships. |
| Durable admission | Crash between inbox acceptance and logged message. | Recovery reports or reconciles uncertainty instead of claiming execution. |
| Cost accounting | Child completion is delivered twice after reconnect. | One charge, correct aggregate and unchanged context-size accounting. |
| Artifact concurrency | Two writers propose against one revision. | One valid commit and one conflict, or an explicitly serial equivalent. |
| Corruption | Truncate a state snapshot or lose an artifact blob. | Quarantine or explicit unavailability; no silent empty-success rewrite. |
| Refinement containment | Proposal targets base prompt or unauthorized global scope. | Deterministic rejection before mutation. |
| Skill containment | Memory update names an uninstalled executable package. | No implicit installation or privilege grant. |
| Projection | Compaction removes an unchanged overview. | The active view is restored before the next applicable model request. |
| Request-series integrity | A wrapping pre-step hook changes messages. | `startsRequestSeries` semantics remain intact. |
| Replay | Store contents change after the original request. | Old model-visible history reconstructs the original view. |
| External effects | Crash after a remote write but before its result is logged. | Idempotent reconciliation or explicit uncertain state, never blind retry. |
| Reload/disposal | Replace a plugin with cells and children active. | Admission stops; owned work drains or fails visibly; no orphan bridge. |
| Knowledge revocation | Revoke a lesson used by an earlier run. | Future views exclude it while historical provenance remains inspectable. |
| Budget containment | Children and refiners recursively request more work. | Root limits remain effective across the whole tree and restarts. |

Include negative controls that intentionally bypass a guard or drop a generation check so the tests demonstrate sensitivity. An independent observer should inspect process ownership, persisted receipts and outbound effects rather than trust only the agent's final explanation.

## 26. Staged implementation and exit criteria

**Stage A: seam qualification.** Build a minimal external DSH plugin with one canonical-output tool and one dynamic context contribution. Exercise normal calls, a request-series transition, compaction and unload. Establish whether the required nested-dispatch seam is externally usable. Exit only when the current pinned contracts are understood through tests.

**Stage B: persistent execution.** Add a session-owned Python service with serialized cells, bounded output, host-mediated tools and generation fencing. Support cold recovery only. Exit when two sessions cannot interfere, cancellation reaches quiescence and nested policy cannot be bypassed through the bridge.

**Stage C: recursive delegation.** Adapt continuable children with immediate handles, explicit later replies, exact model policy and aggregate budgets. Exit when admission/restart uncertainty is observable and subtree teardown leaves no unowned resources.

**Stage D: continual artifacts.** Qualify or adapt the existing community implementation. Add revisioned views, single-writer mutation and local-only default application. Exit when concurrent proposals conflict safely, compaction restores the view and executable references do not install code implicitly.

**Stage E: refinement evaluation.** Add bounded automatic triggers and controlled promotion only after manual refinement works. Run the ablation matrix and held-out tasks. Exit when results show the value and overhead of each component, including negative results.

**Stage F: isolated fleet and exploration integration.** Add a qualified execution-world provider and optional Yggdrasil bridge. Exit criteria include credential separation, egress enforcement, identity renewal, effect reconciliation and explicit checkpoint capabilities. Warm snapshots and broad shared knowledge are optimizations or extensions, not prerequisites for the earlier stages.

These are dependency stages, not delivery promises or calendar estimates. A stage can falsify the need for a later one.

## 27. Open questions and reasons to change direction

The most important unresolved question is whether persistent Python materially improves the intended workload over DSH PTC plus artifact handles. If it does not, the simpler stateless baseline should win. The second is whether an external plugin can reuse nested execution safely without depending on unstable internals. A small upstream seam may be preferable to a large compatibility layer.

The community continual plugin needs a concrete integration assessment, especially around current prompt semantics, single-writer storage and conservative promotion defaults. Source inspection identifies questions; a pinned test composition should decide whether to adapt, contribute upstream or replace a component.

Recovery remains a policy choice. Cold reconstruction is simpler and safer to reason about; richer snapshots may save work but introduce compatibility and trust obligations. The design should not promise both effortless recovery and unrestricted interpreter state without measuring what is actually recoverable.

Other questions include how much artifact provenance to retain, how to bound knowledge-view growth, when a project-qualified lesson becomes reusable, how to revoke poisoned knowledge across a fleet, and whether a separate artifact service is justified by deployment scale. None requires a new database by default, but each requires an explicit consistency model.

The proposal should be reconsidered if reproducing basic Prime behavior requires replacing DSH's loop, inbox and persistence together; if policy mediation cannot cover the chosen execution mode; if refinement repeatedly regresses held-out performance; or if operational overhead exceeds the benefit over simply running Prime in a well-isolated workload.

The desired result is not a second Prime with DSH names attached. It is a DSH-native system that preserves the useful semantics: **programmatic working context, real recursive agents, evidence-backed reusable artifacts, and authority that remains outside the mutable behavior of the agent.**

## 28. References and evidence map

All source references below are pinned to the evidence snapshot in section 2. Paths named through an architecture document are documented component locations, not an assertion that every implementation line in that component was independently audited.

### Prime Agent

- **[P1]** [Prime Agent README](https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/README.md): stated RLM/continual abstractions, Pi acknowledgement, Python skills and explicit security warning.
- **[P2]** [Root package manifest](https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/package.json): source workspaces, build ordering and package version.
- **[P3]** [Architecture overview](https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/packages/coding-agent/docs/architecture.md): client, supervisor, worker, session and kernel ownership.
- **[P4]** [RLM runtime architecture](https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/packages/coding-agent/docs/rlm-runtime.md): current `rlm.spawn`, internal `rlm.run` request, admission-only handles, serialization, child registry, usage attribution, persistence and trust model.
- **[P5]** [Python harness-state implementation](https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/prime-agent-runtime/src/rlm/harness.py): four-kind store, scope resolution, skill-reference validation, mtime reload, permissive load recovery and atomic-save path.
- **[P6]** [TypeScript refinement implementation](https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/packages/coding-agent/src/core/refinement/refinement.ts): structured proposals, applied-edit snapshots, scope rules, refinement planner and budget handling.

### Pi

- **[I1]** [Pi SDK implementation](https://github.com/earendil-works/pi/blob/71dca871bc80b6bc97be37f0ca3189399d651fff/packages/coding-agent/src/core/sdk.ts): session construction, model runtime, configurable tool surface, resource loader and session restoration integration.

### DeepSeek Harness

- **[D1]** [DSH README](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/README.md): plugin-oriented foundation and developer-preview status.
- **[D2]** [DSH architecture](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/architecture.md): composition, ownership, event domains, request-series handling, durable model history, persistence and capability seams.
- **[D3]** [Subagent subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/subsystems/subagent.md): one-shot capabilities, continuable admission, activation lifetime, adjacent messaging, cancellation and final-flush qualifications.
- **[D4]** [System-prompt subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/subsystems/system-prompt.md): scoped sections, complete sections, dynamic context and assembly contracts.
- **[D5]** [CodeRuntime service definition](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/packages/code-runtime/code-runtime/src/index.ts): per-run isolation, session independence, informational substrate label and Python-backend publication status.
- **[D6]** [PTC transport implementation](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/packages/core/tools/src/ptc.ts): `run_code`, language-specific presentation, nested execution and curated output.
- **[D7]** [Tool subsystem contracts](https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/subsystems/tools.md): canonical output schemas, tool restrictions, monotonic guards, cancellation, concurrency and nested execution identity.

### Existing DSH continual implementation

- **[C1]** [Community plugin composition and configuration](https://github.com/jasen215/dsh-continual-harness/blob/d4e336a907d47a7e03562bd1710d1529480dadde/src/index.ts): actual store/coordinator/tool/driver wiring, scope and approval choices, diagnostics and skill-materialization configuration.
- **[C2]** [Community plugin prompt projection](https://github.com/jasen215/dsh-continual-harness/blob/d4e336a907d47a7e03562bd1710d1529480dadde/src/projection.ts): digest tracking, pre-step wrapping and surface replacement. The compatibility questions in section 15 are inferences from this source, not reproduced failures.

### Related local exploration

- **[Y1]** [Yggdrasil](yggdrasil.md), particularly sections 3-7 in the 2026-09-11 draft: independent state domains, forward-moving authority, explicit reset capabilities and checkpoint boundaries. The relationship proposed in section 20 does not certify a Workestrate or microVM adapter.

[P1]: https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/README.md
[P2]: https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/package.json
[P3]: https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/packages/coding-agent/docs/architecture.md
[P4]: https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/packages/coding-agent/docs/rlm-runtime.md
[P5]: https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/prime-agent-runtime/src/rlm/harness.py
[P6]: https://github.com/PrimeIntellect-ai/prime-agent/blob/46c60b7500923be9e77022cb85c731241f35e2ac/packages/coding-agent/src/core/refinement/refinement.ts
[I1]: https://github.com/earendil-works/pi/blob/71dca871bc80b6bc97be37f0ca3189399d651fff/packages/coding-agent/src/core/sdk.ts
[D1]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/README.md
[D2]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/architecture.md
[D3]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/subsystems/subagent.md
[D4]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/subsystems/system-prompt.md
[D5]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/packages/code-runtime/code-runtime/src/index.ts
[D6]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/packages/core/tools/src/ptc.ts
[D7]: https://github.com/deepseek-ai/deepseek-harness/blob/c291e7961a515f6d7af9304e7fd1d257929aef26/docs/subsystems/tools.md
[C1]: https://github.com/jasen215/dsh-continual-harness/blob/d4e336a907d47a7e03562bd1710d1529480dadde/src/index.ts
[C2]: https://github.com/jasen215/dsh-continual-harness/blob/d4e336a907d47a7e03562bd1710d1529480dadde/src/projection.ts
[Y1]: yggdrasil.md
