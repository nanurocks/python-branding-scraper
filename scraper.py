from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests, re, cssutils, json
from urllib.parse import urljoin, urlparse


# ==============================
# 🔹 MAIN SCRAPER FUNCTION
# ==============================
def scrape_brand_data(domain):
    html = None
    try:
        url = domain if domain.startswith("http") else f"https://{domain}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=60000, wait_until="networkidle")
                html = page.content()
            except Exception as e:
                return {"error": f"Failed to load website: {str(e)}"}
            finally:
                # Ensure page and browser are closed even if there's an error
                try:
                    page.close()
                except:
                    pass
                try:
                    browser.close()
                except:
                    pass
        
        if not html:
            return {"error": "Failed to retrieve page content"}
        
        soup = BeautifulSoup(html, "html.parser")

    except Exception as e:
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

    headings = [h.get_text(strip=True) for h in soup.find_all(re.compile("^h[1]$"))]
    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
    visible_text = re.sub(r"\s+", " ", " ".join(paragraphs)).strip()
    content_snippet = visible_text[:3000]

    # ----------------------------
    # Logo Extraction System
    # ----------------------------
    logo_candidates = []

    # (1) Find nav/header elements and look for anchor with href="/" or domain + logo keyword
    parsed_url = urlparse(url)
    domain_name = parsed_url.netloc.replace("www.", "")

    for section in soup.find_all(["nav", "header"]):
        anchors = section.find_all("a", href=True)
        for a in anchors:
            href = a["href"].strip()
            role = a.get("role", "").lower()
            aria_label = a.get("aria-label", "").lower()
            classes = " ".join(a.get("class", [])).lower()

            if (
                href in ["/", "", f"https://{domain_name}", f"http://{domain_name}"]
                or domain_name in href
                or "logo" in role
                or "logo" in aria_label
                or re.search(r"(^|_|-)logo($|_|-)", classes)
            ):
                # Find image or SVG inside this anchor
                img = a.find("img")
                if img:
                    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                    srcset = img.get("srcset")
                    final_src = parse_srcset(srcset) or src
                    if final_src and not is_small_image(final_src):
                        logo_candidates.append(abs_url(url, final_src))
                else:
                    svg = a.find("svg")
                    if svg:
                        logo_candidates.append(str(svg))

    # (2) meta og:image / twitter:image
    for prop in ("og:image", "twitter:image", "og:image:secure_url"):
        m = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if m and m.get("content"):
            href = abs_url(url, m["content"])
            if href:
                logo_candidates.append(href)

    # (3) Fallback <img> scan with logo hints
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        srcset = img.get("srcset")
        final_src = parse_srcset(srcset) or src
        if not final_src or is_small_image(final_src):
            continue

        attrs_text = " ".join(
            [img.get("alt", ""), " ".join(img.get("class", [])), img.get("id", "")]
        ).lower()

        if re.search(r"logo|brand|header", attrs_text):
            logo_candidates.append(abs_url(url, final_src))

    # Deduplicate
    seen = set()
    unique_logos = []
    for l in logo_candidates:
        if l and l not in seen:
            seen.add(l)
            unique_logos.append(l)

    logo = unique_logos[0] if unique_logos else ""

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

    # Final structured output
    result = {
        "url": url,
        "title": title,
        "meta_description": meta_desc,
        "headings": headings,
        "content_snippet": content_snippet,
        "logo": logo,
        "favicon": favicon,
        "colors": colors,
    }

    return result


# ==============================
# 🔹 SEND TO PHP SERVER
# ==============================
def send_to_php(domain):
    scraped_data = scrape_brand_data(domain)
    print("Scraped data received:")
    print(scraped_data)
    if "error" in scraped_data:
        print("❌ Scraping failed:", scraped_data["error"])
        return

    php_endpoint = "http://www.kblive.com/brand/collect"
    headers = {
        "Content-Type": "application/json",
        "X-Auth-Key": "SECRET123"  # Optional: use for security
    }

    try:
        response = requests.post(php_endpoint, headers=headers, json=scraped_data, timeout=30)
        print("✅ Data sent successfully to PHP. Response:")
        print(response.text)
    except Exception as e:
        print("❌ Error sending data to PHP:", e)


# ==============================
# 🔹 RUN SCRAPER
# ==============================
if __name__ == "__main__":
    domain = input("Enter website URL or domain: ").strip()
    send_to_php(domain)
