"""External data provider adapters.

These adapters return uniform status dictionaries and never expose full API
keys in URLs or logs.  They are intentionally thin wrappers around the shared
rate-limited cache client.
"""

from .base import BaseProvider, ProviderResult, ProviderStatus
from .akshare_news_provider import AkShareNewsProvider
from .newsapi_unified_provider import NewsApiNewsProvider
from .provider_registry import build_provider_registry, list_provider_registry
from .sina_unified_provider import SinaRealtimeQuoteProvider


__all__ = [
    "BaseProvider",
    "ProviderResult",
    "ProviderStatus",
    "AkShareNewsProvider",
    "SinaRealtimeQuoteProvider",
    "NewsApiNewsProvider",
    "build_provider_registry",
    "list_provider_registry",
]
