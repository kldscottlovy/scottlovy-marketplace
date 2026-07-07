---
name: pip-github-pr
description: >
  Create a GitHub Pull Request for the PIP repository (kldiscovery/PIP). Use this skill whenever
  the user wants to open, submit, or create a PR, pull request, or merge request for the current
  branch in PIP. Also trigger when the user says "ship this", "ready for review", "push this up
  as a PR", or similar. Targets master by default.
---

# PIP GitHub PR Creator

Creates a GitHub Pull Request for the PIP repo. Generates the full PR content from the diff, opens a browser form for the user to review and edit it, then creates the PR on submit.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status`)
- On a feature branch (not `master`)
- Python 3 available

## Step-by-Step Process

### 1. Gather branch context

Run these in parallel:
- `git branch --show-current` — get the current branch name
- `git log master..HEAD --oneline` — commits on this branch
- `git diff master..HEAD --stat` — files changed
- `git diff master..HEAD` — full diff (for understanding changes)

### 2. Extract work item IDs

Look for numeric IDs in the branch name. PIP branch names follow the pattern `dev/<id>-<description>` where `<id>` is a 6-digit Azure DevOps work item number.

Examples:
- `dev/518294-gettaskbyid-copytaskcontroller` → `518294`
- `dev/123456-789012-some-feature` → `123456`, `789012`

If no numeric ID is found, set work item IDs to an empty list.

### 3. Dispatch parallel subagents and start the form server

Do all three of the following **at the same time**:
- Start the form server (so it's ready the moment the data arrives)
- Subagent A — generate PR content from the diff
- Subagent B — fetch Azure DevOps work item details

**Start the form server now** — write an empty placeholder input file and launch the server before the subagents finish:

```python
import json, os
placeholder = {"title": "", "summary": "", "changes": "", "test_plan": "", "notes": "", "fixes_lines": [], "work_items": []}
with open(os.path.join(os.environ["TEMP"], "pr_input.json"), "w") as f:
    json.dump(placeholder, f)
```

Run this command **in the background** (`run_in_background: true`) so it does not block:
```bash
python <skill-dir>/scripts/pr_form.py "%TEMP%\pr_input.json" "%TEMP%\pr_result.json"
```

The script prints `{"url": "...", "output_file": "..."}` to stdout immediately after binding. Read the background task's output file to get the URL — you'll open it after the subagents finish. The server re-reads the input file on every request, so it will serve the real data once it's written.

Then spawn these two subagents simultaneously:

---

**Subagent A — PR Content Generator**

Prompt:
```
You are generating PR content for a GitHub pull request. Analyze the following git diff and commit log, then return a JSON object with exactly these keys:

- title: concise plain-English title, ≤72 chars, no prefixes, no work item numbers
- summary: 1–3 sentences describing what this PR accomplishes and why
- changes: bullet list of key changes as a single string, one bullet per line, each starting with "- "
- test_plan: how this was tested; if unknown, describe what a reasonable engineer would have done and note it as assumed
- notes: context reviewers should know (breaking changes, dependencies, migrations, limitations); write "None." if nothing notable
- fixes_lines: array of strings, one per work item ID provided, each formatted as:
  "fixes [AB#<id>](https://dev.azure.com/eddomglobal/78379422-5737-4422-a7f5-a3eb8bae87b5/_workitems/edit/<id>)"

Work item IDs: <comma-separated IDs, or "none">

Commit log:
<git log output>

Diff:
<git diff output>

Return ONLY valid JSON, no markdown fences, no explanation.
```

Save the JSON output to `%TEMP%\pr_content.json`.

---

**Subagent B — Work Item Fetcher**

For each work item ID, run:
```bash
az boards work-item show --id <id> --query "fields" -o json
```

Extract these fields (use empty string if absent):
- `System.Title` → `title`
- `System.WorkItemType` → `type`
- `System.State` → `state`
- `System.Description` → `description` (HTML — pass as-is)
- `Microsoft.VSTS.Common.AcceptanceCriteria` → `acceptance_criteria` (HTML — pass as-is)

Build a JSON array of objects with keys: `id`, `title`, `type`, `state`, `description`, `acceptance_criteria`.

If `az` is unavailable or fails, return an empty array `[]`.

Save the result to `%TEMP%\pr_work_items.json`.

---

### 4. Merge data and open the browser

Once both subagents are done, merge their outputs into the input file the server is already watching:

```python
import json, os
content = json.load(open(os.path.join(os.environ['TEMP'], 'pr_content.json')))
work_items = json.load(open(os.path.join(os.environ['TEMP'], 'pr_work_items.json')))
content['work_items'] = work_items

with open(os.path.join(os.environ['TEMP'], 'pr_input.json'), 'w') as f:
    json.dump(content, f, indent=2)
```

**Before opening the browser, confirm the server is responding.** Poll the URL with a retry loop:

```python
import urllib.request, time
url = "<url-from-step-3>"
server_ok = False
for _ in range(15):
    try:
        urllib.request.urlopen(url, timeout=2).read()
        server_ok = True
        break
    except Exception:
        time.sleep(1)
```

**If `server_ok` is `True`:** open the browser and tell the user to review the form:
```bash
start <url>   # Windows
```
Tell the user: "I've opened the PR form in your browser — review the content, make any edits, and click **Create Pull Request** when ready."

**If `server_ok` is `False`:** skip the browser form and create the PR directly. Build the body using this exact format:

```
<fixes_lines joined with \n>

## Summary
<summary>

## Changes
<changes>

## Test Plan
<test_plan>

## Notes
<notes>
```

Then run:
```bash
gh pr create --base master --title "<title>" --body "<body>"
```
Tell the user the form server failed to start and that the PR was created directly, then show the resulting URL.

### 5. Wait for submission

Wait for the user to confirm the form was submitted or cancelled. Then read `pr_result.json`.

If `cancelled` is `true`, tell the user "PR creation cancelled." and stop.

The form server runs `gh pr create` automatically on submit and writes the result to `pr_result.json`:

```json
{
  "cancelled": false,
  "title": "...",
  "pr_url": "https://github.com/kldiscovery/PIP/pull/123"
}
```

### 6. Report back

Read `pr_result.json` and show the user the `pr_url`. If `pr_url` is null, show the error and offer to retry.
