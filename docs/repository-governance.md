# Repository governance and protection rollout

Status: reviewed proposal and activation guide, not a receipt of live changes.
Inspection date: 2026-09-11.

## Scope and review baseline

This follow-up builds on [curation PR #5](https://github.com/rybskiworks/sketchbook/pull/5)
at commit `4530fbe2f91b796444b774983ed3d3672c4bf0e8`. That work moves the original
notes into `explorations/`, adds a human README and themed assets, and introduces
offline checks and read-only CI. This follow-up preserves that work rather than
reorganizing it again.

The remaining gaps addressed here are the human/agent documentation split, local
review ownership, staged branch policy, discoverability from old note URLs and
checker regressions. The three legacy paths now contain navigation stubs, not
duplicate source documents. Old heading fragments are not preserved by those
stubs; historical commit permalinks remain the accurate way to cite old content.

At inspection, the repository ruleset listing including parent rules returned an
empty list, and the branch listing reported `main` as not protected. The classic
branch-protection endpoint returned HTTP 403, so its detailed configuration could
not be inspected. The connected GitHub App's published permission set lacks
Administration, even though the acting user has repository admin permission.
These are distinct authorization layers. No live protection or repository setting
was changed by this follow-up.

Do not use this dated snapshot as a permanent statement about live settings.
Re-read repository and inherited organization rules immediately before activation.

## Documentation responsibilities

[README.md](../README.md) is the human front door.
[README.agents.md](../README.agents.md) is optional repository architecture and
reading context. [AGENTS.md](../AGENTS.md) is concise operational guidance, not a
second copy of either README. A subagent should load broader context only when
its task needs it.

Canonical explorations stay in `explorations/`. Maintenance documentation stays
in `docs/`; policy payloads stay in `.github/rulesets/`. Local CODEOWNERS routes
review to `@georgrybski`, whose write/admin access was verified during inspection.
CODEOWNERS alone does not require approval. Organization community guidance is
reused through links rather than copied into competing local policies.

## Staged rulesets

Every JSON file in [.github/rulesets](../.github/rulesets/) is a repository-scoped
GitHub REST payload with `enforcement: disabled`. Importing one unchanged still
does not enforce it. No workflow applies these files and no admin credential
belongs in the repository or Actions.

| File | Proposed policy when explicitly activated | Prerequisite |
| --- | --- | --- |
| `default-integrity.json` | Prevent default-branch deletion and non-fast-forward updates; no bypass. | Compare inherited integrity rules first; do not duplicate adequate organization policy. |
| `upstream-integrity.json` | Prevent deletion/force pushes under both `upstream/*` and nested `upstream/**/*`; allow ordinary fast-forward synchronization. | Relevant if upstream tracking refs are introduced; do not freeze their normal updates. |
| `main-pr.json` | Require PRs and resolved review threads on the default branch. | Verify a maintainer can merge through the intended workflow. |
| `main-ci.json` | Require the strict, up-to-date `Documentation integrity` check. | Observe a successful run and bind the actual app ID before activation. |
| `main-merge-authority.json` | Restrict default-branch updates to the explicitly named operator via a narrowly scoped bypass. | Verify the user ID and test interaction with the independent PR and integrity rules. |

The PR rule deliberately requests zero approving reviews initially. A sole
maintainer cannot approve their own PR; blindly requiring one independent review
can deadlock normal maintenance. Zero approvals is not a human-approval guarantee.
The separate merge-authority proposal restricts who can merge without providing a
bypass to the independent PR, CI or integrity rules. Strengthen reviewer counts
and code-owner approval after a second eligible reviewer exists and the intended
workflow has been tested.

The merge-authority payload names GitHub user ID `118467860` (`georgrybski`),
verified from repository issue/PR metadata. It uses the current REST `User` bypass
actor type. Confirm that the live service accepts that actor for this repository
before enabling the rule; do not replace it with an invented team ID or broad
integration bypass. Its `always` bypass applies only to the separate update
restriction, not to other rulesets.

An agent using the human operator's credentials is indistinguishable from that
operator at this boundary. A branch prefix is not an ACL. Use a separate machine
identity with only the required repository access before claiming human-only
merge authority. Never give that machine identity the operator's bypass, admin
permission or a broad organization-owner credential.

`main-ci.json` has a deliberately unbound `integration_id: null` while disabled.
It is a staging template, not ready-to-enable source authentication. Replace null
with the ID observed on the successful check run. Do not infer an ID from an app's
name, use another repository's custom check identity, or enable a required check
before it can report. Review status context names before renaming a workflow/job.

## Activation sequence for an authorized administrator

First merge the curation and governance file changes through review. Retarget
stacked follow-up PRs to `main` after their base PR merges; inspect their diffs
again, especially after a squash merge. Do not merge a stacked PR into another
agent's branch merely to make the stack disappear.

Inspect the current repository rules, inherited organization rules, classic
protection, available plan features, merge methods and the actor's permissions.
Keep a private before-state export. The organization already has reusable policy
material in [rybskiworks/.github](https://github.com/rybskiworks/.github/tree/main/rulesets)
and a [read-only-plan/additive-integrity helper](https://github.com/rybskiworks/.github/blob/main/scripts/rulesets.py).
Prefer adequate inherited rules rather than maintaining equivalent layers here.
Do not repurpose the helper to enable unrelated staged rules automatically.

Run the documentation workflow on the reviewed default-branch state. Confirm its
check name, successful conclusion and app identity, as well as normal PR execution.
The workflow already includes `merge_group` for a future merge queue, but enabling
a queue is not part of this proposal.

Import the chosen payloads disabled, one at a time, through Settings > Rules or
an authorized API client. For example, after checking that the name does not
already exist, this imports only the disabled integrity definition:

```sh
gh api --hostname github.com --method POST \
  -H 'Accept: application/vnd.github+json' \
  repos/rybskiworks/sketchbook/rulesets \
  --input .github/rulesets/default-integrity.json
```

Record each returned ruleset ID. A lost response is an unknown outcome: read the
live list before retrying rather than creating duplicate named rules. Do not
blindly overwrite existing rulesets by name or remove stricter inherited policy.

Review the live payloads, then activate integrity and PR gates first. Activate the
CI gate only after binding the observed app identity and checking its availability.
Activate operator-only update authority only after confirming the actor and its
interaction with the other rules. Use a disposable repository or temporary test
scope for denied-operation probes; never test protection by trying to delete or
force-push the real default branch.

Read every activated rule back and record its ID, scope, exact policy, actor,
time and verification outcome in an administrative receipt. Committed JSON and
successful REST writes alone are not evidence that the intended branches and
actors are covered. Keep secrets and sensitive account details out of receipts
published here.

If a new gate blocks intended maintenance, change only that gate with authorized
admin access and document why. Keep deletion/non-fast-forward integrity intact;
do not solve a missing CI check by disabling all protections. No automation in
this PR changes or rolls back live settings.

## Deliberately not enabled here

There is no visibility change, collaborator cleanup, branch deletion, forced
history rewrite, mandatory signed-commit policy, release/tag automation or switch
of allowed merge methods. Signed commits need a tested author/bot signing path
before enforcement. Sketchbook is a notebook, not yet a versioned software package.
Repository-description and topic cleanup can be done by an authorized administrator
without pretending that the old demo description is part of its architecture.

The documentation workflow remains read-only, SHA-pinned, bounded and without
persisted checkout credentials. Do not use `pull_request_target` to execute PR
content with write/admin authority. Required checks still execute proposed code;
human review of workflow/checker changes remains necessary.

## Verification and references

Run the contribution guide's commands. The added regression suite checks staged
policy shape, inert enforcement, branch scopes, narrowly confined bypasses and the
CI context, as well as the documentation checker's new edge cases. These are local
contract checks, not API validation or live-enforcement tests. GitHub's server is
the authority for which payloads a repository's current plan and permissions accept.

Primary references, inspected 2026-09-11:

- [Available rules and their interactions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Repository rules REST schema and permissions](https://docs.github.com/en/rest/repos/rules)
- [GitHub Actions secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use)
