"""ORBITRA — Universal semantic query analyzer.

Tokenizes an arbitrary query, matches concepts from semantic_vocab,
infers domain(s), and returns multilingual expansions.
"""

from __future__ import annotations
import re
from functools import lru_cache
from typing import NamedTuple

from semantic_vocab import CONCEPTS, TRANSLATIONS, DOMAINS


# ──────────────────────────────────────────────────────────────────────────────
# Porter-lite stemmer (no deps)
# ──────────────────────────────────────────────────────────────────────────────

_STEP1A = [("sses","ss"),("ies","i"),("ss","ss"),("s","")]
_STEP1B = [("eed","ee"),("ed",""),("ing","")]
_STEP2 = [
    ("ational","ate"),("tional","tion"),("enci","ence"),("anci","ance"),
    ("izer","ize"),("bli","ble"),("alli","al"),("entli","ent"),("eli","e"),
    ("ousli","ous"),("ization","ize"),("ation","ate"),("ator","ate"),
    ("alism","al"),("iveness","ive"),("fulness","ful"),("ousness","ous"),
    ("aliti","al"),("iviti","ive"),("biliti","ble"),
]
_STEP3 = [
    ("icate","ic"),("ative",""),("alize","al"),("iciti","ic"),
    ("ical","ic"),("ful",""),("ness",""),
]
_STEP4 = [
    "al","ance","ence","er","ic","able","ible","ant","ement","ment",
    "ent","ion","ou","ism","ate","iti","ous","ive","ize",
]

def _vowel(c: str) -> bool:
    return c in "aeiou"

def _has_vowel(s: str) -> bool:
    return any(_vowel(c) for c in s)

def stem(word: str) -> str:
    w = word.lower()
    if len(w) <= 2:
        return w
    # step 1a
    for suf, rep in _STEP1A:
        if w.endswith(suf):
            w = w[:-len(suf)] + rep
            break
    # step 1b
    if w.endswith("eed"):
        if len(w[:-3]) > 1:
            w = w[:-1]
    elif w.endswith("ed") and _has_vowel(w[:-2]):
        w = w[:-2]
        for s,r in [("at","ate"),("bl","ble"),("iz","ize")]:
            if w.endswith(s):
                w = w[:-len(s)] + r
                break
        else:
            if len(w)>1 and w[-1]==w[-2] and w[-1] not in "lsz":
                w = w[:-1]
    elif w.endswith("ing") and _has_vowel(w[:-3]):
        w = w[:-3]
        for s,r in [("at","ate"),("bl","ble"),("iz","ize")]:
            if w.endswith(s):
                w = w[:-len(s)] + r
                break
        else:
            if len(w)>1 and w[-1]==w[-2] and w[-1] not in "lsz":
                w = w[:-1]
    # step 2
    for suf, rep in _STEP2:
        if w.endswith(suf) and len(w[:-len(suf)]) > 1:
            w = w[:-len(suf)] + rep
            break
    # step 3
    for suf, rep in _STEP3:
        if w.endswith(suf) and len(w[:-len(suf)]) > 0:
            w = w[:-len(suf)] + rep
            break
    # step 4
    for suf in _STEP4:
        if w.endswith(suf):
            stem_part = w[:-len(suf)]
            if len(stem_part) > 1:
                if suf == "ion" and stem_part and stem_part[-1] in "st":
                    w = stem_part
                elif suf != "ion":
                    w = stem_part
            break
    return w


# ──────────────────────────────────────────────────────────────────────────────
# Build inverted index at import time
# index: stemmed_token -> list of (concept_id, domain, match_score_weight)
# ──────────────────────────────────────────────────────────────────────────────

class _ConceptHit(NamedTuple):
    concept_id: str
    domain: str
    weight: float  # 1.0 = exact synonym, 0.7 = partial


def _build_index() -> dict[str, list[_ConceptHit]]:
    index: dict[str, list[_ConceptHit]] = {}
    for concept_id, domain, synonyms in CONCEPTS:
        for syn in synonyms:
            # Index each word in the synonym phrase
            words = re.findall(r"[a-z0-9]+", syn.lower())
            stemmed = [stem(w) for w in words if len(w) > 2]
            for st in stemmed:
                hit = _ConceptHit(concept_id, domain, 1.0 if len(words) == 1 else 0.8)
                index.setdefault(st, []).append(hit)
            # Also index the full phrase collapsed
            phrase_key = "_".join(words)
            if len(words) > 1:
                full_hit = _ConceptHit(concept_id, domain, 1.2)
                index.setdefault(phrase_key, []).append(full_hit)
    return index


_INDEX: dict[str, list[_ConceptHit]] = _build_index()

# Precompute stemmed synonyms list for phrase-level matching
_PHRASES: list[tuple[str, str, str]] = []  # (phrase_key, concept_id, domain)
for _cid, _dom, _syns in CONCEPTS:
    for _syn in _syns:
        _words = re.findall(r"[a-z0-9]+", _syn.lower())
        if len(_words) > 1:
            _PHRASES.append(("_".join(_words), _cid, _dom))
# Sort longest first so longer phrases win
_PHRASES.sort(key=lambda x: len(x[0]), reverse=True)


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

class AnalysisResult(NamedTuple):
    concepts: list[str]          # matched concept_ids, ranked by score
    domains: list[str]           # matched domain codes, ranked
    translations: dict[str, list[str]]  # lang_code -> [translated terms]
    primary_domain: str | None


def analyze(query: str, max_concepts: int = 8) -> AnalysisResult:
    """Analyze a free-text query. Returns concepts, domains, and translations."""
    q = query.lower()
    tokens = re.findall(r"[a-z0-9]+", q)
    if not tokens:
        return AnalysisResult([], [], {}, None)

    stemmed_tokens = [stem(t) for t in tokens if len(t) > 2]

    # Score each concept
    concept_scores: dict[str, float] = {}
    concept_domains: dict[str, str] = {}

    # Phrase-level matching (highest weight)
    q_collapsed = "_".join(tokens)
    for phrase_key, cid, dom in _PHRASES:
        if phrase_key in q_collapsed:
            concept_scores[cid] = concept_scores.get(cid, 0) + 2.0
            concept_domains[cid] = dom

    # Token-level matching
    for st in stemmed_tokens:
        for hit in _INDEX.get(st, []):
            concept_scores[hit.concept_id] = (
                concept_scores.get(hit.concept_id, 0) + hit.weight
            )
            concept_domains[hit.concept_id] = hit.domain

    if not concept_scores:
        return AnalysisResult([], [], {}, None)

    # Rank concepts
    ranked = sorted(concept_scores.items(), key=lambda x: x[1], reverse=True)
    top_concepts = [cid for cid, _ in ranked[:max_concepts]]

    # Infer domains
    domain_scores: dict[str, float] = {}
    for cid, score in ranked[:max_concepts]:
        dom = concept_domains.get(cid, "general")
        domain_scores[dom] = domain_scores.get(dom, 0) + score
    ranked_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)
    top_domains = [d for d, _ in ranked_domains]
    primary_domain = top_domains[0] if top_domains else None

    # Gather translations
    translations: dict[str, list[str]] = {}
    for cid in top_concepts:
        if cid not in TRANSLATIONS:
            continue
        for lang_code, terms in TRANSLATIONS[cid].items():
            if lang_code not in translations:
                translations[lang_code] = []
            for t in terms:
                if t not in translations[lang_code]:
                    translations[lang_code].append(t)

    return AnalysisResult(
        concepts=top_concepts,
        domains=top_domains,
        translations=translations,
        primary_domain=primary_domain,
    )


def get_translated_terms(query: str, lang_code: str, max_terms: int = 6) -> list[str]:
    """Convenience: analyze query and return terms for one language."""
    result = analyze(query)
    return result.translations.get(lang_code, [])[:max_terms]


def build_native_query(query: str, lang_code: str, mode: str = "leadgen") -> str | None:
    """Build a native-language query string for the given lang_code."""
    terms = get_translated_terms(query, lang_code, max_terms=5)
    if not terms:
        return None

    # For CJK: concatenate without spaces
    if lang_code in ("zh", "zh_tw", "ja", "ko"):
        base = "".join(terms[:4])
        if mode == "leadgen" and lang_code in ("zh", "zh_tw"):
            if "联系" not in base and "聯絡" not in base:
                base += " 联系方式"
        return base

    # Latin-script: join with spaces, limit length
    return " ".join(terms[:4])
