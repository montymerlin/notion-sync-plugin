# CLAUDE.md — notion-sync

Canonical instructions for this repo live in [AGENTS.md](AGENTS.md). Read that first and treat it as the source of truth.

This file is a Claude compatibility wrapper. When working here:

- Read `AGENTS.md` first
- Treat `AGENTS.md` as the source of truth
- Use `.claude-plugin/` as Claude-specific packaging metadata only
- Keep any Claude-only notes thin and local to this wrapper

## Claude-specific notes

- Release-version source of truth for published Claude plugin builds remains `.claude-plugin/plugin.json`.
- Cowork install is via `.plugin` zip uploaded through Claude Desktop → Plugins → Upload a file. See [SETUP.md](SETUP.md) for the canonical install flow.
- Claude Code CLI install: `claude plugins install github.com/montymerlin/notion-sync-plugin` (global) or symlink for project-scoped install. See SETUP.md.

For everything else — repo structure, conventions, design principles, boundaries — see `AGENTS.md`.
