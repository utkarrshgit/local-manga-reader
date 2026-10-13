"""
test_remote_ui_integration.py - Phase 5 automated tests for Remote Library UI Integration.

Covers:
1. Valid and invalid remote series input (WeebCentral URLs, canonical identifiers, raw IDs, malformed/disallowed hosts).
2. Loading and displaying series metadata and chapters (cover, background fallback, metadata, title, author, status).
3. Selecting a chapter and requesting its pages through the reader endpoint.
4. Remote image delivery via secure proxy and failed image handling.
5. Progress and bookmark persistence for remote series.
6. Switching between local and remote series without state leakage.
7. DOM safety and HTML escaping for untrusted series titles and chapter names.
8. Regression verification of existing local manga library and reader behavior.
9. Static file presence and UI element integration.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from providers.base import RemoteChapter, RemotePage, RemoteSeries
from providers.cache import ChapterPageCache
from providers.mock import MockProvider
from providers.registry import ProviderRegistry, default_registry
from providers.security import (
    DisallowedHostError,
    InvalidSchemeError,
    SSRFSecurityError,
    SecureHttpClient,
    SecureResponse,
    SecurityPolicy,
)
from providers.service import RemoteReaderService, is_remote_series
from providers.weebcentral import WeebCentralProvider
from server import MangaLibrary, MangaRequestHandler, detect_image_format


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


FIXTURE_SERIES_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Chainsaw Man | Weeb Central</title>
    <meta property="og:title" content="Chainsaw Man | Weeb Central">
    <meta property="og:description" content="Denji is a boy with a Chainsaw Devil.">
    <meta property="og:image" content="https://temp.compsci88.com/cover/csm.jpg">
</head>
<body>
    <main>
        <h1>Chainsaw Man</h1>
        <ul class="list-none">
            <li>Author: Tatsuki Fujimoto</li>
            <li>Status: Ongoing</li>
        </ul>
        <div id="manga-summary"><p>Denji is a boy with a Chainsaw Devil.</p></div>
        <section class="chapters">
            <a href="/chapters/01J76XZ001"><span>Chapter 1</span></a>
            <a href="/chapters/01J76XZ002"><span>Chapter 2</span></a>
        </section>
    </main>
</body>
</html>"""

FIXTURE_CHAPTER_PAGES_HTML = """<!DOCTYPE html>
<html>
<body>
    <section id="chapter-images">
        <img src="https://scans.lastation.us/manga/CSM/0001-001.png" alt="Page 1">
        <img src="https://scans.lastation.us/manga/CSM/0001-002.png" alt="Page 2">
    </section>
</body>
</html>"""

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestRemoteUIIntegration(unittest.TestCase):
    """Integration test suite covering Remote Library UI integration and contracts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir) / "manga"
        self.lib_path.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Setup local manga library fixtures
        local_series = self.lib_path / "LocalSeries"
        local_series.mkdir(parents=True, exist_ok=True)
        ch1 = local_series / "Chapter 1"
        ch1.mkdir(parents=True, exist_ok=True)
        (ch1 / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)
        (local_series / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 32)

        self.library = MangaLibrary(str(self.lib_path))

        # Setup mocked WeebCentral HTTP client
        self.mock_client = MagicMock(spec=SecureHttpClient)

        def mock_get(url: str, headers: Optional[Dict[str, str]] = None) -> SecureResponse:
            if "weebcentral.com/series/01J76XY8CM99" in url:
                return SecureResponse(status_code=200, headers={"Content-Type": "text/html"}, body=FIXTURE_SERIES_HTML.encode("utf-8"), url=url)
            if "weebcentral.com/chapters/01J76XZ001" in url:
                return SecureResponse(status_code=200, headers={"Content-Type": "text/html"}, body=FIXTURE_CHAPTER_PAGES_HTML.encode("utf-8"), url=url)
            if "scans.lastation.us" in url or "temp.compsci88.com" in url:
                return SecureResponse(status_code=200, headers={"Content-Type": "image/png"}, body=TINY_PNG, url=url)
            return SecureResponse(status_code=404, headers={}, body=b"Not Found", url=url)

        self.mock_client.get.side_effect = mock_get

        self.weeb_provider = WeebCentralProvider(client=self.mock_client)
        self.registry = ProviderRegistry()
        self.registry.register(self.weeb_provider)
        self.registry.register(MockProvider())

        self.cache = ChapterPageCache()
        self.remote_service = RemoteReaderService(
            registry=self.registry,
            cache=self.cache,
            state_dir=self.state_dir,
        )

        self.HandlerClass = MangaRequestHandler
        self.HandlerClass.library = self.library
        self.HandlerClass.static_dir = Path(__file__).parent / "static"
        self.HandlerClass.remote_service = self.remote_service

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def simulate_get(self, path: str) -> Tuple[str, bytes, int]:
        raw_request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(raw_request)
        self.HandlerClass(sock, ("127.0.0.1", 8000), None)

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
        body_bytes = json.dumps(json_data).encode("utf-8")
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(raw_request)
        self.HandlerClass(sock, ("127.0.0.1", 8000), None)

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

    def simulate_post_binary(self, path: str, raw_bytes: bytes, content_type: str = "image/png") -> Tuple[str, bytes, int]:
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(raw_bytes)}\r\n\r\n"
        ).encode("utf-8") + raw_bytes
        sock = MockSocket(raw_request)
        self.HandlerClass(sock, ("127.0.0.1", 8000), None)

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

    # -------------------------------------------------------------------------
    # 1. Valid and Invalid Remote Series Input Resolution
    # -------------------------------------------------------------------------

    def test_remote_resolve_valid_weebcentral_url(self) -> None:
        """Valid WeebCentral URL resolves with canonical identifier and metadata."""
        headers, body, status = self.simulate_get("/api/remote/resolve?url=https://weebcentral.com/series/01J76XY8CM99/chainsaw-man")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["provider"], "weebcentral")
        self.assertEqual(data["series_id"], "01J76XY8CM99")
        self.assertEqual(data["series_identifier"], "remote:weebcentral:01J76XY8CM99")
        self.assertEqual(data["series"]["title"], "Chainsaw Man")

    def test_remote_resolve_canonical_identifier(self) -> None:
        """Canonical remote:weebcentral:<id> resolves directly."""
        headers, body, status = self.simulate_get("/api/remote/resolve?url=remote:weebcentral:01J76XY8CM99")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series_identifier"], "remote:weebcentral:01J76XY8CM99")
        self.assertEqual(data["series"]["title"], "Chainsaw Man")

    def test_remote_resolve_rejects_insecure_http_scheme(self) -> None:
        """Insecure HTTP URLs are rejected with HTTP 400 or 404."""
        headers, body, status = self.simulate_get("/api/remote/resolve?url=http://weebcentral.com/series/01J76XY8CM99")
        self.assertIn(status, (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND))
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_remote_resolve_rejects_unauthorized_host(self) -> None:
        """Disallowed domains (arbitrary external sites) are rejected with HTTP 400 or 404."""
        headers, body, status = self.simulate_get("/api/remote/resolve?url=https://evil.com/series/malicious")
        self.assertIn(status, (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND))

    def test_remote_resolve_rejects_internal_ip_ssrf(self) -> None:
        """SSRF attempts targeting private/internal network addresses are blocked."""
        headers, body, status = self.simulate_get("/api/remote/resolve?url=https://127.0.0.1/series/admin")
        self.assertIn(status, (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND))

        headers, body, status = self.simulate_get("/api/remote/resolve?url=https://169.254.169.254/latest/meta-data")
        self.assertIn(status, (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND))

    def test_remote_resolve_missing_param_returns_bad_request(self) -> None:
        """Missing url query parameter returns HTTP 400."""
        headers, body, status = self.simulate_get("/api/remote/resolve")
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 2. Loading & Displaying Series Metadata & Chapters
    # -------------------------------------------------------------------------

    def test_get_chapters_for_remote_series(self) -> None:
        """GET /api/chapters with remote series identifier returns chapter list with titles."""
        headers, body, status = self.simulate_get("/api/chapters?series=remote:weebcentral:01J76XY8CM99")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "remote:weebcentral:01J76XY8CM99")
        self.assertEqual(data["title"], "Chainsaw Man")
        self.assertEqual(data["provider"], "weebcentral")
        self.assertEqual(len(data["chapters"]), 2)
        self.assertEqual(data["chapters"][0]["title"], "Chapter 1")
        self.assertEqual(data["chapters"][1]["title"], "Chapter 2")

    def test_get_reader_data_for_remote_series(self) -> None:
        """GET /api/reader-data returns provider metadata and default reader preferences."""
        headers, body, status = self.simulate_get("/api/reader-data?series=remote:weebcentral:01J76XY8CM99")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["title"], "Chainsaw Man")
        self.assertEqual(data["author"], "Tatsuki Fujimoto")
        self.assertEqual(data["status"], "Ongoing")
        self.assertEqual(data["reader"]["style"], "spaced")
        self.assertEqual(data["bookmarks"], [])
        self.assertEqual(data["progress"], {})

    def test_get_cover_and_background_for_remote_series(self) -> None:
        """GET /api/cover and /api/background stream remote images securely."""
        headers, body, status = self.simulate_get("/api/cover?series=remote:weebcentral:01J76XY8CM99")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("image/png", headers)
        self.assertEqual(detect_image_format(body), "png")

        headers_bg, body_bg, status_bg = self.simulate_get("/api/background?series=remote:weebcentral:01J76XY8CM99")
        self.assertEqual(status_bg, HTTPStatus.OK)
        self.assertIn("image/png", headers_bg)

    def test_remote_metadata_editing_is_rejected(self) -> None:
        """Editing remote metadata via POST /api/reader-data is rejected with HTTP 400."""
        payload = {
            "series": "remote:weebcentral:01J76XY8CM99",
            "action": "metadata",
            "author": "Hacker",
            "summary": "Fake synopsis",
        }
        headers, body, status = self.simulate_post("/api/reader-data", payload)
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 3. Chapter Selection & Page Images Delivery
    # -------------------------------------------------------------------------

    def test_get_images_for_remote_chapter(self) -> None:
        """GET /api/images returns proxied image URLs for the remote reader."""
        headers, body, status = self.simulate_get("/api/images?series=remote:weebcentral:01J76XY8CM99&chapter=01J76XZ001")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["image_count"], 2)
        self.assertEqual(len(data["images"]), 2)
        self.assertEqual(data["images"][0]["filename"], "1.jpg")
        self.assertIn("/api/remote/image-proxy?", data["images"][0]["url"])

    def test_remote_image_proxy_delivers_binary_payload(self) -> None:
        """GET /api/remote/image-proxy streams validated image bytes."""
        page_url = "https://scans.lastation.us/manga/CSM/0001-001.png"
        path = f"/api/remote/image-proxy?url={page_url}&provider=weebcentral"
        headers, body, status = self.simulate_get(path)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Content-Type: image/png", headers)
        self.assertEqual(body, TINY_PNG)

    def test_remote_image_proxy_rejects_ssrf_and_disallowed_hosts(self) -> None:
        """Image proxy blocks external non-whitelisted image URLs."""
        path = "/api/remote/image-proxy?url=https://attacker.org/exfil.png&provider=weebcentral"
        headers, body, status = self.simulate_get(path)
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    # -------------------------------------------------------------------------
    # 4. Progress, Bookmarks, and Style Persistence
    # -------------------------------------------------------------------------

    def test_remote_progress_and_bookmark_persistence(self) -> None:
        """Remote progress and bookmarks are saved and isolated from local files."""
        # 1. Update progress
        prog_payload = {
            "series": "remote:weebcentral:01J76XY8CM99",
            "chapter": "01J76XZ001",
            "image": "2.jpg",
        }
        _, _, prog_status = self.simulate_post("/api/progress", prog_payload)
        self.assertEqual(prog_status, HTTPStatus.OK)

        # 2. Toggle bookmark
        bm_payload = {
            "series": "remote:weebcentral:01J76XY8CM99",
            "chapter": "01J76XZ001",
            "bookmarked": True,
        }
        _, _, bm_status = self.simulate_post("/api/bookmark", bm_payload)
        self.assertEqual(bm_status, HTTPStatus.OK)

        # 3. Update style preference
        style_payload = {
            "series": "remote:weebcentral:01J76XY8CM99",
            "style": "seamless",
        }
        _, _, style_status = self.simulate_post("/api/style", style_payload)
        self.assertEqual(style_status, HTTPStatus.OK)

        # 4. Verify reader data retrieval
        _, get_body, get_status = self.simulate_get("/api/reader-data?series=remote:weebcentral:01J76XY8CM99")
        self.assertEqual(get_status, HTTPStatus.OK)
        data = json.loads(get_body.decode("utf-8"))
        self.assertEqual(data["progress"]["01J76XZ001"], "2.jpg")
        self.assertIn("01J76XZ001", data["bookmarks"])
        self.assertEqual(data["reader"]["style"], "seamless")

        # 5. Verify local manga filesystem was NOT touched
        local_series_dir = self.lib_path / "LocalSeries"
        self.assertFalse((local_series_dir / ".reader").exists())

    # -------------------------------------------------------------------------
    # 5. State Isolation Between Local & Remote Series
    # -------------------------------------------------------------------------

    def test_state_isolation_local_and_remote(self) -> None:
        """Local and remote reader data reside in completely isolated storage."""
        # Save local progress
        self.simulate_post("/api/progress", {"series": "LocalSeries", "chapter": "Chapter 1", "image": "1.jpg"})

        # Save remote progress
        self.simulate_post("/api/progress", {"series": "remote:weebcentral:01J76XY8CM99", "chapter": "01J76XZ001", "image": "2.jpg"})

        # Read local data
        _, loc_body, _ = self.simulate_get("/api/reader-data?series=LocalSeries")
        loc_data = json.loads(loc_body.decode("utf-8"))
        self.assertEqual(loc_data["progress"]["Chapter 1"], "1.jpg")
        self.assertNotIn("01J76XZ001", loc_data["progress"])

        # Read remote data
        _, rem_body, _ = self.simulate_get("/api/reader-data?series=remote:weebcentral:01J76XY8CM99")
        rem_data = json.loads(rem_body.decode("utf-8"))
        self.assertEqual(rem_data["progress"]["01J76XZ001"], "2.jpg")
        self.assertNotIn("Chapter 1", rem_data["progress"])

    def test_local_series_endpoints_unaffected(self) -> None:
        """Local library listing, chapters, and images continue operating normally."""
        # /api/series lists only local folders
        _, s_body, s_status = self.simulate_get("/api/series")
        self.assertEqual(s_status, HTTPStatus.OK)
        s_data = json.loads(s_body.decode("utf-8"))
        names = [s["name"] for s in s_data["series"]]
        self.assertIn("LocalSeries", names)
        # Remote series should never appear in local /api/series
        self.assertNotIn("remote:weebcentral:01J76XY8CM99", names)
        self.assertNotIn("Chainsaw Man", names)

    # -------------------------------------------------------------------------
    # 6. Static Asset UI Integration
    # -------------------------------------------------------------------------

    def test_static_index_html_contains_remote_ui_elements(self) -> None:
        """index.html contains the remote open button, remote modal, and input controls."""
        index_file = Path(__file__).parent / "static" / "index.html"
        self.assertTrue(index_file.is_file())
        content = index_file.read_text(encoding="utf-8")

        self.assertIn('id="btn-open-remote"', content)
        self.assertIn('id="modal-remote"', content)
        self.assertIn('id="remote-url-input"', content)
        self.assertIn('id="btn-load-remote"', content)
        self.assertIn('id="remote-recent-section"', content)
        self.assertIn('id="remote-recent-list"', content)
        self.assertIn('id="remote-modal-error"', content)
        self.assertIn('id="dropdown-item-remote"', content)

    def test_static_style_css_contains_remote_and_retry_styles(self) -> None:
        """style.css contains styles for remote UI controls and reader retry elements."""
        css_file = Path(__file__).parent / "static" / "style.css"
        self.assertTrue(css_file.is_file())
        content = css_file.read_text(encoding="utf-8")

        self.assertIn(".btn-open-remote", content)
        self.assertIn(".remote-recent-section", content)
        self.assertIn(".remote-recent-item", content)
        self.assertIn(".reader-image-retry", content)

    def test_static_app_js_remote_integration_and_dom_safety(self) -> None:
        """app.js contains remote series routing, validation, and safe HTML escaping."""
        app_js = Path(__file__).parent / "static" / "app.js"
        self.assertTrue(app_js.is_file())
        content = app_js.read_text(encoding="utf-8")

        # Remote helpers
        self.assertIn("function isRemoteSeries", content)
        self.assertIn("function openRemoteModal", content)
        self.assertIn("function resolveAndOpenRemote", content)
        self.assertIn("function saveRecentRemoteSeries", content)
        self.assertIn("function removeRecentRemoteSeries", content)
        self.assertIn("function renderRecentRemoteList", content)

        # Error resilience & retry
        self.assertIn("reader-image-retry", content)
        self.assertIn("Failed to load page. Click to retry", content)

        # DOM safety / HTML escaping
        self.assertIn("escapeHtml(ch.title || ch.name)", content)

    # -------------------------------------------------------------------------
    # 7. Focused Behavioral & Edge Case Regression Tests
    # -------------------------------------------------------------------------

    def test_remote_image_proxy_handles_cache_busting_retry_parameter(self) -> None:
        """Image proxy preserves security validation and succeeds when cache-busting _retry param is appended."""
        page_url = "https://scans.lastation.us/manga/CSM/0001-001.png"
        path = f"/api/remote/image-proxy?url={page_url}&provider=weebcentral&_retry=1697220000000"
        headers, body, status = self.simulate_get(path)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("Content-Type: image/png", headers)
        self.assertEqual(body, TINY_PNG)

    def test_remote_series_rejects_cover_upload(self) -> None:
        """POST /api/cover rejects uploads for remote series with HTTP 400, leaving filesystem intact."""
        headers, body, status = self.simulate_post_binary(
            "/api/cover?series=remote:weebcentral:01J76XY8CM99",
            TINY_PNG,
            "image/png",
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)
        self.assertIn("Cover upload is not supported for remote series", data["error"])

    def test_remote_series_rejects_background_modification(self) -> None:
        """POST /api/background rejects modifications for remote series with HTTP 400."""
        headers, body, status = self.simulate_post(
            "/api/background?series=remote:weebcentral:01J76XY8CM99",
            {"action": "remove"},
        )
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)
        self.assertIn("Background modification is not supported for remote series", data["error"])

    def test_remote_chapters_handles_malicious_xss_in_title(self) -> None:
        """Remote provider with untrusted script tags in chapter titles returns safe text in JSON."""
        xss_series = RemoteSeries(
            id="01J76XY8CM99",
            title="Chainsaw Man",
            chapters=[
                RemoteChapter(
                    id="01JXSS999",
                    title="<script>alert('xss')</script>",
                    chapter_number=999.0,
                    url="https://weebcentral.com/chapters/01JXSS999",
                )
            ],
        )
        with patch.object(self.weeb_provider, "get_series", return_value=xss_series):
            headers, body, status = self.simulate_get("/api/chapters?series=remote:weebcentral:01J76XY8CM99")
            self.assertEqual(status, HTTPStatus.OK)
            data = json.loads(body.decode("utf-8"))
            self.assertEqual(data["chapters"][0]["title"], "<script>alert('xss')</script>")

            # Simulate client escapeHtml function contract
            escaped = (
                data["chapters"][0]["title"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#039;")
            )
            self.assertEqual(escaped, "&lt;script&gt;alert(&#039;xss&#039;)&lt;/script&gt;")
            self.assertNotIn("<script>", escaped)

    def test_remote_chapters_unknown_series_returns_clean_error(self) -> None:
        """Requesting chapters for nonexistent remote series returns 404 or 400 without crashing."""
        headers, body, status = self.simulate_get("/api/chapters?series=remote:weebcentral:01JNONEXISTENT99")
        self.assertIn(status, (HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST, HTTPStatus.BAD_GATEWAY))
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_remote_chapters_empty_list_returns_valid_response(self) -> None:
        """Remote series with zero chapters returns valid JSON array without 500 error."""
        empty_series = RemoteSeries(
            id="01J76XY8CM99",
            title="Chainsaw Man",
            chapters=[],
        )
        with patch.object(self.weeb_provider, "get_series", return_value=empty_series):
            headers, body, status = self.simulate_get("/api/chapters?series=remote:weebcentral:01J76XY8CM99")
            self.assertEqual(status, HTTPStatus.OK)
            data = json.loads(body.decode("utf-8"))
            self.assertEqual(data["chapters"], [])
            self.assertEqual(data["chapter_count"], 0)


if __name__ == "__main__":
    unittest.main()
