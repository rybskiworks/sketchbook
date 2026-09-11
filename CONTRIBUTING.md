# contributing to sketchbook

A useful question is enough to start. This repository is a shared place to think, not a promise to implement every idea.

## issue or note?

Use an **issue** to propose an investigation, discuss scope, collect leads, or identify a gap in an existing exploration. Use a **note** when there is an argument, comparison, experiment, or body of evidence worth preserving. Change repository files through a **pull request**.

Before opening a new thread, check the [catalogue](explorations/README.md) and [issues](https://github.com/rybskiworks/sketchbook/issues). Extend a related note rather than creating a competing version of the same investigation.

## where things go

| Location | Purpose |
| :--- | :--- |
| `explorations/<descriptive-slug>.md` | One durable investigation per subject. |
| `assets/` | Small, self-contained illustrations and diagrams. |
| `templates/exploration.md` | A starting structure for a new note. |
| Issues | Questions, scope, research tasks, and discussion. |
| Pull requests | Reviewable changes to notes, navigation, and tooling. |

Use lowercase, hyphenated filenames. Keep the root small. Do not add empty topic folders, speculative placeholder documents, binary screenshots of text, or a site build merely to publish Markdown. A focused executable experiment can live beside a note when its dependencies, safety boundaries, and reproduction steps are explicit.

## what makes a useful exploration

Start from the [template](templates/exploration.md), keeping only the sections that help. Include a clear question and scope, assumptions and non-goals, at least the meaningful alternatives, unresolved questions, and references. For security-sensitive ideas, identify the trust boundaries and failure modes before declaring a design safe.

Separate **observed behavior**, **documented capability**, **inference**, and **proposal**. Prefer primary sources. For claims about code, record the repository, branch, commit, and inspection date. Do not assume a project's default branch is its current development edge, and do not silently turn an aspirational API into an implemented capability.

For experiments, describe the setup, version pins, measurement method, result, and limits. A benchmark without an interpretable baseline is not a conclusion. Never commit credentials, private user data, live production snapshots, or sensitive traces.

Write normally. Keep headings descriptive, examples copyable, and terminology consistent. Prefer ordinary punctuation and avoid ornamental prose. Existing notes do not need a wholesale rewrite merely to match a template.

## status without ceremony

A short status line is enough. Useful descriptions include **seed**, **exploration**, **distilled**, and **archived**. These are descriptions, not a mandatory pipeline or approval process. Existing, more specific status wording is fine.

A distilled note records what survived investigation and what remains uncertain. An archived note records why it stopped or what superseded it. Neither should erase useful rationale. Accepted ADRs, product requirements, and implementation work belong in their owning projects, with links in both directions.

## links and illustrations

Use relative links for other files here. Add new notes to the root catalogue and the reading guide. Update incoming repository links when moving files; warn reviewers about old branch-based URLs that external readers may have saved. A commit permalink remains the right citation for a historical version.

Keep SVGs editable and self-contained. Provide a title, description, descriptive image alt text, and readable contrast. Avoid scripts, animation, external fonts, remote resources, and `foreignObject`. Keep important information in the surrounding Markdown too. The [asset notes](assets/README.md) describe the current light/dark pairs.

## checks

Python 3.10+ and Git are sufficient; no package installation is needed:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_docs.py
```

The checker covers local file targets in ordinary inline/reference Markdown links and HTML `href`, `src`, and `srcset` attributes. It ignores fenced examples, inline code, remote URLs, and URL fragments. It checks SVG XML, basic accessibility metadata, and accidental active/external content. It is deliberately not a complete CommonMark parser, an anchor checker, an external-link crawler, or a security sanitizer.

CI runs the same commands with read-only repository permissions. Review references and inspect the rendered README in both themes before merging; a passing structural check does not establish the truth of an architectural claim.
