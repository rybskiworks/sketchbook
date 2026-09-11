# Repository governance and protection rollout

Status: staged proposal and activation guide, not a receipt of live changes.
Inspection date: 2026-09-11.

## Review baseline and delivery

[Curation PR #5](https://github.com/rybskiworks/sketchbook/pull/5) was
squash-merged to `main` at `73efa2fc872ce1992cb367daf90e53af6a957504`.
[Governance PR #12](https://github.com/rybskiworks/sketchbook/pull/12) then
merged into its curation-branch base, not `main`.
[PR #13](https://github.com/rybskiworks/sketchbook/pull/13) carried its file
tree to a main-targeted proposal. The corrective follow-up preserves that
content while fixing CI-payload shape and documentation path checks.

Use the current main-targeted corrective PR, not the already-merged branch PR,
to deliver these changes. Confirm its base is `main` and inspect the actual diff
before merging. GitHub's merged badge does not mean a change reached the default
branch when the PR targeted something else. Keep the separate
[Yggdrasil draft #14](https://github.com/rybskiworks/sketchbook/pull/14) independently
reviewable. Neither proposal needs to merge into the other's feature branch.

The curation's layout, SVGs and original technical explorations are preserved.
The three legacy note paths contain navigation stubs, not duplicate documents.
They preserve file discovery, not old heading fragments; use commit permalinks
for historical content.

## Documentation responsibilities

[README.md](../README.md) is the human front door.
[README.agents.md](../README.agents.md) provides optional repository context.
[AGENTS.md](../AGENTS.md) contains concise operating instructions. Load broader
context according to the task rather than making every subagent read all notes.

Canonical investigations stay in `explorations/`, maintenance documentation in
`docs/`, and proposed policies in `.github/rulesets/`. Local CODEOWNERS routes
review to `@georgrybski`; its admin/write access was checked during the initial
review. CODEOWNERS alone does not require approval.

## Observed access and live-state limits

During the initial review, the accessible ruleset listing including parent rules
was empty and the branch listing reported `main` unprotected. Classic protection
inspection returned HTTP 403. The connected GitHub App lacks Administration
permission even though the acting user has repository admin access. These are
different authorization layers. No live protection, repository setting or
organization policy was changed by these PRs.

This is a dated observation, not an enduring claim about current settings.
Re-read live repository and inherited rules immediately before activation.
GitHub documents repository-ruleset creation as requiring Administration write
access [R1]. Do not add an administration credential to Actions to work around
connector permissions.

## Disabled policy definitions

Every file in [.github/rulesets](../.github/rulesets/) is repository-scoped and
uses `enforcement: disabled`. Committing a file does not import it; importing it
unchanged does not enforce it. There is no automatic application workflow.

| File | Intended policy after explicit activation | Prerequisite |
| --- | --- | --- |
| `default-integrity.json` | Block deletion and non-fast-forward updates to the default branch, with no bypass. | Reuse adequate inherited rules rather than duplicating them. |
| `upstream-integrity.json` | Block deletion and force pushes for `upstream/*` and nested `upstream/**/*`; allow normal fast-forward updates. | Needed only if upstream tracking refs are used. |
| `main-pr.json` | Require PRs and resolved review threads. | Verify the intended maintainer workflow. |
| `main-ci.json` | Require the strict, up-to-date `Documentation integrity` check. | Observe a successful run and bind its actual source app first. |
| `main-merge-authority.json` | Restrict default-branch updates to the named operator. | Verify the actor and interaction with independent PR, CI and integrity gates. |

The initial PR rule requests zero approving reviews: a sole maintainer cannot
approve their own PR. This is not a human-approval guarantee. Increase the count
and require code-owner approval once another eligible reviewer exists and the
workflow has been tested.

The separate update restriction names user ID `118467860` (`georgrybski`).
GitHub's current REST schema supports the `User` bypass actor type [R1]. Verify
that ID and server acceptance before activation. The `always` bypass belongs
only to that update restriction; it provides no bypass of the independent PR,
CI or integrity rules. Do not replace it with an invented team or a broad bot
bypass. An agent using the operator's credential is still the operator as far
as GitHub is concerned. A branch prefix is not an ACL. Use a separate machine
identity without admin permission or the operator's bypass for meaningful
separation.

The disabled CI definition intentionally **omits `integration_id`**. GitHub
documents this field as an optional integer, not a nullable field [R1]. When it
is omitted the definition does not bind a source app. Before activation, add the
positive integer ID observed on a successful `Documentation integrity` check
run. This prevents accepting the same context from an unexpected publisher [R2].
Do not activate the unbound template or invent an ID from an app name. Source
binding does not prove which workflow produced a check: review workflow changes
and duplicate job names too. A required check that cannot report can block merges.

## Activation by an authorized administrator

1. Review and merge the main-targeted file changes. Inspect live repository and
   inherited rules, classic protection, plan capabilities, merge methods and
   actor permissions. Save a private before-state export. Prefer adequate
   organization rules from [rybskiworks/.github](https://github.com/rybskiworks/.github/tree/main/rulesets).
   Its [additive-integrity helper](https://github.com/rybskiworks/.github/blob/main/scripts/rulesets.py)
   is not a general activator for these staged policies.
2. Obtain a successful documentation run on the reviewed state and confirm normal
   PR execution, the exact check name and source app ID. Inspect check runs on
   both the PR head and test-merge commit when relevant, plus workflow runs by
   branch/event. An empty head-only query is not proof that no CI ran. Keep a
   recorded commit, run/check ID and conclusion rather than assuming green.
3. Compare existing policy names and semantics. Import only the necessary disabled
   payloads, one at a time, and record each returned ID. Never blindly overwrite
   an existing rule or remove stricter inherited policy. An unknown write outcome
   requires a read before retry, not another create request.
4. Review the imported definitions. Activate integrity and PR gates first. Bind
   the observed CI app before enabling the CI gate. Enable operator-only update
   authority only after verifying its interaction with those separate rules.
5. Read back each activated rule and record scope, policy, actor, time and outcome.
   Test allowed and denied actions in a disposable repository or temporary scope,
   never by deleting or force-pushing the real default branch. Confirm intended
   maintainers can still merge. A successful API write alone is not proof of
   correct coverage or enforcement.

For example, after verifying no conflicting definition exists, this command
imports only the disabled integrity payload:

```sh
gh api --hostname github.com --method POST \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/rybskiworks/sketchbook/rulesets \
  --input .github/rulesets/default-integrity.json
```

If a new gate prevents intended maintenance, change only that gate with authorized
admin access and record the reason. Keep deletion/force-push integrity intact;
a missing CI result does not justify disabling every protection. Keep secrets
and sensitive account data out of any published receipt.

## Checks and deliberate limits

Run the [contribution checks](../CONTRIBUTING.md#checks). The Git index supplies
file names; source bytes come from the working tree. Stage additions/removals
and inspect the staged diff separately. The checker rejects untracked local
targets, symlinked sources and targets, non-finite SVG dimensions and unresolved
SVG references. It rejects lexical symlinks before resolution and reports target
resolution failures as diagnostics. Both Markdown and SVG paths receive checks.

These are offline documentation checks, not a CommonMark parser, external-link
crawler, anchor validator, technical fact checker or hostile-filesystem sandbox.
They assume the checkout is not being mutated concurrently. Regression tests and
policy-contract tests do not establish live GitHub API acceptance or enforcement.
Report exactly which local tests, corpus checks and hosted runs were observed.

No PR here changes visibility, collaborators, allowed merge methods, release
settings or signing requirements. There are no branch deletions or history
rewrites. Signed-commit rules need a tested author/bot signing path before use.
The existing workflow stays read-only, SHA-pinned and bounded, with checkout
credentials unpersisted. Do not execute PR code with privileged
`pull_request_target` authority [R3]. Required checks also run proposed code;
human review of changes to the checker and workflow remains necessary.

## Primary references

Inspected 2026-09-11. These describe the API and behavior, not this repository's
live enforcement state.

- [R1: Repository rules REST schema and permissions](https://docs.github.com/en/rest/repos/rules)
- [R2: Available rules and required-check source binding](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [R3: GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use)
