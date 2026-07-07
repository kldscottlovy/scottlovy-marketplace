# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

This is a Claude Code **plugin marketplace** — a catalog (`.claude-plugin/marketplace.json`) that points to one or more plugins, each of which bundles skills for use in Claude Code.

## Structure

- `.claude-plugin/marketplace.json` — the marketplace manifest. Lists each plugin's `name`, `source` (relative path), and `description`. Adding a new plugin means adding an entry here that points at a directory under `plugins/`.
- `plugins/<plugin-name>/.claude-plugin/plugin.json` — per-plugin manifest (`name`, `description`, `version`).
- `plugins/<plugin-name>/skills/<skill-name>/skill.md` — a skill definition. The frontmatter (`description`) controls when Claude Code surfaces the skill; the body is the prompt/instructions injected when the skill runs.

## Working in this repo

- To add a new plugin: create `plugins/<name>/.claude-plugin/plugin.json`, add its skills under `plugins/<name>/skills/<skill-name>/skill.md`, then register it in `.claude-plugin/marketplace.json`.
- To add a new skill to an existing plugin: create `plugins/<plugin-name>/skills/<new-skill-name>/skill.md` with a `description` frontmatter field and the skill's instructions as the body — no other registration is needed.
- There is no build, lint, or test tooling in this repo — it's plain JSON/Markdown consumed directly by Claude Code. Validate changes by checking that `marketplace.json` and `plugin.json` are well-formed JSON and that plugin `source` paths resolve correctly.
