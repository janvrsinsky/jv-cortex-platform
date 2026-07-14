---
title: "Broken draft"
type: memo
tags: important
created: 2026-03-02
---

# Broken draft

This note is deliberately broken to show the linter catching real problems.
Expected violations:

  * filename "Broken_Draft.md" is not kebab-case (uppercase plus underscore)
  * required key "status" is missing
  * type "memo" is not in the allowed vocabulary
  * "tags" is a bare scalar, not a list

The remaining sample notes are clean, so the linter's summary should report
these four issues and nothing else.
