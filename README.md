# scottlovy-marketplace

A [Claude Code](https://claude.ai/code) plugin marketplace. It catalogs plugins that bundle skills for use in Claude Code.

## Adding this marketplace to Claude Code

In Claude Code, run:

```
/plugin marketplace add kldscottlovy/scottlovy-marketplace
```

Or, if you've cloned the repo locally, point at the local path instead:

```
/plugin marketplace add /path/to/scottlovy-marketplace
```

## Installing a plugin

Once the marketplace is added, list and install plugins with:

```
/plugin
```

or install directly by name:

```
/plugin install quality-review-plugin@scottlovy-marketplace
```

## Available plugins

| Plugin | Description |
|---|---|
| [quality-review-plugin](plugins/quality-review-plugin) | Adds a `quality-review` skill for quick code reviews (bugs, security, performance, readability) |

## Repository layout

```
.claude-plugin/marketplace.json          # marketplace manifest — lists all plugins
plugins/<plugin-name>/.claude-plugin/plugin.json   # per-plugin manifest
plugins/<plugin-name>/skills/<skill-name>/skill.md # skill definition (frontmatter + prompt)
```

## Adding a new plugin

1. Create `plugins/<name>/.claude-plugin/plugin.json` with `name`, `description`, and `version`.
2. Add one or more skills under `plugins/<name>/skills/<skill-name>/skill.md`, each with a `description` frontmatter field and the skill's instructions as the body.
3. Register the plugin in `.claude-plugin/marketplace.json` by adding an entry with `name`, `source` (relative path), and `description`.
