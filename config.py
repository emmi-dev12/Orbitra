"""ORBITRA CORE — global configuration and concurrency profiles."""

from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["personal", "research", "leadgen"]
Profile = Literal["light", "medium", "heavy"]


@dataclass
class ConcurrencyProfile:
    name: Profile
    max_pages: int
    max_browsers: int
    max_jobs: int
    request_delay: float  # seconds between requests per browser


PROFILES: dict[Profile, ConcurrencyProfile] = {
    "light": ConcurrencyProfile("light", max_pages=10, max_browsers=2, max_jobs=1, request_delay=1.5),
    "medium": ConcurrencyProfile("medium", max_pages=30, max_browsers=8, max_jobs=2, request_delay=0.5),
    "heavy": ConcurrencyProfile("heavy", max_pages=80, max_browsers=20, max_jobs=3, request_delay=0.1),
}


@dataclass
class ScoreWeights:
    keyword_freq: int = 25
    semantic_cluster: int = 20
    contact_presence: int = 20
    content_length: int = 10
    multilingual: int = 10
    metadata_quality: int = 8
    link_authority: int = 7


MODE_WEIGHTS: dict[Mode, ScoreWeights] = {
    "personal": ScoreWeights(keyword_freq=30, semantic_cluster=15, contact_presence=15,
                             content_length=15, multilingual=8, metadata_quality=10, link_authority=7),
    "research": ScoreWeights(keyword_freq=20, semantic_cluster=25, contact_presence=10,
                             content_length=8, multilingual=10, metadata_quality=7, link_authority=20),
    "leadgen": ScoreWeights(keyword_freq=15, semantic_cluster=10, contact_presence=40,
                            content_length=5, multilingual=15, metadata_quality=5, link_authority=10),
}


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]

CRAWL_TIMEOUT = 35
PAGE_LOAD_TIMEOUT = 30000
NETWORK_IDLE_TIMEOUT = 5000
MAX_RETRIES = 3
MAX_DEPTH = 5
MAX_PAGES_PER_DOMAIN = 50
MIN_SCORE_THRESHOLD = 10
MAX_SEEDS_FROM_DISCOVERY = 200
DDG_REQUEST_DELAY = 3.0

DB_PATH = "orbitra.db"
RESULTS_DIR = "results/jobs"

BLOCKED_RESOURCE_TYPES = ["image", "font", "media", "stylesheet"]
BLOCKED_DOMAINS = [
    "google-analytics.com", "googletagmanager.com", "doubleclick.net",
    "facebook.net", "twitter.com", "linkedin.com", "amazon-adsystem.com",
    "hotjar.com", "intercom.io", "segment.com", "mixpanel.com",
]

SEMANTIC_CLUSTERS: dict[str, list[str]] = {
    "sports": ["football", "soccer", "basketball", "tennis", "swimming", "athletics",
               "training", "camp", "tournament", "league", "coach", "academy",
               "sport", "athlete", "fitness", "gym", "competition", "championship"],
    "travel": ["tour", "travel", "trip", "holiday", "vacation", "hotel", "resort",
               "booking", "accommodation", "flight", "destination", "itinerary",
               "guide", "agency", "package", "excursion"],
    "business": ["company", "corporation", "enterprise", "solution", "service",
                 "consulting", "management", "strategy", "investment", "partner",
                 "industry", "market", "professional", "commercial"],
    "contact": ["contact", "reach", "email", "phone", "address", "office",
                "headquarters", "inquiry", "support", "sales", "info"],
    "education": ["school", "university", "college", "institute", "training",
                  "course", "program", "learning", "education", "study", "class"],
}

LOCATION_KEYWORDS: list[str] = [
    "Thailand", "Bangkok", "Chiang Mai", "Phuket",
    "China", "Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu",
    "Singapore", "Hong Kong", "Malaysia", "Kuala Lumpur", "Vietnam", "Hanoi", "Ho Chi Minh",
    "Indonesia", "Jakarta", "Philippines", "Manila", "Myanmar", "Yangon",
    "Cambodia", "Phnom Penh", "Laos", "Vientiane", "Japan", "Tokyo", "Seoul", "Korea",
    "泰国", "中国", "北京", "上海", "广州", "新加坡", "香港", "马来西亚", "越南",
    "东南亚", "亚洲",
]

ORG_SUFFIXES = [
    "Co.", "Ltd.", "Corp.", "Inc.", "LLC", "Group", "Holdings", "International",
    "Enterprise", "Services", "Solutions", "Agency", "Association",
    "集团", "公司", "有限公司", "股份", "机构", "协会",
]
