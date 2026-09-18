# explorations

[Back to sketchbook](../README.md)

This catalogue connects the long-form explorations. Their original bodies and status statements are preserved; being listed here does not endorse every component choice or claim current implementation support.

## reading routes

**Start with the user experience:** [Compartmentalized NixOS workstation](compartmentalized-nixos-architecture-seed.md) explores a NixOS configuration / flake with isolated applications and a coherent desktop. It is a separate system concept that might reuse Workestrate, not a proposal to make Workestrate an operating system.

**Start with the implementation gaps:** [Compartmentalized NixOS enablement](compartmentalized-nixos-enablement-roadmap.md) traces the consumed Microsandbox, libkrun, firmware and tooling sources, identifies relevant upstream graphics proposals, and maps missing integration to testable work packages and issues. It distinguishes existing mechanisms from unqualified desktop, authorization and restore capabilities.

**Start with the infrastructure:** [Shared Nix store fabric](shared-nix-store-microvm-fabric.md) explores immutable store generations, private writable overlays, build/cache placement, storage CoW, and memory-sharing options for dense microVM fleets. These mechanisms need distinct capability and correctness contracts.

**Start with implementation:** [Microsandbox storage and memory enablement](microsandbox-storage-memory-enablement.md) traces the consumed image, block and RAM primitives through to Workestrate. It prioritizes existing layered/reflink storage, then qualified checkpoint lifetimes, optional KSM, reclamation and adoption of newer upstream full-memory branching. Pinned source observations, proposed APIs, implementation issues and unrun acceptance tests remain distinct.

**Start with the evidence:** [Workestrate testing philosophy](workestrate-testing-philosophy.md) explores properties, independent observers, generated histories, fault injection, replay, and minimization. It is a testing direction, not a requirement to adopt Antithesis or deterministic hypervisor execution.

**Start with the agent's exploration:** [Yggdrasil](yggdrasil.md) drafts a time-traveling-agent harness: the agent can request checkpoints, forks and rewinds, retain scoped evidence from its siblings, and trace an evolutionary path toward a solution. Execution is resettable only within a declared boundary; knowledge, authority and external effects have different lifecycles. The draft proposes a storage-first experiment and keeps Clone, forkd and Workestrate adapter capabilities explicitly qualified.

**Start with the agent runtime:** [A continual RLM on DeepSeek Harness](continual-rlm-on-deepseek-harness.md) compares pinned Pi, Prime Agent, DSH and an existing continual-harness plugin. It proposes native composition for persistent Python, recursive children and evidence-backed artifacts while keeping authority, knowledge and recovery boundaries distinct.

**Start with lifecycle and orchestration:** [Workestrate Kubernetes control plane](workestrate-kubernetes-control-plane.md) is a discovery PRD for a Go adapter, with k0s as the reference deployment. It connects local NixOS compartments and remote runtime hosts through declarative lifecycle, explicit recovery modes, bounded agent spawning and capability-gated branching. It distinguishes CRD reconciliation from Pod scheduling and CRI, and keeps storage CoW, RAM CoW and host-owned KSM separate.

**Start with engineering coordination:** [Local agentic engineering control plane](local-agentic-engineering-control-plane.md) proposes one human-facing mainframe coordinating durable domain agents and substantial isolated workloads. It connects selective context access and peer handoff to forge-neutral candidates, progressive deterministic and agentic E2E CI, warm Nix baselines, evidence publication and bounded authority. The Workestrate integration investigation is [#66](https://github.com/rybskiworks/workestrate/issues/66).

## how the threads connect

The workstation sketch describes a possible consumer of isolation and orchestration. Its enablement roadmap identifies implementation seams and qualification gates without making the architecture an accepted product specification. The store sketch investigates one part of making many isolated workloads economical. The testing sketch asks how to establish that lifecycle, policy, persistence, and recovery behave correctly. Yggdrasil investigates agent-directed use of those primitives while retaining what previous attempts learned.

The storage/memory roadmap turns selected questions into component-owned implementation work without making live-memory forks or KSM prerequisites for storage sharing. It does not replace the broader store-lifetime or branching-capability investigations.

The continual-RLM sketch investigates a possible agent substrate and reusable knowledge layer. Yggdrasil could add execution-world branching to that substrate, but persistent Python, conversational forks and VM checkpoints remain different capabilities. Neither exploration assumes an implemented Workestrate adapter.

The engineering-control-plane sketch is a consumer above those boundaries: it owns goals, task routing, CI plans and candidate evidence rather than a new hypervisor or model runtime. Its optional k0s integration reuses the lifecycle investigation in [sketchbook PR #32](https://github.com/rybskiworks/sketchbook/pull/32) and [Workestrate #44](https://github.com/rybskiworks/workestrate/issues/44). The first useful local loop does not require Kubernetes, complete RAM forks or KSM.

The Kubernetes control-plane PRD investigates a common lifecycle interface above those runtime mechanisms. It can serve the workstation and store fabric without owning their desktop or storage implementations, and can expose execution operations to Yggdrasil without owning its learning strategy. Recovery never implies undoing external effects or restoring old authority. Repository placement and deeper Kubernetes integration remain discovery decisions.

They are related investigations, not a single approved architecture. Shared vocabulary should make comparisons easier without forcing every idea into Workestrate.

## new threads

[Open an exploration issue](https://github.com/rybskiworks/sketchbook/issues/new/choose) before investing in a large new note. Record the question, scope, competing options, and the smallest useful evidence. Only add a catalogue entry once a note actually exists.
