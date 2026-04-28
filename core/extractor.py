"""ORBITRA CORE — deterministic HTML content extractor. No ML, pure heuristics."""

import re
import json
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag

from config import LOCATION_KEYWORDS, ORG_SUFFIXES

log = logging.getLogger("orbitra.extractor")

# --- Regex patterns ---

RE_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

RE_PHONE = re.compile(
    r"(?:"
    r"\+?66[\s\-]?\d[\s\-]?\d{4}[\s\-]?\d{4}"       # Thailand
    r"|\+?86[\s\-]?\d{2,3}[\s\-]?\d{4}[\s\-]?\d{4}"  # China
    r"|\+?65[\s\-]?\d{4}[\s\-]?\d{4}"                 # Singapore
    r"|\+?852[\s\-]?\d{4}[\s\-]?\d{4}"                # Hong Kong
    r"|\+?60[\s\-]?\d{1,2}[\s\-]?\d{3,4}[\s\-]?\d{4}"# Malaysia
    r"|\+?84[\s\-]?\d{1,2}[\s\-]?\d{4}[\s\-]?\d{4}"  # Vietnam
    r"|\+?63[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{4}"    # Philippines
    r"|\+?62[\s\-]?\d{2,3}[\s\-]?\d{4}[\s\-]?\d{4}"  # Indonesia
    r"|\+?1[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}"# USA/Canada
    r"|\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}"             # Generic
    r")"
)

RE_WECHAT = re.compile(
    r"(?:微信|wechat|weixin|wx)[\s:：#号]*([a-zA-Z0-9_\-]{5,30})",
    re.IGNORECASE
)

RE_LINE = re.compile(
    r"(?:line[\s]?id|line@|line号)[\s:：]*([a-zA-Z0-9_@.\-]{3,30})",
    re.IGNORECASE
)

RE_CJK = re.compile(r"[一-鿿㐀-䶿豈-﫿]")

# Tags considered boilerplate
NOISE_TAGS = {"nav", "header", "footer", "aside", "script", "style",
              "noscript", "iframe", "form", "button", "input", "select"}

CONTENT_TAGS = {"article", "main", "section", "div", "p", "td"}

HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass
class ExtractedPage:
    url: str
    title: str
    headings: list[str]
    main_text: str
    word_count: int
    links: list[dict]
    metadata: dict
    entities: dict
    language: str
    schema_org: list[dict]


def extract(url: str, html: str) -> ExtractedPage:
    soup = BeautifulSoup(html, "lxml")

    _remove_noise(soup)

    title = _extract_title(soup)
    headings = _extract_headings(soup)
    main_text = _extract_main_text(soup)
    links = _extract_links(url, soup)
    metadata = _extract_metadata(soup)
    schema_org = _extract_schema_org(soup)
    entities = _extract_entities(main_text + " " + title)
    language = _detect_language(main_text)
    word_count = len(main_text.split())

    return ExtractedPage(
        url=url,
        title=title,
        headings=headings,
        main_text=main_text[:50000],  # cap storage
        word_count=word_count,
        links=links,
        metadata=metadata,
        entities=entities,
        language=language,
        schema_org=schema_org,
    )


def _remove_noise(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()
    # Remove hidden elements
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden")):
        tag.decompose()
    # Remove common ad/cookie banners
    for tag in soup.find_all(class_=re.compile(r"cookie|banner|popup|modal|overlay|ad-|ads-", re.I)):
        tag.decompose()


def _score_block(tag: Tag) -> float:
    text = tag.get_text(separator=" ", strip=True)
    words = text.split()
    if len(words) < 5:
        return 0.0

    tag_count = len(tag.find_all(True)) + 1
    text_ratio = len(words) / tag_count

    # Boost if inside article/main
    ancestors = {p.name for p in tag.parents if p.name}
    in_main = bool(ancestors & {"article", "main"})

    # Penalize if near nav/footer ancestors
    near_noise = bool(ancestors & {"nav", "footer", "aside", "header"})

    score = text_ratio
    if in_main:
        score *= 2.0
    if near_noise:
        score *= 0.2

    # Boost blocks with headings nearby
    prev = tag.find_previous_sibling(HEADING_TAGS)
    if prev:
        score *= 1.3

    return score


def _extract_main_text(soup: BeautifulSoup) -> str:
    # Try article/main first
    for selector in ["article", "main", '[role="main"]', ".content", "#content", ".post", ".entry"]:
        el = soup.select_one(selector)
        if el:
            return el.get_text(separator=" ", strip=True)

    # Score all div/section blocks
    candidates = []
    for tag in soup.find_all(["div", "section", "td"]):
        s = _score_block(tag)
        if s > 0:
            candidates.append((s, tag))

    if not candidates:
        return soup.get_text(separator=" ", strip=True)[:5000]

    candidates.sort(key=lambda x: x[0], reverse=True)
    top = candidates[0][1]
    return top.get_text(separator=" ", strip=True)


def _extract_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def _extract_headings(soup: BeautifulSoup) -> list[str]:
    headings = []
    for tag in soup.find_all(HEADING_TAGS):
        text = tag.get_text(strip=True)
        if text:
            headings.append(f"{tag.name}: {text}")
    return headings[:30]


def _extract_links(base_url: str, soup: BeautifulSoup) -> list[dict]:
    from urllib.parse import urljoin
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        anchor = a.get_text(strip=True)[:150]
        try:
            full = urljoin(base_url, href)
            if full not in seen and full.startswith("http"):
                seen.add(full)
                links.append({"url": full, "anchor": anchor})
        except Exception:
            continue
    return links[:300]


def _extract_metadata(soup: BeautifulSoup) -> dict:
    meta = {}

    og_props = ["og:title", "og:description", "og:image", "og:url", "og:type", "og:site_name"]
    for prop in og_props:
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            meta[prop] = tag["content"].strip()

    twitter_props = ["twitter:title", "twitter:description", "twitter:image"]
    for prop in twitter_props:
        tag = soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            meta[prop] = tag["content"].strip()

    for name in ["description", "keywords", "author", "robots"]:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            meta[name] = tag["content"].strip()

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        meta["lang"] = html_tag["lang"].strip()

    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        meta["canonical"] = canonical["href"].strip()

    return meta


def _extract_schema_org(soup: BeautifulSoup) -> list[dict]:
    schemas = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                schemas.extend(data)
            elif isinstance(data, dict):
                schemas.append(data)
        except Exception:
            continue
    return schemas[:10]


def _extract_entities(text: str) -> dict:
    emails = list(set(RE_EMAIL.findall(text)))
    phones = list(set(RE_PHONE.findall(text)))
    wechat = list(set(RE_WECHAT.findall(text)))
    line_ids = list(set(RE_LINE.findall(text)))
    locations = _detect_locations(text)
    organizations = _detect_organizations(text)

    return {
        "emails": emails[:20],
        "phones": phones[:20],
        "wechat": wechat[:10],
        "line_ids": line_ids[:10],
        "locations": locations[:15],
        "organizations": organizations[:15],
    }


def _detect_locations(text: str) -> list[str]:
    found = []
    text_lower = text.lower()
    for loc in LOCATION_KEYWORDS:
        if loc.lower() in text_lower:
            found.append(loc)
    return found


def _detect_organizations(text: str) -> list[str]:
    orgs = []
    for suffix in ORG_SUFFIXES:
        pattern = re.compile(
            r"([A-Z][a-zA-Z\s一-鿿]{1,40}" + re.escape(suffix) + r")",
            re.UNICODE
        )
        matches = pattern.findall(text)
        orgs.extend(m.strip() for m in matches)
    return list(set(orgs))[:15]


def _detect_language(text: str) -> str:
    if not text:
        return "unknown"
    total = len(text.replace(" ", ""))
    if total == 0:
        return "unknown"
    cjk_count = len(RE_CJK.findall(text))
    ratio = cjk_count / total
    if ratio > 0.30:
        return "zh"
    if ratio > 0.05:
        return "mixed"
    return "en"
