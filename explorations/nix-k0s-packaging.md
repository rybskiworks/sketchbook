# Nix packaging for k0s and the Go operator

[Catalogue](README.md) | [Workestrate investigation #44](https://github.com/rybskiworks/workestrate/issues/44)

> Status: packaging survey, not a tested build.
> Date: 2026-09-16.

**Evidence boundary:** no Nix build was performed for this note.

## 1. k0s

nixpkgs provides no k0s package or module, so choosing k0s means owning a flake-built binary plus hand-maintained systemd units and tracking upstream releases explicitly. Per-host-role closures (controller, worker, agent host) are declared in Nix; Nix remains responsible for pinned construction and deployment inputs and the operator never builds host closures itself. k3s is the low-friction path because nixpkgs already provides `services.k3s`; the pick guide in the comparison note records when each wins.

## 2. Go operator

Standard Nix Go packaging (`buildGoModule` with vendored deps or `gomod2nix`), pinned Go toolchain following the single nixpkgs/fenix authority, flake outputs for the operator binary, CRD manifests, conformance runner, and NixOS modules per host role. Dev shells carry Go plus controller-runtime generators, never host secrets.
