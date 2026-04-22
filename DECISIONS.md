# Decisions — notion-sync

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

---

## Decision 006: Dual-distribution packaging with marketplace.json (2026-04-21)

**Status:** Accepted
**Date:** 2026-04-21

**Context:** The plugin CLAUDE.md positioned it as a "Cowork plugin" while the README already showed both Cowork and Claude Code CLI installation paths. This inconsistency needed resolving. Additionally, no marketplace.json existed for Claude Code CLI's `claude plugins install` command.

**Decision:** Add `.claude-plugin/marketplace.json`, add a Distribution section to CLAUDE.md (replacing the "This is a Cowork plugin" heading), and update the directory structure listing. The README already had dual-install instructions so only minor consistency fixes were needed there.

**Consequences:**
- Users can install via `claude plugins install github.com/montymerlin/notion-sync-plugin`
- CLAUDE.md no longer contradicts README on host support
- marketplace.json version must stay in sync with plugin.json on each release

**Alternatives Considered:**
- *Keep Cowork-only positioning* — rejected. README already documented Claude Code CLI installation; the CLAUDE.md just hadn't caught up

---

## Decision 007: Direct API push + integration token as first-class config

**Status:** Accepted
**Date:** 2026-04-22

**Context:** The v0.2 push path called `notion-update-page(command="replace_content", new_str=<content>)` via MCP. The `new_str` value is generated token-by-token by the LLM, making content fabrication near-certain for large documents. The EthicHub document (85K chars, ~300 blocks) was pushed as AI-regenerated prose. A workaround script calling the Notion Blocks API directly was written in the bridging-worlds consumer repo, confirming direct API push eliminates the problem.

**Decision:** Notion integration token is required for content writes. `push_markdown.py push-content` reads the staging file as bytes and sends it to the Blocks API directly — no LLM generation in the path. MCP is retained for reads (`notion-fetch`, `notion-search`) and property writes (`notion-update-page update_properties`) since those paths don't pass generated prose.

**Consequences:**
- Content fabrication eliminated by design, not by workaround
- Token setup adds one step to `/notion-setup`
- Property-only changes remain token-free (use MCP)
- bridging-worlds `.scripts/notion_push_content.py` can be retired

**Alternatives Considered:**
- MCP-only with documented size limits — rejected, data integrity failure not a performance issue
- Token optional with MCP fallback — rejected, adds complexity without benefit for single-operator
- Ecosystem research confirmed only `go-notion-md-sync` achieves bidirectional sync; all other tools are export-only, validating the custom plugin approach

---

## Decision 008: Manifest v2 with property snapshots

**Status:** Accepted
**Date:** 2026-04-22

**Context:** The v1 manifest stored only a content hash per page. Property changes (e.g. updating `research_stage` in frontmatter) were detected by the SKILL.md agent manually, not by the diff script — making the detection inconsistent and the push unnecessarily heavy (any change triggered a full content push even if only frontmatter changed).

**Decision:** Add `"properties"` snapshot per manifest entry (keyed by `yaml_key`). `manifest.py diff` now outputs `push_target` (`properties_only`, `content_only`, `both`, `none`) and `property_diff` per changed file. Property-only changes route to `push-properties` (fast, no token, no Blocks API call). Auto-migration from v1 adds `"properties": {}` to existing entries on first load.

**Consequences:**
- Properties-only changes are now fast, targeted, zero-fabrication-risk operations
- Manifest format change (non-breaking — auto-migration on load)
- `manifest.py diff` is the single source of truth for change classification
- First sync after migration re-captures all property baselines

**Alternatives Considered:**
- Separate `property_hash` field — rejected, full snapshot enables per-field diffs and human-readable conflict display
- Manual property inspection in SKILL.md — rejected, too slow and too easy to skip

<!-- Agentic Scaffold v0.1.0 | adapted for Cowork plugin conventions -->
