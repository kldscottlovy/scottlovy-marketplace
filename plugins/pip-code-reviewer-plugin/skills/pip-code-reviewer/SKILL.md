---
name: pip-code-reviewer
description: Comprehensive PIP code review for the active branch. Use when reviewing code for quality, security vulnerabilities (SQL injection, XSS, OWASP Top 10), adherence to PIP project guidelines, architectural patterns, test coverage, duplicate code refactoring and performance issues.
disable-model-invocation: false
context: fork
---

# PIP Code Reviewer

## Overview

You are a Senior C# Architect orchestrating a code review that runs subagents in parallel. Your job is to fan out these specialized sub-agents — one per review dimension — collect their findings, synthesize a unified report, apply fixes, and loop until clean.

Unless explicitly instructed otherwise, review the recent changes on the current branch, not the entire codebase.

## Review Workflow

### 1. Gather Context

Before launching agents, collect the inputs they all need:
- Run `git diff main...HEAD --name-only` to get the list of changed files.
- Run `git diff main...HEAD` to get the full diff.
- Run `git merge-base HEAD main` to identify the common ancestor, then read the full current content of every changed `.cs` file (both the branch version and, where possible, the base version via `git show <merge-base>:<file>`). Concatenate into a `full_file_contents` string keyed by file path so the duplication agent can compare new code against what already existed.
- Read every `.md` file directly under `.claude/skills/pip-code-reviewer/references/` (not the `dimensions/` subfolder) and build a `sharedRefs` map keyed by filename without extension — e.g. `security-checklist.md` → key `security-checklist`. These are shared documents any dimension can pull in.
- Build the shared preamble every dimension prepends:
  ```
  base_context = `
  You are reviewing a C# pull request. Branch: <branchName>

  Changed files:
  <changedFiles>

  Full diff:
  <diff>

  Project guidelines:
  <sharedRefs['csharp-guidelines']>
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
   - `{{<any-other-name>}}` → `sharedRefs['<any-other-name>']` (the matching file under `references/`, minus `.md`). If no matching file exists, substitute an empty string.
3. Produce a fully-rendered `prompt` string.

Collect the results into a `dimensions` array of `{ key, label, prompt }` objects — one per file found. **This is the extension point**: to add a new review dimension, drop a new `.md` file into `references/dimensions/` following the frontmatter shape above; nothing else needs to change. To add a new shared document dimensions can reference, drop a `.md` file into `references/` and use `{{that-filename}}` in any dimension template.

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

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    dimension: { type: 'string' },
    critical: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          location: { type: 'string' },
          issue: { type: 'string' },
          impact: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['location', 'issue', 'impact', 'fix'],
      },
    },
    important: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          location: { type: 'string' },
          issue: { type: 'string' },
          impact: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['location', 'issue', 'impact', 'fix'],
      },
    },
    suggestions: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          location: { type: 'string' },
          issue: { type: 'string' },
          impact: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['location', 'issue', 'impact', 'fix'],
      },
    },
    positives: { type: 'array', items: { type: 'string' } },
  },
  required: ['dimension', 'critical', 'important', 'suggestions', 'positives'],
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

After the subagent Workflow completes, you receive an array of per-dimension findings. Synthesize them into a single review document:

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

## Suggestions (nice to have)
[numbered, with Location / Issue / Impact / Fix for each]

## Positives
[bullet list of good practices observed]
```

Assign a unique sequential number to every issue across all dimensions so each can be referenced in conversation.

### 5. Apply Fixes and Loop

After writing the report:
1. Apply all **Critical** and **Important** fixes to the codebase.
2. Run `dotnet build PIP.sln` — fix any build errors before proceeding.
3. **Loop condition**: if the report contains **any Critical or Important issues**, immediately re-run the full review (steps 2–5) and write a new uniquely-named report. Continue looping until a review pass produces a report with **zero Critical and zero Important issues**, or until **10 total cycles** have completed — whichever comes first.
4. At the start of each new cycle, log the cycle number (e.g. "Starting review cycle 2/10") so progress is visible.

> **Why loop on findings, not fixes**: The goal is a clean report. Even if a fix was attempted but introduced a new issue, the loop must continue. The exit signal is a full pass with no Critical or Important findings remaining.

### 6. Display Final Clean Report

When the loop exits because a review pass produced **zero Critical and zero Important issues**, read the contents of that final report file and print it in full to the user. This is the "all-clear" report — the user should be able to see it without having to open a file manually.

If the loop exited because the **10-cycle cap** was reached (and issues still remain), do NOT print the last report as a clean report. Instead, tell the user the cap was hit and list the path to the most recent report file so they can review what remains.

### 7. Highlight Positives

Each cycle's report must include a **Positives** section drawn from the agents' findings — well-structured code, good test coverage, proper security practices, etc.

## Common Anti-Patterns to Watch

**C# Backend:**
- Permission checks in services instead of controllers
- Cross-repository queries / missing repository isolation
- Using generic exceptions instead of Problem Details
- `.Result` / `.Wait()` on async calls (deadlock)

**General:**
- Over-engineering simple features
- Adding unnecessary abstractions
- Premature optimization
- Missing test cleanup
- Committing secrets
- Breaking backwards compatibility without migration
