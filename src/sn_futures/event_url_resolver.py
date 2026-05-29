from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests


SAFE_EXTERNAL_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class CanonicalUrlResult:
    raw_url: str
    canonical_url: str
    url_status: str
    reason: str = ""
    final_open_url: str = ""
    redirect_chain: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        final_url = self.final_open_url or self.canonical_url
        can_open = is_external_open_allowed(final_url)
        return {
            "raw_url": self.raw_url,
            "canonical_url": self.canonical_url,
            "final_open_url": final_url if can_open else "",
            "url_status": self.url_status,
            "reason": self.reason,
            "blocked_reason": "" if can_open else (self.reason or "unsafe_url"),
            "redirect_chain": list(self.redirect_chain),
            "open_mode": "external_browser" if can_open else "unavailable",
        }


def _canonicalize_text_url(url: str) -> str:
    text = str(url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme.lower() not in SAFE_EXTERNAL_SCHEMES or not parsed.netloc:
        return ""
    # Recompose from parsed parts instead of normalizing to the root domain.
    # Article paths and query strings are essential for policy/news pages.
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",
        )
    )


def _host_from_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.lower() not in SAFE_EXTERNAL_SCHEMES:
        return ""
    return (parsed.hostname or "").strip(".").lower()


def _host_is_local_or_private(host: str) -> bool:
    normalized = str(host or "").strip("[]").strip(".").lower()
    if not normalized:
        return True
    if normalized in {"localhost", "localhost.localdomain"} or normalized.endswith(".localhost"):
        return True
    if normalized.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def is_public_http_url(url: str) -> bool:
    text = _canonicalize_text_url(url)
    if not text:
        return False
    host = _host_from_url(text)
    return bool(host and not _host_is_local_or_private(host))


def is_trusted_host(host: str) -> bool:
    """Compatibility shim kept for older call sites/tests.

    V3.8 deliberately no longer gates news/policy links by a fixed financial
    domain allowlist.  A host is "trusted enough to open" if it is public and
    the original URL uses http(s); source credibility is shown separately in
    event evidence and model weights.
    """

    return bool(str(host or "").strip()) and not _host_is_local_or_private(host)


def resolve_canonical_url(raw_url: str, *, network: bool = False, timeout: float = 3.0) -> CanonicalUrlResult:
    """Resolve a public event URL while preserving article path/query.

    The resolver no longer blocks unfamiliar public domains.  It only prevents
    unsafe schemes and local/private network targets.  If network redirect
    resolution fails, a safe raw URL is returned as ``raw_fallback`` so events
    remain clickable instead of disappearing from the research workflow.
    """

    raw = str(raw_url or "").strip()
    safe_raw = _canonicalize_text_url(raw)
    if not raw:
        return CanonicalUrlResult(raw_url=raw, canonical_url="", final_open_url="", url_status="missing", reason="empty_url")
    if not safe_raw:
        return CanonicalUrlResult(raw_url=raw, canonical_url="", final_open_url="", url_status="invalid", reason="unsupported_scheme")
    if not is_public_http_url(safe_raw):
        return CanonicalUrlResult(raw_url=raw, canonical_url="", final_open_url="", url_status="blocked", reason="unsafe_or_private_url")
    if not network:
        return CanonicalUrlResult(raw_url=raw, canonical_url=safe_raw, final_open_url=safe_raw, url_status="ok")
    try:
        response = requests.get(
            safe_raw,
            allow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "SNInsightTerminal/3.6"},
        )
    except requests.Timeout:
        return CanonicalUrlResult(raw_url=raw, canonical_url=safe_raw, final_open_url=safe_raw, url_status="raw_fallback", reason="request_timeout")
    except Exception as exc:
        return CanonicalUrlResult(raw_url=raw, canonical_url=safe_raw, final_open_url=safe_raw, url_status="raw_fallback", reason=str(exc)[:120])

    chain = tuple(_canonicalize_text_url(item.url) or str(item.url) for item in response.history) + (response.url or safe_raw,)
    final_url = _canonicalize_text_url(response.url or safe_raw)
    if final_url and is_public_http_url(final_url):
        status = "redirected" if final_url != safe_raw else "ok"
        return CanonicalUrlResult(
            raw_url=raw,
            canonical_url=final_url,
            final_open_url=final_url,
            url_status=status,
            redirect_chain=chain,
        )
    return CanonicalUrlResult(
        raw_url=raw,
        canonical_url=safe_raw,
        final_open_url=safe_raw,
        url_status="raw_fallback",
        reason="redirect_target_unsafe",
        redirect_chain=chain,
    )


def is_external_open_allowed(url: str) -> bool:
    return is_public_http_url(str(url or "").strip())
