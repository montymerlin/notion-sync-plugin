# Decisions — notion-cowork

Architectural decisions for this plugin, logged in a lightweight ADR format. Each entry captures the context, the choice made, and its consequences.

**Format:** Each decision gets a sequential number, a status, and four sections: Context, Decision, Consequences, and (optionally) Alternatives Considered.

---

## Decision 001: Adopted agentic scaffold

**Status:** Accepted
**Date:** 2026-04-10

**Context:** The plugin had grown to include multiple skills, four scripts, and detailed reference docs. Without explicit agent instructions, contributors and agents made inconsistent assumptions about conventions.

**Decision:** Adopted the Agentic Scaffold pattern — CLAUDE.md for agent instructions, DECISIONS.md for architectural choices, CHANGELOG.md for narrative history, ROADMAP.md for future directions.

**Consequences:**
- Agents working in this repo have clear instructions from session one
- Plugin-specific conventions (generalizable skills, JSON output, no external deps) are documented
- Small file overhead, but each serves a distinct purpose

---

## Decision 002: Link registry as persistent bidirectional map

**Status:** Accepted
**Date:** 2026-04-10

**Context:** During the first real-world sync session (Bridging Worlds, 46 research pages), link conversion between local markdown cross-references and Notion page URLs was the biggest pain point. Auto-slugifying Notion titles failed for short local slugs (e.g. `berkana-two-loop.md` for a page titled "The Berkana Two Loop: Reimagining Finance — A Living Systems View"). Two passes and manual mappings were needed.

**Decision:** Introduced `.notion-sync/link-registry.json` — a persistent bidirectional map (file→page ID and page ID→file) rebuilt from the manifest after every sync. A dedicated `link_registry.py` script handles build, lookup, and link conversion in both directions.

**Consequences:**
- Link conversion is now a single script call, not ad-hoc Python
- Maps by page ID, not by title — immune to slug mismatches
- Registry must be rebuilt after every sync (automated in the skill workflow)
- Adds one more file to `.notion-sync/` (gitignored with the rest)

**Alternatives Considered:**
- Title-based slug matching — brittle, fails on short slugs
- Inline lookup from manifest on every conversion — works but slower and duplicates logic across push/pull

---

## Decision 003: Multi-folder sync to single database

**Status:** Accepted
**Date:** 2026-04-10

**Context:** Users may have files in different local folders (e.g. `research/` and `report/`) that all sync to the same Notion database. The v0.1 config only supported a single `sync_folder`.

**Decision:** Changed config to `sync_folders` (array). Backward-compatible: `sync_folder` (singular) is treated as a single-element array. When creating new files from Notion, the agent asks which folder to place them in if multiple folders exist.

**Consequences:**
- Config schema change (non-breaking — old format still works)
- All file discovery scripts (`bootstrap`, `discover`, `diff`) accept `--folders` with multiple paths
- Agent must prompt user for folder choice when creating new local files

---

## Decision 004: Database query over semantic search for page discovery

**Status:** Accepted
**Date:** 2026-04-10

**Context:** The v0.1 setup and sync skills used `notion-search` with 3-4 semantic queries to discover pages. This gave ~70-90% coverage per round, requiring multiple queries and still missing pages with unusual titles.

**Decision:** Prefer `notion-fetch(id="collection://<data_source_id>")` for exhaustive page enumeration. Keep semantic search as a fallback when database query is unavailable.

**Consequences:**
- Full page discovery in a single call
- Eliminates the "missed pages" problem from v0.1
- Requires the data source ID (already stored in config)
- Semantic search remains useful for quick checks of specific pages

---

## Decision 005: Separate push script (push_markdown.py)

**Status:** Accepted
**Date:** 2026-04-10

**Context:** The v0.1 plugin had `build_markdown.py` for pull (Notion→local) but no equivalent for push (local→Notion). During the first sync session, the agent wrote ad-hoc Python in bash to strip frontmatter, convert links, and compute hashes — error-prone and unrepeatable.

**Decision:** Created `push_markdown.py` as the push counterpart — strips frontmatter, converts links via link registry, computes content hash. Supports single-file (`prepare`) and batch modes.

**Consequences:**
- Push preparation is now deterministic and repeatable
- Content hash is computed after link conversion (correct ordering — see gotchas)
- Batch mode enables efficient multi-file syncs
- Agent no longer needs to write custom Python for each push

<!-- Agentic Scaffold v0.1.0 | adapted for Cowork plugin conventions -->
