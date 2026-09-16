# Elixir verdict for the control plane

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: recorded verdict, not a prototype.
> Date: 2026-09-16.

**Evidence boundary:** no Elixir service was built for this note.

## Verdict

No Elixir/OTP anywhere in the shipped k0s plus Go plus Workestrate stack. No broker service, no observer, no sidecar.

## Reasons

- Faults live at host, control-plane, and backend level (dead hosts, partitions, VM boot failures). OTP supervises in-VM processes; this stack needs supervision of hosts, VMs, and declared intent, which systemd plus kubelet plus controller-runtime plus etcd already do.
- A broker in Elixir is worse: in-memory budget state does not survive crashes, and making it durable removes the reason to use Elixir. Spawn rates are tens per minute, nowhere near the BEAM sweet spot, and the broker must share Go module types with the operator anyway.
- An observer in Elixir re-implements informers and work queues one hop further from the apiserver. Distributed Erlang fights the default-deny posture and duplicates etcd membership.
- Costs: fourth runtime plus Hex feed, second Nix packaging project against the small-host principle, FFI across the custody boundary, rarer hiring pool.

Revisit only if thousands of concurrent presence-tracked sessions are measured plus a prototype wins past packaging and staffing costs, as a leaf service behind the broker contract, never holding policy or credentials.
