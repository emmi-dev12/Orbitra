"""ORBITRA CORE — tech fingerprinting via headers, HTML patterns, and meta signals."""

import re
import logging
from dataclasses import dataclass

log = logging.getLogger("orbitra.fingerprint")


@dataclass
class Fingerprint:
    server: str | None
    cms: str | None
    framework: str | None
    cdn: str | None
    analytics: list[str]
    security_headers: list[str]
    language_hint: str | None
    interesting_headers: dict[str, str]


def fingerprint(headers: dict[str, str], html: str) -> Fingerprint:
    headers_lower = {k.lower(): v for k, v in headers.items()}
    html_lower = html[:100000]  # Cap for perf

    return Fingerprint(
        server=_detect_server(headers_lower),
        cms=_detect_cms(headers_lower, html_lower),
        framework=_detect_framework(html_lower),
        cdn=_detect_cdn(headers_lower),
        analytics=_detect_analytics(html_lower),
        security_headers=_check_security_headers(headers_lower),
        language_hint=_detect_server_language(headers_lower, html_lower),
        interesting_headers=_extract_interesting_headers(headers_lower),
    )


def _detect_server(headers: dict) -> str | None:
    server = headers.get("server", "")
    powered = headers.get("x-powered-by", "")

    servers = {
        "nginx": "Nginx", "apache": "Apache", "iis": "IIS",
        "cloudflare": "Cloudflare", "gunicorn": "Gunicorn",
        "uwsgi": "uWSGI", "caddy": "Caddy", "litespeed": "LiteSpeed",
    }
    combined = (server + " " + powered).lower()
    for sig, name in servers.items():
        if sig in combined:
            return name
    return server.split("/")[0].strip() if server else None


def _detect_cms(headers: dict, html: str) -> str | None:
    cms_patterns = {
        "WordPress": ["wp-content/", "wp-includes/", "wp-json/"],
        "Drupal": ["Drupal.settings", "/sites/default/files/", "X-Generator: Drupal"],
        "Joomla": ["/components/com_", "joomla", "/media/jui/"],
        "Magento": ["mage/", "Magento_", "/magento/"],
        "Shopify": ["cdn.shopify.com", "shopify.com/s/"],
        "Wix": ["parastorage.com", "wix.com/"],
        "Squarespace": ["squarespace.com", "sqspcdn.com"],
        "Ghost": ["ghost.io", "/ghost/api/"],
        "Webflow": ["webflow.com", "Webflow"],
        "HubSpot": ["hs-scripts.com", "hubspot.com"],
    }
    # Check X-Generator header
    generator = headers.get("x-generator", "").lower()
    for cms in cms_patterns:
        if cms.lower() in generator:
            return cms

    # Check meta generator
    gen_match = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if gen_match:
        content = gen_match.group(1)
        for cms in cms_patterns:
            if cms.lower() in content.lower():
                return cms

    # Check HTML patterns
    for cms, patterns in cms_patterns.items():
        if any(p.lower() in html for p in patterns):
            return cms

    return None


def _detect_framework(html: str) -> str | None:
    frameworks = {
        "Next.js": ["__NEXT_DATA__", "_next/static"],
        "Nuxt.js": ["__nuxt", "_nuxt/"],
        "Gatsby": ["gatsby-", "__gatsby"],
        "Angular": ["ng-version=", "ng-app="],
        "Vue.js": ["__vue__", "data-v-app"],
        "React": ["react-root", "__reactFiber"],
        "Svelte": ["svelte-", "__svelte"],
        "Django": ["csrfmiddlewaretoken", "__admin_media_prefix__"],
        "Laravel": ["laravel_session", "XSRF-TOKEN"],
        "Ruby on Rails": ["authenticity_token", "rails-"],
        "ASP.NET": ["__VIEWSTATE", "asp.net"],
        "Spring": ["spring", "SPRING_SECURITY"],
    }
    for framework, signals in frameworks.items():
        if any(s.lower() in html for s in signals):
            return framework
    return None


def _detect_cdn(headers: dict) -> str | None:
    cdns = {
        "cloudflare": "Cloudflare",
        "cf-ray": "Cloudflare",
        "x-amz-cf-id": "AWS CloudFront",
        "x-cache": None,  # Could be various
        "fastly-io-info": "Fastly",
        "x-fastly": "Fastly",
        "x-akamai": "Akamai",
        "via": None,
    }
    for header, cdn in cdns.items():
        if header in headers:
            if cdn:
                return cdn
            # Parse generic
            via = headers.get("via", "")
            if "cloudfront" in via.lower():
                return "AWS CloudFront"
            if "varnish" in via.lower():
                return "Varnish"
    return None


def _detect_analytics(html: str) -> list[str]:
    analytics = []
    patterns = {
        "Google Analytics": ["google-analytics.com", "gtag(", "GoogleAnalyticsObject"],
        "Google Tag Manager": ["googletagmanager.com", "GTM-"],
        "Facebook Pixel": ["connect.facebook.net", "fbq("],
        "Hotjar": ["hotjar.com", "hj("],
        "Mixpanel": ["mixpanel.com", "mixpanel.track"],
        "Segment": ["segment.com", "analytics.js"],
        "Intercom": ["intercom.io", "Intercom("],
        "Crisp": ["crisp.chat"],
        "Tawk.to": ["tawk.to"],
        "HubSpot": ["hs-analytics.net", "hubspot.com/analytics"],
        "Baidu Analytics": ["hm.baidu.com", "百度统计"],
    }
    for name, sigs in patterns.items():
        if any(s in html for s in sigs):
            analytics.append(name)
    return analytics


def _check_security_headers(headers: dict) -> list[str]:
    present = []
    security_headers = [
        "strict-transport-security",
        "content-security-policy",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
        "x-xss-protection",
    ]
    for h in security_headers:
        if h in headers:
            present.append(h)
    return present


def _detect_server_language(headers: dict, html: str) -> str | None:
    powered = headers.get("x-powered-by", "").lower()
    langs = {
        "php": "PHP", "python": "Python", "ruby": "Ruby",
        "java": "Java", "asp.net": "ASP.NET", "node.js": "Node.js",
        "express": "Node.js",
    }
    for sig, lang in langs.items():
        if sig in powered:
            return lang

    # Check file extensions in HTML
    if re.search(r'action=["\'][^"\']*\.php', html, re.I):
        return "PHP"
    if re.search(r'action=["\'][^"\']*\.asp', html, re.I):
        return "ASP.NET"
    return None


def _extract_interesting_headers(headers: dict) -> dict[str, str]:
    interesting = ["server", "x-powered-by", "x-generator", "x-framework",
                   "x-application", "x-version", "via", "x-cache"]
    return {h: headers[h] for h in interesting if h in headers}
