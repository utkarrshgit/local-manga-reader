"""
providers/service.py - Remote reader integration service.

Coordinates between the provider registry, chapter page cache, SSRF security layer,
and reader endpoints. Provides an explicit separation between local manga collections
and remote provider series, chapters, and pages.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

from providers.base import BaseProvider, RemoteChapter, RemotePage, RemoteSeries
from providers.cache import ChapterPageCache
from providers.mock import MockProvider
from providers.registry import (
    ProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
    default_registry,
)
from providers.security import (
    DisallowedHostError,
    InvalidSchemeError,
    SSRFSecurityError,
    SecurityPolicy,
    validate_provider_target_url,
)


SUPPORTED_IMAGE_TYPES: Dict[str, str] = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "avif": "image/avif",
    "bmp": "image/bmp",
}


def detect_image_format(data: bytes) -> Optional[str]:
    """
    Detect supported image format from magic bytes.
    Returns format identifier ('jpeg', 'png', 'webp', 'gif', 'avif', 'bmp') or None.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 12:
        return None

    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    if data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return "avif"
    if data.startswith(b"BM") and len(data) >= 14:
        return "bmp"
    return None


def is_remote_series(series_str: Optional[str]) -> bool:
    """
    Check if a series identifier represents remote provider content
    rather than a local manga directory.
    """
    if not series_str or not isinstance(series_str, str):
        return False
    s = series_str.strip()
    return s.startswith("remote:") or s.startswith("http://") or s.startswith("https://")


def get_default_state_dir() -> Path:
    """Get user configuration directory for remote reader data persistence."""
    if os.environ.get("LOCAL_MANGA_CONFIG_DIR"):
        return Path(os.environ["LOCAL_MANGA_CONFIG_DIR"])
    if os.environ.get("LOCAL_MANGA_CONFIG_FILE"):
        return Path(os.environ["LOCAL_MANGA_CONFIG_FILE"]).parent
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser(r"~\AppData\Local"))
        return Path(local_app_data) / "LocalMangaReader"
    if sys.platform.startswith("linux"):
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return Path(xdg_config_home) / "LocalMangaReader"
    return Path(os.path.expanduser("~/Library/Application Support/LocalMangaReader"))


class RemoteReaderService:
    """
    Explicit integration service connecting remote providers to the reader.

    Responsibilities:
    - Resolves remote series identifiers and URLs to authorized providers.
    - Manages chapter page discovery with LRU/TTL caching via ChapterPageCache.
    - Proxies and streams remote page, cover, and backdrop images with SSRF protection.
    - Maintains decoupled reading progress, bookmarks, and reader style preferences.
    """

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        cache: Optional[ChapterPageCache] = None,
        state_dir: Optional[Path] = None,
    ) -> None:
        self.registry = registry if registry is not None else default_registry
        self.cache = cache if cache is not None else ChapterPageCache()
        self.state_dir = Path(state_dir) if state_dir is not None else get_default_state_dir()
        self._state_file = self.state_dir / "remote_reader_data.json"
        self._lock = threading.RLock()
        self._state: Dict[str, Dict[str, Any]] = {}

        # Ensure default providers are available
        if "mock" not in self.registry:
            try:
                self.registry.register(MockProvider())
            except Exception:
                pass

        if "weebcentral" not in self.registry:
            try:
                from providers.weebcentral import WeebCentralProvider
                self.registry.register(WeebCentralProvider())
            except Exception:
                pass

        if "nhentai" not in self.registry:
            try:
                from providers.nhentai import NhentaiProvider
                self.registry.register(NhentaiProvider())
            except Exception:
                pass

        self._load_state()

    def _load_state(self) -> None:
        """Load remote reader data from disk if present."""
        with self._lock:
            if self._state_file.is_file():
                try:
                    raw = json.loads(self._state_file.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self._state = raw
                except Exception:
                    self._state = {}

    def _save_state(self) -> None:
        """Atomically persist remote reader data to disk."""
        with self._lock:
            temp_file = None
            try:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                temp_file = self.state_dir / f"{self._state_file.name}.{os.getpid()}.tmp"
                temp_file.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
                temp_file.replace(self._state_file)
            except Exception:
                if temp_file is not None and temp_file.is_file():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

    def parse_series_identifier(self, series_identifier: str) -> Tuple[BaseProvider, str]:
        """
        Parse a series identifier (e.g. 'remote:mock:sololeveling' or 'https://mock.local/series/sololeveling')
        into its matching BaseProvider and target series ID or URL.

        Raises:
            ValueError: If identifier is empty or invalid.
            ProviderNotFoundError: If no matching provider is registered.
            SSRFSecurityError: If URL violates security constraints.
        """
        if not series_identifier or not isinstance(series_identifier, str):
            raise ValueError("Series identifier must be a non-empty string.")

        s = series_identifier.strip()
        if s.startswith("remote:"):
            parts = s[len("remote:") :].split(":", 1)
            provider_id = parts[0].strip()
            series_id = parts[1].strip() if len(parts) > 1 else ""
            if not provider_id:
                raise ValueError(f"Missing provider ID in remote series identifier: {series_identifier}")
            if not series_id:
                raise ValueError(f"Missing series ID in remote series identifier: {series_identifier}")
            provider = self.registry.get(provider_id)
            if provider is None:
                raise ProviderNotFoundError(f"Provider '{provider_id}' is not registered.")
            return provider, series_id

        if s.startswith("http://") or s.startswith("https://"):
            provider, target_url = self.registry.resolve_url(s)
            validate_provider_target_url(target_url, provider.allowed_domains)
            return provider, target_url

        raise ValueError(f"Unrecognized remote series identifier: {series_identifier}")

    def resolve_series(self, url_or_identifier: str) -> Dict[str, Any]:
        """
        Resolve remote series metadata by identifier or URL.

        Returns:
            Dictionary containing normalized series data, provider ID, and canonical identifier.
        """
        provider, target = self.parse_series_identifier(url_or_identifier)
        series = provider.get_series(target)

        canonical_id = f"remote:{provider.id}:{series.id}"
        return {
            "provider": provider.id,
            "series_id": series.id,
            "series_identifier": canonical_id,
            "series": series.to_dict(),
        }

    def get_supported_sources(self) -> List[Dict[str, str]]:
        """
        Return registered public providers and their supported URL types and patterns.
        Acts as the single source of truth for the Remote Manga UI.
        """
        sources: List[Dict[str, str]] = []
        for provider in self.registry.list_providers():
            if not getattr(provider, "is_public", True) or provider.id == "mock":
                continue
            sources.append({
                "id": provider.id,
                "name": getattr(provider, "name", provider.id),
                "url_type": getattr(provider, "supported_url_types", "Series URL"),
                "url_pattern": getattr(provider, "url_pattern", ""),
            })
        return sources

    def get_chapters(self, series_identifier: str) -> Dict[str, Any]:
        """
        Retrieve naturally ordered chapters for a remote series.
        Matches the shape expected by the reader frontend (/api/chapters).
        """
        provider, target = self.parse_series_identifier(series_identifier)
        series = provider.get_series(target)

        series_key = self._normalize_series_key(series_identifier)
        chapters_list: List[Dict[str, Any]] = []
        for ch in series.chapters:
            cached_pages = self.cache.get(f"{series_key}:{ch.id}")
            img_count = len(ch.pages) if ch.pages else (len(cached_pages) if cached_pages else 0)
            chapters_list.append({
                "name": ch.id,
                "title": ch.title,
                "chapter_number": ch.chapter_number,
                "url": ch.url,
                "date": ch.date,
                "image_count": img_count,
            })

        canonical_id = f"remote:{provider.id}:{series.id}"
        return {
            "series": canonical_id,
            "title": series.title,
            "provider": provider.id,
            "chapter_count": len(chapters_list),
            "chapters": chapters_list,
        }

    def get_chapter_pages(self, series_identifier: str, chapter_id: str) -> List[RemotePage]:
        """
        Fetch normalized pages for a remote chapter, leveraging ChapterPageCache.
        """
        if not chapter_id or not isinstance(chapter_id, str):
            raise ValueError("Chapter ID must be a non-empty string.")

        provider, _ = self.parse_series_identifier(series_identifier)
        cache_key = f"{self._normalize_series_key(series_identifier)}:{chapter_id.strip()}"

        # 1. Check cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # 2. Fetch from provider
        pages = provider.get_chapter_pages(chapter_id.strip())
        if not isinstance(pages, list):
            raise ValueError(f"Provider returned malformed pages of type: {type(pages).__name__}")

        for p in pages:
            if not isinstance(p, RemotePage) or not p.url:
                raise ValueError("Provider response contains malformed or empty RemotePage.")
            # Validate each page URL against security policies
            validate_provider_target_url(p.url, provider.allowed_domains)

        # 3. Store in cache
        self.cache.set(cache_key, pages)
        return pages

    def get_chapter_images_for_reader(
        self, series_identifier: str, chapter_id: str
    ) -> Dict[str, Any]:
        """
        Fetch chapter images formatted for the reader view (/api/images).
        Image URLs route through the SSRF-protected remote image proxy.
        """
        provider, _ = self.parse_series_identifier(series_identifier)
        pages = self.get_chapter_pages(series_identifier, chapter_id)

        canonical_series = series_identifier
        if not canonical_series.startswith("remote:"):
            canonical_series = f"remote:{provider.id}:{chapter_id}"

        image_items: List[Dict[str, Any]] = []
        for idx, page in enumerate(pages, start=1):
            filename = f"{idx}.jpg"
            proxy_url = f"/api/remote/image-proxy?url={quote(page.url)}&provider={quote(provider.id)}"
            image_items.append({
                "filename": filename,
                "url": proxy_url,
                "index": page.index,
                "byte_size": page.byte_size,
            })

        return {
            "series": series_identifier,
            "chapter": chapter_id,
            "image_count": len(image_items),
            "images": image_items,
        }

    def stream_page_image(self, provider_id: str, page_url: str) -> Tuple[bytes, str]:
        """
        Fetch and validate image bytes for a remote page URL via the provider security policy.

        Returns:
            Tuple of (binary_image_data, content_type_mime_string).

        Raises:
            ProviderNotFoundError: If provider ID is unknown.
            SSRFSecurityError / DisallowedHostError / InvalidSchemeError: If URL fails validation.
            ValueError: If image payload is invalid or unsupported.
        """
        if not provider_id or not page_url:
            raise ValueError("Provider ID and page URL must be provided.")

        provider = self.registry.get(provider_id.strip())
        if provider is None:
            raise ProviderNotFoundError(f"Provider '{provider_id}' not found.")

        # Strict allowlist and SSRF validation
        validate_provider_target_url(page_url, provider.allowed_domains)

        data = provider.get_image(page_url)
        fmt = detect_image_format(data)
        if not fmt or fmt not in SUPPORTED_IMAGE_TYPES:
            raise ValueError("Provider returned an invalid or unsupported image payload.")
        mime = SUPPORTED_IMAGE_TYPES[fmt]

        return data, mime

    def get_cover(self, series_identifier: str) -> Optional[Tuple[bytes, str]]:
        """
        Retrieve binary cover image for a remote series.
        Falls back to the first page of the first chapter if cover_url is absent.
        """
        try:
            provider, target = self.parse_series_identifier(series_identifier)
            series = provider.get_series(target)

            if series.cover_url:
                return self.stream_page_image(provider.id, series.cover_url)

            # Fallback to first chapter first page
            if series.chapters:
                first_ch = series.chapters[0]
                pages = self.get_chapter_pages(series_identifier, first_ch.id)
                if pages:
                    return self.stream_page_image(provider.id, pages[0].url)
        except Exception:
            return None
        return None

    def get_background(self, series_identifier: str) -> Optional[Tuple[bytes, str]]:
        """
        Retrieve binary hero background image for a remote series.
        Falls back to cover image if backdrop_url is absent.
        """
        try:
            provider, target = self.parse_series_identifier(series_identifier)
            series = provider.get_series(target)

            if series.backdrop_url:
                return self.stream_page_image(provider.id, series.backdrop_url)
        except Exception:
            pass

        return self.get_cover(series_identifier)

    def _normalize_series_key(self, series_identifier: str) -> str:
        """Generate a canonical state key for storing reader progress and bookmarks."""
        try:
            provider, target = self.parse_series_identifier(series_identifier)
            # If target is already a series ID
            if "://" not in target:
                return f"remote:{provider.id}:{target}"
            # Extract series ID from URL
            if hasattr(provider, "_extract_series_id"):
                extracted = provider._extract_series_id(target)
                return f"remote:{provider.id}:{extracted}"
            return f"remote:{provider.id}:{target}"
        except Exception:
            return series_identifier.strip()

    def get_reader_data(self, series_identifier: str) -> Dict[str, Any]:
        """
        Retrieve reading progress, bookmarks, and preferences for a remote series.
        """
        provider, target = self.parse_series_identifier(series_identifier)
        series = provider.get_series(target)

        key = self._normalize_series_key(series_identifier)
        with self._lock:
            state_entry = self._state.get(key, {})

        has_cover = bool(series.cover_url or (series.chapters and len(series.chapters) > 0))
        has_bg = bool(series.backdrop_url)

        links: Dict[str, str] = {}
        if isinstance(series.metadata, dict):
            raw_links = series.metadata.get("links")
            if isinstance(raw_links, dict):
                links = {str(k): str(v) for k, v in raw_links.items()}

        reader_cfg = state_entry.get("reader", {})
        style = reader_cfg.get("style", "spaced") if isinstance(reader_cfg, dict) else "spaced"
        if style not in ("spaced", "seamless"):
            style = "spaced"

        return {
            "series": series_identifier,
            "title": series.title,
            "summary": series.description or "",
            "author": series.author or "",
            "status": series.status or "",
            "links": links,
            "has_cover": has_cover,
            "has_background": has_bg,
            "progress": dict(state_entry.get("progress", {})),
            "bookmarks": list(state_entry.get("bookmarks", [])),
            "reader": {"style": style},
        }

    def update_progress(
        self, series_identifier: str, chapter_id: str, image_name: str
    ) -> Dict[str, Any]:
        """
        Update reading progress for a remote chapter.
        """
        if not chapter_id or not image_name:
            raise ValueError("Chapter ID and image filename are required.")

        key = self._normalize_series_key(series_identifier)
        with self._lock:
            if key not in self._state:
                self._state[key] = {"progress": {}, "bookmarks": [], "reader": {"style": "spaced"}}

            entry = self._state[key]
            if "progress" not in entry or not isinstance(entry["progress"], dict):
                entry["progress"] = {}
            entry["progress"][chapter_id.strip()] = image_name.strip()
            self._save_state()

        return self.get_reader_data(series_identifier)

    def toggle_bookmark(
        self, series_identifier: str, chapter_id: str, bookmarked: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Add, remove, or toggle bookmark for a remote chapter.
        """
        if not chapter_id:
            raise ValueError("Chapter ID is required.")

        key = self._normalize_series_key(series_identifier)
        ch = chapter_id.strip()

        with self._lock:
            if key not in self._state:
                self._state[key] = {"progress": {}, "bookmarks": [], "reader": {"style": "spaced"}}

            entry = self._state[key]
            bookmarks = set(entry.get("bookmarks", []))

            if bookmarked is None:
                if ch in bookmarks:
                    bookmarks.remove(ch)
                else:
                    bookmarks.add(ch)
            elif bookmarked:
                bookmarks.add(ch)
            else:
                bookmarks.discard(ch)

            entry["bookmarks"] = sorted(list(bookmarks))
            self._save_state()

        return self.get_reader_data(series_identifier)

    def update_reader_style(self, series_identifier: str, style: str) -> Dict[str, Any]:
        """
        Update reading style preference ('spaced' or 'seamless') for a remote series.
        """
        if style not in ("spaced", "seamless"):
            raise ValueError("Invalid reader style. Must be 'spaced' or 'seamless'.")

        key = self._normalize_series_key(series_identifier)
        with self._lock:
            if key not in self._state:
                self._state[key] = {"progress": {}, "bookmarks": [], "reader": {"style": "spaced"}}

            entry = self._state[key]
            entry["reader"] = {"style": style}
            self._save_state()

        return self.get_reader_data(series_identifier)
