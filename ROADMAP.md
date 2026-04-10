# Roadmap — notion-cowork

Where this plugin could go. Items here are aspirations, not commitments — a place to capture ideas and future directions.

When an item gets evaluated, the outcome is logged in [DECISIONS.md](DECISIONS.md).

**Statuses:** `active` (in progress) · `idea` (worth evaluating) · `parked` (inspiration, no timeline) · `decided` (evaluated — see DECISIONS.md)

---

## Near-term

- **Webhook-based change detection** — Replace timestamp polling with Notion webhooks for real-time sync triggers when webhooks become available via the MCP. `status: idea`
- **Sync report output** — Write `.notion-sync/last-sync-report.md` after each sync with a human-readable summary of changes. `status: idea`
- **Script test suite** — Basic pytest coverage for content hashing, link conversion, frontmatter parsing, and manifest operations. `status: idea`

## Future explorations

- **Block-level sync** — Instead of replacing entire pages, track changes at the block level for more granular sync. Requires understanding Notion's block API. `status: parked`
- **Conflict merge UI** — Instead of "keep local or keep Notion", offer a side-by-side diff with the ability to merge specific sections. `status: parked`
- **Multiple database support** — Sync files from different folders to different Notion databases within the same workspace, managed from a single config. `status: parked`
- **CRDT-based conflict resolution** — Explore Notion's offline CRDT approach for more sophisticated conflict handling. `status: parked`

## Parking lot

- [go-notion-md-sync](https://github.com/byvfx/go-notion-md-sync) — Battle-tested Go CLI with push/pull/watch modes. Worth studying for watch mode patterns.
- [notionfs](https://github.com/can1357/notionfs) — Local-first sync treating pages as markdown files. Interesting FUSE-based approach.
- [notion-to-md](https://github.com/souvikinator/notion-to-md) — Most feature-rich export tool. Good reference for handling edge cases in Notion→markdown conversion.
- [Notion enhanced markdown spec](https://developers.notion.com/guides/data-apis/enhanced-markdown) — Official token-efficient markdown format designed for MCP/agentic workflows.
- [Notion offline implementation](https://www.notion.com/blog/how-we-made-notion-available-offline) — Documents CRDT migration and conflict copy strategies.
- Content-update surgical edits could reduce token usage significantly for large pages where only one section changed.

## Decided

- **Link registry** — → Decision 002. `status: decided`
- **Multi-folder sync** — → Decision 003. `status: decided`
- **Database query over semantic search** — → Decision 004. `status: decided`
- **Push script** — → Decision 005. `status: decided`
- **Adopted agentic scaffold** — → Decision 001. `status: decided`

<!-- Agentic Scaffold v0.1.0 | adapted for Cowork plugin conventions -->
