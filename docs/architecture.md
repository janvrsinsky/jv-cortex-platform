# Architecture

This document describes the shape of Cortex: a self-hosted knowledge platform
built so that AI agents can operate it safely, not just a human reading notes.
It is deliberately conceptual. No private content, no real paths, no
credentials, and no personal data appear here. Where a concrete detail would
leak something, this document uses a generic placeholder instead.

## Design goals

The platform is built around a small set of load-bearing bets.

1. **Markdown is the substrate, not a database.** Every note is a plain file:
   human-editable, diffable, and versioned in git. There is no proprietary
   store to migrate off, and history is a real safety net.
2. **Frontmatter is the query layer.** Anything worth filtering on lives in a
   small YAML block at the top of a note, not buried in prose. That is what
   turns an unstructured pile of notes into something an agent can query.
3. **Agents get typed tools, not root.** Everything an agent does flows through
   an allowlisted tool surface (search, read, write). Actions stay observable
   and reversible; a model never receives a raw filesystem handle.
4. **Sync is self-hosted.** A server in Docker keeps every device on one source
   of truth, with no third-party cloud in the loop.
5. **The human stays the editor.** Automation proposes, archives, and alerts.
   Deciding and deleting stay with the human. No autonomous delete is an
   invariant, not a preference.
6. **Capture is cheap, state is honest.** Updates land the moment they happen;
   automation flags drift and stale records instead of papering over them, and
   pushes an alert when something cannot wait.

The durable engineering is the substrate, the tool layer, and the guardrails.
The chat face on top is replaceable.

## Component overview

```
+-------------------+        +----------------------------+
|  Devices          | <----> |  Sync server (Docker)      |
|  laptop, phone    |        |  self-hosted, no cloud     |
+-------------------+        +-------------+--------------+
                                           |
                                           v
                              +----------------------------+
                              |  Markdown vault            |
                              |  plain files, git-versioned|
                              +-------------+--------------+
                                           ^
                        typed, allowlisted |  tools
                                           |
+-------------------+        +-------------+--------------+
|  AI agents        | -----> |  MCP layer                 |
|  scheduled +      |        |  search / read / write     |
|  on-demand        |        |  audit surface             |
+---------+---------+        +----------------------------+
          |
          |  guardrails: no autonomous delete, human is editor
          v
+-------------------+        +----------------------------+
|  Push alerting    | -----> |  Human                     |
|  something to see |        |  decides and deletes       |
+-------------------+        +----------------------------+

  Python tooling (linter, parsers) writes into the vault out of band.
```

### 1. Markdown vault

The system of record is a directory of plain markdown files. Each file opens
with a small YAML frontmatter block that carries the fields worth querying
(a human-readable title, a type, a status, tags, a created date). The body is
ordinary markdown.

Two properties matter here. First, the store is boring on purpose: any editor
or script can read and write it, and there is no lock-in. Second, structure is
enforced by tooling rather than by discipline (see [Python tooling](#4-python-tooling)),
so conventions hold mechanically across a large note count instead of relying
on anyone remembering them.

### 2. Sync server (Docker)

A self-hosted sync server runs in a Docker container and keeps every device on
one copy of the vault. The value is control: no third-party cloud sees the
content, and the sync boundary is one process the owner runs and can inspect.

Conceptually the container exposes a sync endpoint on the local network (or over
a private tunnel), persists the vault to a mounted volume, and is fronted by
whatever reverse proxy and auth the operator prefers. Nothing about the sync
layer is specific to any one vendor: the point of the design is that this box is
replaceable without touching the substrate or the agent layer.

### 3. MCP layer

Agents never touch the filesystem directly. They reach the vault through a
[Model Context Protocol](https://modelcontextprotocol.io) server that exposes a
small set of typed, allowlisted tools: search, read, and a guarded write.

This is the safety seam of the whole platform, and it gets its own document:
see [mcp-layer.md](./mcp-layer.md) for the tool contracts, the write guard, and
the audit surface.

The important architectural fact is that the MCP layer is the *only* path from a
model to the vault. There is no fallback that hands a model raw file access, so
the guarantees the tool layer makes are guarantees about the whole system.

### 4. Python tooling

Two kinds of Python tooling keep the vault honest, running out of band from the
agent layer.

* **Linter.** A structural linter checks naming conventions (kebab-case
  filenames) and frontmatter (required keys present, controlled vocabularies
  respected, field shapes correct) across the whole vault. Running it is how
  convention holds at scale instead of depending on memory. A clean-room version
  of this idea, built from scratch on synthetic data, ships in
  [`examples/`](../examples/README.md) so the approach is visible without any
  private content.

* **Parsers.** Import tooling turns data exports (structured dumps from other
  systems) into clean markdown notes with correct frontmatter, so external data
  lands in the same queryable shape as everything else. The parsers are generic
  transform steps: read an export, normalise it, write frontmatter-topped
  markdown, hand off to the linter.

### 5. Push alerting

Scheduled and on-demand agents run maintenance passes: triaging the capture
inbox, surfacing dated commitments, and watching for stale or self-contradictory
records. When a pass finds something a human has to see, it emits a push alert
to the owner's devices.

The design rule is **fail loud**. Rather than silently reconciling a stale or
conflicting record, automation flags it and, when it matters, pages the human. A
clean run is silent; a run that finds trouble is noisy on purpose.

## Guardrails

Four guarantees define what the platform will and will not do. They are
implemented in code and tool contracts, not left to prompt wording.

* **Actions go through typed tools.** Every read and write is bounded and
  observable through the MCP surface. There is no path around it.
* **Nothing is deleted autonomously.** Automation archives; the human purges. A
  bad automated run degrades into clutter to clean up, never into lost data.
* **State stays honest.** Automation surfaces drift and conflict rather than
  hiding it, and escalates when it matters.
* **The human is the editor.** Automation proposes and prepares; deciding stays
  with the owner.

## What is real, and what is documented here

The platform runs daily on the owner's own infrastructure with one real user who
depends on it. The sync server, the MCP tools, the agent workflows, and the
linter are live.

This repository is architecture and tooling only. It ships no vault content, no
real linter rules, no real paths, and no private data. The one runnable piece is
the clean-room linter in [`examples/`](../examples/README.md), which ships and
lints synthetic sample notes so the tooling approach is visible without exposing
anything private.
