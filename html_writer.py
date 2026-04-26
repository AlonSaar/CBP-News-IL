"""
Generates a self-contained HTML news digest from the articles store.
Output: output/cbp_hebrew_reviews.html
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

OUTPUT_DIR = config.ROOT / "output"
HTML_PATH  = OUTPUT_DIR / "cbp_hebrew_reviews.html"

# ── Admin password — change this to whatever you want ──────────────────────
# Access admin mode by adding ?admin=THIS_PASSWORD to the URL
ADMIN_PASSWORD = "ADMIN2026"
# ───────────────────────────────────────────────────────────────────────────

SITE_TITLE = "סקירות CBP | נציגות ניו יורק"


def _format_body(body: str) -> str:
    if not body:
        return ""
    sentences = [s.strip() for s in body.split(". ") if s.strip()]
    paragraphs = []
    for s in sentences:
        if not s.endswith("."):
            s += "."
        paragraphs.append(f'<p dir="rtl">{s}</p>')
    return "\n".join(paragraphs)


def _crossing_category(crossing_type: str) -> tuple[str, str]:
    """Returns (icon, short_label) for the crossing type badge."""
    ct = crossing_type.replace("סוג מעבר:", "").strip().lower()
    if "ימי" in ct:
        return "🚢", "מעבר ימי"
    if "אווירי" in ct and ("מטען" in ct or "cargo" in ct):
        return "📦", "מעבר אווירי – מטען"
    if "אווירי" in ct:
        return "✈️", "מעבר אווירי"
    if "יבשתי" in ct:
        return "🚛", "מעבר יבשתי"
    if "דואר" in ct or "מתקן" in ct:
        return "📬", "מתקן דואר/מטען"
    ct_orig = crossing_type.replace("סוג מעבר:", "").strip()
    return "🔁", ct_orig[:40]

def _crossing_detail(crossing_type: str) -> str:
    """Returns the descriptive sentence(s) from the crossing type field."""
    ct = crossing_type.replace("סוג מעבר:", "").strip()
    return ct

def _maps_url(location: str) -> str:
    """Build a Google Maps search URL for the location string."""
    # Use the English part after the dash if available
    if " - " in location:
        query = location.split(" - ", 1)[1].strip()
    else:
        query = location.strip()
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(query)}"


def _status_display(status: str) -> tuple[str, str]:
    mapping = {
        "approved": ("approved", "✓ מאושר"),
        "needs-review": ("needs-review", "⚠ לבדיקה"),
        "auto": ("approved", "✓ אוטומטי"),
    }
    return mapping.get(status, ("needs-review", status))


def _nav_html(quarters: dict) -> str:
    """
    Build a two-level year → quarter navigation.

    Top row : [הכל]  [2026 ▾]  [2027 ▾]  …
    Sub-row  : shown only when a year is active → [Q1]  [Q2]  [Q3]  [Q4]
               (empty quarters are greyed-out / disabled)
    """
    years = sorted(
        set(q.split("-")[1] for q in quarters if "-" in q),
        reverse=True,
    )

    # ── top-level row ─────────────────────────────────────────────────
    top_tabs = ['<button class="ytab ytab-all active" data-year="all" '
                'onclick="selectYear(this,\'all\')">הכל</button>']
    for year in years:
        total = sum(len(quarters.get(f"Q{n}-{year}", [])) for n in range(1, 5))
        badge = f'<span class="qtab-badge">{total}</span>'
        top_tabs.append(
            f'<button class="ytab" data-year="{year}" '
            f'onclick="selectYear(this,\'{year}\')">{year}{badge}</button>'
        )

    # ── per-year sub-rows (hidden by default) ─────────────────────────
    sub_rows = []
    for year in years:
        btns = []
        for qnum in ["Q1", "Q2", "Q3", "Q4"]:
            key   = f"{qnum}-{year}"
            count = len(quarters.get(key, []))
            if count == 0:
                btns.append(
                    f'<button class="qtab qtab-empty" disabled title="אין כתבות">{qnum}</button>'
                )
            else:
                badge = f'<span class="qtab-badge">{count}</span>'
                btns.append(
                    f'<button class="qtab" data-q="{key}" '
                    f'onclick="selectQuarter(this,\'{key}\')">{qnum}{badge}</button>'
                )
        sub_rows.append(
            f'<div class="qsub-row" data-year="{year}">\n    '
            + "\n    ".join(btns)
            + "\n  </div>"
        )

    return (
        '<div class="ytab-row">\n  '
        + "\n  ".join(top_tabs)
        + "\n</div>\n"
        + "\n".join(sub_rows)
    )


def generate(articles: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    quarters: dict[str, list[dict]] = {}
    for art in articles:
        q = art.get("quarter", "Q?-????")
        quarters.setdefault(q, []).append(art)

    # Build article cards per quarter
    quarters_html = ""
    for q in sorted(quarters.keys(), reverse=True):
        q_arts = sorted(quarters[q], key=lambda a: a.get("article_date", ""), reverse=True)
        cards = ""
        for art in q_arts:
            url        = art.get("url", "#")
            art_id     = url.split("/")[-1]
            image_url  = art.get("image_url", "")
            image_urls = art.get("image_urls") or ([image_url] if image_url else [])
            status_class, status_label = _status_display(art.get("status", "needs-review"))
            body_html  = _format_body(art.get("body", ""))
            ct_icon, ct_label = _crossing_category(art.get("crossing_type", ""))
            ct_detail  = _crossing_detail(art.get("crossing_type", ""))
            location   = art.get("location", "")
            maps_url   = _maps_url(location) if location else ""

            if image_urls:
                imgs_html = "\n".join(
                    f'<img class="article-image" src="{u}" alt="" loading="lazy" '
                    f'onerror="this.style.display=\'none\'">'
                    for u in image_urls
                )
                img_html = f'''<div class="img-wrapper" data-id="{art_id}">
          {imgs_html}
          <div class="img-overlay admin-only" onclick="changeImage('{art_id}')">📷 שנה תמונה</div>
        </div>'''
            else:
                img_html = f'''<div class="img-wrapper no-img-wrapper" data-id="{art_id}">
          <div class="no-img"><span>📷</span><small>אין תמונה</small></div>
          <div class="img-overlay admin-only" onclick="changeImage('{art_id}')">📷 הוסף תמונה</div>
        </div>'''

            maps_link = f'<a class="maps-link" href="{maps_url}" target="_blank" title="פתח במפות Google">🗺️ מפה</a>' if maps_url else ""
            admin_approved = art.get("admin_approved", True)
            approved_str = "true" if admin_approved else "false"
            pending_banner = "" if admin_approved else '<div class="pending-banner">⏳ ממתין לאישור מנהל — לא מוצג למשתמשים רגילים</div>'
            cards += f"""
      <div class="article-card" data-id="{art_id}" data-status="{status_class}" data-q="{q}" data-approved="{approved_str}" data-url="{url}">
        {pending_banner}{img_html}
        <div class="article-content" dir="rtl">
          <div class="article-top">
            <div class="article-meta">
              <span class="article-date" dir="ltr">{art.get("article_date", "")}</span>
              <span class="article-crossing" dir="rtl" title="{ct_detail}">{ct_icon} {ct_label}</span>
            </div>
            <div class="article-title editable" data-field="title" data-id="{art_id}" dir="rtl">{art.get("title", "")}</div>
            <div class="article-location-row">
              <div class="article-location editable" data-field="location" data-id="{art_id}" dir="rtl">{location}</div>
              {maps_link}
            </div>
            <div class="article-crossing-detail" dir="rtl">{ct_detail}</div>
            <div class="article-body editable" data-field="body" data-id="{art_id}" dir="rtl">{body_html}</div>
          </div>
          <div class="article-footer">
            <div class="footer-right">
              <span class="status-badge status-{status_class}" id="badge-{art_id}">{status_label}</span>
              <button class="approve-btn admin-only" id="approvebtn-{art_id}" onclick="approveArticle('{art_id}')" title="אשר כתבה">✓ אשר</button>
              <button class="delete-btn admin-only" onclick="deleteArticle('{art_id}')" title="מחק כתבה">🗑</button>
            </div>
            <a class="source-link" href="{url}" target="_blank" dir="ltr">מקור: CBP ←</a>
          </div>
        </div>
      </div>"""

        quarters_html += f"""
  <div class="quarter-section" data-q="{q}">
    {cards}
  </div>"""

    nav_html = _nav_html(quarters)

    html = f"""<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{SITE_TITLE}</title>
  <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Heebo', 'Segoe UI', Arial, sans-serif;
      background: #f4f6fb;
      color: #1a1a2e;
      direction: rtl;
    }}

    /* ── Header ── */
    header {{
      background: linear-gradient(135deg, #0d1b3e 0%, #1a3a6e 60%, #0f3460 100%);
      color: white;
      padding: 0 40px;
      height: 72px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 200;
      box-shadow: 0 2px 24px rgba(0,0,0,0.35);
    }}
    .header-brand h1 {{
      font-size: 1.45rem; font-weight: 800; letter-spacing: -0.3px;
    }}
    .header-controls {{ display: flex; gap: 10px; align-items: center; }}
    .badge {{
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.2);
      color: white; padding: 5px 14px; border-radius: 20px;
      font-size: 0.8rem; font-weight: 600;
    }}
    .edit-btn {{
      background: #e94560; border: none; color: white;
      padding: 8px 20px; border-radius: 22px;
      font-size: 0.83rem; cursor: pointer;
      font-family: inherit; font-weight: 700;
      transition: all 0.2s;
      box-shadow: 0 2px 10px rgba(233,69,96,0.4);
      display: none;
    }}
    body.admin-mode .edit-btn {{ display: inline-block; }}
    .edit-btn:hover {{ background: #c73652; transform: translateY(-1px); }}
    .edit-btn.active {{ background: #16a34a; box-shadow: 0 2px 10px rgba(22,163,74,0.4); }}

    /* ── Notices ── */
    .edit-notice {{
      display: none; background: linear-gradient(90deg,#16a34a,#15803d);
      color: white; text-align: center; padding: 10px;
      font-size: 0.87rem; font-weight: 600;
    }}
    body.edit-mode .edit-notice {{ display: block; }}
    .admin-notice {{
      display: none; background: #0d1b3e; color: #f59e0b;
      text-align: center; padding: 7px;
      font-size: 0.8rem; font-weight: 700; letter-spacing: 0.5px;
    }}
    body.admin-mode .admin-notice {{ display: block; }}

    /* ── Container ── */
    .container {{ max-width: 1160px; margin: 0 auto; padding: 36px 24px; }}

    /* ── Stats ── */
    .stats-bar {{
      background: white; border-radius: 14px;
      padding: 16px 28px; margin-bottom: 28px;
      display: flex; box-shadow: 0 1px 6px rgba(0,0,0,0.06);
      border: 1px solid #eaecf0;
    }}
    .stat-item {{
      flex: 1; text-align: center; padding: 4px 0;
      border-left: 1px solid #eee;
    }}
    .stat-item:last-child {{ border-left: none; }}
    .stat-num {{ font-size: 1.6rem; font-weight: 800; color: #0f3460; line-height: 1; margin-bottom: 3px; }}
    .stat-label {{ font-size: 0.74rem; color: #888; font-weight: 500; }}

    /* ── Quarter / Year navigation ── */
    .quarter-tabs {{
      margin-bottom: 28px;
      background: white; border-radius: 14px;
      padding: 14px 20px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.06);
      border: 1px solid #eaecf0;
    }}

    /* Year row */
    .ytab-row {{
      display: flex; gap: 8px; flex-wrap: wrap;
    }}
    .ytab {{
      padding: 8px 22px; border-radius: 22px;
      font-size: 0.85rem; font-weight: 700;
      border: 2px solid #e2e8f0;
      background: white; color: #555;
      cursor: pointer; font-family: inherit;
      transition: all 0.18s;
      display: inline-flex; align-items: center; gap: 7px;
    }}
    .ytab:hover {{ border-color: #0f3460; color: #0f3460; }}
    .ytab.active {{
      background: #0f3460; color: white;
      border-color: #0f3460;
      box-shadow: 0 2px 10px rgba(15,52,96,0.3);
    }}
    .ytab.active .qtab-badge {{ background: rgba(255,255,255,0.25); }}

    /* Quarter sub-row */
    .qsub-row {{
      display: none;
      gap: 7px; flex-wrap: wrap;
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid #eef0f4;
    }}
    .qsub-row.visible {{ display: flex; }}

    /* Quarter pill */
    .qtab {{
      padding: 5px 18px; border-radius: 18px;
      font-size: 0.78rem; font-weight: 700;
      border: 2px solid #e2e8f0;
      background: #f8faff; color: #666;
      cursor: pointer; font-family: inherit;
      transition: all 0.15s;
      display: inline-flex; align-items: center; gap: 6px;
    }}
    .qtab:hover:not(:disabled) {{ border-color: #4c5fd5; color: #4c5fd5; }}
    .qtab.active {{
      background: #4c5fd5; color: white;
      border-color: #4c5fd5;
      box-shadow: 0 2px 8px rgba(76,95,213,0.3);
    }}
    .qtab-empty {{ opacity: 0.32; cursor: not-allowed; }}
    .qtab-badge {{
      background: #e94560; color: white;
      font-size: 0.62rem; padding: 1px 6px;
      border-radius: 10px; font-weight: 800;
    }}
    .qtab.active .qtab-badge {{ background: rgba(255,255,255,0.3); }}

    /* ── Article card ── */
    .article-card {{
      background: white; border-radius: 18px;
      overflow: hidden; margin-bottom: 24px;
      display: grid; grid-template-columns: 300px 1fr;
      box-shadow: 0 1px 8px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04);
      border: 1px solid #eaecf0;
      transition: box-shadow 0.25s, transform 0.25s;
    }}
    .article-card:hover {{
      box-shadow: 0 8px 32px rgba(0,0,0,0.12);
      transform: translateY(-2px);
    }}
    .article-card.hidden {{ display: none; }}

    /* ── Image ── */
    .img-wrapper {{
      position: relative; width: 300px;
      align-self: stretch; background: #0d1b3e;
      display: flex; flex-direction: column;
    }}
    .article-image {{
      width: 100%; height: auto; display: block;
      object-fit: contain; flex-shrink: 0;
    }}
    .img-wrapper img:not(:only-child) {{
      flex: 1; height: 0; min-height: 120px; object-fit: contain;
    }}
    .no-img {{
      flex: 1; min-height: 200px;
      background: linear-gradient(135deg,#0d1b3e,#1a3a6e);
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      gap: 10px; color: rgba(255,255,255,0.25);
    }}
    .no-img span {{ font-size: 2.5rem; }}
    .no-img small {{ font-size: 0.72rem; font-weight: 500; }}
    .img-overlay {{
      position: absolute; inset: 0; z-index: 2;
      background: rgba(15,52,96,0.75);
      color: white; display: flex; align-items: center; justify-content: center;
      font-size: 0.9rem; font-weight: 700;
      opacity: 0; transition: opacity 0.2s; cursor: pointer;
      backdrop-filter: blur(3px);
    }}
    body.edit-mode .img-wrapper:hover .img-overlay {{ opacity: 1; }}

    /* ── Content ── */
    .article-content {{
      padding: 22px 26px; display: flex;
      flex-direction: column; justify-content: space-between; direction: rtl;
    }}
    .article-top {{ flex: 1; }}
    .article-meta {{
      display: flex; gap: 8px; align-items: center;
      margin-bottom: 10px; flex-wrap: wrap;
    }}
    .article-date {{
      font-size: 0.75rem; color: #999; font-weight: 500;
      direction: ltr; unicode-bidi: isolate;
      background: #f4f6fb; padding: 2px 8px; border-radius: 6px;
    }}
    .article-crossing {{
      font-size: 0.7rem;
      background: linear-gradient(135deg,#eef2ff,#e8edff);
      color: #4c5fd5; padding: 3px 10px; border-radius: 8px;
      font-weight: 700; direction: rtl; border: 1px solid #d8deff;
    }}
    .article-title {{
      font-size: 1.1rem; font-weight: 800; color: #0d1b3e;
      line-height: 1.5; margin-bottom: 6px;
      text-align: right; direction: rtl;
    }}
    .article-location {{
      font-size: 0.8rem; color: #e94560; font-weight: 700;
      margin-bottom: 14px; text-align: right; direction: rtl;
      unicode-bidi: plaintext;
    }}
    .article-location::before {{ content: "📍"; font-size: 0.75rem; margin-left: 4px; }}
    .article-location-row {{
      display: flex; align-items: center; gap: 8px;
      margin-bottom: 6px;
    }}
    .article-location-row .article-location {{ margin-bottom: 0; }}
    .maps-link {{
      font-size: 0.75rem; white-space: nowrap;
      color: #4c5fd5; text-decoration: none;
      background: #eef2ff; padding: 2px 8px;
      border-radius: 8px; border: 1px solid #d8deff;
      font-weight: 600; transition: all 0.15s;
      flex-shrink: 0;
    }}
    .maps-link:hover {{ background: #4c5fd5; color: white; }}
    .article-crossing-detail {{
      font-size: 0.75rem; color: #888; font-weight: 400;
      margin-bottom: 10px; text-align: right; direction: rtl;
      line-height: 1.5;
    }}
    .article-body {{
      font-size: 0.88rem; color: #4a4a5a;
      direction: rtl; text-align: right;
    }}
    .article-body p {{
      line-height: 1.85; margin-bottom: 16px;
      text-align: right; direction: rtl; unicode-bidi: plaintext;
    }}
    .article-body p:last-child {{ margin-bottom: 0; }}

    /* ── Footer ── */
    .article-footer {{
      margin-top: 16px; padding-top: 12px;
      border-top: 1px solid #f0f0f4;
      display: flex; justify-content: space-between; align-items: center;
    }}
    .footer-right {{ display: flex; align-items: center; gap: 8px; }}
    .source-link {{
      font-size: 0.73rem; color: #bbb; text-decoration: none;
      direction: ltr; unicode-bidi: isolate; transition: color 0.15s;
    }}
    .source-link:hover {{ color: #4c5fd5; }}
    .status-badge {{
      font-size: 0.68rem; padding: 3px 10px;
      border-radius: 8px; font-weight: 700;
    }}
    .status-approved {{ background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }}
    .status-needs-review {{ background: #fef9c3; color: #92400e; border: 1px solid #fde68a; }}

    /* ── Admin-only elements ── */
    .admin-only {{ display: none !important; }}
    body.admin-mode .admin-only {{ display: inline-flex !important; }}
    .admin-stat {{ display: none !important; }}
    body.admin-mode .admin-stat {{ display: block !important; }}

    /* ── Unapproved articles ── */
    body:not(.admin-mode) .article-card[data-approved="false"] {{ display: none !important; }}
    .pending-banner {{
      background: #fef9c3; color: #92400e;
      padding: 7px 16px; text-align: center;
      font-size: 0.78rem; font-weight: 700;
      border-bottom: 2px solid #fde68a;
      letter-spacing: 0.3px;
    }}
    body.admin-mode .article-card[data-approved="false"] {{
      border: 2px solid #fbbf24;
      box-shadow: 0 0 0 3px rgba(251,191,36,0.12);
    }}

    /* ── Toast notification ── */
    #cbp-toast {{
      position: fixed; bottom: 28px; left: 50%;
      transform: translateX(-50%) translateY(120px);
      padding: 12px 28px; border-radius: 14px;
      font-weight: 700; font-size: 0.9rem;
      box-shadow: 0 4px 24px rgba(0,0,0,0.25);
      z-index: 9999; transition: transform 0.35s cubic-bezier(0.34,1.56,0.64,1);
      pointer-events: none; white-space: nowrap;
    }}
    #cbp-toast.show {{ transform: translateX(-50%) translateY(0); }}
    #cbp-toast.success {{ background: #16a34a; color: white; }}
    #cbp-toast.error   {{ background: #dc2626; color: white; }}

    .approve-btn {{
      font-size: 0.68rem; padding: 3px 10px; border-radius: 8px;
      font-weight: 700; border: 1px solid #bbf7d0;
      background: #f0fdf4; color: #15803d;
      cursor: pointer; font-family: inherit; transition: all 0.15s;
      align-items: center;
    }}
    .approve-btn:hover {{ background: #dcfce7; }}
    .approve-btn.approved {{ background: #16a34a; color: white; border-color: #16a34a; }}

    .delete-btn {{
      font-size: 0.75rem; padding: 3px 8px; border-radius: 8px;
      font-weight: 700; border: 1px solid #fecaca;
      background: #fff5f5; color: #dc2626;
      cursor: pointer; font-family: inherit; transition: all 0.15s;
      align-items: center;
    }}
    .delete-btn:hover {{ background: #fee2e2; }}

    /* ── Edit mode ── */
    body.edit-mode .editable {{
      outline: 2px dashed #e94560; outline-offset: 3px;
      cursor: text; border-radius: 4px; min-height: 1em;
    }}
    body.edit-mode .editable:hover {{ background: rgba(233,69,96,0.04); }}
    body.edit-mode .editable:focus {{ outline: 2px solid #e94560; background: #fff9fa; }}

    /* ── Page footer ── */
    .page-footer {{
      text-align: center; padding: 36px; color: #bbb;
      font-size: 0.78rem; border-top: 1px solid #eaecf0; margin-top: 20px;
    }}

    @media (max-width: 740px) {{
      .article-card {{ grid-template-columns: 1fr; }}
      .img-wrapper {{ width: 100%; }}
      header {{ padding: 0 16px; }}
      .container {{ padding: 20px 12px; }}
    }}
  </style>
</head>
<body>

<div id="cbp-toast"></div>
<div class="edit-notice">✏️ מצב עריכה פעיל — לחץ על כל טקסט לעריכה · לחץ על תמונה לשינויה · השינויים נשמרים אוטומטית</div>
<div class="admin-notice">🔐 מצב מנהל פעיל</div>

<header>
  <div class="header-brand">
    <h1>{SITE_TITLE}</h1>
  </div>
  <div class="header-controls">
    <span class="badge" id="header-count">{len(articles)} כתבות</span>
    <button class="edit-btn" id="editToggle" onclick="toggleEdit()">✏️ עריכה</button>
  </div>
</header>

<div class="container">
  <div class="stats-bar">
    <div class="stat-item">
      <div class="stat-num" id="total-count">{len(articles)}</div>
      <div class="stat-label">כתבות מתורגמות</div>
    </div>
    <div class="stat-item">
      <div class="stat-num" id="quarters-count">{len(quarters)}</div>
      <div class="stat-label">רבעונים</div>
    </div>
    <div class="stat-item admin-stat">
      <div class="stat-num" id="approved-count">0</div>
      <div class="stat-label">ממתינות לאישור</div>
    </div>
    <div class="stat-item">
      <div class="stat-num">{now_str.split()[0]}</div>
      <div class="stat-label">עודכן</div>
    </div>
  </div>

  <div class="quarter-tabs">
    {nav_html}
  </div>

{quarters_html}
</div>

<div class="page-footer">
  נוצר אוטומטית על ידי cbp-translator · {now_str}
</div>

<script>
const STORAGE_KEY = 'cbp_edits';
const IMG_KEY     = 'cbp_images';
const APPROVE_KEY = 'cbp_approved';
const DELETE_KEY  = 'cbp_deleted';
const ADMIN_PASS  = '{ADMIN_PASSWORD}';
const GITHUB_PAT  = '{config.GITHUB_PAT}';
const GITHUB_REPO = '{config.GITHUB_REPO}';
const APPROVED_FILE = 'state/approved_urls.json';

function loadEdits()    {{ try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)  || '{{}}'); }} catch(e) {{ return {{}}; }} }}
function saveEdits(e)   {{ localStorage.setItem(STORAGE_KEY,  JSON.stringify(e)); }}
function loadImgs()     {{ try {{ return JSON.parse(localStorage.getItem(IMG_KEY)      || '{{}}'); }} catch(e) {{ return {{}}; }} }}
function saveImgs(e)    {{ localStorage.setItem(IMG_KEY,      JSON.stringify(e)); }}
function loadApproved() {{ try {{ return JSON.parse(localStorage.getItem(APPROVE_KEY) || '[]');  }} catch(e) {{ return []; }} }}
function saveApproved(a){{ localStorage.setItem(APPROVE_KEY, JSON.stringify(a)); }}
function loadDeleted()  {{ try {{ return JSON.parse(localStorage.getItem(DELETE_KEY)  || '[]');  }} catch(e) {{ return []; }} }}
function saveDeleted(d) {{ localStorage.setItem(DELETE_KEY,  JSON.stringify(d)); }}

// ── Year / Quarter navigation ────────────────────────────────────────────────

// Show/hide sections helper
function _showSections(predicate) {{
  document.querySelectorAll('.quarter-section').forEach(sec => {{
    sec.style.display = predicate(sec.dataset.q) ? '' : 'none';
  }});
  applyDeleted();
}}

function selectYear(btn, year) {{
  // Deactivate all year tabs and hide all sub-rows + quarter tabs
  document.querySelectorAll('.ytab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.qsub-row').forEach(r => r.classList.remove('visible'));
  document.querySelectorAll('.qtab').forEach(b => b.classList.remove('active'));

  btn.classList.add('active');

  if (year === 'all') {{
    _showSections(() => true);
  }} else {{
    // Show articles for this whole year
    _showSections(q => q && q.endsWith('-' + year));
    // Reveal the quarter sub-row for this year
    const subRow = document.querySelector('.qsub-row[data-year="' + year + '"]');
    if (subRow) subRow.classList.add('visible');
  }}
}}

function selectQuarter(btn, q) {{
  // Deactivate other quarter tabs within the same sub-row only
  if (btn.closest('.qsub-row')) {{
    btn.closest('.qsub-row').querySelectorAll('.qtab').forEach(b => b.classList.remove('active'));
  }}
  btn.classList.add('active');
  _showSections(sq => sq === q);
}}

// ── Admin mode ──────────────────────────────────────────────────────────────
function checkAdmin() {{
  const params = new URLSearchParams(window.location.search);
  if (params.get('admin') === ADMIN_PASS) {{
    document.body.classList.add('admin-mode');
  }}
}}

// ── Edit mode ───────────────────────────────────────────────────────────────
function toggleEdit() {{
  const body = document.body;
  const btn  = document.getElementById('editToggle');
  const isEdit = body.classList.toggle('edit-mode');
  btn.classList.toggle('active', isEdit);
  btn.textContent = isEdit ? '✓ סיום עריכה' : '✏️ עריכה';
  document.querySelectorAll('.editable').forEach(el => {{
    el.contentEditable = isEdit ? 'true' : 'false';
    if (isEdit) el.addEventListener('input', onEdit);
    else        el.removeEventListener('input', onEdit);
  }});
}}

function onEdit(e) {{
  const el = e.target;
  if (!el.dataset.id) return;
  const key = el.dataset.id + '_' + el.dataset.field;
  const edits = loadEdits();
  edits[key] = el.innerHTML;
  saveEdits(edits);
}}

// ── Image change ─────────────────────────────────────────────────────────────
function changeImage(id) {{
  if (!document.body.classList.contains('edit-mode')) return;
  const newUrl = prompt('הכנס URL של תמונה:', loadImgs()[id] || '');
  if (newUrl === null) return;
  const imgs = loadImgs();
  if (newUrl.trim() === '') delete imgs[id];
  else imgs[id] = newUrl.trim();
  saveImgs(imgs);
  applyAll();
}}

// ── Toast ─────────────────────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg, type) {{
  const t = document.getElementById('cbp-toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'show ' + (type || 'success');
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {{ t.className = ''; }}, 4000);
}}

// ── Approve (GitHub API) ──────────────────────────────────────────────────────
async function approveArticle(id) {{
  const card = document.querySelector('.article-card[data-id="' + id + '"]');
  if (!card) return;
  const articleUrl = card.dataset.url;
  const badge = document.getElementById('badge-' + id);
  const btn   = document.getElementById('approvebtn-' + id);

  if (!GITHUB_PAT) {{
    showToast('GitHub PAT לא מוגדר — פנה למנהל המערכת', 'error');
    return;
  }}

  // Immediate UI feedback
  if (btn)   {{ btn.textContent = '⏳'; btn.disabled = true; }}
  if (badge) {{ badge.className = 'status-badge status-approved'; badge.textContent = '⏳ שומר...'; }}

  try {{
    const apiBase = 'https://api.github.com/repos/' + GITHUB_REPO + '/contents/' + APPROVED_FILE;

    // GET current file
    const getResp = await fetch(apiBase, {{
      headers: {{ 'Authorization': 'Bearer ' + GITHUB_PAT, 'Accept': 'application/vnd.github+json' }}
    }});
    if (!getResp.ok) throw new Error('GET failed: ' + getResp.status);
    const fileData = await getResp.json();

    // Decode, add URL, re-encode
    const currentList = JSON.parse(atob(fileData.content.replace(/\n/g, '')));
    if (!currentList.includes(articleUrl)) currentList.push(articleUrl);

    // PUT updated file
    const newContent = JSON.stringify(currentList, null, 2);
    const putResp = await fetch(apiBase, {{
      method: 'PUT',
      headers: {{
        'Authorization': 'Bearer ' + GITHUB_PAT,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json'
      }},
      body: JSON.stringify({{
        message: 'approve: ' + id,
        content: btoa(unescape(encodeURIComponent(newContent))),
        sha: fileData.sha
      }})
    }});
    if (!putResp.ok) throw new Error('PUT failed: ' + putResp.status);

    // Success
    card.dataset.approved = 'true';
    const pending = card.querySelector('.pending-banner');
    if (pending) pending.remove();
    if (badge) {{ badge.className = 'status-badge status-approved'; badge.textContent = '✓ מאושר'; }}
    if (btn)   {{ btn.textContent = '✓ מאושר'; btn.classList.add('approved'); btn.disabled = false; }}
    showToast('✓ הכתבה אושרה! האתר יתעדכן תוך כ-2 דקות.', 'success');
    updateCounts();

  }} catch(err) {{
    console.error('Approve failed:', err);
    if (badge) {{ badge.className = 'status-badge status-needs-review'; badge.textContent = '⚠ לבדיקה'; }}
    if (btn)   {{ btn.textContent = '✓ אשר'; btn.disabled = false; }}
    showToast('שגיאה: ' + err.message, 'error');
  }}
}}

function applyApprovals() {{
  // Approvals now come from the server (data-approved attribute on each card).
  // This function is kept for backward compat but does nothing on initial load.
}}

function updateApprovedCount() {{
  let pending = 0;
  document.querySelectorAll('.article-card').forEach(card => {{
    if (card.dataset.approved !== 'true') pending++;
  }});
  const el = document.getElementById('approved-count');
  if (el) el.textContent = pending;
}}

// ── Delete ───────────────────────────────────────────────────────────────────
function deleteArticle(id) {{
  if (!confirm('למחוק כתבה זו מהתצוגה?')) return;
  const deleted = loadDeleted();
  if (!deleted.includes(id)) deleted.push(id);
  saveDeleted(deleted);
  applyDeleted();
}}

function applyDeleted() {{
  const deleted = loadDeleted();
  document.querySelectorAll('.article-card').forEach(card => {{
    card.classList.toggle('hidden', deleted.includes(card.dataset.id));
  }});
  updateCounts();
}}

function updateCounts() {{
  const deleted  = loadDeleted();
  const isAdmin  = document.body.classList.contains('admin-mode');
  let total = 0;
  const qCounts = {{}};

  document.querySelectorAll('.article-card').forEach(card => {{
    const id = card.dataset.id;
    const approved = card.dataset.approved === 'true';
    if (!deleted.includes(id) && (isAdmin || approved)) {{
      total++;
      const q = card.dataset.q;
      qCounts[q] = (qCounts[q] || 0) + 1;
    }}
  }});

  // Update stats bar
  const totalEl = document.getElementById('total-count');
  if (totalEl) totalEl.textContent = total;
  const headerEl = document.getElementById('header-count');
  if (headerEl) headerEl.textContent = total + ' כתבות';

  // Update quarter badges
  document.querySelectorAll('.qtab[data-q]').forEach(btn => {{
    const q = btn.dataset.q;
    const count = qCounts[q] || 0;
    const badge = btn.querySelector('.qtab-badge');
    if (badge) badge.textContent = count;
    if (count === 0) {{ btn.classList.add('qtab-empty'); btn.disabled = true; }}
    else {{ btn.classList.remove('qtab-empty'); btn.disabled = false; }}
  }});

  // Update year badges
  document.querySelectorAll('.ytab[data-year]').forEach(btn => {{
    const year = btn.dataset.year;
    if (year === 'all') return;
    let yearTotal = 0;
    for (const [q, c] of Object.entries(qCounts)) {{
      if (q.endsWith('-' + year)) yearTotal += c;
    }}
    const badge = btn.querySelector('.qtab-badge');
    if (badge) badge.textContent = yearTotal;
  }});

  // Update quarters count (only quarters with remaining articles)
  const activeQs = Object.values(qCounts).filter(c => c > 0).length;
  const qCountEl = document.getElementById('quarters-count');
  if (qCountEl) qCountEl.textContent = activeQs;
}}

// ── Apply saved edits & images ───────────────────────────────────────────────
function applyEditsAndImages() {{
  const edits = loadEdits();
  document.querySelectorAll('.editable[data-id]').forEach(el => {{
    const key = el.dataset.id + '_' + el.dataset.field;
    if (edits[key] !== undefined) el.innerHTML = edits[key];
  }});
  const imgs = loadImgs();
  Object.entries(imgs).forEach(([id, url]) => {{
    const wrapper = document.querySelector(`.img-wrapper[data-id="${{id}}"]`);
    if (!wrapper) return;
    let img = wrapper.querySelector('img.article-image');
    if (img) {{ img.src = url; img.style.display = ''; }}
    else {{
      const noImg = wrapper.querySelector('.no-img');
      if (noImg) noImg.remove();
      wrapper.classList.remove('no-img-wrapper');
      const newImg = document.createElement('img');
      newImg.className = 'article-image'; newImg.src = url; newImg.alt = ''; newImg.loading = 'lazy';
      wrapper.insertBefore(newImg, wrapper.querySelector('.img-overlay'));
    }}
  }});
}}

function applyAll() {{
  applyEditsAndImages();
  applyApprovals();
  applyDeleted();
  updateApprovedCount();
}}

// ── Init ─────────────────────────────────────────────────────────────────────
checkAdmin();
applyAll();
</script>
</body>
</html>"""

    HTML_PATH.write_text(html, encoding="utf-8")
    logger.info("HTML digest written: %s (%d articles)", HTML_PATH, len(articles))
    return HTML_PATH
