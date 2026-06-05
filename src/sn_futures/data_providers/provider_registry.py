from __future__ import annotations

from .base import BaseProvider
from .newsapi_unified_provider import NewsApiNewsProvider
from .sina_unified_provider import SinaRealtimeQuoteProvider


def build_provider_registry() -> dict[str, BaseProvider]:
    providers: list[BaseProvider] = [
        SinaRealtimeQuoteProvider(),
        NewsApiNewsProvider(),
    ]
    return {provider.provider_id: provider for provider in providers}


def list_provider_registry() -> list[dict[str, str]]:
    return [
        {
            "provider_id": provider.provider_id,
            "data_kind": provider.data_kind,
            "schema_version": "provider-result-v1",
        }
        for provider in build_provider_registry().values()
    ]
