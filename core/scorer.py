"""ORBITRA CORE — deterministic 0-100 page scoring engine."""

import math
import re
import logging
from dataclasses import dataclass

from config import ScoreWeights, SEMANTIC_CLUSTERS, Mode, MODE_WEIGHTS
from core.extractor import ExtractedPage

log = logging.getLogger("orbitra.scorer")


@dataclass
class ScoreResult:
    total: int
    breakdown: dict[str, int | float]


def score_page(page: ExtractedPage, query_terms: list[str],
               mode: Mode, inbound_links: int = 0,
               penalty_scale: float = 1.0) -> ScoreResult:
    # Flatten query strings into individual tokens for matching
    tokens: set[str] = set()
    for q in query_terms:
        for word in q.split():
            w = word.strip().lower()
            if len(w) > 2:
                tokens.add(w)
    query_terms = list(tokens)
    weights = MODE_WEIGHTS[mode]
    breakdown = {}

    kf = _keyword_freq_score(page.main_text + " " + page.title, query_terms, weights.keyword_freq)
    breakdown["keyword_freq"] = kf

    sc = _semantic_cluster_score(page.main_text + " " + page.title, weights.semantic_cluster)
    breakdown["semantic_cluster"] = sc

    cp = _contact_presence_score(page.entities, weights.contact_presence)
    breakdown["contact_presence"] = cp

    cl = _content_length_score(page.word_count, weights.content_length)
    breakdown["content_length"] = cl

    ml = _multilingual_score(page.language, weights.multilingual)
    breakdown["multilingual"] = ml

    mq = _metadata_quality_score(page.metadata, page.schema_org, weights.metadata_quality)
    breakdown["metadata_quality"] = mq

    la = _link_authority_score(inbound_links, weights.link_authority)
    breakdown["link_authority"] = la

    raw = sum(breakdown.values())

    penalties = _penalties(page) * penalty_scale
    breakdown["penalties"] = -round(penalties, 1)

    total = max(0, min(100, int(raw - penalties)))
    breakdown["total"] = total

    return ScoreResult(total=total, breakdown=breakdown)


def _keyword_freq_score(text: str, query_terms: list[str], max_pts: int) -> float:
    if not query_terms or not text:
        return 0.0
    text_lower = text.lower()
    words = text_lower.split()
    word_count = max(len(words), 1)

    hits = 0
    for term in query_terms:
        term_lower = term.lower()
        count = text_lower.count(term_lower)
        hits += count

    tf = hits / word_count
    # Log-normalize: tf=0.01 → ~50% of max, tf=0.05 → ~80%
    normalized = math.log1p(tf * 100) / math.log1p(10)
    return min(max_pts, normalized * max_pts)


def _semantic_cluster_score(text: str, max_pts: int) -> float:
    if not text:
        return 0.0
    text_lower = text.lower()
    cluster_hits = 0
    clusters_matched = 0

    for cluster_name, keywords in SEMANTIC_CLUSTERS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > 0:
            clusters_matched += 1
            cluster_hits += hits

    if cluster_hits == 0:
        return 0.0

    normalized = math.log1p(cluster_hits) / math.log1p(30)
    cluster_bonus = clusters_matched / len(SEMANTIC_CLUSTERS)
    return min(max_pts, (normalized * 0.7 + cluster_bonus * 0.3) * max_pts)


def _contact_presence_score(entities: dict, max_pts: int) -> float:
    if mode_contact_weight := max_pts:
        per_type = max_pts / 4
        score = 0.0
        if entities.get("emails"):
            score += per_type
        if entities.get("phones"):
            score += per_type
        if entities.get("wechat"):
            score += per_type
        if entities.get("line_ids") or entities.get("organizations"):
            score += per_type
        return min(max_pts, score)
    return 0.0


def _content_length_score(word_count: int, max_pts: int) -> float:
    if word_count < 50:
        return 0.0
    # Sweet spot: 200-3000 words
    if word_count <= 3000:
        normalized = math.log1p(word_count) / math.log1p(3000)
    else:
        # Slight penalty for very long pages (likely spam dumps)
        normalized = 1.0 - min(0.2, (word_count - 3000) / 50000)
    return min(max_pts, normalized * max_pts)


def _multilingual_score(language: str, max_pts: int) -> float:
    if language == "mixed":
        return float(max_pts)
    if language == "zh":
        return max_pts * 0.5
    return 0.0


def _metadata_quality_score(metadata: dict, schema_org: list, max_pts: int) -> float:
    score = 0.0
    pts_each = max_pts / 4
    if metadata.get("og:title") or metadata.get("og:description"):
        score += pts_each
    if metadata.get("description") and len(metadata["description"]) > 20:
        score += pts_each
    if schema_org:
        score += pts_each
    if metadata.get("og:image"):
        score += pts_each
    return min(max_pts, score)


def _link_authority_score(inbound_links: int, max_pts: int) -> float:
    if inbound_links == 0:
        return 0.0
    normalized = math.log1p(inbound_links) / math.log1p(50)
    return min(max_pts, normalized * max_pts)


def _penalties(page: ExtractedPage) -> float:
    penalty = 0.0
    text = page.main_text

    # Thin content
    if page.word_count < 50:
        penalty += 20

    # No headings
    if not page.headings:
        penalty += 5

    # Keyword stuffing — word frequency > 5% for any single word
    if text:
        words = text.lower().split()
        if words:
            from collections import Counter
            freq = Counter(words)
            most_common_ratio = freq.most_common(1)[0][1] / len(words)
            if most_common_ratio > 0.05:
                penalty += 15

    # No metadata at all
    if not page.metadata:
        penalty += 3

    return penalty


def expand_queries(query: str, mode: Mode,
                   forced_langs: list[str] | None = None) -> list[str]:
    """Universal multilingual query expansion using semantic_engine + lang_expansions.

    forced_langs: list of lang codes from prefs (e.g. ["zh","de"]).
                  None = auto-detect from region.
    """
    from lang_expansions import REGION_AUTO_LANGS
    import semantic_engine as _se

    q = query.strip()
    q_lower = q.lower()
    expanded = [q]

    # ── 1. Detect target region ──────────────────────────────────────────────
    _REGION_MAP: list[tuple[str, str]] = [
        ("southeast asia", "sea"), ("se asia", "sea"),
        ("thailand", "sea"), ("bangkok", "sea"), ("phuket", "sea"), ("chiang mai", "sea"),
        ("singapore", "sea"), ("malaysia", "sea"), ("kuala lumpur", "sea"),
        ("vietnam", "sea"), ("ho chi minh", "sea"), ("hanoi", "sea"),
        ("indonesia", "sea"), ("jakarta", "sea"), ("bali", "sea"),
        ("philippines", "sea"), ("manila", "sea"), ("myanmar", "sea"),
        ("cambodia", "sea"), ("laos", "sea"), ("brunei", "sea"),
        ("china", "china"), ("hong kong", "china"), ("macau", "china"),
        ("taiwan", "china"), ("beijing", "china"), ("shanghai", "china"),
        ("shenzhen", "china"), ("guangzhou", "china"), ("chengdu", "china"),
        ("japan", "japan"), ("tokyo", "japan"), ("osaka", "japan"),
        ("south korea", "korea"), ("korea", "korea"), ("seoul", "korea"),
        ("switzerland", "europe"), ("france", "europe"), ("germany", "europe"),
        ("spain", "europe"), ("italy", "europe"), ("portugal", "europe"),
        ("netherlands", "europe"), ("belgium", "europe"), ("austria", "europe"),
        ("sweden", "europe"), ("norway", "europe"), ("denmark", "europe"),
        ("uk", "europe"), ("united kingdom", "europe"), ("england", "europe"),
        ("europe", "europe"), ("european", "europe"),
        ("usa", "north_america"), ("united states", "north_america"), ("canada", "north_america"),
        ("dubai", "middle_east"), ("uae", "middle_east"), ("qatar", "middle_east"),
        ("saudi", "middle_east"), ("middle east", "middle_east"),
        ("australia", "oceania"), ("new zealand", "oceania"),
        ("brazil", "latam"), ("argentina", "latam"), ("mexico", "latam"),
        ("latin america", "latam"),
        ("india", "south_asia"), ("pakistan", "south_asia"),
        ("russia", "europe"), ("ukraine", "europe"),
    ]

    detected_region: str | None = None
    for keyword, region in _REGION_MAP:
        if keyword in q_lower:
            detected_region = region
            break

    # ── 2. Detect if query is already non-Latin ──────────────────────────────
    def _cjk_ratio(text: str) -> float:
        chars = [c for c in text if c.strip()]
        if not chars:
            return 0.0
        cjk = sum(1 for c in chars if '一' <= c <= '鿿' or '぀' <= c <= 'ヿ' or '가' <= c <= '힣')
        return cjk / len(chars)

    query_is_cjk = _cjk_ratio(q) > 0.25

    # ── 3. Resolve which languages to expand into ────────────────────────────
    if forced_langs is not None and forced_langs:
        active_langs = forced_langs
    elif query_is_cjk:
        active_langs = ["zh"]
    elif detected_region:
        auto = REGION_AUTO_LANGS.get(detected_region, [])
        if detected_region == "europe":
            lang_country_map = {
                "de": ["germany", "austria", "switzerland"],
                "nl": ["netherlands", "belgium"],
                "fr": ["france", "belgium", "switzerland"],
                "es": ["spain"],
                "it": ["italy"],
                "ru": ["russia", "ukraine"],
                "pt": ["portugal"],
            }
            auto = [lang for lang in auto
                    if any(c in q_lower for c in lang_country_map.get(lang, []))]
            if not auto:
                auto = ["de", "fr", "es"]
        active_langs = auto
    else:
        active_langs = []

    def _dedup(lst: list[str]) -> list[str]:
        seen_s: set[str] = set()
        return [x for x in lst if not (x in seen_s or seen_s.add(x))]  # type: ignore

    # ── 4. Semantic analysis (universal — works for any industry/topic) ───────
    sem = _se.analyze(q)

    # ── 5. Mode-specific English expansion ───────────────────────────────────
    city_map: dict[str, list[str]] = {
        "sea":          ["Bangkok", "Singapore", "Kuala Lumpur", "Ho Chi Minh City",
                         "Jakarta", "Manila", "Hanoi", "Phuket"],
        "china":        ["Beijing", "Shanghai", "Shenzhen", "Guangzhou", "Chengdu"],
        "japan":        ["Tokyo", "Osaka", "Kyoto", "Yokohama"],
        "korea":        ["Seoul", "Busan", "Incheon"],
        "north_america":["New York", "Los Angeles", "Toronto", "Chicago"],
        "middle_east":  ["Dubai", "Abu Dhabi", "Doha", "Riyadh"],
        "oceania":      ["Sydney", "Melbourne", "Auckland"],
        "latam":        ["São Paulo", "Mexico City", "Buenos Aires", "Bogotá"],
        "south_asia":   ["Mumbai", "Delhi", "Bangalore", "Colombo"],
        "europe":       [],
    }

    # Domain-aware English expansion suffixes
    _DOMAIN_SUFFIXES: dict[str, dict[str, list[str]]] = {
        "leadgen": {
            "sports":        ["academy", "club", "facility contact"],
            "travel":        ["travel agent", "tour operator", "reseller contact"],
            "food":          ["supplier wholesale", "distributor contact"],
            "tech":          ["vendor reseller", "partner contact"],
            "business":      ["company supplier", "contact email"],
            "finance":       ["firm contact", "services email"],
            "education":     ["institute contact", "school email"],
            "health":        ["clinic contact", "provider email"],
            "legal":         ["law firm contact", "attorney email"],
            "realestate":    ["agency contact", "agent email"],
            "retail":        ["wholesaler contact", "distributor email"],
            "manufacturing": ["factory supplier", "OEM contact"],
            "fashion":       ["brand wholesale", "supplier contact"],
            "automotive":    ["dealer contact", "fleet email"],
            "logistics":     ["freight forwarder contact", "shipper email"],
            "marketing":     ["agency contact", "services email"],
            "construction":  ["contractor contact", "builder email"],
            "events":        ["planner contact", "organizer email"],
        },
        "research": {
            "sports":        ["industry association federation", "market overview"],
            "travel":        ["tourism statistics industry", "market report"],
            "tech":          ["landscape ecosystem report", "market analysis"],
            "business":      ["industry report market", "sector overview"],
            "finance":       ["market report regulatory", "sector analysis"],
            "education":     ["statistics enrollment report"],
            "health":        ["industry report healthcare market"],
            "manufacturing": ["industry report output statistics"],
            "energy":        ["market report capacity statistics"],
            "agriculture":   ["industry statistics production report"],
            "crypto":        ["market cap report ecosystem"],
            "gaming":        ["market report revenue statistics"],
        },
    }

    primary_domain = sem.primary_domain or "general"

    if mode == "leadgen":
        cities = city_map.get(detected_region or "", [])
        for city in cities[:3]:
            if city.lower() not in q_lower:
                expanded.append(f"{q} {city}")
        domain_sfx = _DOMAIN_SUFFIXES["leadgen"].get(primary_domain, ["contact email"])
        for sfx in domain_sfx[:2]:
            expanded.append(f"{q} {sfx}")

    elif mode == "research":
        domain_sfx = _DOMAIN_SUFFIXES["research"].get(primary_domain, ["industry market report"])
        for sfx in domain_sfx[:2]:
            expanded.append(f"{q} {sfx}")
        expanded.append(f"{q} association directory")
        if detected_region == "sea":
            for c in ["Thailand", "Singapore", "Malaysia", "Vietnam"]:
                if c.lower() not in q_lower:
                    expanded.append(f"{q} {c}")
        elif detected_region == "europe":
            for c in ["Germany", "France", "UK"]:
                if c.lower() not in q_lower:
                    expanded.append(f"{q} {c}")
        elif detected_region == "china":
            expanded.append(f"{q} China mainland")
        elif not detected_region:
            expanded.append(f"{q} international global")

    elif mode == "personal":
        expanded.append(f"{q} official site")
        expanded.append(f"{q} about contact")

    # ── 6. Universal language expansions via semantic_engine ─────────────────
    for lang_code in active_langs:
        native = _se.build_native_query(q, lang_code, mode=mode)
        if native and native.lower() != q_lower:
            # For CJK leadgen: add contact suffix variant
            if lang_code in ("zh", "zh_tw") and mode == "leadgen":
                expanded.append(native)
                contact_terms = sem.translations.get(lang_code, [])
                # Find a contact-related term
                contact_native = next(
                    (t for t in contact_terms if any(
                        c in t for c in ["联系", "聯絡", "邮件", "電郵"]
                    )), None
                )
                if contact_native and contact_native not in native:
                    expanded.append(f"{native} {contact_native}")
            else:
                expanded.append(native)
                # Add mode suffix in target language if available
                if mode == "leadgen":
                    contact_terms = sem.translations.get(lang_code, [])
                    # pick first 2 unique terms not already in native
                    extras = [t for t in contact_terms
                              if t not in native.split() and len(t) > 2][:2]
                    if extras:
                        expanded.append(f"{native} {' '.join(extras)}")

    # ── 7. Deduplicate preserving order ─────────────────────────────────────
    seen: set[str] = set()
    result = []
    for item in expanded:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)

    return result[:15]
