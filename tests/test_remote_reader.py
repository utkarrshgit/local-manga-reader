"""
test_remote_reader.py - Comprehensive Phase 3 integration tests for remote provider reader integration.

Demonstrates:
1. Mock remote series resolution and chapter listing.
2. Mock remote chapter opened and pages rendered through the existing reader flow.
3. Local reading works independently of remote-provider functionality.
4. Network, provider, and malformed-response errors fail gracefully.
5. Cache behavior works correctly through the integration layer.
6. Remote URLs cannot bypass provider allowlists or security validation.
7. Existing progress, bookmarks, and reading-mode behavior remain correct.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import BaseProvider, RemoteChapter, RemotePage, RemoteSeries
from providers.cache import ChapterPageCache
from providers.mock import MockProvider
from providers.registry import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ProviderRegistry,
    default_registry,
)
from providers.security import (
    BlockedIPError,
    DisallowedHostError,
    InvalidSchemeError,
    SSRFSecurityError,
    SecurityPolicy,
    validate_provider_target_url,
)
from providers.service import (
    RemoteReaderService,
    is_remote_series,
)
from server import (
    MangaLibrary,
    MangaRequestHandler,
    detect_image_format,
)


class MockSocket:
    """Mock socket simulating client-server HTTP communication."""

    def __init__(self, data_bytes: bytes) -> None:
        self.rfile = io.BytesIO(data_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, *args: Any, **kwargs: Any) -> io.BytesIO:
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            elif "w" in mode:
                return self.wfile
        raise ValueError(f"Unsupported socket mode: {mode}")

    def sendall(self, data: bytes) -> None:
        self.wfile.write(data)


class BaseReaderIntegrationTestCase(unittest.TestCase):
    """Base test case providing test fixtures and HTTP simulation helpers."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir) / "manga"
        self.lib_path.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Setup local manga library fixtures
        op_ch1 = self.lib_path / "OnePiece" / "Chapter 1"
        op_ch1.mkdir(parents=True, exist_ok=True)
        (op_ch1 / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
        (op_ch1 / "2.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)

        op_ch2 = self.lib_path / "OnePiece" / "Chapter 2"
        op_ch2.mkdir(parents=True, exist_ok=True)
        (op_ch2 / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)

        (self.lib_path / "OnePiece" / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)

        self.library = MangaLibrary(str(self.lib_path))

        # Setup isolated registry, cache, and remote service
        self.registry = ProviderRegistry()
        self.mock_provider = MockProvider()
        self.registry.register(self.mock_provider)

        self.cache = ChapterPageCache(max_entries=20, max_total_pages=500)
        self.remote_service = RemoteReaderService(
            registry=self.registry,
            cache=self.cache,
            state_dir=self.state_dir,
        )

        self.HandlerClass = MangaRequestHandler
        self.HandlerClass.library = self.library
        self.HandlerClass.static_dir = PROJECT_ROOT / "static"
        self.HandlerClass.remote_service = self.remote_service

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def simulate_get(self, path: str) -> Tuple[str, bytes, int]:
        """Simulate an HTTP GET request against MangaRequestHandler."""
        raw_request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(raw_request)

        handler = self.HandlerClass(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_bytes = sock.wfile.read()
        header_end = response_bytes.find(b"\r\n\r\n")
        if header_end == -1:
            return "", b"", 500

        headers_str = response_bytes[:header_end].decode("utf-8", errors="replace")
        body = response_bytes[header_end + 4:]

        status_code = 200
        if headers_str:
            first_line = headers_str.split("\r\n")[0]
            parts = first_line.split(" ")
            if len(parts) >= 2 and parts[1].isdigit():
                status_code = int(parts[1])

        return headers_str, body, status_code

    def simulate_post(self, path: str, json_data: Dict[str, Any]) -> Tuple[str, bytes, int]:
        """Simulate an HTTP POST request against MangaRequestHandler."""
        body_bytes = json.dumps(json_data).encode("utf-8")
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(raw_request)

        handler = self.HandlerClass(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_bytes = sock.wfile.read()
        header_end = response_bytes.find(b"\r\n\r\n")
        if header_end == -1:
            return "", b"", 500

        headers_str = response_bytes[:header_end].decode("utf-8", errors="replace")
        body = response_bytes[header_end + 4:]

        status_code = 200
        if headers_str:
            first_line = headers_str.split("\r\n")[0]
            parts = first_line.split(" ")
            if len(parts) >= 2 and parts[1].isdigit():
                status_code = int(parts[1])

        return headers_str, body, status_code


# ===========================================================================
# 1. Mock Remote Series Resolution & Chapter Listing Tests
# ===========================================================================

class TestRemoteSeriesResolutionAndChapters(BaseReaderIntegrationTestCase):
    """Demonstrate mock remote series resolution and chapter discovery."""

    def test_resolve_remote_series_by_url(self):
        """Mock remote series can be resolved via URL through /api/remote/resolve."""
        headers, body, status = self.simulate_get("/api/remote/resolve?url=https://mock.local/series/sololeveling")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["provider"], "mock")
        self.assertEqual(data["series_id"], "sololeveling")
        self.assertEqual(data["series_identifier"], "remote:mock:sololeveling")
        self.assertEqual(data["series"]["title"], "Solo Leveling")
        self.assertEqual(data["series"]["author"], "Chugong")
        self.assertEqual(len(data["series"]["chapters"]), 2)

    def test_resolve_remote_series_by_identifier(self):
        """Mock remote series can be resolved via canonical identifier remote:mock:sololeveling."""
        headers, body, status = self.simulate_get("/api/remote/series?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series_id"], "sololeveling")
        self.assertEqual(data["series"]["title"], "Solo Leveling")

    def test_list_remote_chapters_via_dedicated_endpoint(self):
        """Remote chapters are listed via /api/remote/chapters with normalized attributes."""
        headers, body, status = self.simulate_get("/api/remote/chapters?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "remote:mock:sololeveling")
        self.assertEqual(data["title"], "Solo Leveling")
        self.assertEqual(data["chapter_count"], 2)

        ch1, ch2 = data["chapters"]
        self.assertEqual(ch1["name"], "mock-ch-1")
        self.assertEqual(ch1["title"], "Chapter 1: The Awakening")
        self.assertEqual(ch1["chapter_number"], 1.0)
        self.assertEqual(ch1["image_count"], 3)

        self.assertEqual(ch2["name"], "mock-ch-2")
        self.assertEqual(ch2["title"], "Chapter 2: The Next Trial")
        self.assertEqual(ch2["chapter_number"], 2.0)
        self.assertEqual(ch2["image_count"], 2)

    def test_list_remote_chapters_via_existing_reader_endpoint(self):
        """Remote chapters are served through the existing /api/chapters endpoint."""
        headers, body, status = self.simulate_get("/api/chapters?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "remote:mock:sololeveling")
        self.assertEqual(data["title"], "Solo Leveling")
        self.assertEqual(data["chapter_count"], 2)
        self.assertEqual([c["name"] for c in data["chapters"]], ["mock-ch-1", "mock-ch-2"])


# ===========================================================================
# 2. Mock Remote Chapter Opened & Pages Rendered Through Reader Flow
# ===========================================================================

class TestRemoteChapterReaderFlow(BaseReaderIntegrationTestCase):
    """Demonstrate mock remote chapters opened and rendered through the existing reader flow."""

    def test_chapter_images_list_via_existing_reader_endpoint(self):
        """GET /api/images returns normalized image items with SSRF-protected proxy URLs."""
        headers, body, status = self.simulate_get("/api/images?series=remote:mock:sololeveling&chapter=mock-ch-1")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "remote:mock:sololeveling")
        self.assertEqual(data["chapter"], "mock-ch-1")
        self.assertEqual(data["image_count"], 3)

        images = data["images"]
        self.assertEqual(len(images), 3)
        self.assertEqual(images[0]["filename"], "1.jpg")
        self.assertIn("/api/remote/image-proxy?", images[0]["url"])
        self.assertIn("provider=mock", images[0]["url"])

    def test_stream_page_image_through_proxy(self):
        """GET /api/remote/image-proxy streams validated binary image bytes with MIME headers."""
        page_url = "https://cdn.mock.local/series1/ch1/1.jpg"
        proxy_path = f"/api/remote/image-proxy?url={page_url}&provider=mock"

        headers, body, status = self.simulate_get(proxy_path)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Content-Type: image/png", headers)
        self.assertGreater(len(body), 10)
        self.assertEqual(detect_image_format(body), "png")

    def test_stream_page_image_through_image_file_endpoint(self):
        """GET /api/image-file supports remote series cleanly."""
        headers, body, status = self.simulate_get("/api/image-file?series=remote:mock:sololeveling&chapter=mock-ch-1&file=1.jpg")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(detect_image_format(body), "png")

    def test_remote_cover_image_stream(self):
        """GET /api/cover?series=remote:mock:sololeveling streams remote cover."""
        headers, body, status = self.simulate_get("/api/cover?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Content-Type: image/png", headers)
        self.assertEqual(detect_image_format(body), "png")

    def test_remote_background_image_stream(self):
        """GET /api/background?series=remote:mock:sololeveling streams remote backdrop."""
        headers, body, status = self.simulate_get("/api/background?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Content-Type: image/png", headers)
        self.assertEqual(detect_image_format(body), "png")

    def test_remote_reader_data_initial_structure(self):
        """GET /api/reader-data?series=remote:mock:sololeveling returns reader metadata."""
        headers, body, status = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "remote:mock:sololeveling")
        self.assertEqual(data["title"], "Solo Leveling")
        self.assertEqual(data["author"], "Chugong")
        self.assertTrue(data["has_cover"])
        self.assertTrue(data["has_background"])
        self.assertEqual(data["reader"]["style"], "spaced")
        self.assertEqual(data["progress"], {})
        self.assertEqual(data["bookmarks"], [])


# ===========================================================================
# 3. Local Reading Independence & Regression Prevention
# ===========================================================================

class TestLocalReadingIndependence(BaseReaderIntegrationTestCase):
    """Demonstrate local reading functions completely independently without regressions."""

    def test_local_series_listing_unaffected(self):
        """Local library discovery lists only local folder series."""
        headers, body, status = self.simulate_get("/api/series")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series_count"], 1)
        self.assertEqual(data["series"][0]["name"], "OnePiece")

    def test_local_chapter_listing_unaffected(self):
        """Local chapter listing reads from filesystem without invoking remote providers."""
        headers, body, status = self.simulate_get("/api/chapters?series=OnePiece")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "OnePiece")
        self.assertEqual(data["chapter_count"], 2)
        self.assertEqual([c["name"] for c in data["chapters"]], ["Chapter 1", "Chapter 2"])

    def test_local_images_listing_and_streaming_unaffected(self):
        """Local chapter images list and stream directly from disk."""
        headers, body, status = self.simulate_get("/api/images?series=OnePiece&chapter=Chapter%201")
        self.assertEqual(status, HTTPStatus.OK)

        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["image_count"], 2)
        self.assertEqual(data["images"][0]["filename"], "1.jpg")

        # Stream image
        img_headers, img_body, img_status = self.simulate_get("/api/image-file?series=OnePiece&chapter=Chapter%201&file=1.jpg")
        self.assertEqual(img_status, HTTPStatus.OK)
        self.assertEqual(img_body, b"\xff\xd8\xff\xe0" + b"\x00" * 32)

    def test_local_reading_works_when_registry_is_empty(self):
        """Clearing all remote providers does not affect local reading."""
        self.registry.clear()
        self.assertEqual(len(self.registry), 0)

        headers, body, status = self.simulate_get("/api/chapters?series=OnePiece")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["chapter_count"], 2)

    def test_local_progress_and_bookmarks_isolated_from_remote(self):
        """Local progress persists to .reader/reader_data.json without touching remote state."""
        # Save local progress
        self.simulate_post("/api/progress", {"series": "OnePiece", "chapter": "Chapter 1", "image": "2.jpg"})
        self.simulate_post("/api/bookmark", {"series": "OnePiece", "chapter": "Chapter 1", "bookmarked": True})

        # Save remote progress
        self.simulate_post("/api/progress", {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "image": "1.jpg"})
        self.simulate_post("/api/bookmark", {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "bookmarked": True})

        # Check local reader data
        _, local_body, _ = self.simulate_get("/api/reader-data?series=OnePiece")
        local_data = json.loads(local_body.decode("utf-8"))
        self.assertEqual(local_data["progress"]["Chapter 1"], "2.jpg")
        self.assertIn("Chapter 1", local_data["bookmarks"])
        self.assertNotIn("mock-ch-1", local_data["progress"])

        # Verify on-disk file
        local_reader_file = self.lib_path / "OnePiece" / ".reader" / "reader_data.json"
        self.assertTrue(local_reader_file.is_file())


# ===========================================================================
# 4. Error Handling & Graceful Failure Tests
# ===========================================================================

class TestGracefulErrorHandling(BaseReaderIntegrationTestCase):
    """Demonstrate network, provider, and malformed responses fail gracefully with proper status codes."""

    def test_nonexistent_remote_series_returns_404(self):
        """Requesting an unknown remote series returns 404."""
        headers, body, status = self.simulate_get("/api/chapters?series=remote:mock:unknown_series")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_nonexistent_remote_chapter_returns_404(self):
        """Requesting an unknown remote chapter returns 404."""
        headers, body, status = self.simulate_get("/api/images?series=remote:mock:sololeveling&chapter=unknown_ch")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_unregistered_provider_returns_404(self):
        """Requesting a series from an unregistered provider returns 404."""
        headers, body, status = self.simulate_get("/api/chapters?series=remote:unregistered_p:123")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_simulated_provider_failure_returns_502(self):
        """A provider raising an exception returns 502 Bad Gateway without crashing the server."""
        failing_provider = MockProvider(simulate_error=True)
        self.registry.register(failing_provider, overwrite=True)

        headers, body, status = self.simulate_get("/api/chapters?series=remote:mock:sololeveling")
        self.assertEqual(status, HTTPStatus.BAD_GATEWAY)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

        # Images also fail gracefully
        _, img_body, img_status = self.simulate_get("/api/images?series=remote:mock:sololeveling&chapter=mock-ch-1")
        self.assertEqual(img_status, HTTPStatus.BAD_GATEWAY)

    def test_missing_query_parameters_returns_400(self):
        """Missing parameters return 400 Bad Request."""
        _, _, status1 = self.simulate_get("/api/remote/resolve")
        self.assertEqual(status1, HTTPStatus.BAD_REQUEST)

        _, _, status2 = self.simulate_get("/api/remote/image-proxy?url=https://mock.local/img.jpg")
        self.assertEqual(status2, HTTPStatus.BAD_REQUEST)

        _, _, status3 = self.simulate_get("/api/remote/images?series=remote:mock:sololeveling")
        self.assertEqual(status3, HTTPStatus.BAD_REQUEST)

    def test_malformed_provider_pages_response_handled_gracefully(self):
        """Provider returning invalid pages type (e.g. non-list) fails gracefully."""
        class MalformedProvider(BaseProvider):
            id = "malformed"
            name = "Malformed Provider"
            allowed_domains = ("mock.local",)

            def can_handle_url(self, url: str) -> bool: return True
            def get_series(self, url_or_id: str) -> RemoteSeries:
                return RemoteSeries(id="m1", title="M1", chapters=[RemoteChapter(id="c1", title="C1")])
            def get_chapter_pages(self, chapter_url_or_id: str) -> Any:
                return "not a list"  # Malformed

        self.registry.register(MalformedProvider())
        headers, body, status = self.simulate_get("/api/images?series=remote:malformed:m1&chapter=c1")
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)


# ===========================================================================
# 5. Cache Behavior Verification
# ===========================================================================

class TestCacheBehaviorIntegration(BaseReaderIntegrationTestCase):
    """Demonstrate chapter page cache hits, misses, and isolation through the integration layer."""

    def test_cache_hit_prevents_duplicate_provider_calls(self):
        """First call populates cache; subsequent call serves from cache without provider call."""
        call_count = 0
        original_get_pages = self.mock_provider.get_chapter_pages

        def counted_get_pages(chapter_id: str) -> List[RemotePage]:
            nonlocal call_count
            call_count += 1
            return original_get_pages(chapter_id)

        self.mock_provider.get_chapter_pages = counted_get_pages  # type: ignore

        # 1. First fetch (Cache Miss)
        self.assertIsNone(self.cache.get("remote:mock:sololeveling:mock-ch-1"))
        pages1 = self.remote_service.get_chapter_pages("remote:mock:sololeveling", "mock-ch-1")
        self.assertEqual(len(pages1), 3)
        self.assertEqual(call_count, 1)

        # 2. Second fetch (Cache Hit)
        cached_pages = self.cache.get("remote:mock:sololeveling:mock-ch-1")
        self.assertIsNotNone(cached_pages)
        pages2 = self.remote_service.get_chapter_pages("remote:mock:sololeveling", "mock-ch-1")
        self.assertEqual(len(pages2), 3)
        self.assertEqual(call_count, 1)  # Provider was NOT invoked again

    def test_cache_defensive_copying(self):
        """Mutating returned pages does not corrupt internal cache state."""
        pages = self.remote_service.get_chapter_pages("remote:mock:sololeveling", "mock-ch-1")
        pages[0].url = "https://mutated.com/hacked.jpg"

        fresh = self.remote_service.get_chapter_pages("remote:mock:sololeveling", "mock-ch-1")
        self.assertEqual(fresh[0].url, "https://cdn.mock.local/series1/ch1/1.jpg")

    def test_cache_invalidation(self):
        """Cache invalidation forces fresh fetch on next access."""
        self.remote_service.get_chapter_pages("remote:mock:sololeveling", "mock-ch-1")
        self.assertTrue(self.cache.invalidate("remote:mock:sololeveling:mock-ch-1"))
        self.assertIsNone(self.cache.get("remote:mock:sololeveling:mock-ch-1"))


# ===========================================================================
# 6. Security & SSRF Protection Integration Tests
# ===========================================================================

class TestSecurityAndSSRFProtection(BaseReaderIntegrationTestCase):
    """Demonstrate outbound security policies and SSRF defenses through the integration layer."""

    def test_disallowed_host_blocked_in_image_proxy(self):
        """Attempting to proxy an unauthorized host returns 400 Bad Request."""
        unauthorized_url = "https://evil.com/malicious.jpg"
        headers, body, status = self.simulate_get(f"/api/remote/image-proxy?url={unauthorized_url}&provider=mock")
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_non_https_scheme_blocked(self):
        """HTTP, file, and javascript schemes are rejected with 400."""
        for bad_url in [
            "http://mock.local/series1/ch1/1.jpg",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ]:
            _, body, status = self.simulate_get(f"/api/remote/image-proxy?url={bad_url}&provider=mock")
            self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_private_and_loopback_ip_targets_blocked(self):
        """Outbound requests targeting private networks, loopback, or metadata services are blocked."""
        for blocked_ip_url in [
            "https://127.0.0.1/admin",
            "https://10.0.0.1/secret",
            "https://192.168.1.1/router",
            "https://169.254.169.254/latest/meta-data",
        ]:
            _, body, status = self.simulate_get(f"/api/remote/image-proxy?url={blocked_ip_url}&provider=mock")
            self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_user_credentials_in_url_blocked(self):
        """URLs embedding user credentials (user:pass@host) are rejected."""
        cred_url = "https://admin:password@cdn.mock.local/1.jpg"
        _, body, status = self.simulate_get(f"/api/remote/image-proxy?url={cred_url}&provider=mock")
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_cannot_bypass_allowlist_via_resolve_endpoint(self):
        """Arbitrary URLs outside registered provider domains are rejected by /api/remote/resolve."""
        _, body, status = self.simulate_get("/api/remote/resolve?url=https://attacker-domain.com/series/1")
        self.assertEqual(status, HTTPStatus.NOT_FOUND)


# ===========================================================================
# 7. Progress, Bookmarks, and Reading Modes Integration Tests
# ===========================================================================

class TestRemoteProgressBookmarksAndReadingModes(BaseReaderIntegrationTestCase):
    """Demonstrate reading progress, bookmarks, and style persistence for remote series."""

    def test_remote_progress_persistence(self):
        """Saving reading progress persists across requests and is reflected in reader-data."""
        # 1. Update progress
        post_headers, post_body, post_status = self.simulate_post(
            "/api/progress",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "image": "2.jpg"}
        )
        self.assertEqual(post_status, HTTPStatus.OK)
        post_data = json.loads(post_body.decode("utf-8"))
        self.assertTrue(post_data["success"])
        self.assertEqual(post_data["progress"]["mock-ch-1"], "2.jpg")

        # 2. Fetch reader-data
        _, get_body, get_status = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        self.assertEqual(get_status, HTTPStatus.OK)
        get_data = json.loads(get_body.decode("utf-8"))
        self.assertEqual(get_data["progress"]["mock-ch-1"], "2.jpg")

    def test_remote_bookmark_toggle(self):
        """Bookmarking a remote chapter toggles bookmark state and persists."""
        # 1. Add bookmark
        _, b1_body, b1_status = self.simulate_post(
            "/api/bookmark",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "bookmarked": True}
        )
        self.assertEqual(b1_status, HTTPStatus.OK)
        data1 = json.loads(b1_body.decode("utf-8"))
        self.assertTrue(data1["bookmarked"])
        self.assertIn("mock-ch-1", data1["bookmarks"])

        # 2. Remove bookmark
        _, b2_body, b2_status = self.simulate_post(
            "/api/bookmark",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "bookmarked": False}
        )
        self.assertEqual(b2_status, HTTPStatus.OK)
        data2 = json.loads(b2_body.decode("utf-8"))
        self.assertFalse(data2["bookmarked"])
        self.assertNotIn("mock-ch-1", data2["bookmarks"])

    def test_remote_reading_style_preference(self):
        """Updating reading style to 'seamless' or 'spaced' persists for remote series."""
        # 1. Update to seamless
        _, s1_body, s1_status = self.simulate_post(
            "/api/style",
            {"series": "remote:mock:sololeveling", "style": "seamless"}
        )
        self.assertEqual(s1_status, HTTPStatus.OK)
        self.assertEqual(json.loads(s1_body.decode("utf-8"))["style"], "seamless")

        # 2. Verify via reader-data
        _, get_body, _ = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        self.assertEqual(json.loads(get_body.decode("utf-8"))["reader"]["style"], "seamless")

        # 3. Invalid style rejected with 400
        _, _, err_status = self.simulate_post(
            "/api/style",
            {"series": "remote:mock:sololeveling", "style": "invalid_mode"}
        )
        self.assertEqual(err_status, HTTPStatus.BAD_REQUEST)

    def test_dedicated_remote_endpoints_for_state(self):
        """Dedicated /api/remote/progress, /api/remote/bookmark, and /api/remote/style work identically."""
        # Progress
        _, p_body, p_status = self.simulate_post(
            "/api/remote/progress",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-2", "image": "1.jpg"}
        )
        self.assertEqual(p_status, HTTPStatus.OK)
        self.assertEqual(json.loads(p_body.decode("utf-8"))["progress"]["mock-ch-2"], "1.jpg")

        # Bookmark
        _, b_body, b_status = self.simulate_post(
            "/api/remote/bookmark",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-2", "bookmarked": True}
        )
        self.assertEqual(b_status, HTTPStatus.OK)
        self.assertIn("mock-ch-2", json.loads(b_body.decode("utf-8"))["bookmarks"])

        # Style
        _, s_body, s_status = self.simulate_post(
            "/api/remote/style",
            {"series": "remote:mock:sololeveling", "style": "spaced"}
        )
        self.assertEqual(s_status, HTTPStatus.OK)
        self.assertEqual(json.loads(s_body.decode("utf-8"))["reader"]["style"], "spaced")

    def test_cache_collision_prevention_across_series(self):
        """Chapters in different series with identical chapter IDs never collide in cache."""
        mock_p = MockProvider()
        svc = RemoteReaderService(registry=ProviderRegistry(), cache=ChapterPageCache())
        svc.registry.register(mock_p, overwrite=True)

        current_target = ["a"]

        def dynamic_get_pages(ch_id):
            return [RemotePage(index=1, url=f"https://cdn.mock.local/{current_target[0]}/1.jpg")]

        mock_p.get_chapter_pages = dynamic_get_pages  # type: ignore

        # 1. Fetch for Series A
        current_target[0] = "a"
        pages_a = svc.get_chapter_pages("remote:mock:series_a", "ch1")
        self.assertEqual(pages_a[0].url, "https://cdn.mock.local/a/1.jpg")

        # 2. Fetch for Series B with same chapter ID 'ch1'
        current_target[0] = "b"
        pages_b = svc.get_chapter_pages("remote:mock:series_b", "ch1")
        self.assertEqual(pages_b[0].url, "https://cdn.mock.local/b/1.jpg")

        # 3. Verify both entries exist independently in cache
        cached_a = svc.cache.get("remote:mock:series_a:ch1")
        cached_b = svc.cache.get("remote:mock:series_b:ch1")
        self.assertIsNotNone(cached_a)
        self.assertIsNotNone(cached_b)
        self.assertEqual(cached_a[0].url, "https://cdn.mock.local/a/1.jpg")
        self.assertEqual(cached_b[0].url, "https://cdn.mock.local/b/1.jpg")

    def test_stream_page_image_rejects_non_image_payload(self):
        """Proxy strictly enforces binary image magic bytes, rejecting text/HTML payloads."""
        mock_p = MockProvider(
            images_data={
                "https://cdn.mock.local/fake_image.jpg": b"<html><body>Not an image</body></html>"
            }
        )
        svc = RemoteReaderService(registry=ProviderRegistry())
        svc.registry.register(mock_p, overwrite=True)

        with self.assertRaises(ValueError):
            svc.stream_page_image("mock", "https://cdn.mock.local/fake_image.jpg")

    def test_parse_series_identifier_validates_urls_and_empty_id(self):
        """URL series identifiers enforce security policies; empty series IDs are rejected."""
        svc = RemoteReaderService()

        # Empty series ID
        with self.assertRaises(ValueError):
            svc.parse_series_identifier("remote:mock:")

        # Insecure HTTP scheme
        with self.assertRaises(InvalidSchemeError):
            svc.parse_series_identifier("http://mock.local/series/sololeveling")

        # Credentials in URL
        with self.assertRaises(SSRFSecurityError):
            svc.parse_series_identifier("https://admin:pass@mock.local/series/sololeveling")

    def test_remote_cover_and_background_upload_rejected(self):
        """POST /api/cover and POST /api/background reject remote series with 400."""
        # Cover upload
        _, c_body, c_status = self.simulate_post(
            "/api/cover?series=remote:mock:sololeveling",
            {"series": "remote:mock:sololeveling", "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="}
        )
        self.assertEqual(c_status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Cover upload is not supported", json.loads(c_body.decode("utf-8"))["error"])

        # Background modification
        _, bg_body, bg_status = self.simulate_post(
            "/api/background?series=remote:mock:sololeveling&action=remove",
            {}
        )
        self.assertEqual(bg_status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Background modification is not supported", json.loads(bg_body.decode("utf-8"))["error"])

    def test_unified_reader_data_post_endpoint_handles_remote(self):
        """POST /api/reader-data handles progress, bookmark, and style for remote series, and rejects metadata editing."""
        # 1. Progress
        _, p_body, p_status = self.simulate_post(
            "/api/reader-data",
            {"series": "remote:mock:sololeveling", "action": "progress", "chapter": "mock-ch-1", "image": "2.jpg"}
        )
        self.assertEqual(p_status, HTTPStatus.OK)
        self.assertEqual(json.loads(p_body.decode("utf-8"))["progress"]["mock-ch-1"], "2.jpg")

        # 2. Bookmark
        _, b_body, b_status = self.simulate_post(
            "/api/reader-data",
            {"series": "remote:mock:sololeveling", "action": "bookmark", "chapter": "mock-ch-1", "bookmarked": True}
        )
        self.assertEqual(b_status, HTTPStatus.OK)
        self.assertIn("mock-ch-1", json.loads(b_body.decode("utf-8"))["bookmarks"])

        # 3. Style
        _, s_body, s_status = self.simulate_post(
            "/api/reader-data",
            {"series": "remote:mock:sololeveling", "action": "style", "style": "seamless"}
        )
        self.assertEqual(s_status, HTTPStatus.OK)
        self.assertEqual(json.loads(s_body.decode("utf-8"))["reader"]["style"], "seamless")

        # 4. Metadata editing rejected
        _, m_body, m_status = self.simulate_post(
            "/api/reader-data",
            {"series": "remote:mock:sololeveling", "action": "metadata", "author": "New Author"}
        )
        self.assertEqual(m_status, HTTPStatus.BAD_REQUEST)
        self.assertIn("Metadata editing is not supported", json.loads(m_body.decode("utf-8"))["error"])

    def test_remote_image_file_missing_and_traversal(self):
        """GET /api/image-file returns 404 for nonexistent remote pages and traversal."""
        # Nonexistent page
        _, _, not_found = self.simulate_get(
            "/api/image-file?series=remote:mock:sololeveling&chapter=mock-ch-1&file=nonexistent.jpg"
        )
        self.assertEqual(not_found, HTTPStatus.NOT_FOUND)

        # Path traversal
        _, _, traversal_status = self.simulate_get(
            "/api/image-file?series=remote:mock:sololeveling&chapter=mock-ch-1&file=../../etc/passwd"
        )
        self.assertEqual(traversal_status, HTTPStatus.NOT_FOUND)

    def test_remote_chapter_completion_and_progress_isolation(self):
        """POST /api/remote/complete sets completed and unread states for remote series while preserving reading position."""
        # 1. Set progress on remote chapter
        _, p_body, p_status = self.simulate_post(
            "/api/progress",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "image": "2.jpg"}
        )
        self.assertEqual(p_status, HTTPStatus.OK)
        self.assertEqual(json.loads(p_body.decode("utf-8"))["progress"]["mock-ch-1"], "2.jpg")

        # 2. Mark remote chapter as completed
        _, c_body, c_status = self.simulate_post(
            "/api/remote/complete",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "completed": True}
        )
        self.assertEqual(c_status, HTTPStatus.OK)
        c_res = json.loads(c_body.decode("utf-8"))
        self.assertTrue(c_res["success"])
        self.assertIn("mock-ch-1", c_res["completed_chapters"])
        self.assertNotIn("mock-ch-1", c_res["unread_chapters"])

        # 3. Verify reading position is intact
        _, r_body, r_status = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        self.assertEqual(r_status, HTTPStatus.OK)
        r_data = json.loads(r_body.decode("utf-8"))
        self.assertEqual(r_data["progress"]["mock-ch-1"], "2.jpg")
        self.assertIn("mock-ch-1", r_data["completed"])

        # 4. Mark remote chapter as unread
        _, u_body, u_status = self.simulate_post(
            "/api/remote/complete",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-1", "completed": False}
        )
        self.assertEqual(u_status, HTTPStatus.OK)
        u_res = json.loads(u_body.decode("utf-8"))
        self.assertTrue(u_res["success"])
        self.assertNotIn("mock-ch-1", u_res["completed_chapters"])
        self.assertIn("mock-ch-1", u_res["unread_chapters"])

        # 5. Position is still intact and chapter is in unread
        _, r2_body, _ = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        r2_data = json.loads(r2_body.decode("utf-8"))
        self.assertEqual(r2_data["progress"]["mock-ch-1"], "2.jpg")
        self.assertNotIn("mock-ch-1", r2_data.get("completed", []))
        self.assertIn("mock-ch-1", r2_data["unread"])

        # 6. Reject invalid requests
        _, _, bad1 = self.simulate_post("/api/remote/complete", {"chapter": "mock-ch-1", "completed": True})
        self.assertEqual(bad1, HTTPStatus.BAD_REQUEST)

        _, _, bad2 = self.simulate_post("/api/remote/complete", {"series": "not-remote", "chapter": "ch-1", "completed": True})
        self.assertEqual(bad2, HTTPStatus.BAD_REQUEST)

    def test_remote_last_read_tracking_and_persistence(self):
        """Updating progress on remote series updates and persists last_read across reloads."""
        # 1. Update progress
        _, p_body, p_status = self.simulate_post(
            "/api/progress",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-2", "image": "3.jpg"}
        )
        self.assertEqual(p_status, HTTPStatus.OK)
        p_res = json.loads(p_body.decode("utf-8"))
        self.assertEqual(p_res.get("last_read"), "mock-ch-2")

        # 2. Verify reader-data returns last_read
        _, r_body, r_status = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        self.assertEqual(r_status, HTTPStatus.OK)
        r_res = json.loads(r_body.decode("utf-8"))
        self.assertEqual(r_res.get("last_read"), "mock-ch-2")

        # 3. Completing chapter preserves last_read
        self.simulate_post(
            "/api/remote/complete",
            {"series": "remote:mock:sololeveling", "chapter": "mock-ch-2", "completed": True}
        )
        _, r2_body, _ = self.simulate_get("/api/reader-data?series=remote:mock:sololeveling")
        r2_res = json.loads(r2_body.decode("utf-8"))
        self.assertEqual(r2_res.get("last_read"), "mock-ch-2")


if __name__ == "__main__":
    unittest.main()

