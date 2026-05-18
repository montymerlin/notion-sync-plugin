# CLAUDE.md — notion-sync

Before doing anything else in this repo, Read `AGENTS.md` in full. It is the canonical instruction set for this repo; this file is a thin Claude compatibility wrapper and assumes you have read `AGENTS.md` first.

In Claude Code (CLI), an `@AGENTS.md` directive will expand recursively. In Cowork (desktop), that expansion is not reliable, so the explicit imperative above is required — do not skip it.

## Claude-specific notes

- Release-version source of truth for published Claude plugin builds remains `.claude-plugin/plugin.json`.
- Cowork install is via `.plugin` zip uploaded through Claude Desktop → Plugins → Upload a file. See [SETUP.md](SETUP.md) for the canonical install flow.
- Claude Code CLI install: `claude plugins install github.com/montymerlin/notion-sync-plugin` (global) or symlink for project-scoped install. See SETUP.md.

For everything else — repo structure, conventions, design principles, boundaries — see `AGENTS.md`.
