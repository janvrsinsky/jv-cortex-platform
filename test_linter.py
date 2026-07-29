#!/usr/bin/env python3
"""Check for the vault linter example. Standard library only.

The linter is the flagship runnable piece in this repo, and the README describes
what it enforces. This is the check on that description.

It works from both ends. Over the shipped sample docs it pins the exact verdict,
violation for violation, so a rule change shows up as a diff. Rule by rule it
fires each check in isolation on a minimal file, so a rule that quietly stops
working cannot hide behind a fixture that trips a different rule first.

Two of the checks exist because of a real defect. The em-dash rule once held an
ASCII hyphen instead of the em-dash character, which made the linter flag every
hyphenated word while its own comment claimed otherwise. So the rule is checked
in both directions here: an em-dash is flagged, a plain hyphen is not.

Runs offline, needs nothing installed, and exits non-zero on any drift:

    python test_linter.py
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "examples"))

import vault_linter_concept as linter  # noqa: E402
from frontmatter_parser import parse_frontmatter, split_frontmatter  # noqa: E402

SAMPLE_DOCS = _HERE / "examples" / "sample_docs"
LINTER_SOURCE = _HERE / "examples" / "vault_linter_concept.py"

VALID_NOTE = """---
title: "A valid note"
type: reference
status: active
tags: [ops, runbook]
created: 2026-02-11
---

A body with a hyphenated-word and nothing else to complain about.
"""

# What the shipped sample docs are built to produce: one file with one violation
# per rule class, and two files that are clean.
EXPECTED_BROKEN = [
    ("ERROR", "naming"),
    ("ERROR", "required-key"),
    ("ERROR", "vocabulary"),
    ("WARN", "field-shape"),
]
CLEAN_SAMPLES = ("onboarding-runbook.md", "quarterly-planning.md")

_results: list[tuple[str, bool, str]] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    _results.append((label, bool(passed), detail))


def lint_text(text: str, name: str = "a-note.md") -> list:
    """Write one file into a throwaway directory and lint it."""
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return linter.lint_file(str(path))


def rules_of(violations) -> list[tuple[str, str]]:
    return [(v.severity, v.rule) for v in violations]


def note_without(key: str) -> str:
    return "\n".join(
        line for line in VALID_NOTE.splitlines() if not line.startswith(key + ":")
    ) + "\n"


def run_main(target) -> int:
    """Call the example's main() with its output swallowed."""
    with contextlib.redirect_stdout(io.StringIO()):
        return linter.main(["vault_linter_concept.py", str(target)])


def check_the_samples() -> None:
    violations = linter.lint_directory(str(SAMPLE_DOCS))

    broken = [v for v in violations if v.path.endswith("Broken_Draft.md")]
    check("the broken sample trips exactly the documented violations",
          rules_of(broken) == EXPECTED_BROKEN, f"got {rules_of(broken)}")

    for name in CLEAN_SAMPLES:
        clean = [v for v in violations if v.path.endswith(name)]
        check(f"clean sample stays clean: {name}", clean == [], f"got {rules_of(clean)}")

    errors = [v for v in violations if v.severity == linter.ERROR]
    warnings = [v for v in violations if v.severity == linter.WARN]
    check("the sample verdict is 3 errors and 1 warning",
          (len(errors), len(warnings)) == (3, 1),
          f"got {len(errors)} errors, {len(warnings)} warnings")

    check("linting is deterministic",
          rules_of(violations) == rules_of(linter.lint_directory(str(SAMPLE_DOCS))))

    check("every violation names a file, a rule and a message",
          all(v.path and v.rule and v.message for v in violations))


def check_the_rules() -> None:
    check("a valid note passes every rule", lint_text(VALID_NOTE) == [],
          f"got {rules_of(lint_text(VALID_NOTE))}")

    check("rule fires: filename is not kebab-case",
          rules_of(lint_text(VALID_NOTE, "Broken_Draft.md")) == [("ERROR", "naming")])
    check("a kebab-case filename with digits is accepted",
          lint_text(VALID_NOTE, "runbook-2026.md") == [])

    no_fence = lint_text("# Just a heading\n\nNo frontmatter here.\n")
    check("rule fires: missing frontmatter",
          rules_of(no_fence) == [("ERROR", "frontmatter")]
          and "missing frontmatter block" in no_fence[0].message,
          f"got {rules_of(no_fence)}")

    unclosed = lint_text("---\ntitle: \"Unclosed\"\ntype: note\nstatus: active\n")
    check("an unclosed fence is reported as its own case",
          rules_of(unclosed) == [("ERROR", "frontmatter")]
          and "never closed" in unclosed[0].message,
          f"got {rules_of(unclosed)}")

    for key in ("title", "type", "status"):
        got = rules_of(lint_text(note_without(key)))
        check(f"rule fires: required key missing ({key})",
              ("ERROR", "required-key") in got, f"got {got}")

    check("rule fires: type outside the vocabulary",
          rules_of(lint_text(VALID_NOTE.replace("type: reference", "type: memo")))
          == [("ERROR", "vocabulary")])
    check("rule fires: status outside the vocabulary",
          rules_of(lint_text(VALID_NOTE.replace("status: active", "status: pending")))
          == [("ERROR", "vocabulary")])

    check("rule fires: tags is not a list",
          rules_of(lint_text(VALID_NOTE.replace("tags: [ops, runbook]", "tags: ops")))
          == [("WARN", "field-shape")])

    # The defect this file exists for, checked in both directions.
    em_dash_body = VALID_NOTE.replace("hyphenated-word", "an aside " + linter.EM_DASH + " like this")
    check("rule fires: an em-dash in the body",
          rules_of(lint_text(em_dash_body)) == [("WARN", "style")],
          f"got {rules_of(lint_text(em_dash_body))}")
    check("a plain hyphen in the body is not an em-dash",
          lint_text(VALID_NOTE) == [])
    # Referenced by escape, not as a literal, for the same reason the linter does
    # it: neither of these files should contain the glyph it forbids.
    check("the em-dash constant is the em-dash character",
          linter.EM_DASH == "\u2014" and len(linter.EM_DASH) == 1)
    check("neither the linter nor this check carries an em-dash glyph",
          all(linter.EM_DASH not in path.read_text(encoding="utf-8")
              for path in (LINTER_SOURCE, pathlib.Path(__file__))))


def check_the_exit_codes() -> None:
    # Severity decides the exit code: an error fails the run, a warning does not.
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "clean-note.md").write_text(VALID_NOTE, encoding="utf-8")
        check("a clean directory exits 0", run_main(root) == 0)

        (root / "warned-note.md").write_text(
            VALID_NOTE.replace("tags: [ops, runbook]", "tags: ops"), encoding="utf-8")
        check("a warning alone still exits 0", run_main(root) == 0)

        (root / "bad-note.md").write_text(
            VALID_NOTE.replace("type: reference", "type: memo"), encoding="utf-8")
        check("an error exits 1", run_main(root) == 1)

        check("a target that is not a directory exits 2",
              run_main(root / "clean-note.md") == 2)


def check_the_parser() -> None:
    fields, body = parse_frontmatter(VALID_NOTE)
    check("the parser reads scalars and inline lists",
          fields["title"] == "A valid note" and fields["tags"] == ["ops", "runbook"],
          f"got {fields}")
    check("the parser keeps the body out of the fields",
          "hyphenated-word" in body and "title" not in body)

    raw, _rest = split_frontmatter("# No fence\n")
    check("the parser reports no fence rather than guessing", raw is None)


def main() -> int:
    print("Vault linter check")
    print("-" * 62)

    check_the_samples()
    check_the_rules()
    check_the_exit_codes()
    check_the_parser()

    for label, passed, detail in _results:
        mark = "PASS" if passed else "FAIL"
        line = f"  [{mark}] {label}"
        if not passed and detail:
            line += f"  ->  {detail}"
        print(line)

    failed = [label for label, passed, _detail in _results if not passed]
    print("-" * 62)
    print(f"{len(_results) - len(failed)}/{len(_results)} checks passed.")
    if failed:
        print("Linter drift. The rules no longer match what the README describes.")
        return 1
    print("Every rule fires where it should, and stays quiet where it should not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
