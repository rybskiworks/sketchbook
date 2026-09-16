# Go operator patterns for the fleet operator

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: pattern survey, not an implementation specification.
> Date: 2026-09-16.

**Evidence boundary:** controller-runtime and Kubebuilder documentation as summarized here. No operator was scaffolded for this note.

## 1. Shape

A separate Go repository owns the fleet layer: CRDs, controllers, conformance tests, deployment manifests. It must not live inside the Workestrate Rust tree: the two evolve on different rhythms and the operator may fail or upgrade without taking the local CLI with it. The Workestrate side gains a narrow, versioned integration contract plus a conformance suite both sides run.

## 2. Patterns

- Reconcilers derive actions from current state, not from receiving every watch event. Normal controller-runtime work queues, cancellation, bounded retries.
- Finalizers own safe stop: deletion means stop, and stop is not resurrected against operator intent.
- Status subresources carry observed generation, actual launch identity, effective capabilities, readiness. Desired state and observed state are separate facts.
- CRD versioning (v1alpha1 to v1beta1 to v1 with conversion) from the first schema; closed decisions (module paths, registries, ownership) are ADRs in the owning repo.
- Conformance: the same binary-level contract suite runs against the local CLI backend and the operator backend, so moving a workload changes placement, not semantics.

## 3. Execution order

External-runtime CRDs first, Pod-backed execution later, CRI last. Each phase keeps the same Workestrate contract underneath, so backends change without renegotiating policy custody.
