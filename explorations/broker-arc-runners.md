# Broker and on-demand runners on the fleet

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: design sketch, not an implemented service.
> Date: 2026-09-16.

**Evidence boundary:** no broker or runner pool was deployed for this note.

## 1. Broker

Agent-spawned sandboxes go through a broker, not through cluster credentials. The broker mints launch-bound tokens: one operation ID, one budget (time, count, resources), one policy scope. The agent receives the operation ID and an honest result; it never sees host administration or general cluster credentials. Bounded child creation and checkpoint-derived branches are broker policies above the same execution contract, with external effects explicitly outside any undo boundary.

## 2. Runners

Ephemeral CI uses ARC `gha-runner-scale-set` on the fleet cluster: k3s carries this pattern today, and k0s can carry it once its packaging gap is closed. Runner pools are tainted and tolerated so ordinary workloads never land on runner nodes and runners never borrow workload capacity silently. Scale sets bind to the same launch-identity and budget discipline as agent sandboxes; a workflow run is a brokered operation with a different caller. Capability gating (pure, nix, kvm) lets one policy drive several machines: a job whose requirement is missing is skipped with reason, not failed.
