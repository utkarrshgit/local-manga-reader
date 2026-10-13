"""
providers/registry.py - Provider registration and URL resolution.

Maintains a thread-safe registry of BaseProvider instances, resolving
incoming remote URLs to the corresponding provider implementation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

from providers.base import BaseProvider


class ProviderError(Exception):
    """Base exception for provider registry errors."""
    pass


class ProviderNotFoundError(ProviderError):
    """Raised when no provider is found for an ID or URL."""
    pass


class DuplicateProviderError(ProviderError):
    """Raised when attempting to register a provider with an existing ID."""
    pass


class ProviderRegistry:
    """
    Thread-safe registry for managing remote manga/manhwa providers.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, BaseProvider] = {}
        self._lock = threading.RLock()

    def register(self, provider: BaseProvider, overwrite: bool = False) -> None:
        """
        Register a new provider instance.

        Args:
            provider: The BaseProvider instance to register.
            overwrite: If True, replace any existing provider with the same ID.

        Raises:
            ValueError: If provider.id is empty or provider is invalid.
            DuplicateProviderError: If provider.id is already registered and overwrite is False.
        """
        if not isinstance(provider, BaseProvider):
            raise ValueError(f"Expected BaseProvider instance, got {type(provider).__name__}")
        if not provider.id or not provider.id.strip():
            raise ValueError("Provider must define a non-empty string ID.")

        provider_id = provider.id.strip()
        with self._lock:
            if provider_id in self._providers and not overwrite:
                raise DuplicateProviderError(
                    f"Provider with ID '{provider_id}' is already registered."
                )
            self._providers[provider_id] = provider

    def unregister(self, provider_id: str) -> bool:
        """
        Unregister a provider by its ID.

        Returns:
            True if the provider was unregistered, False if it was not found.
        """
        with self._lock:
            return self._providers.pop(provider_id.strip(), None) is not None

    def get(self, provider_id: str) -> Optional[BaseProvider]:
        """Retrieve a provider by its unique ID."""
        with self._lock:
            return self._providers.get(provider_id.strip())

    def list_providers(self) -> List[BaseProvider]:
        """Return a snapshot list of all currently registered providers."""
        with self._lock:
            return list(self._providers.values())

    def find_for_url(self, url: str) -> Optional[BaseProvider]:
        """
        Inspect all registered providers to find one that can handle the given URL.

        Returns:
            The first matching BaseProvider, or None if no match is found.
        """
        if not url:
            return None
        with self._lock:
            for provider in self._providers.values():
                try:
                    if provider.can_handle_url(url):
                        return provider
                except Exception:
                    # Providers should not break registry discovery
                    continue
        return None

    def resolve_url(self, url: str) -> Tuple[BaseProvider, str]:
        """
        Resolve a URL to its matching provider.

        Returns:
            A tuple of (matched_provider, url).

        Raises:
            ProviderNotFoundError: If no registered provider can handle the URL.
        """
        provider = self.find_for_url(url)
        if provider is None:
            raise ProviderNotFoundError(f"No provider found capable of handling URL: {url}")
        return provider, url

    def clear(self) -> None:
        """Clear all registered providers from the registry."""
        with self._lock:
            self._providers.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._providers)

    def __contains__(self, provider_id: str) -> bool:
        with self._lock:
            return provider_id.strip() in self._providers


# Global default registry instance
default_registry = ProviderRegistry()


def register_provider(provider: BaseProvider, overwrite: bool = False) -> None:
    """Convenience helper to register a provider with the default registry."""
    default_registry.register(provider, overwrite=overwrite)


def unregister_provider(provider_id: str) -> bool:
    """Convenience helper to unregister a provider from the default registry."""
    return default_registry.unregister(provider_id)


def get_provider(provider_id: str) -> Optional[BaseProvider]:
    """Convenience helper to get a provider from the default registry."""
    return default_registry.get(provider_id)


def find_provider_for_url(url: str) -> Optional[BaseProvider]:
    """Convenience helper to find a provider for a URL in the default registry."""
    return default_registry.find_for_url(url)


def resolve_url(url: str) -> Tuple[BaseProvider, str]:
    """Convenience helper to resolve a URL in the default registry."""
    return default_registry.resolve_url(url)


def list_providers() -> List[BaseProvider]:
    """Convenience helper to list all providers in the default registry."""
    return default_registry.list_providers()


def clear_registry() -> None:
    """Convenience helper to clear the default registry."""
    default_registry.clear()
