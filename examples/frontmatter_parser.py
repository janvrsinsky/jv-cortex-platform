"""Minimal YAML-frontmatter parser (standard library only).

This is a deliberately small, clean-room parser. It understands the subset of
YAML that a markdown note's frontmatter actually uses:

  * a leading ``---`` fence, a trailing ``---`` fence
  * ``key: value`` scalar pairs
  * inline flow lists: ``tags: [a, b, c]``
  * block lists:
        tags:
          - a
          - b
  * ``#`` comments and simple quotes around scalars

It is NOT a general YAML engine (no anchors, no nested maps, no multiline
scalars). That is on purpose: frontmatter should stay flat and queryable, and a
tiny parser with no dependencies is easy to audit and safe to run anywhere.

The public surface is two functions:

    split_frontmatter(text)  -> (raw_frontmatter_or_None, body)
    parse_frontmatter(text)  -> (dict_of_fields, body)
"""

from __future__ import annotations

from typing import Optional, Tuple

FENCE = "---"


def split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    """Split a document into (raw frontmatter block, body).

    Returns ``(None, text)`` when the document does not open with a ``---``
    fence on its first line. The returned frontmatter string excludes the two
    fence lines; the body is everything after the closing fence.
    """
    # Normalise line endings so a CRLF file behaves like an LF file.
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalised.split("\n")

    if not lines or lines[0].strip() != FENCE:
        return None, text

    for index in range(1, len(lines)):
        if lines[index].strip() == FENCE:
            frontmatter = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1:])
            return frontmatter, body

    # Opening fence with no closing fence: treat the whole thing as body so the
    # linter can report a "malformed frontmatter" violation rather than crash.
    return None, text


def _strip_inline_comment(value: str) -> str:
    """Drop a trailing ``# comment`` that is not inside quotes."""
    in_single = False
    in_double = False
    for position, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            # A comment marker must be preceded by whitespace to count.
            if position == 0 or value[position - 1].isspace():
                return value[:position]
    return value


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_flow_list(value: str) -> list:
    inner = value.strip()[1:-1]  # drop the surrounding brackets
    if not inner.strip():
        return []
    return [_unquote(item) for item in inner.split(",") if item.strip()]


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Parse frontmatter into a dict of fields and return ``(fields, body)``.

    Values are strings, or lists of strings for list-valued keys. Unknown or
    malformed lines are skipped rather than raising, so one bad line does not
    hide the rest of the fields from the linter.
    """
    raw, body = split_frontmatter(text)
    if raw is None:
        return {}, body

    fields: dict = {}
    current_list_key: Optional[str] = None

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Block-list continuation: "  - value" under a bare "key:" line.
        if stripped.startswith("- ") and current_list_key is not None:
            item = _unquote(_strip_inline_comment(stripped[2:]).strip())
            fields.setdefault(current_list_key, [])
            fields[current_list_key].append(item)
            continue

        if ":" not in stripped:
            current_list_key = None
            continue

        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = _strip_inline_comment(rest).strip()

        if rest == "":
            # Bare "key:" opens a possible block list.
            current_list_key = key
            fields[key] = []
            continue

        current_list_key = None
        if rest.startswith("[") and rest.endswith("]"):
            fields[key] = _parse_flow_list(rest)
        else:
            fields[key] = _unquote(rest)

    # A key that opened a block list but collected nothing stays an empty list;
    # that is a legitimate "declared but empty" signal for the linter.
    return fields, body


if __name__ == "__main__":
    sample = (
        "---\n"
        "title: \"Example note\"\n"
        "type: reference\n"
        "tags: [alpha, beta]\n"
        "status: active  # inline comment\n"
        "---\n"
        "# Body starts here\n"
    )
    parsed, remainder = parse_frontmatter(sample)
    print("fields:", parsed)
    print("body:", repr(remainder))
