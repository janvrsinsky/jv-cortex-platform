# Examples: clean-room vault linter

This directory holds a runnable, from-scratch re-creation of the *idea* behind
the private vault linter that keeps thousands of markdown notes structurally
honest. It contains none of the real rules, paths, or content. Everything here
is generic and runs against synthetic sample notes.

Standard library only. No third-party dependencies, no network access, no
private data.

## Run it

From the repository root:

```bash
python examples/vault_linter_concept.py examples/sample_docs
```

With no directory argument, the linter defaults to the bundled `sample_docs/`
next to the script:

```bash
python examples/vault_linter_concept.py
```

Expected output: the two clean notes pass silently, and the one deliberately
broken note reports its violations, ending with a summary line and a non-zero
exit code (so the linter is usable as a CI gate).

```
Broken_Draft.md
  [ERROR] naming: filename is not kebab-case ...
  [ERROR] required-key: missing or empty required key 'status'
  [ERROR] vocabulary: type 'memo' is not in the allowed set ...
  [WARN] field-shape: 'tags' should be a list ...

summary: 3 error(s), 1 warning(s)
```

## What it checks

| Rule | Severity | Description |
|---|---|---|
| naming | ERROR | Filename must be kebab-case (`a-b-c.md`) |
| frontmatter | ERROR | A leading `---` fenced YAML block must exist and close |
| required-key | ERROR | `title`, `type`, `status` must be present and non-empty |
| vocabulary | ERROR | `type` and `status` must be from the allowed sets |
| field-shape | WARN | `tags`, if present, must be a list |
| style | WARN | Body must not use the em-dash character |

The controlled vocabularies (`ALLOWED_TYPES`, `ALLOWED_STATUS`) and the required
keys are illustrative constants at the top of `vault_linter_concept.py`. They are
synthetic, not the private vault's real taxonomy. Adjust them to fit any
frontmatter schema.

## Files

* **`vault_linter_concept.py`** the linter. Walks a directory, lints every `.md`
  file, groups violations by file, and exits non-zero on any ERROR.
* **`frontmatter_parser.py`** a minimal, dependency-free YAML-frontmatter parser.
  It understands the flat subset of YAML that note frontmatter actually uses
  (scalars, inline lists, block lists, comments, quotes) and nothing more, on
  purpose: a tiny parser is easy to audit and safe to run anywhere. Run it
  directly to see a parse demo:

  ```bash
  python examples/frontmatter_parser.py
  ```

* **`sample_docs/`** three synthetic notes:
  * `quarterly-planning.md` clean, inline-list tags.
  * `onboarding-runbook.md` clean, block-list tags.
  * `Broken_Draft.md` deliberately broken (bad filename, missing `status`,
    unknown `type`, scalar `tags`) so the linter has something to catch.

## Scope

This is a concept re-creation, not the production linter. It demonstrates the
approach (structure enforced by tooling, not by discipline) on public, synthetic
data. See [`../docs/architecture.md`](../docs/architecture.md) for where linting
sits in the wider platform.
