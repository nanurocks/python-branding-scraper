from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests, re, cssutils
from urllib.parse import urljoin, urlparse


def scrape_brand_data(domain):
    browser = None
    try:
        url = domain if domain.startswith("http") else f"https://{domain}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=60000, wait_until="networkidle")
            except Exception as e:
                browser.close()
                return {"error": f"Failed to load website: {str(e)}"}
            html = page.content()
            browser.close()
            browser = None
        soup = BeautifulSoup(html, "html.parser")

    except Exception as e:
        if browser:
            try:
                browser.close()
            except:
                pass
        return {"error": f"Scraping error: {str(e)}"}

    # ----------------------------
    # Utility helpers
    # ----------------------------
    def abs_url(base, link):
        return urljoin(base, link) if link else None

    def parse_srcset(srcset):
        if not srcset:
            return None
        parts = [s.strip().split()[0] for s in srcset.split(",") if s.strip()]
        return parts[-1] if parts else None

    def is_potential_logo_filename(path):
        return bool(re.search(r"logo|brand|identity|site|main|header", path, re.I))

    def is_small_image(url):
        # Quick heuristic by file name or extension
        if not url:
            return False
        return bool(re.search(r"favicon|apple-touch-icon|icon-\d+", url, re.I))

    # ----------------------------
    # Basic Metadata
    # ----------------------------
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    meta_desc = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        meta_desc = desc_tag["content"].strip()

    headings = [h.get_text(strip=True) for h in soup.find_all(re.compile("^h[1-3]$"))]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    visible_text = re.sub(r"\s+", " ", " ".join(paragraphs)).strip()
    content_snippet = visible_text[:2000]

    # ----------------------------
    # Logo Extraction System
    # ----------------------------
    logo_candidates = []

    # (1) <link> icons
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel", [])).lower()
        href = abs_url(url, link["href"])
        if any(k in rel for k in ["icon", "shortcut", "apple-touch-icon"]):
            if not is_small_image(href):
                logo_candidates.append((href, 10))

    # (2) meta og:image / twitter:image
    for prop in ("og:image", "twitter:image", "og:image:secure_url"):
        m = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if m and m.get("content"):
            href = abs_url(url, m["content"])
            if href:
                score = 40 if is_potential_logo_filename(href) else 20
                logo_candidates.append((href, score))

    # (3) <img> with logo hints
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        srcset = img.get("srcset")
        final_src = parse_srcset(srcset) or src
        if not final_src:
            continue

        href = abs_url(url, final_src)
        if not href:
            continue
        if is_small_image(href):
            continue

        attrs_text = " ".join(
            [img.get("alt", ""), " ".join(img.get("class", [])), img.get("id", "")]
        ).lower()

        score = 10
        if re.search(r"logo|brand|site|main", attrs_text):
            score += 40
        if re.search(r"header|nav", attrs_text):
            score += 10
        if is_potential_logo_filename(href):
            score += 30
        logo_candidates.append((href, score))

    # (4) Inline SVG (score-based detection)
    all_svgs = soup.find_all("svg")
    for svg in all_svgs:
        score = 0
        attrs = " ".join([svg.get("id", ""), " ".join(svg.get("class", []))]).lower()
        if re.search(r"logo|brand|site|header", attrs):
            score += 50

        # Check parent hierarchy
        parent = svg.parent
        for _ in range(3):
            if not parent or not getattr(parent, "name", None):
                break
            parent_attrs = " ".join(
                [parent.get("id", ""), " ".join(parent.get("class", []))]
            ).lower()
            if re.search(r"logo|brand|nav|header", parent_attrs):
                score += 30
                break
            parent = parent.parent

        # Width/height ratio
        try:
            width = float(svg.get("width", 0) or 0)
            height = float(svg.get("height", 0) or 0)
            if width > height * 2:
                score += 15
        except:
            pass

        if score >= 50:
            logo_candidates.append((str(svg), score))

    # (5) CSS background logos
    css_links = [
        abs_url(url, link.get("href"))
        for link in soup.find_all("link", rel="stylesheet")
        if link.get("href")
    ]
    for css_link in css_links:
        try:
            r = requests.get(css_link, timeout=10)
            if not r.ok:
                continue
            for match in re.finditer(r'url\(["\']?(.*?)["\']?\)', r.text):
                path = match.group(1)
                if is_potential_logo_filename(path):
                    logo_candidates.append((abs_url(css_link, path), 20))
        except Exception:
            continue

    # ----------------------------
    # Rank & Deduplicate
    # ----------------------------
    seen = set()
    ranked = []
    for logo, score in sorted(logo_candidates, key=lambda x: x[1], reverse=True):
        if logo and logo not in seen:
            seen.add(logo)
            ranked.append(logo)

    logo = ranked[0] if ranked else ""

    # ----------------------------
    # Favicon (backup)
    # ----------------------------
    favicon = ""
    icon_tag = soup.find("link", rel=re.compile("icon", re.I))
    if icon_tag and icon_tag.get("href"):
        favicon = abs_url(url, icon_tag["href"])

    # ----------------------------
    # Basic color extraction
    # ----------------------------
    colors = []
    for style_tag in soup.find_all("style"):
        colors += re.findall(r"(#[0-9a-fA-F]{3,6}|rgb\([^)]*\))", style_tag.get_text())
    colors = list(set(colors))[:10]

    return {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "headings": headings,
        "content_snippet": content_snippet,
        "logo": logo,
        "favicon": favicon,
        "colors": colors,
    }
