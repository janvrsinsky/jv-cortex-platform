# MCP layer

The MCP layer is how AI agents read and write the vault. It is the single seam
between a language model and the files, and it is where the platform's safety
guarantees are actually enforced. This document describes the tool contracts and
the guard behavior conceptually. It contains no private content, no real paths,
and no credentials.

## Why a tool layer at all

The tempting shortcut is to give an agent a filesystem: let it open, edit, and
delete files directly. That fails on three counts.

* **No audit surface.** Raw file writes leave no structured record of what an
  agent did or why.
* **No bounds.** A model with filesystem access can touch anything, including
  things far outside the task.
* **No reversibility contract.** A destructive mistake is indistinguishable from
  a legitimate edit until the damage is noticed.

A typed tool layer fixes all three. Agents get a small set of named tools with
declared inputs and outputs; every call is observable; and the write path is
guarded so that dangerous operations are simply not expressible.

The platform uses the [Model Context Protocol](https://modelcontextprotocol.io)
for this. MCP gives each tool a typed schema the model can call against, and it
keeps the vault access server-side rather than in the model's hands.

## Tool surface

The server exposes a deliberately small allowlist. The exact set evolves, but it
stays in three families. Names and signatures below are illustrative.

### Read-side tools

* **`search_notes(query, filters)`** returns note references (path, title, and
  the matched frontmatter fields) for notes matching a text query and optional
  frontmatter filters (for example a type or a status). It returns references,
  not full bodies, so a broad search stays cheap and the agent pulls only what
  it needs.
* **`read_note(ref)`** returns the frontmatter and body of a single note. This is
  the only way an agent obtains full note content.
* **`list_folder(ref)`** enumerates notes under a location, for orientation.

Read-side tools are unguarded beyond scoping: they cannot mutate anything, so
the only concern is that they stay within the vault root, which the server
enforces by resolving and checking every path.

### Write-side tools

* **`write_note(ref, frontmatter, body)`** creates or updates a note. This is the
  guarded path (see below).
* **`append_log(ref, entry)`** appends an entry to a note's log section without
  rewriting the rest of the note. Append-only writes are the common case for
  capture, and keeping them separate from full rewrites narrows the blast radius
  of the guarded write path.
* **`archive_note(ref)`** moves a note into an archive location with a dated
  prefix. Crucially, there is no `delete_note`. The write surface can archive but
  cannot destroy (see [The no-delete invariant](#the-no-delete-invariant)).

### Housekeeping tools

* **`propose_change(ref, rationale)`** records a suggested edit for the human to
  review rather than applying it, used when an agent notices something out of
  scope.
* **`flag_stale(ref, reason)`** marks a record as suspect so a later pass or the
  human can reconcile it, instead of the agent silently rewriting state.

## The write guard

Every call to `write_note` passes through a guard before anything touches disk.
The guard is code, not prompt text, so it holds regardless of what a model was
told. Conceptually it enforces:

1. **Path containment.** The target resolves inside the vault root. Any path that
   escapes the root (through traversal or a symlink) is rejected.
2. **Frontmatter validity.** The write must carry the required frontmatter keys
   with values from the controlled vocabularies, so an agent cannot create a note
   that the linter would immediately flag. This is the same rule set the
   clean-room linter in [`examples/`](../examples/README.md) demonstrates.
3. **No blind overwrite of unrelated content.** A full-body write to an existing
   note is checked against what the agent claims to be editing; append-style
   updates use `append_log` instead so routine capture never rewrites a whole
   note.
4. **Audit record.** Every accepted write emits a structured audit entry: which
   tool, which note, which agent, and when. The audit trail is a first-class
   output, not a side effect.

If any check fails, the write is refused and the reason is returned to the agent.
The guard prefers to fail loud and refuse rather than to silently do something
approximate.

## The no-delete invariant

There is no tool that deletes a note. The strongest destructive operation an
agent can perform is `archive_note`, which moves content into a dated archive
location and leaves it fully recoverable.

This single invariant changes the failure mode of the entire platform. A bad
automated run can create clutter that a human later cleans up, but it cannot
cause data loss. Deleting is a human-only operation performed outside the agent
surface entirely.

## Audit and observability

Because every read and write is a typed call, the platform gets an audit surface
for free. Each write carries who (which agent), what (which note and which
tool), and when. Combined with git history on the vault itself, this gives two
independent records of every change: the structured audit entry that says a
change was requested and accepted, and the git diff that says exactly what bytes
moved.

That redundancy is the point. If the audit trail and the git history ever
disagree, that disagreement is itself a signal worth surfacing to the human,
which is exactly the fail-loud posture the rest of the platform takes.

## How this maps to the architecture

The MCP layer is component 3 in [architecture.md](./architecture.md). It sits
between the agents and the vault, and it is the only path between them. The sync
server, the Python tooling, and the push alerting all live outside this layer;
the guarantees documented here are specifically about agent access, which is the
part that most needs bounding.
