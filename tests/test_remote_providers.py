"""
test_remote_providers.py - Isolated foundation tests for remote provider architecture.

Tests:
1. Base models (RemoteSeries, RemoteChapter, RemotePage) serialization and normalization.
2. Provider registry (registration, duplicate rejection, resolution, concurrency).
3. Cache (limits, oversized rejection, TTL expiry, LRU eviction, counter math, safe copies, concurrency).
4. Security (HTTPS-only, host boundaries, IP blocking, IPv4-mapped IPv6, redirects, connection-level SSRF, TLS SNI).
5. Mock provider (data fetching, error handling, cache and registry integration).
"""

from __future__ import annotations

import http.server
import ipaddress
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
from providers.registry import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
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


# ===========================================================================
# 1. Base Model Tests
# ===========================================================================

class TestRemoteModels(unittest.TestCase):
    """Verify serialization, normalization, and immutability of remote models."""

    def test_remote_page_serialization(self):
        page = RemotePage(
            index=1,
            url="https://cdn.example.com/p1.jpg",
            headers={"Referer": "https://example.com"},
            byte_size=1024,
        )
        d = page.to_dict()
        self.assertEqual(d["index"], 1)
        self.assertEqual(d["url"], "https://cdn.example.com/p1.jpg")
        self.assertEqual(d["headers"]["Referer"], "https://example.com")
        self.assertEqual(d["byte_size"], 1024)

        restored = RemotePage.from_dict(d)
        self.assertEqual(restored.index, page.index)
        self.assertEqual(restored.url, page.url)
        self.assertEqual(restored.headers, page.headers)
        self.assertEqual(restored.byte_size, page.byte_size)

    def test_remote_page_defaults(self):
        page = RemotePage(index=0, url="https://cdn.example.com/0.jpg")
        self.assertEqual(page.headers, {})
        self.assertIsNone(page.byte_size)
        d = page.to_dict()
        self.assertNotIn("byte_size", d)

    def test_remote_chapter_serialization(self):
        page = RemotePage(index=1, url="https://cdn.example.com/p1.jpg")
        chapter = RemoteChapter(
            id="ch-01",
            title="Chapter 1: The Start",
            chapter_number=1.5,
            url="https://example.com/ch/1",
            date="2026-01-01",
            pages=[page],
            metadata={"scan": "GroupA"},
        )
        d = chapter.to_dict()
        self.assertEqual(d["id"], "ch-01")
        self.assertEqual(d["chapter_number"], 1.5)
        self.assertEqual(len(d["pages"]), 1)
        self.assertEqual(d["metadata"]["scan"], "GroupA")

        restored = RemoteChapter.from_dict(d)
        self.assertEqual(restored.id, chapter.id)
        self.assertEqual(restored.chapter_number, 1.5)
        self.assertEqual(len(restored.pages), 1)
        self.assertEqual(restored.pages[0].url, page.url)

    def test_chapter_from_dict_non_numeric_chapter_number(self):
        d = {"id": "extra", "title": "Special Episode", "chapter_number": "special_extra"}
        ch = RemoteChapter.from_dict(d)
        self.assertIsNone(ch.chapter_number)

        d_empty = {"id": "extra2", "title": "Prologue", "chapter_number": ""}
        ch_empty = RemoteChapter.from_dict(d_empty)
        self.assertIsNone(ch_empty.chapter_number)

    def test_remote_series_serialization(self):
        ch = RemoteChapter(id="ch-1", title="Ch 1", chapter_number=1.0)
        series = RemoteSeries(
            id="solo",
            title="Solo Leveling",
            url="https://example.com/series/solo",
            cover_url="https://example.com/cover.jpg",
            backdrop_url="https://example.com/hero.jpg",
            description="A great webtoon",
            author="Chugong",
            status="Completed",
            chapters=[ch],
            metadata={"score": 9.5},
        )
        d = series.to_dict()
        self.assertEqual(d["title"], "Solo Leveling")
        self.assertEqual(d["status"], "Completed")
        self.assertEqual(len(d["chapters"]), 1)

        restored = RemoteSeries.from_dict(d)
        self.assertEqual(restored.id, series.id)
        self.assertEqual(restored.author, "Chugong")
        self.assertEqual(len(restored.chapters), 1)
        self.assertEqual(restored.chapters[0].title, "Ch 1")


# ===========================================================================
# 2. Provider Registry Tests
# ===========================================================================

class TestProviderRegistry(unittest.TestCase):
    """Verify provider registration, duplicate handling, resolution, and thread safety."""

    def setUp(self):
        self.registry = ProviderRegistry()

    def test_register_and_get(self):
        mock_p = MockProvider()
        self.registry.register(mock_p)
        self.assertEqual(len(self.registry), 1)
        self.assertIn("mock", self.registry)
        self.assertIs(self.registry.get("mock"), mock_p)

    def test_duplicate_registration_raises(self):
        mock_p = MockProvider()
        self.registry.register(mock_p)
        with self.assertRaises(DuplicateProviderError):
            self.registry.register(mock_p, overwrite=False)

    def test_overwrite_registration(self):
        mock_p1 = MockProvider()
        mock_p2 = MockProvider()
        self.registry.register(mock_p1)
        self.registry.register(mock_p2, overwrite=True)
        self.assertIs(self.registry.get("mock"), mock_p2)

    def test_invalid_provider_registration(self):
        with self.assertRaises(ValueError):
            self.registry.register("not_a_provider")  # type: ignore

        class NoIdProvider(BaseProvider):
            id = ""
            name = "Invalid"
            allowed_domains = ()
            def can_handle_url(self, url: str) -> bool: return False
            def get_series(self, url_or_id: str) -> RemoteSeries: raise NotImplementedError
            def get_chapter_pages(self, chapter_url_or_id: str) -> List[RemotePage]: raise NotImplementedError

        with self.assertRaises(ValueError):
            self.registry.register(NoIdProvider())

    def test_unregister(self):
        mock_p = MockProvider()
        self.registry.register(mock_p)
        self.assertTrue(self.registry.unregister("mock"))
        self.assertFalse(self.registry.unregister("mock"))
        self.assertIsNone(self.registry.get("mock"))

    def test_find_and_resolve_url(self):
        mock_p = MockProvider()
        self.registry.register(mock_p)

        target_url = "https://mock.local/series/sololeveling"
        found = self.registry.find_for_url(target_url)
        self.assertIs(found, mock_p)

        provider, url = self.registry.resolve_url(target_url)
        self.assertIs(provider, mock_p)
        self.assertEqual(url, target_url)

    def test_resolve_unknown_url_raises(self):
        with self.assertRaises(ProviderNotFoundError):
            self.registry.resolve_url("https://unknown-domain.com/series/1")

    def test_concurrent_registration_and_lookup(self):
        mock_p = MockProvider()
        self.registry.register(mock_p)

        errors: List[Exception] = []

        def worker(idx: int):
            try:
                for _ in range(50):
                    p = self.registry.find_for_url("https://mock.local/series/sololeveling")
                    if p is None:
                        raise RuntimeError("Provider lookup returned None during concurrent run")
                    self.registry.list_providers()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent registry errors: {errors}")


# ===========================================================================
# 3. Chapter Page Cache Tests
# ===========================================================================

class TestChapterPageCache(unittest.TestCase):
    """Verify LRU/TTL chapter page cache, limits, counter accounting, and safe values."""

    def _sample_pages(self, count: int, prefix: str = "p") -> List[RemotePage]:
        return [
            RemotePage(
                index=i,
                url=f"https://cdn.example.com/{prefix}_{i}.jpg",
                headers={"Referer": "https://example.com"},
            )
            for i in range(1, count + 1)
        ]

    def test_basic_set_and_get(self):
        cache = ChapterPageCache(max_entries=10, max_total_pages=100)
        pages = self._sample_pages(5)
        self.assertTrue(cache.set("ch1", pages))
        self.assertEqual(cache.entries_count, 1)
        self.assertEqual(cache.total_pages, 5)

        retrieved = cache.get("ch1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 5)
        self.assertEqual(retrieved[0].url, "https://cdn.example.com/p_1.jpg")

    def test_safe_page_list_returns_cannot_mutate_cache(self):
        """Mutating the returned list or its items must not mutate internal cache state."""
        cache = ChapterPageCache()
        pages = self._sample_pages(3)
        cache.set("ch1", pages)

        # Mutate the original passed list
        pages.clear()
        self.assertEqual(len(cache.get("ch1")), 3)

        # Mutate the returned list
        got = cache.get("ch1")
        got.clear()
        self.assertEqual(len(cache.get("ch1")), 3)

        # Mutate attributes of items in returned list
        got2 = cache.get("ch1")
        got2[0].url = "https://mutated.com/hacked.jpg"
        got2[0].headers["Injected"] = "Bad"
        got3 = cache.get("ch1")
        self.assertNotEqual(got3[0].url, "https://mutated.com/hacked.jpg")
        self.assertNotIn("Injected", got3[0].headers)

    def test_reject_single_entry_exceeding_page_limit(self):
        """Single entry exceeding total page count limit is rejected even if cache is empty."""
        cache = ChapterPageCache(max_entries=10, max_total_pages=5)
        pages = self._sample_pages(6)  # 6 > 5
        result = cache.set("oversized", pages)
        self.assertFalse(result)
        self.assertEqual(cache.entries_count, 0)
        self.assertEqual(cache.total_pages, 0)
        self.assertIsNone(cache.get("oversized"))
        cache.assert_counters_consistent()

    def test_reject_single_entry_exceeding_metadata_size_limit(self):
        """Single entry exceeding metadata size limit is rejected even if cache is empty."""
        cache = ChapterPageCache(max_entries=10, max_metadata_size=100)
        pages = self._sample_pages(10)  # metadata size will exceed 100 bytes
        self.assertGreater(calculate_pages_metadata_size(pages), 100)
        result = cache.set("oversized_meta", pages)
        self.assertFalse(result)
        self.assertEqual(cache.entries_count, 0)
        self.assertEqual(cache.metadata_size, 0)
        cache.assert_counters_consistent()

    def test_reject_when_max_entries_zero(self):
        """If max_entries <= 0, any insertion is immediately rejected."""
        cache = ChapterPageCache(max_entries=0)
        result = cache.set("ch1", self._sample_pages(1))
        self.assertFalse(result)
        self.assertEqual(cache.entries_count, 0)

    def test_replacement_maintains_exact_counters(self):
        """Replacing an existing key correctly deducts old stats and adds new stats."""
        cache = ChapterPageCache(max_entries=5, max_total_pages=20)
        cache.set("ch1", self._sample_pages(5, "old"))
        self.assertEqual(cache.total_pages, 5)
        cache.assert_counters_consistent()

        # Replace with 8 pages
        cache.set("ch1", self._sample_pages(8, "new"))
        self.assertEqual(cache.entries_count, 1)
        self.assertEqual(cache.total_pages, 8)
        cache.assert_counters_consistent()

        # Replace with 3 pages
        cache.set("ch1", self._sample_pages(3, "smaller"))
        self.assertEqual(cache.entries_count, 1)
        self.assertEqual(cache.total_pages, 3)
        cache.assert_counters_consistent()

        retrieved = cache.get("ch1")
        self.assertEqual(len(retrieved), 3)
        self.assertEqual(retrieved[0].url, "https://cdn.example.com/smaller_1.jpg")

    def test_lru_eviction_by_entry_count(self):
        """Cache evicts least-recently-used entry when max_entries is exceeded."""
        cache = ChapterPageCache(max_entries=2, max_total_pages=100)
        cache.set("ch1", self._sample_pages(2))
        cache.set("ch2", self._sample_pages(2))
        self.assertEqual(cache.entries_count, 2)

        # Access ch1 so ch2 becomes least recently used
        cache.get("ch1")

        # Insert ch3: should evict ch2
        cache.set("ch3", self._sample_pages(2))
        self.assertEqual(cache.entries_count, 2)
        self.assertIsNotNone(cache.get("ch1"))
        self.assertIsNone(cache.get("ch2"))
        self.assertIsNotNone(cache.get("ch3"))
        cache.assert_counters_consistent()

    def test_lru_eviction_by_total_page_count(self):
        """Cache evicts older entries when adding pages exceeds max_total_pages."""
        cache = ChapterPageCache(max_entries=10, max_total_pages=10)
        cache.set("ch1", self._sample_pages(4))
        cache.set("ch2", self._sample_pages(4))
        self.assertEqual(cache.total_pages, 8)

        # Inserting ch3 with 4 pages (8 + 4 = 12 > 10) must evict ch1
        cache.set("ch3", self._sample_pages(4))
        self.assertIsNone(cache.get("ch1"))
        self.assertIsNotNone(cache.get("ch2"))
        self.assertIsNotNone(cache.get("ch3"))
        self.assertEqual(cache.total_pages, 8)
        cache.assert_counters_consistent()

    def test_ttl_expiration(self):
        """Expired entries return None and are pruned from counters."""
        cache = ChapterPageCache(ttl_seconds=0.05)
        cache.set("ch1", self._sample_pages(3))
        self.assertEqual(cache.entries_count, 1)
        self.assertEqual(cache.total_pages, 3)

        # Immediate access: present
        self.assertIsNotNone(cache.get("ch1"))

        # Wait for TTL to expire
        time.sleep(0.07)

        # Access after TTL: should return None and prune entry
        self.assertIsNone(cache.get("ch1"))
        self.assertEqual(cache.entries_count, 0)
        self.assertEqual(cache.total_pages, 0)
        self.assertEqual(cache.metadata_size, 0)
        cache.assert_counters_consistent()

    def test_prune_expired_explicit(self):
        cache = ChapterPageCache(ttl_seconds=0.05)
        cache.set("ch1", self._sample_pages(2))
        cache.set("ch2", self._sample_pages(3))
        time.sleep(0.07)

        pruned = cache.prune_expired()
        self.assertEqual(pruned, 2)
        self.assertEqual(cache.entries_count, 0)
        self.assertEqual(cache.total_pages, 0)
        cache.assert_counters_consistent()

    def test_concurrent_cache_access(self):
        """Verify thread-safety and counter consistency under concurrent operations."""
        cache = ChapterPageCache(max_entries=10, max_total_pages=50, ttl_seconds=5.0)
        errors: List[Exception] = []

        def worker(thread_id: int):
            try:
                for i in range(20):
                    key = f"key_{thread_id}_{i % 5}"
                    pages = self._sample_pages(3, f"t{thread_id}")
                    cache.set(key, pages)
                    cache.get(key)
                    if i % 3 == 0:
                        cache.invalidate(key)
                    cache.assert_counters_consistent()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent cache errors: {errors}")
        cache.assert_counters_consistent()

    def test_cache_handles_none_headers_defensively(self):
        cache = ChapterPageCache()
        # Page with headers=None or uninitialized
        p = RemotePage(index=1, url="https://cdn.example.com/1.jpg")
        p.headers = None  # type: ignore
        self.assertTrue(cache.set("ch_none_headers", [p]))
        cached = cache.get("ch_none_headers")
        self.assertIsNotNone(cached)
        self.assertEqual(cached[0].headers, {})

    def test_cache_contains_and_len_prune_expired(self):
        cache = ChapterPageCache(ttl_seconds=0.04)
        cache.set("ch1", self._sample_pages(2))
        self.assertIn("ch1", cache)
        self.assertEqual(len(cache), 1)

        time.sleep(0.06)
        # After expiry, 'in' evaluates to False and evicts the entry
        self.assertNotIn("ch1", cache)
        self.assertEqual(len(cache), 0)
        cache.assert_counters_consistent()


# ===========================================================================
# 4. Security Tests
# ===========================================================================

class TestSecurityValidation(unittest.TestCase):
    """Verify IP classification, hostname boundaries, HTTPS enforcement, and redirects."""

    def test_is_safe_ip_rejects_loopback(self):
        self.assertFalse(is_safe_ip("127.0.0.1"))
        self.assertFalse(is_safe_ip("127.0.0.2"))
        self.assertFalse(is_safe_ip("127.255.255.255"))
        self.assertFalse(is_safe_ip("::1"))

    def test_is_safe_ip_rejects_private(self):
        self.assertFalse(is_safe_ip("10.0.0.1"))
        self.assertFalse(is_safe_ip("10.254.0.1"))
        self.assertFalse(is_safe_ip("172.16.0.1"))
        self.assertFalse(is_safe_ip("172.31.255.255"))
        self.assertFalse(is_safe_ip("192.168.0.1"))
        self.assertFalse(is_safe_ip("192.168.1.100"))
        self.assertFalse(is_safe_ip("fc00::1"))
        self.assertFalse(is_safe_ip("fd00::1"))

    def test_is_safe_ip_rejects_link_local_and_cloud_metadata(self):
        # 169.254.169.254 is the critical AWS/GCP/Azure/Oracle cloud metadata endpoint
        self.assertFalse(is_safe_ip("169.254.169.254"))
        self.assertFalse(is_safe_ip("169.254.0.1"))
        self.assertFalse(is_safe_ip("fe80::1"))

    def test_is_safe_ip_rejects_cgnat_and_reserved(self):
        self.assertFalse(is_safe_ip("100.64.0.1"))     # Carrier-Grade NAT
        self.assertFalse(is_safe_ip("0.0.0.0"))        # Unspecified
        self.assertFalse(is_safe_ip("::"))             # Unspecified IPv6
        self.assertFalse(is_safe_ip("240.0.0.1"))      # Reserved IPv4
        self.assertFalse(is_safe_ip("255.255.255.255"))# Broadcast

    def test_is_safe_ip_rejects_documentation_and_benchmark(self):
        self.assertFalse(is_safe_ip("192.0.2.1"))      # TEST-NET-1
        self.assertFalse(is_safe_ip("198.51.100.1"))   # TEST-NET-2
        self.assertFalse(is_safe_ip("203.0.113.1"))    # TEST-NET-3
        self.assertFalse(is_safe_ip("198.18.0.1"))     # Benchmarking
        self.assertFalse(is_safe_ip("2001:db8::1"))    # Documentation IPv6

    def test_is_safe_ip_rejects_ipv4_mapped_ipv6(self):
        # IPv4-mapped IPv6 addresses embedding disallowed IPv4
        self.assertFalse(is_safe_ip("::ffff:127.0.0.1"))
        self.assertFalse(is_safe_ip("::ffff:10.0.0.1"))
        self.assertFalse(is_safe_ip("::ffff:169.254.169.254"))
        self.assertFalse(is_safe_ip("::ffff:192.168.1.1"))

    def test_is_safe_ip_accepts_public_global_ips(self):
        self.assertTrue(is_safe_ip("8.8.8.8"))
        self.assertTrue(is_safe_ip("1.1.1.1"))
        self.assertTrue(is_safe_ip("93.184.216.34"))   # example.com
        self.assertTrue(is_safe_ip("2001:4860:4860::8888"))

    def test_is_safe_ip_allow_localhost_flag(self):
        self.assertFalse(is_safe_ip("127.0.0.1", allow_localhost=False))
        self.assertTrue(is_safe_ip("127.0.0.1", allow_localhost=True))
        # Even with allow_localhost=True, non-loopback private IPs remain blocked!
        self.assertFalse(is_safe_ip("10.0.0.1", allow_localhost=True))
        self.assertFalse(is_safe_ip("169.254.169.254", allow_localhost=True))

    def test_https_scheme_enforced(self):
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        # Non-HTTPS schemes must be rejected immediately
        with self.assertRaises(InvalidSchemeError):
            policy.validate_url("http://example.com/ch1")
        with self.assertRaises(InvalidSchemeError):
            policy.validate_url("ftp://example.com/ch1")
        with self.assertRaises(InvalidSchemeError):
            policy.validate_url("file:///etc/passwd")
        with self.assertRaises(InvalidSchemeError):
            policy.validate_url("javascript:alert(1)")

    def test_exact_hostname_boundaries(self):
        policy = SecurityPolicy(allowed_hosts=["example.com", "*.cdn.example.com"])

        # Exact match
        self.assertTrue(policy.match_hostname("example.com"))
        # Wildcard match
        self.assertTrue(policy.match_hostname("img.cdn.example.com"))
        self.assertTrue(policy.match_hostname("a.b.cdn.example.com"))

        # Exact boundary enforcement: prefix/suffix tricks must be rejected
        self.assertFalse(policy.match_hostname("attacker-example.com"))
        self.assertFalse(policy.match_hostname("example.com.evil.com"))
        self.assertFalse(policy.match_hostname("notexample.com"))
        self.assertFalse(policy.match_hostname("badcdn.example.com"))
        self.assertFalse(policy.match_hostname("evil.com"))

    def test_url_credentials_rejected(self):
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        with self.assertRaises(SSRFSecurityError):
            policy.validate_url("https://user:pass@example.com/chapter")

    def test_raw_ip_as_hostname_rejected(self):
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        with self.assertRaises(DisallowedHostError):
            policy.validate_url("https://127.0.0.1/chapter")
        with self.assertRaises(DisallowedHostError):
            policy.validate_url("https://93.184.216.34/chapter")

    def test_arbitrary_browser_proxy_target_rejected(self):
        """Validate validate_provider_target_url rejects unapproved targets."""
        allowed = ("provider.com", "cdn.provider.com")
        valid = "https://provider.com/series/1"
        self.assertEqual(validate_provider_target_url(valid, allowed), valid)

        with self.assertRaises(DisallowedHostError):
            validate_provider_target_url("https://evil.com/ch", allowed)
        with self.assertRaises(InvalidSchemeError):
            validate_provider_target_url("http://provider.com/ch", allowed)

    def test_is_safe_ip_handles_deprecated_ipv4_compatible_and_siit_ipv6(self):
        self.assertFalse(is_safe_ip("::127.0.0.1"))
        self.assertFalse(is_safe_ip("::169.254.169.254"))
        self.assertFalse(is_safe_ip("::ffff:0:127.0.0.1"))

    def test_is_safe_ip_handles_integer_and_invalid_types_safely(self):
        self.assertFalse(is_safe_ip(2130706433))  # 127.0.0.1 as int
        self.assertFalse(is_safe_ip(None))        # None
        self.assertFalse(is_safe_ip(object()))    # arbitrary object

    def test_url_validation_port_edge_cases(self):
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        with self.assertRaises(SSRFSecurityError):
            policy.validate_url("https://example.com:-1/ch")
        with self.assertRaises(SSRFSecurityError):
            policy.validate_url("https://example.com:0/ch")
        with self.assertRaises(SSRFSecurityError):
            policy.validate_url("https://example.com:65536/ch")
        with self.assertRaises(DisallowedHostError):
            policy.validate_url("https://example.com:8443/ch")

    def test_url_validation_rejects_control_characters(self):
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        with self.assertRaises(SSRFSecurityError):
            policy.validate_url("https://example.com\r\n/ch")
        with self.assertRaises(SSRFSecurityError):
            policy.validate_url("https://example.com\x00/ch")

    def test_wildcard_matching_rejects_tld_wildcards(self):
        policy = SecurityPolicy(allowed_hosts=["*.com"])
        self.assertFalse(policy.match_hostname("evil.com"))


# ===========================================================================
# 5. Connection-Level SSRF & Redirect Transport Tests
# ===========================================================================

class TestConnectionLevelSSRFTransport(unittest.TestCase):
    """
    Verify custom transport connection-level defenses.
    Tests:
    - Pre-connection rejection of loopback/private IPs
    - DNS rebinding TOCTOU defense
    - Post-connect socket peer verification
    - Redirect validation and hop limits
    - Real TLS handshake and certificate/SNI verification
    """

    def test_connection_aborts_on_loopback_and_private_ips(self):
        """SSRFProtectedHTTPSConnection rejects loopback/private IPs at connection time."""
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        conn = SSRFProtectedHTTPSConnection("example.com", 443, security_policy=policy)

        # Mock socket.getaddrinfo to simulate resolution returning 127.0.0.1
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
            ]
            with self.assertRaises(BlockedIPError):
                conn.connect()

        # Simulate resolution returning cloud metadata service IP 169.254.169.254
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))
            ]
            with self.assertRaises(BlockedIPError):
                conn.connect()

    def test_dns_rebinding_defense_deterministic(self):
        """
        Simulate DNS rebinding where attacker DNS returns mixed or malicious IPs.
        The custom transport inspects the actual candidates before socket connection.
        """
        policy = SecurityPolicy(allowed_hosts=["rebind.example.com"])
        conn = SSRFProtectedHTTPSConnection("rebind.example.com", 443, security_policy=policy)

        # DNS returns public IP and private IP
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
            ]
            with self.assertRaises(BlockedIPError):
                conn.connect()

    def test_connected_socket_peer_verification(self):
        """
        If a socket somehow connected to a prohibited IP, sock.getpeername()
        detection immediately closes the socket and raises BlockedIPError.
        """
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        conn = SSRFProtectedHTTPSConnection("example.com", 443, security_policy=policy)

        mock_sock = MagicMock()
        mock_sock.getpeername.return_value = ("127.0.0.1", 443)  # Loopback peer!

        with patch("socket.getaddrinfo") as mock_gai:
            # getaddrinfo claimed public IP 93.184.216.34
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
            ]
            with patch("socket.socket", return_value=mock_sock):
                with self.assertRaises(BlockedIPError):
                    conn.connect()
                mock_sock.close.assert_called()

    def test_redirect_to_unauthorized_host_blocked(self):
        """Redirect from allowed host to unauthorized host is blocked before connecting."""
        policy = SecurityPolicy(allowed_hosts=["allowed.com"])
        client = SecureHttpClient(policy=policy)

        # Mock connection to return 302 to https://evil.com
        mock_resp = MagicMock()
        mock_resp.status = 302
        mock_resp.getheader.side_effect = lambda h: "https://evil.com/ch1" if h == "Location" else None

        with patch.object(SSRFProtectedHTTPSConnection, "connect"), \
             patch.object(SSRFProtectedHTTPSConnection, "request"), \
             patch.object(SSRFProtectedHTTPSConnection, "getresponse", return_value=mock_resp):
                with self.assertRaises(DisallowedHostError):
                    client.get("https://allowed.com/start")

    def test_redirect_to_non_https_blocked(self):
        """Redirect from HTTPS to HTTP is blocked."""
        policy = SecurityPolicy(allowed_hosts=["allowed.com"])
        client = SecureHttpClient(policy=policy)

        mock_resp = MagicMock()
        mock_resp.status = 301
        mock_resp.getheader.side_effect = lambda h: "http://allowed.com/plain" if h == "Location" else None

        with patch.object(SSRFProtectedHTTPSConnection, "connect"), \
             patch.object(SSRFProtectedHTTPSConnection, "request"), \
             patch.object(SSRFProtectedHTTPSConnection, "getresponse", return_value=mock_resp):
                with self.assertRaises(InvalidSchemeError):
                    client.get("https://allowed.com/start")

    def test_redirect_loop_detected(self):
        """Redirect loop A -> B -> A is detected and rejected."""
        policy = SecurityPolicy(allowed_hosts=["allowed.com"])
        client = SecureHttpClient(policy=policy)

        # Mock connection: start -> loop -> start
        responses = [
            MagicMock(status=302, getheader=lambda h: "https://allowed.com/loop" if h == "Location" else None),
            MagicMock(status=302, getheader=lambda h: "https://allowed.com/start" if h == "Location" else None),
        ]

        with patch.object(SSRFProtectedHTTPSConnection, "connect"), \
             patch.object(SSRFProtectedHTTPSConnection, "request"), \
             patch.object(SSRFProtectedHTTPSConnection, "getresponse", side_effect=responses):
                with self.assertRaises(RedirectSecurityError):
                    client.get("https://allowed.com/start")

    def test_max_redirects_exceeded(self):
        """Exceeding configured max_redirects raises MaxRedirectsExceededError."""
        policy = SecurityPolicy(allowed_hosts=["allowed.com"], max_redirects=2)
        client = SecureHttpClient(policy=policy)

        def make_redirect_resp(target: str):
            r = MagicMock()
            r.status = 302
            r.getheader.side_effect = lambda h: target if h == "Location" else None
            return r

        responses = [
            make_redirect_resp("https://allowed.com/step1"),
            make_redirect_resp("https://allowed.com/step2"),
            make_redirect_resp("https://allowed.com/step3"),
        ]

        with patch.object(SSRFProtectedHTTPSConnection, "connect"), \
             patch.object(SSRFProtectedHTTPSConnection, "request"), \
             patch.object(SSRFProtectedHTTPSConnection, "getresponse", side_effect=responses):
                with self.assertRaises(MaxRedirectsExceededError):
                    client.get("https://allowed.com/start")

    def test_mixed_dns_candidates_fails_safe(self):
        """DNS returning a mixture of public and prohibited IPs fails closed immediately."""
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        conn = SSRFProtectedHTTPSConnection("example.com", 443, security_policy=policy)

        # Public candidate followed by loopback candidate
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
            ]
            with self.assertRaises(BlockedIPError):
                conn.connect()

        # Loopback candidate followed by public candidate
        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            ]
            with self.assertRaises(BlockedIPError):
                conn.connect()

    def test_post_connect_peer_violation_aborts_immediately_without_retrying_candidates(self):
        """When socket peer verification detects an SSRF violation, it aborts without trying subsequent candidates."""
        policy = SecurityPolicy(allowed_hosts=["example.com"])
        conn = SSRFProtectedHTTPSConnection("example.com", 443, security_policy=policy)

        mock_sock1 = MagicMock()
        mock_sock1.getpeername.return_value = ("127.0.0.1", 443)  # Loopback peer violation!

        mock_sock2 = MagicMock()
        mock_sock2.getpeername.return_value = ("93.184.216.35", 443)

        with patch("socket.getaddrinfo") as mock_gai:
            mock_gai.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.35", 443)),
            ]
            with patch("socket.socket", side_effect=[mock_sock1, mock_sock2]):
                with self.assertRaises(BlockedIPError):
                    conn.connect()
                # Candidate 1 was closed due to violation
                mock_sock1.close.assert_called()
                # Candidate 2 must NEVER have been attempted
                mock_sock2.connect.assert_not_called()

    def test_redirect_strips_sensitive_headers_on_host_change(self):
        """Cross-host redirects strip Authorization and Cookie headers according to RFC 7235 / RFC 9110."""
        policy = SecurityPolicy(allowed_hosts=["allowed.com", "cdn.allowed.com"])
        client = SecureHttpClient(policy=policy)

        captured_requests = []

        def mock_request(method, path, body=None, headers=None):
            captured_requests.append(dict(headers or {}))

        # First response: 302 to cdn.allowed.com
        resp1 = MagicMock(status=302, getheader=lambda h: "https://cdn.allowed.com/img.jpg" if h == "Location" else None)
        # Second response: 200 OK
        resp2 = MagicMock(status=200, getheader=lambda h: None)
        resp2.read.side_effect = [b"OK", b""]
        resp2.getheaders.return_value = [("Content-Length", "2")]

        with patch.object(SSRFProtectedHTTPSConnection, "connect"), \
             patch.object(SSRFProtectedHTTPSConnection, "request", side_effect=mock_request), \
             patch.object(SSRFProtectedHTTPSConnection, "getresponse", side_effect=[resp1, resp2]):
            client.get(
                "https://allowed.com/start",
                headers={"Authorization": "Bearer secret123", "Cookie": "session=abc", "X-Custom": "Safe"}
            )

        self.assertEqual(len(captured_requests), 2)
        # Request 1 (allowed.com): has credentials and Host: allowed.com
        self.assertEqual(captured_requests[0].get("Authorization"), "Bearer secret123")
        self.assertEqual(captured_requests[0].get("Cookie"), "session=abc")
        self.assertEqual(captured_requests[0].get("Host"), "allowed.com")

        # Request 2 (cdn.allowed.com): sensitive headers stripped, Host updated
        self.assertNotIn("Authorization", captured_requests[1])
        self.assertNotIn("Cookie", captured_requests[1])
        self.assertEqual(captured_requests[1].get("X-Custom"), "Safe")
        self.assertEqual(captured_requests[1].get("Host"), "cdn.allowed.com")

    def test_redirect_rejects_crlf_in_location(self):
        """Location headers with CRLF or control characters are rejected."""
        policy = SecurityPolicy(allowed_hosts=["allowed.com"])
        client = SecureHttpClient(policy=policy)

        mock_resp = MagicMock(
            status=302,
            getheader=lambda h: "https://allowed.com/foo\r\nSet-Cookie:hacked" if h == "Location" else None
        )

        with patch.object(SSRFProtectedHTTPSConnection, "connect"), \
             patch.object(SSRFProtectedHTTPSConnection, "request"), \
             patch.object(SSRFProtectedHTTPSConnection, "getresponse", return_value=mock_resp):
            with self.assertRaises(RedirectSecurityError):
                client.get("https://allowed.com/start")

    def test_real_transport_tls_handshake_and_sni_verification(self):
        """
        Deterministic connection-level test using a real TLS server socketpair.
        Verifies:
        - Real SSLContext handshake
        - SNI (server_hostname) matching
        - Certificate verification
        - Rejection when hostname / SNI does not match certificate
        """
        with tempfile.TemporaryDirectory() as td:
            keyfile = f"{td}/key.pem"
            certfile = f"{td}/cert.pem"

            # Generate a real self-signed certificate for localhost
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", keyfile, "-out", certfile, "-days", "1",
                "-nodes", "-subj", "/CN=localhost"
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_ctx.load_cert_chain(certfile, keyfile)

            client_ctx = ssl.create_default_context(cafile=certfile)

            s1, s2 = socket.socketpair()

            def server_worker():
                try:
                    tls_server = server_ctx.wrap_socket(s2, server_side=True)
                    req = tls_server.recv(1024)
                    self.assertIn(b"GET /test", req)
                    tls_server.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 12\r\nContent-Type: text/plain\r\n\r\nHello Secure"
                    )
                    tls_server.close()
                except Exception as e:
                    s2.close()

            server_thread = threading.Thread(target=server_worker)
            server_thread.start()

            # Client connects with valid SNI = "localhost"
            tls_client = client_ctx.wrap_socket(s1, server_hostname="localhost")
            tls_client.sendall(b"GET /test HTTP/1.1\r\nHost: localhost\r\n\r\n")
            data = tls_client.recv(1024)
            self.assertIn(b"200 OK", data)
            self.assertIn(b"Hello Secure", data)
            tls_client.close()
            server_thread.join()

            # Now test SNI / Certificate mismatch rejection:
            s3, s4 = socket.socketpair()

            def server_mismatch_worker():
                try:
                    server_ctx.wrap_socket(s4, server_side=True)
                except ssl.SSLError:
                    pass
                finally:
                    s4.close()

            server_thread2 = threading.Thread(target=server_mismatch_worker)
            server_thread2.start()

            # Attempt handshake with mismatched server_hostname "evil.com"
            with self.assertRaises(ssl.SSLCertVerificationError):
                client_ctx.wrap_socket(s3, server_hostname="evil.com")

            s3.close()
            server_thread2.join()


# ===========================================================================
# 6. Mock Provider Integration Tests
# ===========================================================================

class TestMockProvider(unittest.TestCase):
    """Verify MockProvider operations and integration with cache & registry."""

    def setUp(self):
        self.provider = MockProvider()

    def test_can_handle_url(self):
        self.assertTrue(self.provider.can_handle_url("https://mock.local/series/sololeveling"))
        self.assertTrue(self.provider.can_handle_url("https://cdn.mock.local/covers/1.jpg"))
        self.assertFalse(self.provider.can_handle_url("https://external.com/series/1"))

    def test_get_series_and_chapters(self):
        series = self.provider.get_series("sololeveling")
        self.assertEqual(series.title, "Solo Leveling")
        self.assertEqual(series.author, "Chugong")
        self.assertEqual(len(series.chapters), 2)

        # Test URL resolution
        series_by_url = self.provider.get_series("https://mock.local/series/sololeveling")
        self.assertEqual(series_by_url.id, "sololeveling")

    def test_get_chapter_pages(self):
        pages = self.provider.get_chapter_pages("mock-ch-1")
        self.assertEqual(len(pages), 3)
        self.assertEqual(pages[0].url, "https://cdn.mock.local/series1/ch1/1.jpg")

        pages_by_url = self.provider.get_chapter_pages(
            "https://mock.local/series/sololeveling/chapter-2"
        )
        self.assertEqual(len(pages_by_url), 2)

    def test_not_found_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.provider.get_series("non-existent-series")
        with self.assertRaises(KeyError):
            self.provider.get_chapter_pages("non-existent-ch")

    def test_cache_integration_with_mock_provider(self):
        cache = ChapterPageCache()
        # Initial: not in cache
        self.assertIsNone(cache.get("mock-ch-1"))

        # Fetch from mock provider and cache
        pages = self.provider.get_chapter_pages("mock-ch-1")
        self.assertTrue(cache.set("mock-ch-1", pages))

        # Subsequent retrieval from cache
        cached_pages = cache.get("mock-ch-1")
        self.assertIsNotNone(cached_pages)
        self.assertEqual(len(cached_pages), len(pages))
        self.assertEqual(cached_pages[0].url, pages[0].url)


if __name__ == "__main__":
    unittest.main()
