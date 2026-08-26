"""Small, dependency-free HTML renderer for the operator review pages.

FastAPI does not require Jinja, and the service's JSON API should remain usable in
minimal installations.  Keeping these two fixed pages as Python renderers avoids
making application import contingent on an optional template package.
"""
from html import escape
from urllib.parse import quote

from fastapi.responses import HTMLResponse


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _path(value) -> str:
    return quote(str(value), safe="")


def _status(value) -> str:
    return _e(str(value).replace("_", " "))


def _base(title: str, body: str, error=None) -> str:
    alert = ""
    if error:
        alert = f'<div class="error" role="alert"><strong>Action not completed.</strong> {_e(error)}</div>'
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)} · Release Manager</title><link rel="stylesheet" href="/static/review.css"></head>
<body><header class="site-header"><a class="brand" href="/review">Release Manager</a>
<span class="access-note">Network access permits review actions; authentication is not yet enabled.</span></header>
<main class="page">{alert}{body}</main></body></html>'''


def _activity(events) -> str:
    if not events:
        return '<p class="muted">No activity recorded.</p>'
    rows = []
    for event in events:
        actor = f' by {_e(event.get("actor"))}' if event.get("actor") else ""
        rows.append(f'<li><time>{_e(event.get("created_at"))}</time> {_status(event.get("kind"))}{actor}</li>')
    return '<ul class="activity">' + "".join(rows) + "</ul>"


def review_list(context) -> str:
    packs = context["packs"]
    if not packs:
        content = '''<header class="page-heading"><div><p class="eyebrow">Repository releases</p><h1>Review queue</h1></div>
<p>Inspect durable release packs and their publication status.</p></header>
<section class="empty"><h2>No release packs yet</h2><p>Run a scan to create a pack when repository changes are release-worthy.</p></section>'''
        return _base("Release reviews", content)
    selected = context.get("selected_id")
    timeline, cards = [], []
    for pack in packs:
        pid, status = pack["id"], pack["status"]
        selected_class = " selected" if pid == selected else ""
        timeline.append(f'''<li class="status-{_e(status)}{selected_class}"><a href="/review?selected={quote(str(pid))}">
<strong>v{_e(pack.get('version'))}</strong><span>{_status(status)}</span></a></li>''')
        metrics = ""
        if pack.get("metrics"):
            values = "".join(f'<div><dd>{_e(value)}</dd><dt>{_e(label)}</dt></div>' for label, value in pack["metrics"].items())
            metrics = f'<dl class="metrics">{values}</dl>'
        card_class = " selected-card" if pid == selected else ""
        cards.append(f'''<article class="pack-card{card_class}" id="pack-{_e(pid)}"><header><div><p class="eyebrow">{_e(pack.get('created_at'))}</p>
<h2>{_e(pack.get('title'))}</h2></div><span class="pill status-{_e(status)}">{_status(status)}</span></header>
<p>{_e(pack.get('rationale'))}</p>{metrics}<h3>Activity</h3>{_activity(pack.get('activity'))}
<a class="detail-link" href="/review/packs/{_path(pid)}">Review full release pack <span aria-hidden="true">→</span></a></article>''')
    content = f'''<header class="page-heading"><div><p class="eyebrow">Repository releases</p><h1>Review queue</h1></div>
<p>Inspect durable release packs and their publication status.</p></header><div class="review-layout">
<nav class="timeline" aria-label="Release pack timeline"><h2>Timeline</h2><ol>{''.join(timeline)}</ol></nav>
<section class="cards" aria-label="Release packs">{''.join(cards)}</section></div>'''
    return _base("Release reviews", content)


def _history(events) -> str:
    if not events:
        return '<p class="muted">No activity recorded.</p>'
    rows = []
    for event in events:
        detail = event.get("detail") or {}
        actor = f'<span>Actor: {_e(event.get("actor"))}</span>' if event.get("actor") else ""
        reason = f'<p>{_e(detail.get("reason"))}</p>' if detail.get("reason") else ""
        receipt = f'<a href="{_e(detail.get("url"))}">Publication receipt</a>' if detail.get("url") else ""
        rows.append(f'<li><strong>{_status(event.get("kind"))}</strong><time>{_e(event.get("created_at"))}</time>{actor}{reason}{receipt}</li>')
    return "<ol>" + "".join(rows) + "</ol>"


def pack_detail(context) -> str:
    pack, evidence = context["pack"], context["evidence"]
    pid, status = pack["id"], pack["status"]
    items = list(evidence.get("pulls", [])) + list(evidence.get("commits", []))
    if items:
        rows = "".join(f'''<li><a href="{_e(item.get('url'))}" rel="noopener noreferrer">{_e(item.get('id'))} — {_e(item.get('title'))}</a>
<small>{_e(item.get('kind'))} by {_e(item.get('author'))} · {_e(item.get('occurred_at'))}</small></li>''' for item in items)
        evidence_html = f'<ul class="evidence">{rows}</ul>'
    else:
        evidence_html = '<p class="muted">No stored commit or pull-request evidence is available.</p>'
    if status == "pending":
        values = context.get("values") or {}
        actor, reason = _e(values.get("actor", "")), _e(values.get("reason", ""))
        actions = f'''<section class="actions"><h2>Decision</h2><p>Both decisions are terminal. Approval immediately publishes this release to GitHub.</p>
<form method="post" action="/review/packs/{_path(pid)}/approve"><h3>Approve and publish</h3><label for="approve-actor">Your name</label>
<input id="approve-actor" name="actor" value="{actor}" required><label for="approve-reason">Reason</label>
<textarea id="approve-reason" name="reason" required>{reason}</textarea><button class="approve" type="submit">Approve and publish</button></form>
<form method="post" action="/review/packs/{_path(pid)}/reject"><h3>Reject release</h3><label for="reject-actor">Your name</label>
<input id="reject-actor" name="actor" value="{actor}" required><label for="reject-reason">Reason</label>
<textarea id="reject-reason" name="reason" required>{reason}</textarea><button class="reject" type="submit">Reject release</button></form></section>'''
    else:
        actions = f'<section class="outcome"><h2>Review outcome</h2><p>This pack is <strong>{_status(status)}</strong>. A new decision is not available.</p></section>'
    content = f'''<a class="back" href="/review">← All release packs</a><header class="detail-heading"><div>
<p class="eyebrow">Release v{_e(pack.get('version'))} · {_e(pack.get('created_at'))}</p><h1>{_e(pack.get('title'))}</h1></div>
<span class="pill status-{_e(status)}">{_status(status)}</span></header><div class="detail-grid"><section>
<article class="content-block"><h2>Changelog and release notes</h2><pre>{_e(pack.get('body'))}</pre></article>
<article class="content-block"><h2>Announcement</h2><p class="preserve">{_e(pack.get('announcement'))}</p></article>
<article class="content-block"><h2>Version rationale</h2><p class="preserve">{_e(pack.get('rationale'))}</p></article>
<article class="content-block"><h2>Supporting evidence</h2>{evidence_html}</article></section><aside>{actions}
<section class="history"><h2>Audit history</h2>{_history(context.get('activity'))}</section></aside></div>'''
    return _base(pack.get("title", "Release pack"), content, context.get("error"))


class Templates:
    """Compatibility-sized facade for the two TemplateResponse call sites."""

    def TemplateResponse(self, request, name, context, status_code=200):
        render = review_list if name == "review_list.html" else pack_detail
        return HTMLResponse(render(context), status_code=status_code)
