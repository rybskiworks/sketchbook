# Fleet CRD design: Workload, host, operation, checkpoint

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: API sketch, not an installed schema.
> Date: 2026-09-16.

**Evidence boundary:** no schema was applied to any cluster for this note. Names and fields are illustrative.

## 1. Resources

- `Workload`: one logical runtime slot (immutable template identity, desired lifecycle, resources, policy refs, placement constraints, persistence and recovery policy).
- `RuntimeHost`: operator-enrolled capacity and capabilities. Not automatically a Kubernetes Node. Host deny beats fleet allow, always.
- `WorkloadOperation`: one durable action (checkpoint, restore, fork request) with operation ID, generation, expected version, payload digest.
- `Checkpoint`: immutable manifest plus retention evidence, never VM dumps or secrets.

## 2. Rules

- Launch identity per workload plus monotonically fresh generations; stale generations rejected.
- Finalizers own safe stop; deletion means stop.
- Break-glass local stop writes a fence (cordon plus fence taint, credential revocation) so reconcile never revives; rejoin is an explicit host action.
- Deliberate stops and completed tasks are never revived; revive paths (adopt, restart, cold boot, supported restore, fenced replacement) are never silently substituted for one another.
- Brokered agent requests carry launch-bound auth, delegated templates, namespace scope, atomic budgets, depth/rate/TTL limits, revocation. No general cluster credentials in guests.
