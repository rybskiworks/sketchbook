# Threat model and fault plan for the fleet

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: plan sketch, not a completed assessment.
> Date: 2026-09-16.

**Evidence boundary:** no red-team exercise or fault injection was run for this note.

## 1. Threats

- Untrusted guests: malicious content, confused deputies, spoofed prompts, stale authorizations, unattended agent actions, unsafe device sharing.
- Broker abuse: budget exhaustion, scope escape, replayed operation IDs, compromised controller issuing placement the host must still refuse.
- Controller and node loss, stale-view overcommit (second launch fails closed with accounting conflict), snapshot restores with identity fencing (no duplicated network or credential identity).

## 2. Fault gates

M0 contract plus conformance-local, M1 one-host truthful status, M2 recovery plus broker, M3 backend parity with measured numbers, M4 multi-host plus ARC. Negative controls stay red on purpose per promotion. Model-vs-final-state checks, replay and minimization, mutation bar for the harness.
