"""
providers/cache.py - Thread-safe LRU/TTL chapter-page cache.

Maintains an in-memory cache of chapter pages with:
- Strict limit on maximum cached entries
- Strict limit on total page count across all cached entries
- Strict limit on metadata byte size across all cached entries
- Configurable TTL (time-to-live) per entry
- True LRU eviction when limits are reached
- Atomic counter accounting during insertion, replacement, eviction, and expiry
- Defensive copying so callers cannot mutate internal cache state
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import threading
import time
from typing import Any, Dict, List, Optional

from providers.base import RemotePage


def calculate_pages_metadata_size(pages: List[RemotePage]) -> int:
    """
    Deterministically calculate the metadata size in bytes for a list of RemotePage items.

    Counts UTF-8 encoded bytes for URL and headers, 8 bytes per index and byte_size,
    plus 32 bytes base object overhead per page.
    """
    size = 0
    for p in pages:
        size += len(p.url.encode("utf-8", errors="replace"))
        size += 8  # index integer representation
        if p.byte_size is not None:
            size += 8
        if p.headers:
            for k, v in p.headers.items():
                size += len(str(k).encode("utf-8", errors="replace"))
                size += len(str(v).encode("utf-8", errors="replace"))
        size += 32  # base RemotePage structure overhead
    return size


@dataclass
class _CacheEntry:
    key: str
    pages: List[RemotePage]
    page_count: int
    metadata_size: int
    created_at: float
    last_accessed: float


class ChapterPageCache:
    """
    Thread-safe LRU & TTL cache for chapter pages.

    Enforces limits on:
    - max_entries: Total number of chapters cached.
    - max_total_pages: Total number of pages cached across all chapters.
    - max_metadata_size: Maximum total metadata size (in bytes).
    - ttl_seconds: Time-to-live in seconds before an entry expires.
    """

    def __init__(
        self,
        max_entries: int = 100,
        max_total_pages: int = 10_000,
        max_metadata_size: int = 10 * 1024 * 1024,  # 10 MB default
        ttl_seconds: float = 3600.0,  # 1 hour default
    ) -> None:
        self.max_entries = int(max_entries)
        self.max_total_pages = int(max_total_pages)
        self.max_metadata_size = int(max_metadata_size)
        self.ttl_seconds = float(ttl_seconds)

        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._current_total_pages = 0
        self._current_metadata_size = 0
        self._lock = threading.RLock()

    def set(self, key: str, pages: List[RemotePage]) -> bool:
        """
        Store pages for a chapter key in the cache.

        Enforces:
        - Rejection of oversized entries (single entry exceeding any limit is never inserted).
        - Pruning of expired entries.
        - Replacement of existing key with correct counter math.
        - LRU eviction of oldest entries until new entry fits within all limits.
        - Deep copy storage so caller mutation cannot affect cache.

        Returns:
            True if inserted, False if rejected because the single entry exceeds limits.
        """
        if not key:
            return False

        with self._lock:
            # Enforce limits: reject single entry that exceeds any capacity limit
            if self.max_entries <= 0:
                return False

            new_page_count = len(pages)
            if new_page_count > self.max_total_pages:
                return False

            new_metadata_size = calculate_pages_metadata_size(pages)
            if new_metadata_size > self.max_metadata_size:
                return False

            now = time.time()

            # Handle replacement: if key exists, deduct old entry before checking space
            old_entry = self._entries.pop(key, None)
            if old_entry is not None:
                self._current_total_pages -= old_entry.page_count
                self._current_metadata_size -= old_entry.metadata_size

            # Prune any expired entries to free up capacity
            self._prune_expired_locked(now)

            # Evict LRU entries until the new entry fits within all three limits
            while self._entries and (
                len(self._entries) + 1 > self.max_entries
                or self._current_total_pages + new_page_count > self.max_total_pages
                or self._current_metadata_size + new_metadata_size > self.max_metadata_size
            ):
                _, evicted = self._entries.popitem(last=False)
                self._current_total_pages -= evicted.page_count
                self._current_metadata_size -= evicted.metadata_size

            # Re-check capacity after evictions
            if (
                len(self._entries) + 1 > self.max_entries
                or self._current_total_pages + new_page_count > self.max_total_pages
                or self._current_metadata_size + new_metadata_size > self.max_metadata_size
            ):
                # Cannot fit even after all evictions (restore old entry if applicable or fail)
                return False

            # Create safe defensive copy for internal storage
            safe_pages = [
                RemotePage(
                    index=p.index,
                    url=p.url,
                    headers=dict(p.headers or {}),
                    byte_size=p.byte_size,
                )
                for p in pages
            ]

            entry = _CacheEntry(
                key=key,
                pages=safe_pages,
                page_count=new_page_count,
                metadata_size=new_metadata_size,
                created_at=now,
                last_accessed=now,
            )

            self._entries[key] = entry
            self._current_total_pages += new_page_count
            self._current_metadata_size += new_metadata_size
            return True

    def get(self, key: str) -> Optional[List[RemotePage]]:
        """
        Retrieve cached pages for a key.

        Returns safe defensive copies of RemotePage instances.
        If entry is expired, it is evicted and None is returned.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None

            now = time.time()
            if now - entry.created_at >= self.ttl_seconds:
                # Expired - evict and decrement counters
                del self._entries[key]
                self._current_total_pages -= entry.page_count
                self._current_metadata_size -= entry.metadata_size
                return None

            # Mark as recently used
            entry.last_accessed = now
            self._entries.move_to_end(key)

            # Return defensive copy so caller cannot mutate cached state
            return [
                RemotePage(
                    index=p.index,
                    url=p.url,
                    headers=dict(p.headers or {}),
                    byte_size=p.byte_size,
                )
                for p in entry.pages
            ]

    def invalidate(self, key: str) -> bool:
        """
        Explicitly invalidate and remove a cached chapter key.

        Returns:
            True if key was in cache, False otherwise.
        """
        with self._lock:
            entry = self._entries.pop(key, None)
            if entry is not None:
                self._current_total_pages -= entry.page_count
                self._current_metadata_size -= entry.metadata_size
                return True
            return False

    def clear(self) -> None:
        """Clear all entries and reset counters to 0."""
        with self._lock:
            self._entries.clear()
            self._current_total_pages = 0
            self._current_metadata_size = 0

    def prune_expired(self) -> int:
        """Prune all expired entries from cache, returning count of pruned items."""
        with self._lock:
            return self._prune_expired_locked(time.time())

    def _prune_expired_locked(self, now: float) -> int:
        """Internal helper to prune expired entries while lock is held."""
        expired_keys = [
            k for k, v in self._entries.items()
            if now - v.created_at >= self.ttl_seconds
        ]
        for k in expired_keys:
            entry = self._entries.pop(k)
            self._current_total_pages -= entry.page_count
            self._current_metadata_size -= entry.metadata_size
        return len(expired_keys)

    @property
    def entries_count(self) -> int:
        """Return current number of entries in cache."""
        with self._lock:
            return len(self._entries)

    @property
    def total_pages(self) -> int:
        """Return total page count across all cached entries."""
        with self._lock:
            return self._current_total_pages

    @property
    def metadata_size(self) -> int:
        """Return total metadata size across all cached entries."""
        with self._lock:
            return self._current_metadata_size

    def stats(self) -> Dict[str, Any]:
        """Return snapshot statistics of the cache."""
        with self._lock:
            return {
                "entries": len(self._entries),
                "total_pages": self._current_total_pages,
                "metadata_size": self._current_metadata_size,
                "max_entries": self.max_entries,
                "max_total_pages": self.max_total_pages,
                "max_metadata_size": self.max_metadata_size,
                "ttl_seconds": self.ttl_seconds,
            }

    def assert_counters_consistent(self) -> None:
        """Diagnostic helper to verify internal counters match actual stored entries."""
        with self._lock:
            assert len(self._entries) == self.entries_count, "Entries count mismatch"
            assert self._current_total_pages >= 0, "Total pages counter negative"
            assert self._current_metadata_size >= 0, "Metadata size counter negative"
            sum_pages = sum(e.page_count for e in self._entries.values())
            sum_size = sum(e.metadata_size for e in self._entries.values())
            assert self._current_total_pages == sum_pages, (
                f"Page counter drift: {self._current_total_pages} != {sum_pages}"
            )
            assert self._current_metadata_size == sum_size, (
                f"Metadata size counter drift: {self._current_metadata_size} != {sum_size}"
            )

    def __contains__(self, key: str) -> bool:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False
            if time.time() - entry.created_at >= self.ttl_seconds:
                # Expired - evict and maintain exact accounting
                del self._entries[key]
                self._current_total_pages -= entry.page_count
                self._current_metadata_size -= entry.metadata_size
                return False
            return True

    def __len__(self) -> int:
        with self._lock:
            self._prune_expired_locked(time.time())
            return len(self._entries)
