# Roadmap — notion-sync

Where this plugin could go. Items here are aspirations, not commitments — a place to capture ideas and future directions.

When an item gets evaluated, the outcome is logged in [DECISIONS.md](DECISIONS.md).

**Statuses:** `active` (in progress) · `idea` (worth evaluating) · `parked` (inspiration, no timeline) · `decided` (evaluated — see DECISIONS.md)

---

## Near-term

- **Webhook-based change detection** — Replace timestamp polling with Notion webhooks for real-time sync triggers when webhooks become available via the MCP. `status: idea`
- **Sync report output** — Write `.notion-sync/last-sync-report.md` after each sync with a human-readable summary of changes. `status: idea`
- **Script test suite** — Basic pytest coverage for content hashing, link conversion, frontmatter parsing, and manifest operations. `status: idea`
- **Per-file sync opt-out** — `sync_enabled: false` frontmatter flag excludes a file from all sync operations without touching config. Pattern from go-notion-md-sync. `status: idea`
- **CDN image hosting** — if a public CDN is configured (Cloudflare R2, S3, GitHub Pages), auto-upload local images on push and replace with HTTPS URL. `status: idea`

## Future explorations

- **Block-level sync** — Instead of replacing entire pages, track changes at the block level for more granular sync. Requires understanding Notion's block API. `status: parked`
- **Conflict merge UI** — Instead of "keep local or keep Notion", offer a side-by-side diff with the ability to merge specific sections. `status: parked`
- **Multiple database support** — Sync files from different folders to different Notion databases within the same workspace, managed from a single config. `status: parked`
- **CRDT-based conflict resolution** — Explore Notion's offline CRDT approach for more sophisticated conflict handling. `status: parked`
- **Multi-operator support** — track `config.json` in git, add `config.local.json` (gitignored) for per-operator token. Currently out of scope: Notion integration access requires a paid seat, making single-operator the practical use case. `status: parked`
- **Page lock after push** — `lock_after_push: true` in `config.json` locks the Notion page after content push, signalling "Git is source of truth." The `--lock` flag in `push-content` implements this. Needs evaluation of whether locking causes problems for readers. `status: idea`

## Parking lot

- [go-notion-md-sync](https://github.com/byvfx/go-notion-md-sync) — Battle-tested Go CLI with push/pull/watch modes. Worth studying for watch mode patterns.
- [notionfs](https://github.com/can1357/notionfs) — Local-first sync treating pages as markdown files. Interesting FUSE-based approach.
- [notion-to-md](https://github.com/souvikinator/notion-to-md) — Most feature-rich export tool. Good reference for handling edge cases in Notion→markdown conversion.
- [Notion enhanced markdown spec](https://developers.notion.com/guides/data-apis/enhanced-markdown) — Official token-efficient markdown format designed for MCP/agentic workflows.
- [Notion offline implementation](https://www.notion.com/blog/how-we-made-notion-available-offline) — Documents CRDT migration and conflict copy strategies.
- Content-update surgical edits could reduce token usage significantly for large pages where only one section changed.

## Decided

- **Adopted agentic scaffold** — → Decision 001. `status: decided`
- **Link registry** — → Decision 002. `status: decided`
- **Multi-folder sync** — → Decision 003. `status: decided`
- **Database query over semantic search** — → Decision 004. `status: decided`
- **Push script** — → Decision 005. `status: decided`
- **Dual-distribution packaging** — → Decision 006. `status: decided`
- **Direct API push + integration token** — → Decision 007. `status: decided`
- **Manifest v2 with property snapshots** — → Decision 008. `status: decided`

<!-- Agentic Scaffold v0.1.0 | adapted for Cowork plugin conventions -->
