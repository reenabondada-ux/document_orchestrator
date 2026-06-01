"""HTML preview renderer for in-progress document runs.

Converts the markdown of all approved / review-ready sections into a single
self-contained HTML page.  No external assets — all CSS is inlined so the
response can be opened directly in a browser without any additional requests.

Usage::

    from mainframe_doc_orchestrator.services.previewer import render_preview_html
    html = render_preview_html(run, status_filter={"approved", "review_ready"})
"""

from __future__ import annotations

import markdown as _md
from mainframe_doc_orchestrator.prompt_library import ASSEMBLY_ORDERS, DEFAULT_ASSEMBLY_ORDER

_REVIEW_READY_BADGE = (
    '<span style="background:#d97706;color:#fff;font-size:0.75rem;'
    "padding:2px 8px;border-radius:9999px;vertical-align:middle;"
    'margin-left:8px;">review ready</span>'
)
_APPROVED_BADGE = (
    '<span style="background:#16a34a;color:#fff;font-size:0.75rem;'
    "padding:2px 8px;border-radius:9999px;vertical-align:middle;"
    'margin-left:8px;">approved</span>'
)
_PENDING_BADGE = (
    '<span style="background:#6b7280;color:#fff;font-size:0.75rem;'
    "padding:2px 8px;border-radius:9999px;vertical-align:middle;"
    'margin-left:8px;">pending</span>'
)

_STATUS_BADGES: dict[str, str] = {
    "approved": _APPROVED_BADGE,
    "review_ready": _REVIEW_READY_BADGE,
    "pending": _PENDING_BADGE,
}

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px;
    line-height: 1.7;
    color: #1f2937;
    background: #f9fafb;
}
.page-wrapper {
    max-width: 960px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
}
header {
    border-bottom: 2px solid #e5e7eb;
    padding-bottom: 1.25rem;
    margin-bottom: 2rem;
}
header h1 { font-size: 1.75rem; font-weight: 700; color: #111827; }
header .meta {
    margin-top: 0.5rem;
    font-size: 0.85rem;
    color: #6b7280;
}
nav {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 2.5rem;
}
nav h2 { font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
         letter-spacing: 0.08em; color: #9ca3af; margin-bottom: 0.6rem; }
nav ol { padding-left: 1.25rem; }
nav li { margin-bottom: 0.2rem; font-size: 0.9rem; }
nav a { color: #2563eb; text-decoration: none; }
nav a:hover { text-decoration: underline; }
.section-card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.75rem 2rem;
    margin-bottom: 2rem;
}
.section-card h2 {
    font-size: 1.25rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid #f3f4f6;
}
.section-body h1,.section-body h2,.section-body h3 {
    font-weight: 600; margin: 1.2rem 0 0.5rem; color: #1f2937;
}
.section-body h1 { font-size: 1.15rem; }
.section-body h2 { font-size: 1.05rem; }
.section-body h3 { font-size: 0.95rem; }
.section-body p  { margin-bottom: 0.75rem; }
.section-body ul,.section-body ol { padding-left: 1.4rem; margin-bottom: 0.75rem; }
.section-body li { margin-bottom: 0.25rem; }
.section-body code {
    background: #f3f4f6; border-radius: 4px;
    padding: 1px 5px; font-size: 0.875em; font-family: monospace;
}
.section-body pre {
    background: #1f2937; color: #f9fafb; border-radius: 6px;
    padding: 1rem 1.25rem; overflow-x: auto;
    font-size: 0.85em; font-family: monospace; margin-bottom: 1rem;
}
.section-body pre code { background: none; padding: 0; color: inherit; }
.section-body table {
    border-collapse: collapse; width: 100%; margin-bottom: 1rem; font-size: 0.9rem;
}
.section-body th,.section-body td {
    border: 1px solid #e5e7eb; padding: 0.4rem 0.75rem; text-align: left;
}
.section-body th { background: #f9fafb; font-weight: 600; }
.section-body blockquote {
    border-left: 3px solid #d1d5db; padding-left: 1rem;
    color: #6b7280; margin-bottom: 0.75rem;
}
.notes {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: #fffbeb;
    border-left: 3px solid #f59e0b;
    border-radius: 0 4px 4px 0;
    font-size: 0.875rem;
    color: #92400e;
}
.notes strong { display: block; margin-bottom: 0.25rem; }
.pending-placeholder {
    color: #9ca3af;
    font-style: italic;
    font-size: 0.9rem;
    padding: 0.5rem 0;
}
.progress-bar-outer {
    background: #e5e7eb;
    border-radius: 9999px;
    height: 8px;
    margin-top: 0.75rem;
    overflow: hidden;
}
.progress-bar-inner {
    background: #2563eb;
    height: 100%;
    border-radius: 9999px;
    transition: width 0.3s ease;
}
"""

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="page-wrapper">
  <header>
    <h1>{title}</h1>
    <div class="meta">
      Run ID: <code>{run_id}</code> &nbsp;·&nbsp;
      System: <code>{system_id}</code> &nbsp;·&nbsp;
      Status: <strong>{status}</strong> &nbsp;·&nbsp;
      Progress: {done}/{total} sections
    </div>
    <div class="progress-bar-outer">
      <div class="progress-bar-inner" style="width:{pct}%"></div>
    </div>
  </header>
  <nav>
    <h2>Table of Contents</h2>
    <ol>{toc}</ol>
  </nav>
  {sections}
</div>
</body>
</html>
"""

_RENDERABLE = {"approved", "review_ready"}


def render_preview_html(run: dict) -> str:
    """Return a self-contained HTML preview for an in-progress document run.

    Sections with status ``approved`` or ``review_ready`` are rendered fully.
    Sections still ``pending`` are listed as placeholders so the reader knows
    what is still outstanding.

    Args:
        run: Raw run dict as returned by the document repository.

    Returns:
        A UTF-8 HTML string ready for a ``text/html`` HTTP response.
    """
    plan = run.get("plan", {})
    _raw_sections: list[dict] = plan.get("sections", [])
    document_type: str = plan.get("document_type", "")
    _order = ASSEMBLY_ORDERS.get(document_type, DEFAULT_ASSEMBLY_ORDER)
    _order_index = {name: i for i, name in enumerate(_order)}
    sections: list[dict] = sorted(
        _raw_sections,
        key=lambda s: _order_index.get(s.get("section_name", ""), len(_order)),
    )
    title = run.get(
        "document_title", f"System Appreciation Document — {run.get('system_id', '')}"
    )
    run_id = run.get("run_id", "")
    system_id = run.get("system_id", "")
    status = run.get("status", "")

    done = sum(1 for s in sections if s.get("status") in _RENDERABLE)
    total = len(sections)
    pct = int(done / total * 100) if total else 0

    toc_items: list[str] = []
    section_html_parts: list[str] = []

    converter = _md.Markdown(
        extensions=["tables", "fenced_code", "nl2br"],
        output_format="html",
    )

    for sec in sections:
        sec_name = sec.get("section_name", "")
        sec_title = sec.get("title", sec_name)
        sec_status = sec.get("status", "pending")
        badge = _STATUS_BADGES.get(sec_status, "")
        anchor = _anchor(sec_name)

        toc_items.append(f'<li><a href="#{anchor}">{sec_title}</a>{badge}</li>')

        if sec_status in _RENDERABLE:
            draft_md = sec.get("draft_markdown", "").strip()
            converter.reset()
            body_html = (
                converter.convert(draft_md)
                if draft_md
                else "<p><em>No content generated.</em></p>"
            )
            notes_html = _render_notes(sec.get("notes", []))
            section_html_parts.append(
                f'<div class="section-card" id="{anchor}">'
                f"<h2>{sec_title}{badge}</h2>"
                f'<div class="section-body">{body_html}</div>'
                f"{notes_html}"
                f"</div>"
            )
        else:
            section_html_parts.append(
                f'<div class="section-card" id="{anchor}">'
                f"<h2>{sec_title}{badge}</h2>"
                f'<p class="pending-placeholder">This section has not been generated yet.</p>'
                f"</div>"
            )

    return _HTML_TEMPLATE.format(
        title=_esc(title),
        run_id=_esc(run_id),
        system_id=_esc(system_id),
        status=_esc(status),
        done=done,
        total=total,
        pct=pct,
        css=_CSS,
        toc="\n".join(toc_items),
        sections="\n".join(section_html_parts),
    )


_DASHBOARD_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 15px; line-height: 1.6; color: #1f2937; background: #f9fafb;
}
.wrapper { max-width: 1000px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
h1 { font-size: 1.6rem; font-weight: 700; color: #111827; margin-bottom: 0.25rem; }
.subtitle { color: #6b7280; font-size: 0.875rem; margin-bottom: 2rem; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
th { background: #f3f4f6; font-size: 0.8rem; font-weight: 600;
     text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280;
     padding: 0.65rem 1rem; text-align: left; border-bottom: 1px solid #e5e7eb; }
td { padding: 0.7rem 1rem; border-bottom: 1px solid #f3f4f6;
     font-size: 0.9rem; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f9fafb; }
code { background: #f3f4f6; border-radius: 4px; padding: 1px 5px;
       font-size: 0.82em; font-family: monospace; }
a.preview-link {
    display: inline-block; background: #2563eb; color: #fff;
    padding: 4px 12px; border-radius: 6px; font-size: 0.82rem;
    text-decoration: none; font-weight: 500;
}
a.preview-link:hover { background: #1d4ed8; }
.badge {
    display: inline-block; font-size: 0.72rem; padding: 2px 8px;
    border-radius: 9999px; font-weight: 500; white-space: nowrap;
}
.badge-created    { background:#e0e7ff; color:#3730a3; }
.badge-review_ready { background:#fef3c7; color:#92400e; }
.badge-approved   { background:#dcfce7; color:#166534; }
.badge-exported   { background:#d1fae5; color:#065f46; }
.badge-in_progress { background:#e0f2fe; color:#0369a1; }
.empty { text-align: center; padding: 3rem; color: #9ca3af; font-style: italic; }
.subtitle-row { display: flex; align-items: baseline; justify-content: space-between;
                flex-wrap: wrap; gap: 0.5rem; margin-bottom: 2rem; }
.subtitle-row .subtitle { margin-bottom: 0; }
.limit-form { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;
              color: #6b7280; }
.limit-form select { border: 1px solid #d1d5db; border-radius: 4px; padding: 2px 6px;
                     font-size: 0.85rem; background: #fff; cursor: pointer; }
"""

_DASHBOARD_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Document Orchestrator — Runs</title>
<style>{css}</style>
</head>
<body>
<div class="wrapper">
  <h1>Document Orchestrator</h1>
  <div class="subtitle-row">
    <p class="subtitle">All document runs — click <strong>Preview</strong> to view rendered sections in a browser.</p>
    <form class="limit-form" method="get" action="/documents/dashboard">
      <label for="limit">Show</label>
      <select id="limit" name="limit" onchange="this.form.submit()">
        <option value="25"{sel25}>25</option>
        <option value="50"{sel50}>50</option>
        <option value="100"{sel100}>100</option>
        <option value="200"{sel200}>200</option>
      </select>
      <span>runs</span>
    </form>
  </div>
  {body}
</div>
</body>
</html>
"""

_STATUS_BADGE_CLASS: dict[str, str] = {
    "created": "badge-created",
    "in_progress": "badge-in_progress",
    "review_ready": "badge-review_ready",
    "approved": "badge-approved",
    "exported": "badge-exported",
}


def render_dashboard_html(runs: list[dict], limit: int = 50) -> str:
    """Return a self-contained HTML dashboard listing all runs with clickable preview links.

    Args:
        runs: List of raw run dicts as returned by the document repository.
        limit: The currently active row limit, used to pre-select the dropdown.

    Returns:
        A UTF-8 HTML string ready for a ``text/html`` HTTP response.
    """
    def _sel(val: int) -> str:
        return ' selected' if val == limit else ''

    if not runs:
        body = '<p class="empty">No document runs found. Create one via <code>POST /documents</code>.</p>'
    else:
        rows: list[str] = []
        for run in runs:
            run_id = run.get("run_id", "")
            title = run.get("document_title", run.get("system_id", "—"))
            system_id = run.get("system_id", "—")
            status = run.get("status", "—")
            created_at = str(run.get("created_at", "—"))[:19].replace("T", " ")
            badge_class = _STATUS_BADGE_CLASS.get(status, "badge-created")
            plan = run.get("plan", {})
            sections = plan.get("sections", [])
            done = sum(1 for s in sections if s.get("status") in _RENDERABLE)
            total = len(sections)
            rows.append(
                f"<tr>"
                f"<td><code>{_esc(run_id)}</code></td>"
                f"<td>{_esc(title)}</td>"
                f"<td><code>{_esc(system_id)}</code></td>"
                f'<td><span class="badge {badge_class}">{_esc(status)}</span></td>'
                f"<td>{done}/{total}</td>"
                f"<td>{_esc(created_at)}</td>"
                f'<td><a class="preview-link" href="/documents/{_esc(run_id)}/preview" target="_blank">Preview</a></td>'
                f"</tr>"
            )
        body = (
            "<table>"
            "<thead><tr>"
            "<th>Run ID</th><th>Title</th><th>System</th><th>Status</th>"
            "<th>Sections</th><th>Created</th><th>Preview</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
        )
    return _DASHBOARD_TEMPLATE.format(css=_DASHBOARD_CSS, body=body,
                                       sel25=_sel(25), sel50=_sel(50),
                                       sel100=_sel(100), sel200=_sel(200))


def _render_notes(notes: list[str]) -> str:
    if not notes:
        return ""
    items = "".join(f"<li>{_esc(n)}</li>" for n in notes)
    return f'<div class="notes"><strong>Validator notes</strong><ul>{items}</ul></div>'


def _anchor(text: str) -> str:
    return text.lower().replace(" ", "-").replace("_", "-").replace("/", "-")


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
