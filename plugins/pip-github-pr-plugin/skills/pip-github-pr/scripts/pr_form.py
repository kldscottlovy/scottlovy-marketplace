"""
Serves a PR review form pre-filled with generated content and an optional
Azure DevOps work item reference panel.

Usage: python pr_form.py <input_json> <output_json>
  input_json:  path to JSON file with keys:
                 title, summary, changes, test_plan, notes, fixes_lines
                 work_items (optional): list of {id, title, type, state, description, acceptance_criteria}
  output_json: path where submitted form data will be saved as JSON

Prints {"url": "...", "output_file": "..."} to stdout on startup.
"""
import sys
import json
import threading
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

INPUT_FILE = os.path.expandvars(sys.argv[1])
OUTPUT_FILE = os.path.expandvars(sys.argv[2])

def load_data():
    with open(INPUT_FILE, encoding="utf-8") as f:
        return json.load(f)


def esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_work_item_panel(data):
    items = data.get("work_items", [])
    if not items:
        return ""

    cards = ""
    for item in items:
        wi_id = item.get("id", "")
        wi_title = esc(item.get("title", ""))
        wi_type = esc(item.get("type", ""))
        wi_state = esc(item.get("state", ""))
        wi_desc = item.get("description", "").strip()
        wi_ac = item.get("acceptance_criteria", "").strip()
        wi_url = f"https://dev.azure.com/eddomglobal/78379422-5737-4422-a7f5-a3eb8bae87b5/_workitems/edit/{wi_id}"

        desc_block = f"""
        <div class="wi-section">
          <div class="wi-section-label">Description</div>
          <div class="wi-content">{wi_desc}</div>
        </div>""" if wi_desc else ""

        ac_block = f"""
        <div class="wi-section">
          <div class="wi-section-label">Acceptance Criteria</div>
          <div class="wi-content">{wi_ac}</div>
        </div>""" if wi_ac else ""

        cards += f"""
      <div class="wi-card">
        <div class="wi-header">
          <div class="wi-meta">
            <span class="wi-type">{wi_type}</span>
            <span class="wi-state">{wi_state}</span>
          </div>
          <a class="wi-title" href="{wi_url}" target="_blank">AB#{wi_id} — {wi_title}</a>
        </div>
        {desc_block}
        {ac_block}
      </div>"""

    return f"""
      <div class="card">
        <div class="section-title">
          Work Item Reference
          <button type="button" class="toggle-btn" onclick="toggleWI(this)">Hide</button>
        </div>
        <div id="wi-body">
          {cards}
        </div>
      </div>"""


def md_field(field_id, label, name, value, hint=""):
    escaped = esc(value)
    hint_html = f'<p class="hint">{hint}</p>' if hint else ""
    return f"""
        <div class="field">
          <label for="{field_id}">{label}</label>
          <textarea id="{field_id}" name="{name}">{escaped}</textarea>
          {hint_html}
        </div>"""


def build_form(data):
    title = esc(data.get("title", ""))
    fixes_lines = data.get("fixes_lines", [])
    fixes_display = esc("\n".join(fixes_lines)) if fixes_lines else "None"
    wi_panel = build_work_item_panel(data)

    summary_field   = md_field("summary",   "Summary",   "summary",   data.get("summary", ""))
    changes_field   = md_field("changes",   "Changes",   "changes",   data.get("changes", ""),   "One bullet per line. Markdown supported.")
    test_plan_field = md_field("test_plan", "Test Plan", "test_plan", data.get("test_plan", ""))
    notes_field     = md_field("notes",     "Notes",     "notes",     data.get("notes", ""),     "Breaking changes, dependencies, migration steps, known limitations.")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Review Pull Request</title>
  <link rel="stylesheet" href="https://unpkg.com/easymde/dist/easymde.min.css">
  <script src="https://unpkg.com/easymde/dist/easymde.min.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f6f8fa;
      padding: 40px 16px 80px;
      color: #1f2328;
    }}
    .container {{ max-width: 760px; margin: 0 auto; }}
    header {{ margin-bottom: 28px; }}
    header h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 6px; }}
    header p {{ font-size: 14px; color: #57606a; }}

    .card {{
      background: #fff;
      border: 1px solid #d0d7de;
      border-radius: 8px;
      padding: 24px 28px;
      margin-bottom: 16px;
    }}
    .section-title {{
      font-size: 14px;
      font-weight: 600;
      color: #1f2328;
      margin-bottom: 16px;
      padding-bottom: 10px;
      border-bottom: 1px solid #d0d7de;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .field + .field {{ margin-top: 24px; }}
    label {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: #1f2328;
      margin-bottom: 6px;
    }}
    .hint {{ font-size: 12px; color: #57606a; margin-top: 6px; }}

    input[type="text"] {{
      width: 100%;
      padding: 8px 12px;
      font-size: 14px;
      font-family: inherit;
      border: 1px solid #d0d7de;
      border-radius: 6px;
      background: #f6f8fa;
      color: #1f2328;
      transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
    }}
    input[type="text"]:focus {{
      outline: none;
      border-color: #0969da;
      background: #fff;
      box-shadow: 0 0 0 3px rgba(9,105,218,0.12);
    }}

    /* EasyMDE overrides */
    .EasyMDEContainer {{ font-size: 14px; }}
    .EasyMDEContainer .CodeMirror {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14px;
      border: 1px solid #d0d7de;
      border-top: none;
      border-radius: 0 0 6px 6px;
      background: #f6f8fa;
      color: #1f2328;
      line-height: 1.6;
    }}
    .EasyMDEContainer .CodeMirror-focused {{
      border-color: #0969da;
      background: #fff;
      box-shadow: 0 0 0 3px rgba(9,105,218,0.12);
    }}
    .EasyMDEContainer .editor-toolbar {{
      border: 1px solid #d0d7de;
      border-radius: 6px 6px 0 0;
      background: #f6f8fa;
      opacity: 1;
    }}
    .EasyMDEContainer .editor-toolbar button {{
      color: #57606a !important;
    }}
    .EasyMDEContainer .editor-toolbar button:hover,
    .EasyMDEContainer .editor-toolbar button.active {{
      background: #e8edf1;
      border-color: #d0d7de;
    }}
    .EasyMDEContainer .editor-preview {{
      background: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      color: #1f2328;
    }}
    .EasyMDEContainer .editor-preview p {{ margin-bottom: 8px; }}
    .EasyMDEContainer .editor-preview ul,
    .EasyMDEContainer .editor-preview ol {{ padding-left: 20px; margin-bottom: 8px; }}
    .EasyMDEContainer .editor-preview li {{ margin-bottom: 3px; }}
    .EasyMDEContainer .editor-preview code {{
      font-size: 12px; background: #f6f8fa;
      padding: 1px 5px; border-radius: 3px; border: 1px solid #d0d7de;
    }}
    .EasyMDEContainer .editor-preview pre {{
      background: #f6f8fa; border: 1px solid #d0d7de;
      border-radius: 6px; padding: 12px; margin: 8px 0;
    }}
    .EasyMDEContainer .editor-preview pre code {{
      background: none; border: none; padding: 0;
    }}
    .editor-statusbar {{ display: none; }}

    /* Work item panel */
    .wi-card {{ border: 1px solid #d0d7de; border-radius: 6px; overflow: hidden; }}
    .wi-card + .wi-card {{ margin-top: 12px; }}
    .wi-header {{ padding: 12px 16px; background: #f6f8fa; border-bottom: 1px solid #d0d7de; }}
    .wi-meta {{ display: flex; gap: 8px; margin-bottom: 6px; }}
    .wi-type, .wi-state {{
      font-size: 11px; font-weight: 600;
      padding: 2px 8px; border-radius: 12px;
      text-transform: uppercase; letter-spacing: 0.03em;
    }}
    .wi-type {{ background: #ddf4ff; color: #0550ae; border: 1px solid #b6e3ff; }}
    .wi-state {{ background: #fff8c5; color: #7d4e00; border: 1px solid #f0d644; }}
    .wi-title {{ font-size: 14px; font-weight: 600; color: #0969da; text-decoration: none; }}
    .wi-title:hover {{ text-decoration: underline; }}
    .wi-section {{ padding: 12px 16px; border-top: 1px solid #d0d7de; }}
    .wi-section-label {{
      font-size: 11px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.05em;
      color: #57606a; margin-bottom: 8px;
    }}
    .wi-content {{
      font-size: 13px; color: #1f2328; line-height: 1.6;
    }}
    .wi-content p {{ margin-bottom: 6px; }}
    .wi-content p:last-child {{ margin-bottom: 0; }}
    .wi-content code {{
      font-family: ui-monospace, "Cascadia Code", monospace;
      font-size: 12px; background: #f6f8fa;
      padding: 1px 5px; border-radius: 3px; border: 1px solid #d0d7de;
    }}
    .wi-content pre {{
      background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px;
      padding: 12px; overflow-x: auto; font-size: 12px;
      font-family: ui-monospace, "Cascadia Code", monospace; margin: 8px 0;
    }}

    .toggle-btn {{
      font-size: 12px; color: #57606a;
      background: none; border: 1px solid #d0d7de;
      border-radius: 4px; padding: 2px 10px; cursor: pointer;
    }}
    .toggle-btn:hover {{ background: #f6f8fa; color: #1f2328; }}

    .fixes-box {{
      background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px;
      padding: 10px 12px; font-size: 13px;
      font-family: ui-monospace, "Cascadia Code", monospace;
      color: #57606a; white-space: pre-wrap; word-break: break-all;
    }}

    .draft-row {{ display: flex; align-items: center; gap: 10px; padding: 4px 0; }}
    .draft-row input[type="checkbox"] {{ width: 16px; height: 16px; cursor: pointer; accent-color: #0969da; }}
    .draft-row label {{ margin: 0; font-size: 14px; font-weight: 500; cursor: pointer; }}
    .draft-desc {{ font-size: 12px; color: #57606a; margin-left: 26px; margin-top: 4px; }}

    .actions {{ display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }}
    .cancel-btn {{
      background: #fff; color: #cf222e;
      border: 1px solid #d0d7de; border-radius: 6px;
      padding: 10px 20px; font-size: 14px; font-weight: 600;
      cursor: pointer; transition: background 0.15s, border-color 0.15s;
    }}
    .cancel-btn:hover {{ background: #fff0ee; border-color: #cf222e; }}
    button[type="submit"] {{
      background: #1f883d; color: #fff; border: none;
      border-radius: 6px; padding: 10px 28px;
      font-size: 14px; font-weight: 600; cursor: pointer;
      transition: background 0.15s;
    }}
    button[type="submit"]:hover {{ background: #1a7f37; }}
    button[type="submit"]:active {{ background: #156d2e; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Review Pull Request</h1>
      <p>Review and edit the generated content. Each field is a full Markdown editor with live preview.</p>
    </header>

    <form method="POST" action="/submit">

      {wi_panel}

      <div class="card">
        <div class="section-title">Title</div>
        <div class="field">
          <input type="text" name="title" value="{title}" required>
        </div>
      </div>

      <div class="card">
        <div class="section-title">Work Items</div>
        <div class="fixes-box">{fixes_display}</div>
        <p class="hint" style="margin-top:8px">Auto-detected from branch name. Not editable here.</p>
      </div>

      <div class="card">
        <div class="section-title">Body</div>
        {summary_field}
        {changes_field}
        {test_plan_field}
        {notes_field}
      </div>

      <div class="card">
        <div class="section-title">Options</div>
        <div class="draft-row">
          <input type="checkbox" id="draft" name="draft" value="true">
          <label for="draft">Create as draft PR</label>
        </div>
        <p class="draft-desc">Draft PRs are not ready for review and cannot be merged.</p>
      </div>

      <div class="actions">
        <button type="button" class="cancel-btn" onclick="cancelPR()">Cancel</button>
        <button type="submit">Create Pull Request</button>
      </div>

    </form>
  </div>

  <script>
    const TOOLBAR = [
      'bold', 'italic', 'strikethrough', '|',
      'heading-2', 'heading-3', '|',
      'unordered-list', 'ordered-list', '|',
      'code', 'link', '|',
      'preview', 'side-by-side', 'fullscreen'
    ];

    function makeMDE(id, minHeight) {{
      return new EasyMDE({{
        element: document.getElementById(id),
        toolbar: TOOLBAR,
        spellChecker: false,
        autofocus: false,
        status: false,
        minHeight: minHeight,
        renderingConfig: {{ singleLineBreaks: false }},
      }});
    }}

    let editors = [];
    document.addEventListener('DOMContentLoaded', () => {{
      editors = [
        makeMDE('summary',   '100px'),
        makeMDE('changes',   '200px'),
        makeMDE('test_plan', '100px'),
        makeMDE('notes',     '100px'),
      ];

      document.querySelector('form').addEventListener('submit', () => {{
        editors.forEach(e => e.codemirror.save());
      }});
    }});

    function toggleWI(btn) {{
      const body = document.getElementById('wi-body');
      const hidden = body.style.display === 'none';
      body.style.display = hidden ? '' : 'none';
      btn.textContent = hidden ? 'Hide' : 'Show';
    }}

    function cancelPR() {{
      fetch('/cancel', {{ method: 'POST' }}).finally(() => {{
        document.body.innerHTML = '<div style="font-family:system-ui;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#f6f8fa"><div style="background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:40px 48px;text-align:center"><div style="font-size:32px;margin-bottom:12px">✕</div><h1 style="font-size:20px;color:#1f2328;margin-bottom:8px">Cancelled</h1><p style="font-size:14px;color:#57606a">PR creation was cancelled. You can close this tab.</p></div></div>';
      }});
    }}

    // Warn when 5 minutes remain before the server shuts down (1800s total)
    (function() {{
      const TOTAL = 1800, WARN_AT = 300;
      let banner = null;
      setTimeout(() => {{
        banner = document.createElement('div');
        banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#fff8c5;border-top:1px solid #f0d644;padding:10px 20px;font-size:13px;color:#7d4e00;display:flex;align-items:center;justify-content:space-between;z-index:9999';
        const msg = document.createElement('span');
        let remaining = WARN_AT;
        const fmt = s => `${{Math.floor(s/60)}}m ${{s%60}}s`;
        msg.textContent = `⚠ Server expires in ${{fmt(remaining)}} — submit or your edits will be lost.`;
        banner.appendChild(msg);
        const close = document.createElement('button');
        close.textContent = 'Dismiss';
        close.style.cssText = 'background:none;border:1px solid #f0d644;border-radius:4px;padding:2px 10px;cursor:pointer;font-size:12px;color:#7d4e00';
        close.onclick = () => banner.remove();
        banner.appendChild(close);
        document.body.appendChild(banner);
        const tick = setInterval(() => {{
          remaining--;
          if (remaining <= 0) {{ clearInterval(tick); msg.textContent = '⚠ Server has expired — your submit will fail. Close this tab and re-run the skill.'; return; }}
          msg.textContent = `⚠ Server expires in ${{fmt(remaining)}} — submit or your edits will be lost.`;
        }}, 1000);
      }}, (TOTAL - WARN_AT) * 1000);
    }})();
  </script>
</body>
</html>"""


LOADING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="2">
  <title>Preparing PR form...</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f6f8fa;
      display: flex; justify-content: center; align-items: center; min-height: 100vh;
    }
    .card {
      background: #fff; border: 1px solid #d0d7de; border-radius: 8px;
      padding: 40px 48px; text-align: center;
    }
    .spinner {
      width: 36px; height: 36px; border: 3px solid #d0d7de;
      border-top-color: #0969da; border-radius: 50%;
      animation: spin 0.8s linear infinite; margin: 0 auto 16px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    h1 { font-size: 18px; color: #1f2328; margin-bottom: 6px; }
    p { font-size: 13px; color: #57606a; }
  </style>
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <h1>Preparing your PR form&hellip;</h1>
    <p>Generating content from the diff. This page will refresh automatically.</p>
  </div>
</body>
</html>"""

def build_result_html(pr_url=None, error=None):
    if pr_url:
        icon = '<div class="check">&#10003;</div>'
        heading = "Pull Request Created"
        body = f'<p>Your PR is ready:</p><a class="pr-link" href="{pr_url}" target="_blank">{pr_url}</a>'
        border_color = "#1f883d"
    else:
        icon = '<div class="err">&#10007;</div>'
        heading = "PR Creation Failed"
        body = f'<pre class="err-msg">{esc(error or "Unknown error")}</pre><p>Check the terminal for details.</p>'
        border_color = "#cf222e"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{"PR Created" if pr_url else "PR Failed"}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f6f8fa;
      display: flex; justify-content: center; align-items: center; min-height: 100vh;
    }}
    .card {{
      background: #fff; border: 1px solid {border_color}; border-radius: 8px;
      padding: 40px 48px; text-align: center; max-width: 520px; width: 100%;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}
    .check {{
      width: 48px; height: 48px; background: #1f883d; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 16px; color: #fff; font-size: 24px;
    }}
    .err {{
      width: 48px; height: 48px; background: #cf222e; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 16px; color: #fff; font-size: 24px;
    }}
    h1 {{ font-size: 20px; color: #1f2328; margin-bottom: 12px; }}
    p {{ font-size: 14px; color: #57606a; margin-bottom: 8px; }}
    .pr-link {{
      display: inline-block; margin-top: 8px; font-size: 14px;
      color: #0969da; word-break: break-all;
    }}
    .err-msg {{
      background: #fff0ee; border: 1px solid #ffcecb; border-radius: 6px;
      padding: 12px; font-size: 12px; color: #cf222e;
      text-align: left; white-space: pre-wrap; margin: 12px 0;
    }}
  </style>
</head>
<body>
  <div class="card">
    {icon}
    <h1>{heading}</h1>
    {body}
  </div>
</body>
</html>"""

shutdown_event = threading.Event()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        data = load_data()
        if not data.get("title"):
            html = LOADING_HTML
        else:
            html = build_form(data)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_POST(self):
        if self.path == "/cancel":
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump({"cancelled": True}, f)
            self.send_response(200)
            self.end_headers()
            threading.Thread(target=shutdown_event.set).start()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        params = parse_qs(body)

        data = load_data()
        fixes_lines = data.get("fixes_lines", [])
        title   = params.get("title",     [""])[0].strip()
        summary = params.get("summary",   [""])[0].strip()
        changes = params.get("changes",   [""])[0].strip()
        test_plan = params.get("test_plan", [""])[0].strip()
        notes   = params.get("notes",     [""])[0].strip()
        draft   = "true" in params.get("draft", [])

        fixes_block = "\n".join(fixes_lines)
        pr_body = f"{fixes_block}\n\n## Summary\n{summary}\n\n## Changes\n{changes}\n\n## Test Plan\n{test_plan}\n\n## Notes\n{notes}".strip()

        cmd = ["gh", "pr", "create", "--base", "master", "--title", title, "--body", pr_body]
        if draft:
            cmd.append("--draft")

        result_data = {
            "cancelled": False,
            "title": title, "summary": summary, "changes": changes,
            "test_plan": test_plan, "notes": notes, "draft": draft,
            "fixes_lines": fixes_lines,
        }

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            pr_url = proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 else None
            error = proc.stderr.strip() if proc.returncode != 0 else None
        except Exception as e:
            pr_url = None
            error = str(e)

        result_data["pr_url"] = pr_url
        result_data["error"] = error
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)

        html = build_result_html(pr_url=pr_url, error=error).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)

        threading.Thread(target=shutdown_event.set).start()

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}"
    print(json.dumps({"url": url, "output_file": OUTPUT_FILE}))
    sys.stdout.flush()

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    shutdown_event.wait(timeout=1800)
    server.shutdown()
