"""
domain_filter.py
────────────────
Reusable domain-level utilities for normalization, extraction, and blocklist
matching.  These are pure string operations with zero Django / web-framework
dependencies, so they can be consumed by the backend, CLI tools, or any other
Python consumer.
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Iterable


# ── Domain Normalisation ──────────────────────────────────────────────

WWW_PREFIX = "www."


def normalize_domain(domain: str) -> str:
    """
    Lower-case, strip whitespace, and remove a leading 'www.'.

    Examples:
        >>> normalize_domain("  WWW.Example.COM  ")
        'example.com'
        >>> normalize_domain("sub.example.com")
        'sub.example.com'
    """
    cleaned = domain.lower().strip()
    if cleaned.startswith(WWW_PREFIX):
        cleaned = cleaned[len(WWW_PREFIX):]
    return cleaned


def extract_domain(url: str) -> str | None:
    """
    Extract the network location (hostname) from a URL string and normalise it.

    Returns ``None`` when *url* is not a valid URL or has no hostname.

    Examples:
        >>> extract_domain("https://www.example.com/path?q=1")
        'example.com'
        >>> extract_domain("ftp://files.example.com/resource")
        'files.example.com'
        >>> extract_domain("not-a-url")
        None
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None
        return normalize_domain(hostname)
    except ValueError:
        return None


# ── Blocklist / Allow-list Matching ───────────────────────────────────

class DomainFilter:
    """
    Stateless engine that checks whether a URL (or its extracted domain) matches
    a list of blocked / allowed domains.

    Matching rules (same as the AegisBrowse extension):
    * **Exact match** — ``hostname == blocked_domain``
    * **Sub-domain match** — ``hostname.endswith('.' + blocked_domain)``

    All inputs are normalised automatically, so callers can pass raw strings.
    """

    @staticmethod
    def matches(hostname: str, blocked_domain: str) -> bool:
        """
        Return ``True`` if *hostname* is *blocked_domain* or a sub-domain of it.

        Both arguments are normalised before comparison.
        """
        host = normalize_domain(hostname)
        block = normalize_domain(blocked_domain)

        if not host or not block:
            return False

        return host == block or host.endswith("." + block)

    @classmethod
    def is_blocked(
        cls,
        url_or_hostname: str,
        blocked_domains: Iterable[str],
    ) -> bool:
        """
        Return ``True`` if *url_or_hostname* is covered by any entry in
        *blocked_domains*.

        If *url_or_hostname* looks like a full URL it is parsed first;
        otherwise it is treated as a raw hostname.
        """
        # Try to extract a hostname if the input looks like a URL
        candidate = extract_domain(url_or_hostname)
        if candidate is None:
            # Fall back to treating it as a raw hostname
            candidate = normalize_domain(url_or_hostname)

        if not candidate:
            return False

        for blocked in blocked_domains:
            if cls.matches(candidate, blocked):
                return True
        return False

    @classmethod
    def filter_blocked(
        cls,
        urls: Iterable[str],
        blocked_domains: Iterable[str],
    ) -> list[str]:
        """
        Return the sub-set of *urls* whose hostnames match the blocklist.
        """
        blocked: list[str] = []
        for url in urls:
            if cls.is_blocked(url, blocked_domains):
                blocked.append(url)
        return blocked

    @classmethod
    def filter_allowed(
        cls,
        urls: Iterable[str],
        blocked_domains: Iterable[str],
    ) -> list[str]:
        """
        Return the sub-set of *urls* whose hostnames do **not** match the
        blocklist.
        """
        allowed: list[str] = []
        for url in urls:
            if not cls.is_blocked(url, blocked_domains):
                allowed.append(url)
        return allowed


# ── Convenience helpers (module-level) ────────────────────────────────


def is_url_blocked(url: str, blocked_domains: Iterable[str]) -> bool:
    """Module-level shortcut for ``DomainFilter.is_blocked``.

    >>> is_url_blocked("https://www.bad.com/page", ["bad.com"])
    True
    """
    return DomainFilter.is_blocked(url, blocked_domains)


def strip_blocked_urls(
    urls: Iterable[str],
    blocked_domains: Iterable[str],
) -> list[str]:
    """Module-level shortcut for ``DomainFilter.filter_allowed``.

    >>> strip_blocked_urls(
    ...     ["https://good.com", "https://bad.com/x"],
    ...     ["bad.com"]
    ... )
    ['https://good.com']
    """
    return DomainFilter.filter_allowed(urls, blocked_domains)
