"""
providers - Remote manga and manhwa provider foundation package.

Exports core data models, provider base interface, registry, cache, and security utilities.
"""

from providers.base import (
    BaseProvider,
    RemoteChapter,
    RemotePage,
    RemoteSeries,
)
from providers.cache import (
    ChapterPageCache,
    calculate_pages_metadata_size,
)
from providers.mock import MockProvider
from providers.weebcentral import WeebCentralProvider
from providers.registry import (
    DuplicateProviderError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
    clear_registry,
    default_registry,
    find_provider_for_url,
    get_provider,
    list_providers,
    register_provider,
    resolve_url,
    unregister_provider,
)
from providers.security import (
    BlockedIPError,
    DisallowedHostError,
    InvalidSchemeError,
    MaxRedirectsExceededError,
    RedirectSecurityError,
    SSRFProtectedHTTPSConnection,
    SSRFSecurityError,
    SecureHttpClient,
    SecureResponse,
    SecurityPolicy,
    is_safe_ip,
    validate_provider_target_url,
)
from providers.service import (
    RemoteReaderService,
    is_remote_series,
)

__all__ = [
    "BaseProvider",
    "RemotePage",
    "RemoteChapter",
    "RemoteSeries",
    "ProviderRegistry",
    "default_registry",
    "register_provider",
    "unregister_provider",
    "get_provider",
    "find_provider_for_url",
    "resolve_url",
    "list_providers",
    "clear_registry",
    "ProviderError",
    "ProviderNotFoundError",
    "DuplicateProviderError",
    "ChapterPageCache",
    "calculate_pages_metadata_size",
    "SecurityPolicy",
    "SSRFProtectedHTTPSConnection",
    "SecureHttpClient",
    "SecureResponse",
    "is_safe_ip",
    "validate_provider_target_url",
    "SSRFSecurityError",
    "InvalidSchemeError",
    "DisallowedHostError",
    "BlockedIPError",
    "RedirectSecurityError",
    "MaxRedirectsExceededError",
    "MockProvider",
    "WeebCentralProvider",
    "RemoteReaderService",
    "is_remote_series",
]
