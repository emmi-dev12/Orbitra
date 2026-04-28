"""ORBITRA CORE — URL discovery. Multi-engine with fallback seed injection."""

import asyncio
import json
import logging
import re
from urllib.parse import urlparse, quote_plus

import httpx
from bs4 import BeautifulSoup

from config import MAX_SEEDS_FROM_DISCOVERY

log = logging.getLogger("orbitra.discovery")

DDG_LITE   = "https://lite.duckduckgo.com/lite/"
YAHOO_URL  = "https://search.yahoo.com/search"
BRAVE_URL  = "https://search.brave.com/search"
ECOSIA_URL = "https://www.ecosia.org/search"
CDX_INDEX  = "https://index.commoncrawl.org/collinfo.json"

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

SKIP_DOMAINS = {
    "facebook.com","twitter.com","instagram.com","youtube.com","wikipedia.org",
    "linkedin.com","reddit.com","pinterest.com","tiktok.com","duckduckgo.com",
    "bing.com","google.com","amazon.com","apple.com","microsoft.com","t.co",
    "lite.duckduckgo.com","yahoo.com","search.yahoo.com","brave.com",
    "ecosia.org","w3.org","schemas.live.com","yimg.com","s.yimg.com",
}

# Fallback seeds organised by (sport/topic, region).
# Only inject seeds whose region matches the detected query region.
# Format: { (topic_keyword, region) : [urls] }
# topic_keyword="" means match any topic for that region.
# region="" means match any region for that topic.
FALLBACK_SEEDS_GEO: dict[tuple[str, str], list[str]] = {
    # Basketball — SE Asia
    ("basketball", "sea"): [
        "https://www.hoopclubth.com",
        "https://www.tigersportstravel.com/sport/basketball",
        "https://worldballtours.com/basketball-tours",
        "https://www.campasia.asia",
        "https://www.pacificpinesports.com",
        "https://basketball.exposureevents.com",
        "https://www.topflighthongkong.com",
    ],
    # Basketball — China
    ("basketball", "china"): [
        "https://www.pacificpinesports.com",
        "https://www.topflighthongkong.com",
        "https://www.nba.cn",
        "https://worldballtours.com/basketball-tours",
    ],
    # Basketball — Europe
    ("basketball", "europe"): [
        "https://www.fiba.basketball/europe",
        "https://worldballtours.com/basketball-tours",
        "https://eurobasket.com",
    ],
    # Basketball — global (no region)
    ("basketball", ""): [
        "https://basketball.exposureevents.com",
        "https://worldballtours.com/basketball-tours",
        "https://www.nbccamps.com/international",
    ],
    # Golf — SE Asia
    ("golf", "sea"): [
        "https://www.golfasian.com",
        "https://www.asiantour.com",
        "https://promo.pgadevelopment.hk/summercamp",
        "https://www.golfthailand.org",
        "https://www.singapore.golf",
    ],
    # Golf — Europe
    ("golf", "europe"): [
        "https://www.europeantour.com",
        "https://www.swiss-golf.ch",
        "https://www.golf.de",
    ],
    # Golf — global
    ("golf", ""): [
        "https://www.golfasian.com",
        "https://www.pga.com",
        "https://www.europeantour.com",
    ],
    # Summer camp — SE Asia
    ("summer camp", "sea"): [
        "https://www.campbeaumont.asia",
        "https://www.littlestepsasia.com",
        "https://theexperiencesfirm.com",
        "https://www.bkkkids.com",
    ],
    # Summer camp — Europe
    ("summer camp", "europe"): [
        "https://www.eurocamps.com",
        "https://www.campsinternational.com",
        "https://www.kidscamps.ch",
    ],
    # Summer camp — global
    ("summer camp", ""): [
        "https://www.campsinternational.com",
        "https://www.urbanadventures.com",
    ],
    # Travel agency — SE Asia
    ("travel agency", "sea"): [
        "https://www.tourradar.com/g/b-south-east-asia-tour-operators",
        "https://www.southeastasiatravel.com",
        "https://www.intrepidtravel.com/en/asia/southeast-asia",
        "https://www.asiatravel.com",
        "https://www.chinahighlights.com/southeast-asia",
    ],
    # Travel agency — Europe
    ("travel agency", "europe"): [
        "https://www.intrepidtravel.com/en/europe",
        "https://www.tourradar.com/g/b-europe-tour-operators",
    ],
    # Travel agency — global
    ("travel agency", ""): [
        "https://www.intrepidtravel.com",
        "https://www.tourradar.com",
        "https://www.g-adventures.com",
    ],
    # Sports (generic) — SE Asia
    ("sports", "sea"): [
        "https://www.sportssingapore.gov.sg",
        "https://www.sportstravel.com",
        "https://seekward.com/basketball/best-basketball-academies-in-asia",
    ],
    # Sports — Europe
    ("sports", "europe"): [
        "https://www.sportstravel.com",
        "https://www.eurosport.com",
    ],
    # Sports — global
    ("sports", ""): [
        "https://www.sportstravel.com",
    ],
    # Academy — SE Asia
    ("academy", "sea"): [
        "https://www.imgacademy.com",
        "https://seekward.com/basketball/best-basketball-academies-in-asia",
    ],
    # Camp — SE Asia
    ("camp", "sea"): [
        "https://www.campasia.asia",
        "https://www.campbeaumont.asia",
    ],
}

_cdx_endpoint: str | None = None


async def discover_urls(queries: list[str], mode: str,
                        seed_urls: list[str] | None = None) -> list[str]:
    all_urls: set[str] = set()

    for u in (seed_urls or []):
        u = u.strip()
        if u and _is_valid(u):
            all_urls.add(u)

    search_queries = _pick_queries(queries)
    log.info(f"Discovery: {len(search_queries)} queries across multiple engines")

    import random
    ua = random.choice(UA_LIST)
    headers = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9",
               "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=8.0),
        headers=headers,
        follow_redirects=True,
    ) as client:

        engine_results: dict[str, int] = {}

        # DDG Lite — primary
        for i, q in enumerate(search_queries[:4]):
            if i > 0:
                await asyncio.sleep(2.0)
            try:
                urls = await _ddg_lite(client, q)
                all_urls.update(urls)
                engine_results["ddg"] = engine_results.get("ddg", 0) + len(urls)
                log.info(f"DDG [{i+1}] '{q[:45]}' → {len(urls)}")
            except Exception as e:
                log.warning(f"DDG error: {e}")

        # Yahoo — fallback if DDG sparse
        if len(all_urls) < 10:
            log.info("DDG sparse — trying Yahoo")
            for q in search_queries[:2]:
                await asyncio.sleep(1.5)
                try:
                    urls = await _yahoo(client, q)
                    all_urls.update(urls)
                    engine_results["yahoo"] = engine_results.get("yahoo", 0) + len(urls)
                    log.info(f"Yahoo '{q[:45]}' → {len(urls)}")
                except Exception as e:
                    log.warning(f"Yahoo error: {e}")

        # Brave — fallback if still sparse
        if len(all_urls) < 10:
            log.info("Still sparse — trying Brave Search")
            for q in search_queries[:2]:
                await asyncio.sleep(2.0)
                try:
                    urls = await _brave(client, q)
                    all_urls.update(urls)
                    engine_results["brave"] = engine_results.get("brave", 0) + len(urls)
                    log.info(f"Brave '{q[:45]}' → {len(urls)}")
                except Exception as e:
                    log.warning(f"Brave error: {e}")

        # Ecosia — last search engine fallback
        if len(all_urls) < 10:
            log.info("Trying Ecosia")
            for q in search_queries[:2]:
                await asyncio.sleep(1.5)
                try:
                    urls = await _ecosia(client, q)
                    all_urls.update(urls)
                    engine_results["ecosia"] = engine_results.get("ecosia", 0) + len(urls)
                    log.info(f"Ecosia '{q[:45]}' → {len(urls)}")
                except Exception as e:
                    log.warning(f"Ecosia error: {e}")

        log.info(f"Search engines: {engine_results} | total raw: {len(all_urls)}")

        # Inject curated fallback seeds based on query keywords
        fallback_injected = _inject_fallback(queries, all_urls)
        if fallback_injected:
            log.info(f"Injected {fallback_injected} curated fallback seeds")

        # CDX augment from known domains
        if all_urls:
            domains = _extract_domains(list(all_urls))[:8]
            log.info(f"CDX augment: {len(domains)} domains")
            try:
                ep = await _get_cdx(client)
                results = await asyncio.gather(
                    *[_cdx_domain(client, ep, d) for d in domains],
                    return_exceptions=True
                )
                for r in results:
                    if isinstance(r, list):
                        all_urls.update(r)
                log.info(f"After CDX: {len(all_urls)}")
            except Exception as e:
                log.warning(f"CDX skipped: {e}")

    filtered = _filter(list(all_urls), mode)
    log.info(f"Final seeds: {len(filtered)}")
    return filtered[:MAX_SEEDS_FROM_DISCOVERY]


# --- Search engines ---

async def _ddg_lite(client: httpx.AsyncClient, q: str) -> list[str]:
    r = await client.post(DDG_LITE, data={"q": q},
                          headers={"Content-Type": "application/x-www-form-urlencoded",
                                   "Referer": "https://duckduckgo.com/"})
    if r.status_code == 202 or len(r.text) < 500:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    return [a["href"] for a in soup.select("a[href^='http']") if _is_valid(a["href"])]


async def _yahoo(client: httpx.AsyncClient, q: str) -> list[str]:
    r = await client.get(YAHOO_URL, params={"p": q, "n": "30"},
                         headers={"Referer": "https://search.yahoo.com/"})
    soup = BeautifulSoup(r.text, "lxml")
    urls = []
    # Yahoo wraps results in /url?u= redirects
    for a in soup.select("a[href*='r.search.yahoo.com']"):
        href = a.get("href", "")
        m = re.search(r"/RU=([^/]+)/", href)
        if m:
            from urllib.parse import unquote
            real = unquote(m.group(1))
            if _is_valid(real):
                urls.append(real)
    # Also grab direct links
    for a in soup.select("a[href^='http']"):
        href = a.get("href", "")
        if _is_valid(href) and "yahoo.com" not in href:
            urls.append(href)
    return list(set(urls))


async def _brave(client: httpx.AsyncClient, q: str) -> list[str]:
    r = await client.get(BRAVE_URL, params={"q": q},
                         headers={"Accept": "text/html", "Referer": "https://search.brave.com/"})
    soup = BeautifulSoup(r.text, "lxml")
    urls = []
    for a in soup.select("a[href^='http']"):
        href = a.get("href", "")
        if _is_valid(href) and "brave.com" not in href:
            urls.append(href)
    return list(set(urls))


async def _ecosia(client: httpx.AsyncClient, q: str) -> list[str]:
    r = await client.get(ECOSIA_URL, params={"q": q},
                         headers={"Referer": "https://www.ecosia.org/"})
    soup = BeautifulSoup(r.text, "lxml")
    urls = []
    for a in soup.select("a.result__title, a[data-test-id='result-title-link'], a[href^='http']"):
        href = a.get("href", "")
        if _is_valid(href) and "ecosia.org" not in href:
            urls.append(href)
    return list(set(urls))


# --- CDX ---

async def _get_cdx(client: httpx.AsyncClient) -> str:
    global _cdx_endpoint
    if _cdx_endpoint:
        return _cdx_endpoint
    r = await client.get(CDX_INDEX, timeout=8)
    _cdx_endpoint = r.json()[0]["cdx-api"]
    return _cdx_endpoint


async def _cdx_domain(client: httpx.AsyncClient, endpoint: str, domain: str) -> list[str]:
    try:
        r = await client.get(endpoint, params={
            "url": f"*.{domain}/*", "output": "json", "fl": "url",
            "filter": "status:200", "limit": "20", "collapse": "urlkey",
        }, timeout=8)
        if r.status_code == 200:
            return [json.loads(l)["url"] for l in r.text.strip().splitlines()
                    if json.loads(l).get("url")]
    except Exception:
        pass
    return []


# --- Helpers ---

def _pick_queries(queries: list[str]) -> list[str]:
    english = sorted([q for q in queries if not _is_cjk(q)], key=len)
    cjk = [q for q in queries if _is_cjk(q)]
    return (english[:3] + cjk[:2])[:5]


def _is_cjk(text: str) -> bool:
    non_space = text.replace(" ", "")
    if not non_space:
        return False
    cjk = sum(1 for c in non_space if '一' <= c <= '鿿' or '぀' <= c <= 'ヿ' or '가' <= c <= '힣')
    return cjk / len(non_space) > 0.25


_REGION_KEYWORDS: list[tuple[str, str]] = [
    ("southeast asia", "sea"), ("se asia", "sea"),
    ("thailand", "sea"), ("bangkok", "sea"), ("singapore", "sea"),
    ("malaysia", "sea"), ("vietnam", "sea"), ("indonesia", "sea"),
    ("philippines", "sea"), ("myanmar", "sea"), ("cambodia", "sea"),
    ("hong kong", "china"), ("china", "china"), ("macau", "china"), ("taiwan", "china"),
    ("beijing", "china"), ("shanghai", "china"), ("shenzhen", "china"),
    ("japan", "japan"), ("tokyo", "japan"),
    ("korea", "korea"), ("seoul", "korea"),
    ("switzerland", "europe"), ("france", "europe"), ("germany", "europe"),
    ("spain", "europe"), ("italy", "europe"), ("uk", "europe"),
    ("england", "europe"), ("europe", "europe"),
    ("usa", "north_america"), ("united states", "north_america"), ("canada", "north_america"),
    ("dubai", "middle_east"), ("uae", "middle_east"),
    ("australia", "oceania"), ("new zealand", "oceania"),
]


def _detect_region(queries: list[str]) -> str:
    q_lower = " ".join(queries).lower()
    for keyword, region in _REGION_KEYWORDS:
        if keyword in q_lower:
            return region
    return ""  # no region = global


def _inject_fallback(queries: list[str], all_urls: set[str]) -> int:
    q_lower = " ".join(queries).lower()
    detected = _detect_region(queries)
    added = 0
    for (topic, region), seeds in FALLBACK_SEEDS_GEO.items():
        topic_match = not topic or topic in q_lower
        # region="" in seed dict means "global fallback for this topic"
        # region match: exact match OR seed is global (region="") OR no region detected
        region_match = (not region) or (region == detected) or (not detected and not region)
        if topic_match and region_match:
            for url in seeds:
                if url not in all_urls:
                    all_urls.add(url)
                    added += 1
    return added


def _extract_domains(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for u in urls:
        try:
            d = urlparse(u).netloc.lstrip("www.")
            if d and d not in seen and not any(s in d for s in SKIP_DOMAINS):
                seen.add(d)
                out.append(d)
        except Exception:
            pass
    return out


def _is_valid(url: str) -> bool:
    try:
        p = urlparse(url)
        return (p.scheme in ("http", "https") and bool(p.netloc) and
                not any(s in p.netloc for s in SKIP_DOMAINS))
    except Exception:
        return False


def _filter(urls: list[str], mode: str) -> list[str]:
    limit = 8 if mode == "research" else 5
    domain_counts: dict[str, int] = {}
    seen: set[str] = set()
    out = []
    for url in urls:
        if url in seen or not _is_valid(url):
            continue
        seen.add(url)
        d = urlparse(url).netloc
        if domain_counts.get(d, 0) >= limit:
            continue
        domain_counts[d] = domain_counts.get(d, 0) + 1
        out.append(url)
    return out
