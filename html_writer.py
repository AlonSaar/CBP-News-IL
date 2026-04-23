"""
Generates a self-contained HTML news digest from the articles store.
Output: output/cbp_hebrew_reviews.html
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

OUTPUT_DIR = config.ROOT / "output"
HTML_PATH  = OUTPUT_DIR / "cbp_hebrew_reviews.html"

# ── Admin password — change this to whatever you want ──────────────────────
# Access admin mode by adding ?admin=THIS_PASSWORD to the URL
ADMIN_PASSWORD = "cbpIL2026"
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


def _crossing_short(crossing_type: str) -> str:
    ct = crossing_type.replace("סוג מעבר:", "").strip()
    first = ct.split(".")[0].strip()
    return first[:60] + ("…" if len(first) > 60 else "")


def _status_display(status: str) -> tuple[str, str]:
    mapping = {
        "approved": ("approved", "✓ מאושר"),
        "needs-review": ("needs-review", "⚠ לבדיקה"),
        "auto": ("approved", "✓ אוטומטי"),
    }
    return mapping.get(status, ("needs-review", status))


def _all_quarter_tabs(quarters: dict) -> str:
    """Generate Q1–Q4 tabs for every year present in the data."""
    years = sorted(
        set(q.split("-")[1] for q in quarters if "-" in q),
        reverse=True
    )
    tabs = ['<button class="qtab active" data-q="all" onclick="filterQ(this,\'all\')">הכל</button>']
    for year in years:
        for qnum in ["Q1", "Q2", "Q3", "Q4"]:
            key = f"{qnum}-{year}"
            count = len(quarters.get(key, []))
            disabled = 'disabled title="אין כתבות"' if count == 0 else f'onclick="filterQ(this,\'{key}\')"'
            cls = "qtab" + (" qtab-empty" if count == 0 else "")
            label = f"{qnum} {year}"
            badge = f'<span class="qtab-badge">{count}</span>' if count > 0 else ""
            tabs.append(f'<button class="{cls}" data-q="{key}" {disabled}>{label}{badge}</button>')
    return "\n".join(tabs)


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
            ct_short   = _crossing_short(art.get("crossing_type", ""))

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

            cards += f"""
      <div class="article-card" data-id="{art_id}" data-status="{status_class}" data-q="{q}">
        {img_html}
        <div class="article-content" dir="rtl">
          <div class="article-top">
            <div class="article-meta">
              <span class="article-date" dir="ltr">{art.get("article_date", "")}</span>
              <span class="article-crossing editable" data-field="crossing_short" dir="rtl">{ct_short}</span>
            </div>
            <div class="article-title editable" data-field="title" data-id="{art_id}" dir="rtl">{art.get("title", "")}</div>
            <div class="article-location editable" data-field="location" data-id="{art_id}" dir="rtl">{art.get("location", "")}</div>
            <div class="article-body editable" data-field="body" data-id="{art_id}" dir="rtl">{body_html}</div>
          </div>
          <div class="article-footer">
            <div class="footer-right">
              <span class="status-badge status-{status_class}" id="badge-{art_id}">{status_label}</span>
              <button class="approve-btn admin-only" id="approvebtn-{art_id}" onclick="toggleApprove('{art_id}')" title="אשר כתבה">✓ אשר</button>
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

    quarter_tabs_html = _all_quarter_tabs(quarters)

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

    /* ── Quarter tabs ── */
    .quarter-tabs {{
      display: flex; gap: 8px; flex-wrap: wrap;
      margin-bottom: 28px;
      background: white; border-radius: 14px;
      padding: 14px 20px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.06);
      border: 1px solid #eaecf0;
    }}
    .qtab {{
      padding: 7px 18px; border-radius: 22px;
      font-size: 0.82rem; font-weight: 700;
      border: 2px solid #e2e8f0;
      background: white; color: #666;
      cursor: pointer; font-family: inherit;
      transition: all 0.18s;
      display: flex; align-items: center; gap: 6px;
    }}
    .qtab:hover:not(:disabled) {{ border-color: #0f3460; color: #0f3460; }}
    .qtab.active {{
      background: #0f3460; color: white;
      border-color: #0f3460;
      box-shadow: 0 2px 8px rgba(15,52,96,0.3);
    }}
    .qtab-empty {{ opacity: 0.35; cursor: not-allowed; }}
    .qtab-badge {{
      background: #e94560; color: white;
      font-size: 0.65rem; padding: 1px 6px;
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

<div class="edit-notice">✏️ מצב עריכה פעיל — לחץ על כל טקסט לעריכה · לחץ על תמונה לשינויה · השינויים נשמרים אוטומטית</div>
<div class="admin-notice">🔐 מצב מנהל פעיל</div>

<header>
  <div class="header-brand">
    <h1>{SITE_TITLE}</h1>
  </div>
  <div class="header-controls">
    <span class="badge">{len(articles)} כתבות</span>
    <button class="edit-btn" id="editToggle" onclick="toggleEdit()">✏️ עריכה</button>
  </div>
</header>

<div class="container">
  <div class="stats-bar">
    <div class="stat-item">
      <div class="stat-num">{len(articles)}</div>
      <div class="stat-label">כתבות מתורגמות</div>
    </div>
    <div class="stat-item">
      <div class="stat-num">{len(quarters)}</div>
      <div class="stat-label">רבעונים</div>
    </div>
    <div class="stat-item">
      <div class="stat-num" id="approved-count">0</div>
      <div class="stat-label">מאושרות</div>
    </div>
    <div class="stat-item">
      <div class="stat-num">{now_str.split()[0]}</div>
      <div class="stat-label">עודכן</div>
    </div>
  </div>

  <div class="quarter-tabs">
    {quarter_tabs_html}
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

function loadEdits()    {{ try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY)  || '{{}}'); }} catch(e) {{ return {{}}; }} }}
function saveEdits(e)   {{ localStorage.setItem(STORAGE_KEY,  JSON.stringify(e)); }}
function loadImgs()     {{ try {{ return JSON.parse(localStorage.getItem(IMG_KEY)      || '{{}}'); }} catch(e) {{ return {{}}; }} }}
function saveImgs(e)    {{ localStorage.setItem(IMG_KEY,      JSON.stringify(e)); }}
function loadApproved() {{ try {{ return JSON.parse(localStorage.getItem(APPROVE_KEY) || '[]');  }} catch(e) {{ return []; }} }}
function saveApproved(a){{ localStorage.setItem(APPROVE_KEY, JSON.stringify(a)); }}
function loadDeleted()  {{ try {{ return JSON.parse(localStorage.getItem(DELETE_KEY)  || '[]');  }} catch(e) {{ return []; }} }}
function saveDeleted(d) {{ localStorage.setItem(DELETE_KEY,  JSON.stringify(d)); }}

// ── Quarter filter ──────────────────────────────────────────────────────────
function filterQ(btn, q) {{
  document.querySelectorAll('.qtab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.quarter-section').forEach(sec => {{
    sec.style.display = (q === 'all' || sec.dataset.q === q) ? '' : 'none';
  }});
  // Also respect deleted cards within visible sections
  applyDeleted();
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

// ── Approve ──────────────────────────────────────────────────────────────────
function toggleApprove(id) {{
  const approved = loadApproved();
  const idx = approved.indexOf(id);
  if (idx === -1) approved.push(id); else approved.splice(idx, 1);
  saveApproved(approved);
  applyApprovals();
  updateApprovedCount();
}}

function applyApprovals() {{
  const approved = loadApproved();
  document.querySelectorAll('.article-card').forEach(card => {{
    const id    = card.dataset.id;
    const badge = document.getElementById('badge-' + id);
    const btn   = document.getElementById('approvebtn-' + id);
    if (!badge) return;
    if (approved.includes(id)) {{
      badge.className = 'status-badge status-approved';
      badge.textContent = '✓ מאושר';
      if (btn) {{ btn.textContent = '✓ מאושר'; btn.classList.add('approved'); }}
    }} else {{
      const orig = card.dataset.status || 'needs-review';
      badge.className = 'status-badge status-' + orig;
      badge.textContent = orig === 'approved' ? '✓ מאושר' : '⚠ לבדיקה';
      if (btn) {{ btn.textContent = '✓ אשר'; btn.classList.remove('approved'); }}
    }}
  }});
}}

function updateApprovedCount() {{
  const el = document.getElementById('approved-count');
  if (el) el.textContent = loadApproved().length;
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
