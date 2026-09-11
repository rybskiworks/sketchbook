# explorations

[Back to sketchbook](../README.md)

This catalogue connects the long-form explorations. Their original bodies and status statements are preserved; being listed here does not endorse every component choice or claim current implementation support.

## reading routes

**Start with the user experience:** [Compartmentalized NixOS workstation](compartmentalized-nixos-architecture-seed.md) explores a NixOS configuration / flake with isolated applications and a coherent desktop. It is a separate system concept that might reuse Workestrate, not a proposal to make Workestrate an operating system.

**Start with the infrastructure:** [Shared Nix store fabric](shared-nix-store-microvm-fabric.md) explores immutable store generations, private writable overlays, build/cache placement, storage CoW, and memory-sharing options for dense microVM fleets. These mechanisms need distinct capability and correctness contracts.

**Start with the evidence:** [Workestrate testing philosophy](workestrate-testing-philosophy.md) explores properties, independent observers, generated histories, fault injection, replay, and minimization. It is a testing direction, not a requirement to adopt Antithesis or deterministic hypervisor execution.

## how the threads connect

The workstation sketch describes a possible consumer of isolation and orchestration. The store sketch investigates one part of making many isolated workloads economical. The testing sketch asks how to establish that lifecycle, policy, persistence, and recovery behave correctly.

They are related investigations, not a single approved architecture. Shared vocabulary should make comparisons easier without forcing every idea into Workestrate.

## new threads

[Open an exploration issue](https://github.com/rybskiworks/sketchbook/issues/new/choose) before investing in a large new note. Record the question, scope, competing options, and the smallest useful evidence. Only add a catalogue entry once a note actually exists.
