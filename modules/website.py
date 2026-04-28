"""ORBITRA CORE — website intelligence: structure, branding, schema, nav detection."""

import re
import json
import logging
from collections import Counter
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

log = logging.getLogger("orbitra.website")


@dataclass
class WebsiteIntel:
    url: str
    domain: str
    title: str
    description: str
    logo_url: str | None
    favicon_url: str | None
    color_palette: list[str]
    navigation: list[dict]
    tech_hints: list[str]
    schema_types: list[str]
    og_metadata: dict
    contact_links: list[str]
    social_links: dict[str, str]
    html_structure: dict


def analyze_website(url: str, html: str) -> WebsiteIntel:
    soup = BeautifulSoup(html, "lxml")
    domain = urlparse(url).netloc

    return WebsiteIntel(
        url=url,
        domain=domain,
        title=_get_title(soup),
        description=_get_description(soup),
        logo_url=_detect_logo(url, soup),
        favicon_url=_detect_favicon(url, soup),
        color_palette=_extract_colors(soup),
        navigation=_extract_navigation(url, soup),
        tech_hints=_detect_tech(soup),
        schema_types=_get_schema_types(soup),
        og_metadata=_get_og(soup),
        contact_links=_find_contact_links(url, soup),
        social_links=_find_social_links(soup),
        html_structure=_analyze_structure(soup),
    )


def _get_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    t = soup.find("title")
    return t.get_text(strip=True) if t else ""


def _get_description(soup: BeautifulSoup) -> str:
    for attr in [("meta", {"property": "og:description"}),
                 ("meta", {"name": "description"}),
                 ("meta", {"name": "twitter:description"})]:
        tag = soup.find(attr[0], attr[1])
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def _detect_logo(base_url: str, soup: BeautifulSoup) -> str | None:
    # Priority 1: img with "logo" in src/class/id/alt
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "").lower()
        cls = " ".join(img.get("class", [])).lower()
        img_id = img.get("id", "").lower()

        if any("logo" in x for x in [src.lower(), alt, cls, img_id]):
            return urljoin(base_url, src) if src else None

    # Priority 2: first image in header tag (top-left heuristic)
    header = soup.find("header")
    if header:
        img = header.find("img")
        if img and img.get("src"):
            return urljoin(base_url, img["src"])

    # Priority 3: schema.org logo
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                logo = data.get("logo")
                if logo:
                    if isinstance(logo, str):
                        return logo
                    if isinstance(logo, dict):
                        return logo.get("url", logo.get("contentUrl"))
        except Exception:
            continue

    return None


def _detect_favicon(base_url: str, soup: BeautifulSoup) -> str | None:
    for rel in ["icon", "shortcut icon", "apple-touch-icon"]:
        link = soup.find("link", rel=lambda r: r and rel in r)
        if link and link.get("href"):
            return urljoin(base_url, link["href"])
    return urljoin(base_url, "/favicon.ico")


def _extract_colors(soup: BeautifulSoup) -> list[str]:
    """Extract color palette from inline styles and style tags."""
    colors: Counter = Counter()

    hex_re = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
    rgb_re = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")

    def process_css(css_text: str):
        for match in hex_re.finditer(css_text):
            hex_val = match.group(0).upper()
            # Normalize 3-digit to 6-digit
            if len(hex_val) == 4:
                hex_val = "#" + "".join(c * 2 for c in hex_val[1:])
            colors[hex_val] += 1

    # Inline styles on all elements
    for tag in soup.find_all(style=True):
        process_css(tag["style"])

    # <style> blocks
    for style_tag in soup.find_all("style"):
        process_css(style_tag.get_text())

    # Return top 8 most frequent, skip near-white and near-black noise
    palette = []
    for color, _ in colors.most_common(30):
        if _is_meaningful_color(color):
            palette.append(color)
        if len(palette) >= 8:
            break
    return palette


def _is_meaningful_color(hex_color: str) -> bool:
    """Skip pure white, black, and near-transparent grays."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        # Skip near-white (all channels > 240)
        if r > 240 and g > 240 and b > 240:
            return False
        # Skip near-black (all channels < 15)
        if r < 15 and g < 15 and b < 15:
            return False
        # Skip pure grays (R=G=B)
        if abs(r - g) < 5 and abs(g - b) < 5:
            return False
        return True
    except Exception:
        return False


def _extract_navigation(base_url: str, soup: BeautifulSoup) -> list[dict]:
    nav_items = []
    seen = set()

    # Find primary nav elements
    for nav in soup.find_all(["nav", "ul"], limit=5):
        cls = " ".join(nav.get("class", [])).lower()
        nav_id = nav.get("id", "").lower()
        # Prioritize main nav
        if nav.name == "ul" and not any(k in cls + nav_id for k in ["nav", "menu", "header"]):
            continue

        for a in nav.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)
            if not text or href in seen:
                continue
            seen.add(href)
            full = urljoin(base_url, href)
            nav_items.append({"label": text, "url": full})
            if len(nav_items) >= 20:
                break
        if len(nav_items) >= 20:
            break

    return nav_items


def _detect_tech(soup: BeautifulSoup) -> list[str]:
    """Detect tech stack from HTML patterns."""
    hints = []
    html_str = str(soup)

    patterns = {
        "WordPress": ["wp-content", "wp-includes", "WordPress"],
        "React": ["react", "__NEXT_DATA__", "_next/static"],
        "Next.js": ["__NEXT_DATA__", "_next/"],
        "Vue.js": ["vue.js", "vue.min.js", "__vue__"],
        "Angular": ["ng-version", "angular.js", "ng-app"],
        "Shopify": ["shopify", "cdn.shopify.com", "Shopify.theme"],
        "Wix": ["wix.com", "parastorage.com"],
        "Squarespace": ["squarespace", "sqspcdn.com"],
        "Bootstrap": ["bootstrap.css", "bootstrap.min.css"],
        "Tailwind": ["tailwind", "tw-"],
        "jQuery": ["jquery.js", "jquery.min.js"],
        "Google Analytics": ["google-analytics.com", "gtag(", "UA-"],
        "Cloudflare": ["cloudflare", "__cf_"],
    }

    for tech, signals in patterns.items():
        if any(s in html_str for s in signals):
            hints.append(tech)

    return hints


def _get_schema_types(soup: BeautifulSoup) -> list[str]:
    types = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                t = data.get("@type")
                if t:
                    types.append(t if isinstance(t, str) else str(t))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        t = item.get("@type")
                        if t:
                            types.append(t if isinstance(t, str) else str(t))
        except Exception:
            continue
    return list(set(types))


def _get_og(soup: BeautifulSoup) -> dict:
    og = {}
    for tag in soup.find_all("meta", property=re.compile(r"^og:")):
        og[tag["property"]] = tag.get("content", "")
    return og


def _find_contact_links(base_url: str, soup: BeautifulSoup) -> list[str]:
    contact = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        if any(k in href or k in text for k in ["contact", "about", "reach", "联系", "お問い合わせ"]):
            contact.append(urljoin(base_url, a["href"]))
    return list(set(contact))[:10]


def _find_social_links(soup: BeautifulSoup) -> dict[str, str]:
    socials = {}
    patterns = {
        "facebook": r"facebook\.com/[\w.]+",
        "instagram": r"instagram\.com/[\w.]+",
        "twitter": r"twitter\.com/[\w.]+",
        "linkedin": r"linkedin\.com/(?:company|in)/[\w\-]+",
        "youtube": r"youtube\.com/(?:channel|user|c)/[\w\-]+",
        "wechat": r"weixin\.qq\.com|mp\.weixin",
        "weibo": r"weibo\.com/[\w.]+",
        "line": r"line\.me/[\w/]+",
    }
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for platform, pattern in patterns.items():
            if platform not in socials and re.search(pattern, href, re.I):
                socials[platform] = href
    return socials


def _analyze_structure(soup: BeautifulSoup) -> dict:
    return {
        "has_header": bool(soup.find("header")),
        "has_footer": bool(soup.find("footer")),
        "has_nav": bool(soup.find("nav")),
        "has_main": bool(soup.find("main")),
        "has_article": bool(soup.find("article")),
        "has_sidebar": bool(soup.find("aside")),
        "form_count": len(soup.find_all("form")),
        "image_count": len(soup.find_all("img")),
        "total_links": len(soup.find_all("a", href=True)),
        "h1_count": len(soup.find_all("h1")),
        "has_schema": bool(soup.find("script", type="application/ld+json")),
    }
