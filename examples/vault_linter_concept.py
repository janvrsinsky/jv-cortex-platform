#!/usr/bin/env python3
"""Clean-room vault linter (concept).

A from-scratch re-creation of the *idea* behind the private vault linter that
keeps thousands of markdown notes structurally honest. It contains none of the
real rules, paths, or content: everything here is generic and runs against
synthetic sample notes shipped alongside this file.

What it checks
--------------
  1. Filename convention .... kebab-case ``a-b-c.md`` (lowercase, digits, hyphens)
  2. Frontmatter presence .... a leading ``---`` fenced YAML block must exist
  3. Required keys ........... ``title``, ``type``, ``status`` must be present
  4. Controlled vocabulary ... ``type`` and ``status`` must be known values
  5. Field shape ............. ``tags`` (if present) must be a list
  6. Style .................. body must not use the em-dash character

Every violation is reported with the file, a severity, and a plain reason.

Usage
-----
    python vault_linter_concept.py [DIRECTORY]

With no argument it lints the bundled ``sample_docs/`` directory next to this
script. Standard library only, no third-party dependencies.

Exit code is 0 when no ERROR-severity violations are found, 1 otherwise, so the
linter is usable as a CI gate.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from typing import List

# Allow running both as "python examples/vault_linter_concept.py" and as an
# imported module, without requiring the package to be installed.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frontmatter_parser import parse_frontmatter, split_frontmatter  # noqa: E402

# The em-dash character, referenced by unicode escape rather than as a literal
# so the linter's own source never contains the glyph it forbids.
EM_DASH = "-"

# Synthetic controlled vocabularies. These are illustrative, not the private
# vault's real taxonomy.
ALLOWED_TYPES = {"project-card", "area", "reference", "note", "log", "system"}
ALLOWED_STATUS = {"active", "paused", "idea", "done", "archived", "inbox"}
REQUIRED_KEYS = ("title", "type", "status")

# kebab-case: one or more lowercase-alphanumeric groups joined by single
# hyphens. Filenames are matched without their ``.md`` suffix.
KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

ERROR = "ERROR"
WARN = "WARN"


@dataclass
class Violation:
    path: str
    severity: str
    rule: str
    message: str


def _check_filename(path: str) -> List[Violation]:
    name = os.path.basename(path)
    stem = name[:-3] if name.endswith(".md") else name
    if not KEBAB_CASE.match(stem):
        return [
            Violation(
                path,
                ERROR,
                "naming",
                "filename is not kebab-case (use lowercase letters, digits, "
                "and single hyphens)",
            )
        ]
    return []


def _check_content(path: str, text: str) -> List[Violation]:
    violations: List[Violation] = []

    raw, _ = split_frontmatter(text)
    if raw is None:
        # Distinguish "no fence at all" from "opened a fence but never closed".
        first_line = text.replace("\r\n", "\n").split("\n", 1)[0].strip()
        if first_line == "---":
            violations.append(
                Violation(
                    path,
                    ERROR,
                    "frontmatter",
                    "frontmatter opens with '---' but is never closed",
                )
            )
        else:
            violations.append(
                Violation(
                    path,
                    ERROR,
                    "frontmatter",
                    "missing frontmatter block (expected a leading '---' fence)",
                )
            )
        return violations

    fields, body = parse_frontmatter(text)

    for key in REQUIRED_KEYS:
        if key not in fields or fields[key] in ("", [], None):
            violations.append(
                Violation(
                    path,
                    ERROR,
                    "required-key",
                    "missing or empty required key '" + key + "'",
                )
            )

    type_value = fields.get("type")
    if isinstance(type_value, str) and type_value not in ALLOWED_TYPES:
        violations.append(
            Violation(
                path,
                ERROR,
                "vocabulary",
                "type '" + type_value + "' is not in the allowed set "
                + str(sorted(ALLOWED_TYPES)),
            )
        )

    status_value = fields.get("status")
    if isinstance(status_value, str) and status_value not in ALLOWED_STATUS:
        violations.append(
            Violation(
                path,
                ERROR,
                "vocabulary",
                "status '" + status_value + "' is not in the allowed set "
                + str(sorted(ALLOWED_STATUS)),
            )
        )

    if "tags" in fields and not isinstance(fields["tags"], list):
        violations.append(
            Violation(
                path,
                WARN,
                "field-shape",
                "'tags' should be a list, for example [a, b] or a block list",
            )
        )

    if EM_DASH in body:
        violations.append(
            Violation(
                path,
                WARN,
                "style",
                "body contains an em-dash; prefer a hyphen or restructured "
                "sentence in human-facing text",
            )
        )

    return violations


def lint_file(path: str) -> List[Violation]:
    """Lint a single markdown file and return its violations."""
    violations = _check_filename(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        return violations + [
            Violation(path, ERROR, "io", "could not read file: " + str(error))
        ]
    violations.extend(_check_content(path, text))
    return violations


def lint_directory(directory: str) -> List[Violation]:
    """Recursively lint every ``.md`` file under ``directory``."""
    all_violations: List[Violation] = []
    for root, _dirs, files in os.walk(directory):
        for filename in sorted(files):
            if filename.endswith(".md"):
                all_violations.extend(lint_file(os.path.join(root, filename)))
    return all_violations


def main(argv: List[str]) -> int:
    if len(argv) > 1:
        target = argv[1]
    else:
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_docs")

    if not os.path.isdir(target):
        print("error: not a directory: " + target)
        return 2

    violations = lint_directory(target)

    if not violations:
        print("OK: no violations found in " + target)
        return 0

    # Group by file for readable output.
    by_file: dict = {}
    for violation in violations:
        by_file.setdefault(violation.path, []).append(violation)

    errors = 0
    warnings = 0
    for path in sorted(by_file):
        rel = os.path.relpath(path, target)
        print(rel)
        for violation in by_file[path]:
            marker = "  [" + violation.severity + "] " + violation.rule + ": "
            print(marker + violation.message)
            if violation.severity == ERROR:
                errors += 1
            else:
                warnings += 1
        print("")

    print("summary: " + str(errors) + " error(s), " + str(warnings) + " warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
