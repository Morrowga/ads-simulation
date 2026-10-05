"""Report PDF with reportlab (pure Python). Reasons and evidence only, never suggestions."""

from __future__ import annotations

from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import get_settings


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def _pct(v: Any, nd: int = 1) -> str:
    try:
        return f"{float(v) * 100:.{nd}f}%"
    except (TypeError, ValueError):
        return "-"


def _rng(d: dict[str, Any] | None, nd: int = 0) -> str:
    if not d:
        return "-"
    try:
        return f"{float(d.get('p10', 0)):.{nd}f} / {float(d.get('p50', 0)):.{nd}f} / {float(d.get('p90', 0)):.{nd}f}"
    except (TypeError, ValueError):
        return "-"


def render_pdf(report: dict[str, Any]) -> bytes:
    import io

    buf = io.BytesIO()
    app_name = get_settings().APP_NAME
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{app_name} report: {report.get('title', '')}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=6)
    h2 = ParagraphStyle(
        "h2",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#1f2a44"),
    )
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    story: list[Any] = []

    summary = report.get("summary", {})
    headline = report.get("headline_metric", {})
    story.append(_p(f"{app_name} · Virtual audience report", small))
    story.append(_p(report.get("title", "Ad test"), h1))
    story.append(
        _p(
            f"Goal: {report.get('goal')} · Post type: {report.get('post_type')} · Country: {report.get('country')} · Engine {report.get('engine_version')}",
            small,
        )
    )
    story.append(Spacer(1, 6))
    score = summary.get("score")
    story.append(
        _p(
            f"Score: {score if score is not None else '-'} / 100 (P10/P50/P90: {_rng(summary.get('score_range'), 1)})",
            body,
        )
    )
    story.append(
        _p(
            f"{headline.get('label', 'Goal metric')}: {_rng(headline.get('value'))} virtual agents (P10/P50/P90); rate {_pct(((headline.get('rate') or {}).get('p50')), 2)}",
            body,
        )
    )
    est = headline.get("estimated_people") or {}
    if est:
        story.append(
            _p(
                f"Estimated real people: {int(est.get('p10', 0))} / {int(est.get('p50', 0))} / {int(est.get('p90', 0))}",
                body,
            )
        )
    story.append(_p(report.get("note", ""), small))

    # funnel
    story.append(_p("Funnel (median run, virtual agents)", h2))
    funnel = report.get("funnel", {})
    rows = [["Step", "Agents"]]
    for k in (
        "seen",
        "skipped",
        "stopped",
        "reacted",
        "commented",
        "shared",
        "saved",
        "clicked",
        "messaged",
        "bought",
    ):
        if k in funnel:
            rows.append([k, str(int(funnel[k]))])
    story.append(_table(rows))

    # platforms
    story.append(_p("Platforms", h2))
    rows = [["Platform", "Audience", "Runs", "Score P50", "Stop rate", "CTR", "Goal rate", "Goal value P50"]]
    for pl in report.get("platforms", []):
        rates = pl.get("rates", {})
        rows.append(
            [
                pl.get("name", pl.get("code")),
                str(pl.get("audience_name", "")),
                str(pl.get("runs")),
                str((pl.get("score") or {}).get("p50", "-")),
                _pct((rates.get("stop_rate") or {}).get("p50")),
                _pct((rates.get("ctr") or {}).get("p50"), 2),
                _pct((pl.get("goal_rate") or {}).get("p50"), 2),
                str((pl.get("goal_value") or {}).get("p50", "-")),
            ]
        )
    story.append(_table(rows))

    # reasons
    story.append(_p("Reasons (from evidence)", h2))
    for r in report.get("reasons", []):
        story.append(
            _p(
                f"[{r.get('section')}] {r.get('statement')}  (evidence {', '.join(r.get('evidence_ids', []))}; confidence {float(r.get('confidence', 0)):.2f})",
                body,
            )
        )
    if not report.get("reasons"):
        story.append(_p("No statements passed the evidence check.", body))

    # evidence
    story.append(PageBreak())
    story.append(_p("Evidence table", h2))
    for e in report.get("evidence", []):
        story.append(_p(f"{e.get('id')} [{e.get('type')}] {e.get('statement')}", body))

    # language groups
    lgs = report.get("language_groups", [])
    if lgs:
        story.append(_p("Language groups", h2))
        rows = [["Group", "Seen", "Stop rate", "CTR", "Comments", "Positive reactions", "Negative reactions"]]
        for g in lgs:
            rows.append(
                [
                    g.get("name", g.get("code")),
                    str(g.get("seen")),
                    _pct(g.get("stop_rate")),
                    _pct(g.get("ctr"), 2),
                    str(g.get("comments")),
                    str(g.get("reactions_positive")),
                    str(g.get("reactions_negative")),
                ]
            )
        story.append(_table(rows))

    # audiences (full tier)
    auds = report.get("audiences", [])
    if len(auds) > 1:
        story.append(_p("Audience comparison", h2))
        rows = [["Audience", "Score P50", "Goal value P50", "Stop rate", "CTR"]]
        for a in auds:
            rates = a.get("rates") or {}
            rows.append(
                [
                    a.get("name"),
                    str((a.get("score") or {}).get("p50", "-")),
                    str((a.get("goal_value") or {}).get("p50", "-")),
                    _pct((rates.get("stop_rate") or {}).get("p50")),
                    _pct((rates.get("ctr") or {}).get("p50"), 2),
                ]
            )
        story.append(_table(rows))

    # comments
    comments = report.get("comments", [])
    if comments:
        story.append(_p("Example comments (virtual audience, English)", h2))
        for c in comments[:25]:
            story.append(
                _p(
                    f"{c.get('archetype')} [{c.get('language_group')}, {c.get('platform')}]: {c.get('text')} ({c.get('topic')})",
                    body,
                )
            )

    story.append(Spacer(1, 8))
    story.append(_p(f"Settings versions: {report.get('settings_versions')}", small))
    story.append(_p(f"Test id: {report.get('test_id')}", small))
    doc.build(story)
    return buf.getvalue()


def _table(rows: list[list[str]]) -> Table:
    t = Table(rows, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2a44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fa")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t
