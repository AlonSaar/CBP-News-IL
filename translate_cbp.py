"""
CBP Newsroom -> Hebrew review translator (Phase 1 MVP).

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python translate_cbp.py <CBP_article_URL>

What it does:
    1. Fetches the article HTML.
    2. Extracts title, body, and hero image URL.
    3. Classifies: is this a qualifying seizure article (drugs/plants/animals) with a real seizure photo?
    4. If yes, translates to Hebrew using the strict template.
    5. Prints result.
"""

import os
import sys
import base64
import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic

# ---------------------------------------------------------------------------
# TRANSLATION RULES - edit this to tune the Hebrew output.
# ---------------------------------------------------------------------------
HEBREW_RULES = """You are a professional Hebrew translator producing CBP seizure reviews for the Israeli Tax Authority. Your translations must be detailed, factual, and use the exact vocabulary listed below.

REQUIRED VOCABULARY - use these exact words:
- Seized: תפסו (NEVER use יירטו)
- Located/found: אותרו
- Confiscated: הוחרמו
- Concealed: הוסתרו / שהוסתרו
- Secondary inspection: הופנה לבדיקה משנית
- CBP agents: סוכני CBP / קציני CBP / מומחי CBP
- Transferred for investigation: הועבר לחקירה / הועבר לטיפול
- Arrested: נעצר
- Screening: סריקה (NEVER use X-ray)
- Estimated value: שווי מוערך של
- Total weight: משקל כולל של

OUTPUT STRUCTURE - exactly this order:
Line 1: Title. Start with "תפיסת" or "איתור" or "מעצר". Include what was seized, quantity if prominent, location.
Line 2: Hebrew location - English location, state/territory
         Example: נמל הכניסה סן חואן - San Juan Port of Entry, פוארטו ריקו
Line 3: סוג מעבר: [standard crossing type wording]
Line 4: blank
Line 5: One detailed paragraph with ALL facts from the source.

PARAGRAPH - include every detail stated in the source:
- Who performed the inspection (CBP unit type)
- What was inspected (vehicle make/model, vessel name, suitcase, cargo container, mail package)
- Inspection type (primary/secondary/agricultural/canine/cargo)
- What was found (exact substance)
- Concealment location (door panels, chassis, under hull, seed bag, vacuum packages in cartons, ship's safe, etc.)
- Exact quantity/weight in pounds (and kg if given), number of packages
- Estimated street value in dollars
- Origin country or destination if stated
- Arrests (who, nationality if stated)
- Which agency received the case (HSI, DEA, local police, etc.)
A short paragraph means you missed facts. Re-read the source and include everything.

CROSSING TYPE - pick whichever applies:
- Land border Mexico-US (trucks): מעבר גבול יבשתי בין מקסיקו לארצות הברית. משמש בעיקר לתנועת משאיות מטען וכלי רכב מסחריים החוצים את הגבול.
- Land border Mexico-US (mixed): מעבר גבול יבשתי בין מקסיקו לארצות הברית. משמש לתנועת משאיות מטען, רכבים פרטיים והולכי רגל.
- Sea: מעבר ימי. משמש להגעת אוניות מטען, כלי שיט מסחריים וסירות.
- International air (passengers): מעבר אווירי בינלאומי. משמש לבדיקת נוסעים, מזוודות ומטענים בטיסות בינלאומיות.
- International air cargo: מעבר אווירי בינלאומי למטען. משמש לבדיקת משלוחי מטען בטיסות בינלאומיות.
- Mail/cargo facility: מתקן דואר או מטען בינלאומי. משמש לבדיקת משלוחי מטען וחבילות בינלאומיות.

FORMAT:
- Plain text only. No markdown (no **, no #, no -).
- No preamble or postamble. Output the 4-block review and nothing else.
"""


# ---------------------------------------------------------------------------
# Classifier prompt - decides whether article qualifies for translation.
# ---------------------------------------------------------------------------
CLASSIFIER_PROMPT = """Decide if this CBP article qualifies for translation.

QUALIFIES if the article describes a CBP seizure of ONE OR MORE of:
- Drugs (cocaine, meth, fentanyl, heroin, marijuana, pills, tablets, etc.)
- Firearms or weapons (guns, ammunition, explosives)
- Animals, wildlife, or any living creatures (live animals, insects, birds, fish, wildlife parts)
- Plants (narcotic plants, agricultural contraband, restricted seeds, prohibited vegetation)

The article must describe an actual seizure with quantities or specific details.

Does NOT qualify: personnel announcements, policy updates, currency-only seizures, statistics reports, general enforcement updates.

Respond with EXACTLY one of:
YES
NO:<short reason>

Title: {title}

Body (truncated): {body}
"""


def fetch_article(url: str) -> dict:
    """Fetch CBP article and extract title, body text, and hero image URL."""
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CBP-Translator/0.1)"}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Remove boilerplate tags that add noise
    for tag in soup.find_all(["nav", "script", "style", "footer", "header", "noscript"]):
        tag.decompose()

    # Try specific content containers first
    body_el = (
        soup.find("div", class_="field--name-body")
        or soup.find("div", class_="field-name-body")
        or soup.find("div", class_="field--name-field-description")
        or soup.find("div", class_="layout__region--content")
        or soup.find("div", class_="node__content")
        or soup.find("article")
        or soup.find("main")
    )

    body = body_el.get_text(" ", strip=True) if body_el else ""

    # Always fall back to full page text if body is short
    if len(body) < 300:
        full_text = soup.get_text(" ", strip=True)
        # Try to cut from the title onwards to remove top navigation noise
        title_pos = full_text.find(title) if title else -1
        if title_pos >= 0:
            body = full_text[title_pos:]
        else:
            body = full_text

    # Hero image - try multiple sources
    image_url = None

    # 1. og:image meta tag (most reliable on CBP)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image_url = og["content"]

    # 2. twitter:image meta tag
    if not image_url:
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            image_url = tw["content"]

    # 3. First <img> inside article body
    if not image_url and body_el:
        img = body_el.find("img")
        if img and img.get("src"):
            image_url = img["src"]

    # 4. Any image URL in page pointing to CBP's media folder
    if not image_url:
        import re
        page_text = str(soup)
        match = re.search(r'(https?://www\.cbp\.gov/sites/default/files/assets/images/[^\s"\'<>]+)', page_text)
        if match:
            image_url = match.group(1)

    if image_url and image_url.startswith("/"):
        image_url = "https://www.cbp.gov" + image_url

    return {"title": title, "body": body, "image_url": image_url, "url": url}


def classify(article: dict, client: Anthropic) -> tuple[bool, str]:
    """Return (qualifies, reason)."""
    prompt = CLASSIFIER_PROMPT.format(
        title=article["title"],
        body=article["body"][:3000],
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=60,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = msg.content[0].text.strip()
    qualifies = answer.upper().startswith("YES")
    return qualifies, answer


def translate(article: dict, client: Anthropic) -> str:
    """Translate article to Hebrew review per strict template."""
    user_msg = f"""Source CBP article (URL: {article['url']}):

TITLE: {article['title']}

BODY:
{article['body']}

Produce the Hebrew review now, following every rule in the system prompt."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=HEBREW_RULES,
        messages=[{"role": "user", "content": user_msg}],
    )
    return msg.content[0].text.strip()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python translate_cbp.py <CBP_article_URL>")
        return 1

    url = sys.argv[1]
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY env var not set.")
        return 1

    client = Anthropic(api_key=api_key)

    print(f"[1/3] Fetching: {url}")
    try:
        article = fetch_article(url)
    except Exception as e:
        print(f"ERROR fetching article: {e}")
        return 1

    print(f"      Title: {article['title'][:80]}")
    print(f"      Image: {article['image_url'] or '(none)'}")

    print("[2/3] Classifying...")
    qualifies, reason = classify(article, client)
    print(f"      Verdict: {reason}")
    if not qualifies:
        print("SKIP: article does not qualify.")
        return 0

    print("[3/3] Translating to Hebrew...")
    review = translate(article, client)

    print()
    print("=" * 70)
    print(review)
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
