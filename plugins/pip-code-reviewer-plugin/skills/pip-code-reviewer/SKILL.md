---
name: pip-code-reviewer
description: Comprehensive multi-dimension code review of the current branch's changes (diff against master) before merging or opening a PR in the PIP repo. Use whenever the user asks to review, audit, or double-check their branch, changes, or diff — even a bare "review this branch" or "check my changes" with no specific concern named — as well as when they call out quality, security vulnerabilities (SQL injection, XSS, OWASP Top 10), PIP project guidelines, architectural patterns, test-coverage gaps in changed code, duplicate/copy-pasted code, or performance issues. This skill does NOT cover writing new tests, patching one already-identified line, or a standalone whole-codebase/whole-project audit with no branch or PR in scope — it only reviews a branch's diff.
disable-model-invocation: false
context: fork
tools: Read, Edit, Write, Glob, Grep, Bash, Workflow, TaskOutput
---

# PIP Code Reviewer

## Overview

You are a Senior C# Architect orchestrating a code review that runs subagents in parallel. Your job is to fan out these specialized sub-agents — one per review dimension — collect their findings, synthesize a unified report, apply fixes, and loop until clean.

Unless explicitly instructed otherwise, review the recent changes on the current branch, not the entire codebase.

## Review Workflow

### 1. Gather Context

Before launching agents, collect the inputs they all need:
- Run `git diff origin/master...HEAD --name-only` to get the list of changed files.
- Run `git diff origin/master...HEAD` to get the full diff.
- Run `git merge-base HEAD origin/master` to identify the common ancestor, then read the full current content of every changed `.cs` file (both the branch version and, where possible, the base version via `git show <merge-base>:<file>`). Concatenate into a `full_file_contents` string keyed by file path so the duplication agent can compare new code against what already existed.
- Read every `.md` file directly under `.claude/skills/pip-code-reviewer/references/` (not the `dimensions/` subfolder) **and** every `.md` file under `.claude/skills/pip-code-reviewer/references/guidelines/`, and build a single `sharedRefs` map keyed by filename without extension — e.g. `security-checklist.md` → key `security-checklist`, `guidelines/architecture.md` → key `architecture`. These are shared documents any dimension can pull in. The `guidelines/` files are curated, per-dimension excerpts of PIP's C# conventions (named to match each dimension's `key`) — this keeps each dimension agent's prompt scoped to only the guidance relevant to it, instead of every agent receiving the full set of PIP conventions.
  **Naming precedence**: keys must be unique across both locations — if a file under `references/` and a file under `references/guidelines/` ever share a basename, read `references/` root files first, then `guidelines/` files second so the `guidelines/` version wins (last-write-wins into the map). Avoid this entirely by never giving a top-level `references/*.md` file the same name as a dimension `key`.
- Build the shared preamble every dimension prepends:
  ```
  base_context = `
  You are reviewing a C# pull request. Branch: <branchName>
  
  Changed files:
  <changedFiles>
  
  Full diff:
  <diff>
  `
  ```

### 2. Load Review Dimensions

Glob `.claude/skills/pip-code-reviewer/references/dimensions/*.md`. Each file is one review dimension and follows this shape:

```
---
key: <short-key>
label: <Display Label>
---
<prompt template, using {{placeholder}} tokens>
```

For each dimension file:
1. Parse the frontmatter to get `key` and `label`.
2. Take the body template and substitute placeholders by simple string replacement:
   - `{{base_context}}` → the `base_context` string built in step 1
   - `{{full_file_contents}}` → the `full_file_contents` string built in step 1
   - `{{<any-other-name>}}` → `sharedRefs['<any-other-name>']` (the matching file under `references/` or `references/guidelines/`, minus `.md`). If no matching file exists, substitute an empty string.
3. Produce a fully-rendered `prompt` string.

Collect the results into a `dimensions` array of `{ key, label, prompt }` objects — one per file found. **This is the extension point**: to add a new review dimension, drop a new `.md` file into `references/dimensions/` following the frontmatter shape above; nothing else needs to change. If it needs PIP-specific conventions, add a matching `references/guidelines/<key>.md` file (same `key` as the dimension) and reference it as `{{<key>}}` in the dimension's template. To add any other shared document dimensions can reference, drop a `.md` file into `references/` and use `{{that-filename}}` in any dimension template.

### 3. Fan Out Review SubAgents

Use the `Workflow` tool with the script below. Pass `dimensions` (already fully rendered — no further templating needed inside the script) in via `args`.

```javascript
export const meta = {
  name: 'csharp-parallel-review',
  description: 'Run all C# review dimensions in parallel and synthesize findings',
  phases: [
    { title: 'Review' },
    { title: 'Synthesize' },
  ],
}

const FINDING_ITEM = {
  type: 'object',
  properties: {
    location: { type: 'string' },
    issue: { type: 'string' },
    impact: { type: 'string' },
    fix: { type: 'string' },
  },
  required: ['location', 'issue', 'impact', 'fix'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    critical: { type: 'array', items: FINDING_ITEM },
    important: { type: 'array', items: FINDING_ITEM },
    easyfixes: { type: 'array', items: FINDING_ITEM },
    suggestions: { type: 'array', items: FINDING_ITEM },
    positives: { type: 'array', items: { type: 'string' } },
  },
  required: ['dimension', 'critical', 'important', 'easyfixes', 'suggestions', 'positives'],
}

const { dimensions } = args

const results = await parallel(dimensions.map(d => () =>
  agent(d.prompt, { label: d.label, phase: 'Review', schema: FINDINGS_SCHEMA })
))

phase('Synthesize')
const combined = results.filter(Boolean)
return combined
```

**Critical — block until the workflow actually finishes.** The `Workflow` tool always runs in the background: it returns immediately with a `task_id`/`runId`, and the real results only arrive later via a `<task-notification>`. Because this skill runs in a forked context (`context: fork`), the fork gets exactly one turn to produce its final answer — it will NOT be resumed by a later notification the way a normal top-level session is. If you invoke `Workflow` and then immediately write your final message (e.g. "agents launched, I'll wait..."), the fork ends there and then the *parent* session ends up fielding the per-dimension notifications one at a time, and the fork never performs steps 4-7 (no report file gets written, no fixes get applied, no loop happens).

To avoid this, you MUST immediately follow the `Workflow` call, in the same turn, with a blocking wait for its result before doing anything else:

```
TaskOutput({ task_id: <the id returned by the Workflow call>, block: true, timeout: 600000 })
```

Do not produce any text output between the `Workflow` call and the `TaskOutput` block call — do not narrate "waiting for agents." Only after `TaskOutput` returns the combined per-dimension findings array should you proceed to step 4.

### 4. Synthesize and Write Report

After the subagent Workflow completes, you receive an array of per-dimension findings. Before writing the report, **dedupe across dimensions**: some dimensions overlap in scope (e.g. Security and Architecture can both flag the same missing franchise filter), so if two or more findings point at the same location and describe the same underlying issue, merge them into a single entry rather than listing each dimension's copy separately — note in the merged entry which dimensions raised it. Then synthesize the deduped findings into a single review document:

**Report location**: `docs/CodeReview/Review_[YYYYMMDD_HHMMSS].md`  
(Create the `docs/CodeReview/` directory if it does not exist.)

**Report structure**:

```
Review Date/Time: <DateTime>
Branch: <branch name>

## Critical Issues (must fix)
[numbered, with Location / Issue / Impact / Fix for each]

## Important Issues (should fix)
[numbered, with Location / Issue / Impact / Fix for each]

## Easy Fixes (must fix)
[numbered, with Location / Issue / Impact / Fix for each]

## Suggestions (nice to have)
[numbered, with Location / Issue / Impact / Fix for each]

## Positives
[bullet list of good practices observed]
```

Assign a unique sequential number to every issue across all dimensions so each can be referenced in conversation.

### 5. Apply Fixes and Loop

After writing the report:
1. Apply all **Critical**, **Important** and **Easy Fixes** to the codebase.
2. Run `dotnet build PIP.sln` — fix any build errors before proceeding.
3. Run `dotnet test PIP.sln` (or the relevant scoped test project, per CLAUDE.md's Goal-Driven Execution guidance) — fix any test failures before proceeding. A clean build does not guarantee an auto-applied fix didn't silently change behavior.
4. **Loop condition**: if the report contains **any Critical, Important, or Easy Fix issues**, immediately re-run the full review (steps 2–5) and write a new uniquely-named report. Continue looping until a review pass produces a report with **zero Critical, zero Important, and zero Easy Fix issues**, or until **10 total cycles** have completed — whichever comes first.
5. At the start of each new cycle, log the cycle number (e.g. "Starting review cycle 2/10") so progress is visible.

> **Why loop on findings, not fixes**: The goal is a clean report. Even if a fix was attempted but introduced a new issue — or an Easy Fix silently failed to apply — the loop must continue. The exit signal is a full pass with no Critical, Important, or Easy Fix findings remaining. Easy Fixes are labeled "must fix" the same as Critical and Important, so a resurfacing Easy Fix must also block a clean exit.

### 6. Display Final Clean Report

When the loop exits because a review pass produced **zero Critical, zero Important, and zero Easy Fix issues**, read the contents of that final report file and print it in full to the user. This is the "all-clear" report — the user should be able to see it without having to open a file manually.

If the loop exited because the **10-cycle cap** was reached (and issues still remain), do NOT print the last report as a clean report. Instead, tell the user the cap was hit and list the path to the most recent report file so they can review what remains.

### 7. Highlight Positives

Each cycle's report must include a **Positives** section drawn from the agents' findings — well-structured code, good test coverage, proper security practices, etc.
