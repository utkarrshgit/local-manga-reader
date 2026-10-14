"""
test_nhentai_provider.py - Deterministic unit and integration tests for nhentai provider.

Covers:
1. Gallery URL validation, canonical identifier resolution, and invalid URL rejection.
2. Metadata extraction (English/Japanese/pretty titles, alternate title, artists, tags, cover image, links).
3. Page URL extraction, sequential ordering (1..N), extension mapping, and media ID mapping.
4. Multiple format resilience (JSON API response, embedded window._gallery, and HTML DOM fallback).
5. Missing or malformed metadata graceful handling.
6. Minimal domain allowlist enforcement, invalid image hosts, and SSRF rejection.
7. Non-image payload rejection and network/HTTP errors (404, 403, 503).
8. RemoteReaderService integration (caching, chapter listing, image proxy, cover, and background).
9. Reading progress, bookmarking, and reading style persistence for nhentai galleries.
10. Regression protection for WeebCentral, Mock provider, and local manga reading.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import RemoteChapter, RemotePage, RemoteSeries
from providers.cache import ChapterPageCache
from providers.mock import MockProvider
from providers.nhentai import (
    IMAGE_TYPE_MAP,
    NhentaiProvider,
    parse_html_tree,
)
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
from server import MangaLibrary, MangaRequestHandler


# ---------------------------------------------------------------------------
# Deterministic Test Fixtures
# ---------------------------------------------------------------------------

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb" + b"\x00" * 32

FIXTURE_GALLERY_DICT: Dict[str, Any] = {
    "id": 177013,
    "media_id": "995830",
    "title": {
        "english": "[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English]",
        "japanese": "[藤本タツキ] 変身 (チェンソープロジェクト) [英訳]",
        "pretty": "Metamorphosis",
    },
    "images": {
        "pages": [
            {"t": "j", "w": 1280, "h": 1810},
            {"t": "p", "w": 1280, "h": 1810},
            {"t": "g", "w": 1280, "h": 1810},
            {"t": "w", "w": 1280, "h": 1810},
        ],
        "cover": {"t": "j", "w": 350, "h": 495},
        "thumbnail": {"t": "j", "w": 250, "h": 353},
    },
    "scanlator": "TestScan",
    "upload_date": 1475712100,
    "tags": [
        {"id": 101, "type": "artist", "name": "tatsuki fujimoto", "url": "/artist/tatsuki-fujimoto/", "count": 12},
        {"id": 102, "type": "group", "name": "fujimoto circle", "url": "/group/fujimoto-circle/", "count": 5},
        {"id": 201, "type": "parody", "name": "original", "url": "/parody/original/", "count": 500},
        {"id": 301, "type": "character", "name": "makima", "url": "/character/makima/", "count": 30},
        {"id": 401, "type": "tag", "name": "drama", "url": "/tag/drama/", "count": 1200},
        {"id": 402, "type": "tag", "name": "sole female", "url": "/tag/sole-female/", "count": 8000},
        {"id": 501, "type": "language", "name": "english", "url": "/language/english/", "count": 90000},
        {"id": 601, "type": "category", "name": "manga", "url": "/category/manga/", "count": 45000},
    ],
    "num_pages": 4,
    "num_favorites": 15000,
}

FIXTURE_API_V2_DICT: Dict[str, Any] = {
    "id": 686216,
    "media_id": "4226233",
    "title": {
        "english": "[Pinochika] Boshi Ecchi Gouhouka｜Legalization Of Mother-Son Sex [English]",
        "japanese": "母子えっち合法化",
        "pretty": "Boshi Ecchi Gouhouka｜Legalization Of Mother-Son Sex",
    },
    "cover": {
        "path": "galleries/4226233/cover.webp.webp",
        "width": 350,
        "height": 262,
    },
    "thumbnail": {
        "path": "galleries/4226233/thumb.webp.webp",
        "width": 250,
        "height": 187,
    },
    "scanlator": "",
    "upload_date": 1791489290,
    "tags": [
        {"id": 101, "type": "artist", "name": "pinochika", "url": "/artist/pinochika/", "count": 15},
        {"id": 401, "type": "tag", "name": "sole female", "url": "/tag/sole-female/", "count": 200000},
        {"id": 501, "type": "language", "name": "english", "url": "/language/english/", "count": 90000},
        {"id": 601, "type": "category", "name": "doujinshi", "url": "/category/doujinshi/", "count": 500000},
    ],
    "num_pages": 2,
    "num_favorites": 3456,
    "pages": [
        {
            "number": 1,
            "path": "galleries/4226233/1.webp",
            "width": 1120,
            "height": 840,
            "thumbnail": "galleries/4226233/1t.webp",
        },
        {
            "number": 2,
            "path": "galleries/4226233/2.webp",
            "width": 1280,
            "height": 1807,
            "thumbnail": "galleries/4226233/2t.webp.webp",
        },
    ],
}

FIXTURE_EMBEDDED_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <title>[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English] » nhentai: hentai doujinshi and manga</title>
    <meta property="og:title" content="[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English] » nhentai">
    <meta property="og:image" content="https://t.nhentai.net/galleries/995830/cover.jpg">
</head>
<body>
    <div id="content">
        <div id="cover">
            <a href="/g/177013/1/">
                <img src="https://t.nhentai.net/galleries/995830/cover.jpg" width="350" height="495" alt="Cover">
            </a>
        </div>
        <div id="info">
            <h1 class="title">[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English]</h1>
            <h2 class="title">[藤本タツキ] 変身 (チェンソープロジェクト) [英訳]</h2>
        </div>
    </div>
    <script>
        window._gallery = JSON.parse({json.dumps(json.dumps(FIXTURE_GALLERY_DICT))});
    </script>
</body>
</html>"""

FIXTURE_STATIC_DOM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Chainsaw Maiden | nhentai</title>
    <meta property="og:title" content="Chainsaw Maiden » nhentai">
    <meta property="og:image" content="https://t.nhentai.net/galleries/888999/cover.jpg">
</head>
<body>
    <div id="content">
        <div id="cover">
            <a href="/g/12345/1/">
                <img src="https://t.nhentai.net/galleries/888999/cover.jpg" alt="Cover">
            </a>
        </div>
        <div id="info">
            <h1>Chainsaw Maiden</h1>
            <h2>チェンソー乙女</h2>
            <section id="tags">
                <div class="tag-container field-name">
                    <span class="name">Artists:</span>
                    <span class="tags">
                        <a href="/artist/denji/" class="tag"><span class="name">denji</span><span class="count">10</span></a>
                    </span>
                </div>
                <div class="tag-container field-name">
                    <span class="name">Tags:</span>
                    <span class="tags">
                        <a href="/tag/action/" class="tag"><span class="name">action</span><span class="count">50</span></a>
                        <a href="/tag/comedy/" class="tag"><span class="name">comedy</span><span class="count">25</span></a>
                    </span>
                </div>
                <div class="tag-container field-name">
                    <span class="name">Languages:</span>
                    <span class="tags">
                        <a href="/language/english/" class="tag"><span class="name">english</span><span class="count">100</span></a>
                    </span>
                </div>
            </section>
        </div>
        <div id="thumbnail-container">
            <div class="thumb"><a href="/g/12345/1/"><img data-src="https://t1.nhentai.net/galleries/888999/1t.jpg" alt="Page 1"></a></div>
            <div class="thumb"><a href="/g/12345/2/"><img data-src="https://t1.nhentai.net/galleries/888999/2t.png" alt="Page 2"></a></div>
        </div>
    </div>
</body>
</html>"""


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


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestNhentaiProviderURLResolution(unittest.TestCase):
    """Test URL parsing, identification, and rejection."""

    def setUp(self) -> None:
        self.provider = NhentaiProvider()

    def test_can_handle_url_valid_formats(self) -> None:
        valid_urls = [
            "https://nhentai.net/g/177013/",
            "https://nhentai.net/g/177013",
            "https://nhentai.net/g/177013/1/",
            "https://nhentai.net/g/177013/25",
            "https://nhentai.net/api/gallery/177013",
            "https://nhentai.net/api/v2/galleries/686216",
            "remote:nhentai:177013",
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(self.provider.can_handle_url(url))

    def test_can_handle_url_invalid_formats(self) -> None:
        invalid_urls = [
            "http://nhentai.net/g/177013/",  # Insecure HTTP
            "https://evil-nhentai.net/g/177013/",  # Disallowed host
            "https://nhentai.net.evil.com/g/177013/",  # Suffix trick
            "https://weebcentral.com/series/01J76XY8CM99",  # WeebCentral URL
            "https://nhentai.net/search/?q=test",  # Search page
            "https://nhentai.net/g/",  # Missing ID
            "https://nhentai.net/g/abc/",  # Non-numeric ID
            "remote:nhentai:",  # Empty canonical ID
            "remote:nhentai:abc",  # Non-numeric canonical ID
            "remote:weebcentral:01J76XY8CM99",
            "",
            None,
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(self.provider.can_handle_url(url))  # type: ignore

    def test_extract_gallery_id(self) -> None:
        self.assertEqual(self.provider._extract_gallery_id("177013"), "177013")
        self.assertEqual(self.provider._extract_gallery_id("remote:nhentai:177013"), "177013")
        self.assertEqual(self.provider._extract_gallery_id("https://nhentai.net/g/177013/"), "177013")
        self.assertEqual(self.provider._extract_gallery_id("https://nhentai.net/g/177013"), "177013")
        self.assertEqual(self.provider._extract_gallery_id("https://nhentai.net/g/177013/5/"), "177013")
        self.assertEqual(self.provider._extract_gallery_id("https://nhentai.net/api/gallery/177013"), "177013")
        self.assertEqual(self.provider._extract_gallery_id("https://nhentai.net/api/v2/galleries/686216"), "686216")

    def test_extract_gallery_id_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.provider._extract_gallery_id("")
        with self.assertRaises(ValueError):
            self.provider._extract_gallery_id("remote:nhentai:")
        with self.assertRaises(ValueError):
            self.provider._extract_gallery_id("remote:nhentai:notanumber")
        with self.assertRaises(ValueError):
            self.provider._extract_gallery_id("https://nhentai.net/other/123")


class TestNhentaiProviderMetadataExtraction(unittest.TestCase):
    """Test extracting titles, alternate titles, authors, tags, and pages."""

    def setUp(self) -> None:
        self.mock_client = MagicMock(spec=SecureHttpClient)
        self.provider = NhentaiProvider(client=self.mock_client)

    def test_metadata_extraction_from_json_api(self) -> None:
        url = "https://nhentai.net/g/177013/"
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(FIXTURE_GALLERY_DICT).encode("utf-8"),
            url=url,
        )

        series = self.provider.get_series("177013")
        self.assertEqual(series.id, "177013")
        self.assertEqual(
            series.title,
            "[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English]",
        )
        self.assertEqual(series.author, "tatsuki fujimoto")
        self.assertIsNone(series.description)  # Non-fabricated description
        self.assertEqual(
            series.cover_url,
            "https://t.nhentai.net/galleries/995830/cover.jpg",
        )
        self.assertIsNone(series.backdrop_url)
        self.assertEqual(series.url, "https://nhentai.net/g/177013/")

        # Verify metadata dictionary
        self.assertEqual(series.metadata["source"], "nhentai")
        self.assertEqual(series.metadata["gallery_id"], "177013")
        self.assertEqual(series.metadata["media_id"], "995830")
        self.assertEqual(
            series.metadata["alternate_title"],
            "[藤本タツキ] 変身 (チェンソープロジェクト) [英訳]",
        )
        self.assertIn("tatsuki fujimoto", series.metadata["artists"])
        self.assertIn("fujimoto circle", series.metadata["groups"])
        self.assertIn("drama", series.metadata["tags"])
        self.assertIn("sole female", series.metadata["tags"])
        self.assertIn("makima", series.metadata["characters"])
        self.assertIn("original", series.metadata["parodies"])
        self.assertIn("english", series.metadata["languages"])
        self.assertIn("manga", series.metadata["categories"])
        self.assertEqual(series.metadata["num_pages"], 4)
        self.assertEqual(series.metadata["links"]["nhentai"], "https://nhentai.net/g/177013/")

        # Verify exactly one readable chapter item
        self.assertEqual(len(series.chapters), 1)
        ch = series.chapters[0]
        self.assertEqual(ch.id, "177013")
        self.assertEqual(ch.title, "Metamorphosis")  # Pretty title
        self.assertIsNone(ch.chapter_number)  # No fake chapter number
        self.assertEqual(len(ch.pages), 4)

    def test_metadata_extraction_from_api_v2(self) -> None:
        url = "https://nhentai.net/api/v2/galleries/686216"
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(FIXTURE_API_V2_DICT).encode("utf-8"),
            url=url,
        )

        series = self.provider.get_series("686216")
        self.assertEqual(series.id, "686216")
        self.assertEqual(
            series.title,
            "[Pinochika] Boshi Ecchi Gouhouka｜Legalization Of Mother-Son Sex [English]",
        )
        self.assertEqual(series.author, "pinochika")
        self.assertEqual(
            series.cover_url,
            "https://t.nhentai.net/galleries/4226233/cover.webp.webp",
        )
        self.assertEqual(len(series.chapters), 1)
        self.assertEqual(len(series.chapters[0].pages), 2)
        self.assertEqual(
            series.chapters[0].pages[0].url,
            "https://i.nhentai.net/galleries/4226233/1.webp",
        )
        self.assertEqual(
            series.chapters[0].pages[1].url,
            "https://i.nhentai.net/galleries/4226233/2.webp",
        )
        self.assertEqual(series.metadata["media_id"], "4226233")
        self.assertEqual(series.metadata["num_pages"], 2)

    def test_api_v2_fallback_to_html_on_error(self) -> None:
        def mock_get(url: str, headers: Optional[Dict[str, str]] = None) -> SecureResponse:
            if "api/v2/galleries" in url:
                return SecureResponse(
                    status_code=500,
                    headers={},
                    body=b"Internal Server Error",
                    url=url,
                )
            if "/g/177013" in url:
                return SecureResponse(
                    status_code=200,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    body=FIXTURE_EMBEDDED_HTML.encode("utf-8"),
                    url=url,
                )
            return SecureResponse(status_code=404, headers={}, body=b"Not Found", url=url)

        self.mock_client.get.side_effect = mock_get
        series = self.provider.get_series("177013")
        self.assertEqual(series.id, "177013")
        self.assertEqual(
            series.title,
            "[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English]",
        )
        self.assertEqual(len(series.chapters[0].pages), 4)

    def test_api_v2_and_html_both_blocked_403(self) -> None:
        def mock_get(url: str, headers: Optional[Dict[str, str]] = None) -> SecureResponse:
            return SecureResponse(
                status_code=403,
                headers={"cf-mitigated": "challenge"},
                body=b"Just a moment...",
                url=url,
            )

        self.mock_client.get.side_effect = mock_get
        with self.assertRaises(RuntimeError) as ctx:
            self.provider.get_series("686216")
        self.assertIn("blocked or rate-limited", str(ctx.exception))
        self.assertIn("403", str(ctx.exception))

    def test_metadata_extraction_from_embedded_html(self) -> None:
        url = "https://nhentai.net/g/177013/"
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=FIXTURE_EMBEDDED_HTML.encode("utf-8"),
            url=url,
        )

        series = self.provider.get_series("177013")
        self.assertEqual(series.id, "177013")
        self.assertEqual(
            series.title,
            "[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English]",
        )
        self.assertEqual(series.author, "tatsuki fujimoto")
        self.assertEqual(len(series.chapters), 1)
        self.assertEqual(len(series.chapters[0].pages), 4)

    def test_metadata_extraction_from_static_html_dom_fallback(self) -> None:
        url = "https://nhentai.net/g/12345/"
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "text/html"},
            body=FIXTURE_STATIC_DOM_HTML.encode("utf-8"),
            url=url,
        )

        series = self.provider.get_series("12345")
        self.assertEqual(series.id, "12345")
        self.assertEqual(series.title, "Chainsaw Maiden")
        self.assertEqual(series.metadata["alternate_title"], "チェンソー乙女")
        self.assertEqual(series.author, "denji")
        self.assertIn("action", series.metadata["tags"])
        self.assertIn("comedy", series.metadata["tags"])
        self.assertIn("english", series.metadata["languages"])
        self.assertEqual(
            series.cover_url,
            "https://t.nhentai.net/galleries/888999/cover.jpg",
        )
        self.assertEqual(len(series.chapters), 1)
        self.assertEqual(len(series.chapters[0].pages), 2)
        self.assertEqual(
            series.chapters[0].pages[0].url,
            "https://i.nhentai.net/galleries/888999/1.jpg",
        )
        self.assertEqual(
            series.chapters[0].pages[1].url,
            "https://i.nhentai.net/galleries/888999/2.png",
        )

    def test_missing_and_malformed_metadata_handling(self) -> None:
        minimal_dict: Dict[str, Any] = {
            "id": 99999,
            "media_id": "99999",
            "images": {
                "pages": [{"t": "j"}],
            },
        }
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(minimal_dict).encode("utf-8"),
            url="https://nhentai.net/g/99999/",
        )

        series = self.provider.get_series("99999")
        self.assertEqual(series.id, "99999")
        self.assertEqual(series.title, "Gallery 99999")
        self.assertIsNone(series.author)
        self.assertIsNone(series.cover_url)
        self.assertEqual(len(series.chapters[0].pages), 1)

    def test_malformed_fields_resilience(self) -> None:
        malformed_dict: Dict[str, Any] = {
            "id": 11111,
            "media_id": None,
            "title": {"english": 12345, "japanese": True, "pretty": None},
            "images": {"cover": None, "pages": None},
            "tags": "not_a_list",
            "upload_date": None,
        }
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(malformed_dict).encode("utf-8"),
            url="https://nhentai.net/g/11111/",
        )

        series = self.provider.get_series("11111")
        self.assertEqual(series.id, "11111")
        self.assertEqual(series.title, "12345")
        self.assertEqual(series.metadata["alternate_title"], "True")
        self.assertIsNone(series.author)
        self.assertIsNone(series.cover_url)
        self.assertEqual(len(series.chapters[0].pages), 0)

    def test_empty_gallery_pages(self) -> None:
        empty_dict: Dict[str, Any] = {
            "id": 22222,
            "title": {"pretty": "Empty Book"},
            "images": {"pages": []},
        }
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(empty_dict).encode("utf-8"),
            url="https://nhentai.net/g/22222/",
        )

        pages = self.provider.get_chapter_pages("22222")
        self.assertEqual(pages, [])


class TestNhentaiProviderPagesAndOrdering(unittest.TestCase):
    """Test ordered page-image extraction and format mapping."""

    def setUp(self) -> None:
        self.mock_client = MagicMock(spec=SecureHttpClient)
        self.provider = NhentaiProvider(client=self.mock_client)

        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=json.dumps(FIXTURE_GALLERY_DICT).encode("utf-8"),
            url="https://nhentai.net/g/177013/",
        )

    def test_page_url_extraction_and_ordering(self) -> None:
        pages = self.provider.get_chapter_pages("177013")
        self.assertEqual(len(pages), 4)

        expected_extensions = ["jpg", "png", "gif", "webp"]
        for idx, (page, ext) in enumerate(zip(pages, expected_extensions), start=1):
            self.assertEqual(page.index, idx)
            expected_url = f"https://i.nhentai.net/galleries/995830/{idx}.{ext}"
            self.assertEqual(page.url, expected_url)
            self.assertEqual(page.headers.get("Referer"), "https://nhentai.net/g/177013/")

    def test_get_chapter_pages_with_canonical_id_and_url(self) -> None:
        pages_from_id = self.provider.get_chapter_pages("177013")
        pages_from_url = self.provider.get_chapter_pages("https://nhentai.net/g/177013/")
        pages_from_canonical = self.provider.get_chapter_pages("remote:nhentai:177013")

        self.assertEqual(len(pages_from_id), len(pages_from_url))
        self.assertEqual(len(pages_from_id), len(pages_from_canonical))
        for p1, p2, p3 in zip(pages_from_id, pages_from_url, pages_from_canonical):
            self.assertEqual(p1.url, p2.url)
            self.assertEqual(p1.url, p3.url)


class TestNhentaiSecurityAndAllowlist(unittest.TestCase):
    """Test domain allowlist enforcement, invalid host rejection, and SSRF defenses."""

    def setUp(self) -> None:
        self.mock_client = MagicMock(spec=SecureHttpClient)
        self.provider = NhentaiProvider(client=self.mock_client)

    def test_minimal_allowlist_matches_only_approved_nhentai_hosts(self) -> None:
        policy = self.provider.policy
        allowed = [
            "nhentai.net",
            "i.nhentai.net",
            "i1.nhentai.net",
            "i2.nhentai.net",
            "i3.nhentai.net",
            "i4.nhentai.net",
            "i5.nhentai.net",
            "i7.nhentai.net",
            "t.nhentai.net",
            "t1.nhentai.net",
            "t2.nhentai.net",
            "t3.nhentai.net",
            "t4.nhentai.net",
            "t5.nhentai.net",
            "t7.nhentai.net",
        ]
        for host in allowed:
            with self.subTest(host=host):
                self.assertTrue(policy.match_hostname(host))

        disallowed = [
            "evil-nhentai.net",
            "nhentai.net.evil.com",
            "random.nhentai.net",  # Unapproved subdomain
            "api.other.com",
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
            "weebcentral.com",
        ]
        for host in disallowed:
            with self.subTest(host=host):
                self.assertFalse(policy.match_hostname(host))

    def test_get_image_rejects_unapproved_host_or_insecure_scheme(self) -> None:
        with self.assertRaises(DisallowedHostError):
            self.provider.get_image("https://evil.com/fake.jpg")

        with self.assertRaises(InvalidSchemeError):
            self.provider.get_image("http://i.nhentai.net/galleries/995830/1.jpg")

    def test_http_error_responses_raise_informative_errors(self) -> None:
        # 404 Not Found
        self.mock_client.get.return_value = SecureResponse(
            status_code=404, headers={}, body=b"Not Found", url="https://nhentai.net/g/999999/"
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.provider.get_series("999999")
        self.assertIn("404", str(ctx.exception))

        # 403 Forbidden / Cloudflare challenge
        self.mock_client.get.return_value = SecureResponse(
            status_code=403, headers={}, body=b"Access Denied", url="https://nhentai.net/g/177013/"
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.provider.get_series("177013")
        self.assertIn("blocked", str(ctx.exception).lower())

        # 503 Service Unavailable / anti-bot
        self.mock_client.get.return_value = SecureResponse(
            status_code=503, headers={}, body=b"Checking your browser", url="https://nhentai.net/g/177013/"
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.provider.get_series("177013")
        self.assertIn("blocked", str(ctx.exception).lower())

    def test_redirect_outside_allowlist_is_rejected(self) -> None:
        # A redirect location targeting an external host must be rejected
        policy = self.provider.policy
        with self.assertRaises(DisallowedHostError):
            policy.validate_url("https://evil.com/phishing/177013")

        with self.assertRaises(InvalidSchemeError):
            policy.validate_url("http://nhentai.net/g/177013/")

    def test_html_with_disallowed_image_domain_filtered(self) -> None:
        malicious_html = """<!DOCTYPE html>
        <html>
        <body>
            <div id="content">
                <div id="info"><h1>Safe Title</h1></div>
                <div id="thumbnail-container">
                    <div class="thumb"><img data-src="https://evil-tracker.com/galleries/123/1t.jpg"></div>
                    <div class="thumb"><img data-src="https://t.nhentai.net/galleries/123/2t.jpg"></div>
                </div>
            </div>
        </body>
        </html>"""
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "text/html"},
            body=malicious_html.encode("utf-8"),
            url="https://nhentai.net/g/123/",
        )
        series = self.provider.get_series("123")
        pages = series.chapters[0].pages
        # Only the legitimate approved host page is kept, evil-tracker is dropped
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].url, "https://i.nhentai.net/galleries/123/2.jpg")


class TestNhentaiServiceIntegration(unittest.TestCase):
    """Test RemoteReaderService integration, caching, image proxy, and isolated persistence."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.mock_client = MagicMock(spec=SecureHttpClient)

        def mock_get(url: str, headers: Optional[Dict[str, str]] = None) -> SecureResponse:
            if "nhentai.net/g/177013" in url or "nhentai.net/api/gallery/177013" in url:
                return SecureResponse(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps(FIXTURE_GALLERY_DICT).encode("utf-8"),
                    url=url,
                )
            if "i.nhentai.net" in url or "t.nhentai.net" in url:
                return SecureResponse(
                    status_code=200,
                    headers={"Content-Type": "image/jpeg"},
                    body=TINY_JPEG,
                    url=url,
                )
            return SecureResponse(status_code=404, headers={}, body=b"Not Found", url=url)

        self.mock_client.get.side_effect = mock_get

        self.provider = NhentaiProvider(client=self.mock_client)
        self.registry = ProviderRegistry()
        self.registry.register(self.provider)
        self.registry.register(MockProvider())

        self.cache = ChapterPageCache()
        self.service = RemoteReaderService(
            registry=self.registry,
            cache=self.cache,
            state_dir=self.state_dir,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_service_resolves_nhentai_series_to_canonical_id(self) -> None:
        res = self.service.resolve_series("https://nhentai.net/g/177013/")
        self.assertEqual(res["provider"], "nhentai")
        self.assertEqual(res["series_id"], "177013")
        self.assertEqual(res["series_identifier"], "remote:nhentai:177013")
        self.assertEqual(
            res["series"]["title"],
            "[Tatsuki Fujimoto] Metamorphosis (Chainsaw Project) [English]",
        )

    def test_service_get_chapters_returns_one_readable_item(self) -> None:
        data = self.service.get_chapters("remote:nhentai:177013")
        self.assertEqual(data["series"], "remote:nhentai:177013")
        self.assertEqual(data["chapter_count"], 1)
        self.assertEqual(len(data["chapters"]), 1)
        ch = data["chapters"][0]
        self.assertEqual(ch["name"], "177013")
        self.assertEqual(ch["title"], "Metamorphosis")
        self.assertEqual(ch["image_count"], 4)
        self.assertIsNone(ch["chapter_number"])

    def test_service_get_chapter_pages_and_caching(self) -> None:
        # First call fetches from provider
        pages1 = self.service.get_chapter_pages("remote:nhentai:177013", "177013")
        self.assertEqual(len(pages1), 4)
        call_count_before = self.mock_client.get.call_count

        # Second call returns from cache without fetching provider
        pages2 = self.service.get_chapter_pages("remote:nhentai:177013", "177013")
        self.assertEqual(len(pages2), 4)
        self.assertEqual(self.mock_client.get.call_count, call_count_before)

    def test_service_chapter_images_for_reader(self) -> None:
        data = self.service.get_chapter_images_for_reader("remote:nhentai:177013", "177013")
        self.assertEqual(data["series"], "remote:nhentai:177013")
        self.assertEqual(data["chapter"], "177013")
        self.assertEqual(data["image_count"], 4)
        self.assertEqual(data["images"][0]["filename"], "1.jpg")
        self.assertIn("/api/remote/image-proxy?", data["images"][0]["url"])
        self.assertIn("provider=nhentai", data["images"][0]["url"])

    def test_service_stream_page_image_and_cover(self) -> None:
        # Stream valid page image
        img_bytes, mime = self.service.stream_page_image(
            "nhentai", "https://i.nhentai.net/galleries/995830/1.jpg"
        )
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(img_bytes, TINY_JPEG)

        # Stream cover
        cover = self.service.get_cover("remote:nhentai:177013")
        self.assertIsNotNone(cover)
        self.assertEqual(cover[1], "image/jpeg")

        # Background falls back to cover
        bg = self.service.get_background("remote:nhentai:177013")
        self.assertIsNotNone(bg)
        self.assertEqual(bg[1], "image/jpeg")

    def test_stream_page_image_rejects_non_image_payload(self) -> None:
        # Mock client returns HTML/text error payload
        self.mock_client.get.side_effect = None
        self.mock_client.get.return_value = SecureResponse(
            status_code=200,
            headers={"Content-Type": "text/html"},
            body=b"<html>Cloudflare Error</html>",
            url="https://i.nhentai.net/galleries/995830/1.jpg",
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.stream_page_image("nhentai", "https://i.nhentai.net/galleries/995830/1.jpg")
        self.assertIn("unsupported image payload", str(ctx.exception).lower())

    def test_isolated_progress_bookmarks_and_style_persistence(self) -> None:
        series_id = "remote:nhentai:177013"

        # Update progress
        data = self.service.update_progress(series_id, "177013", "3.gif")
        self.assertEqual(data["progress"]["177013"], "3.gif")

        # Toggle bookmark
        data = self.service.toggle_bookmark(series_id, "177013", True)
        self.assertIn("177013", data["bookmarks"])

        # Update reader style
        data = self.service.update_reader_style(series_id, "seamless")
        self.assertEqual(data["reader"]["style"], "seamless")

        # Verify persisted state file on disk
        state_file = self.state_dir / "remote_reader_data.json"
        self.assertTrue(state_file.is_file())
        saved_json = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertIn(series_id, saved_json)
        self.assertEqual(saved_json[series_id]["progress"]["177013"], "3.gif")
        self.assertIn("177013", saved_json[series_id]["bookmarks"])
        self.assertEqual(saved_json[series_id]["reader"]["style"], "seamless")


class TestNhentaiHTTPHandlerIntegration(unittest.TestCase):
    """Test full HTTP server dispatching for nhentai remote reader endpoints."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir) / "manga"
        self.lib_path.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.library = MangaLibrary(str(self.lib_path))

        self.mock_client = MagicMock(spec=SecureHttpClient)

        def mock_get(url: str, headers: Optional[Dict[str, str]] = None) -> SecureResponse:
            if "nhentai.net/g/177013" in url or "nhentai.net/api/gallery/177013" in url:
                return SecureResponse(
                    status_code=200,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps(FIXTURE_GALLERY_DICT).encode("utf-8"),
                    url=url,
                )
            if "i.nhentai.net" in url or "t.nhentai.net" in url:
                return SecureResponse(
                    status_code=200,
                    headers={"Content-Type": "image/jpeg"},
                    body=TINY_JPEG,
                    url=url,
                )
            return SecureResponse(status_code=404, headers={}, body=b"Not Found", url=url)

        self.mock_client.get.side_effect = mock_get

        self.nhentai_provider = NhentaiProvider(client=self.mock_client)
        self.registry = ProviderRegistry()
        self.registry.register(self.nhentai_provider)
        self.registry.register(MockProvider())

        self.cache = ChapterPageCache()
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

    def test_http_resolve_nhentai_gallery(self) -> None:
        headers, body, status = self.simulate_get("/api/remote/resolve?url=https://nhentai.net/g/177013/")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["provider"], "nhentai")
        self.assertEqual(data["series_id"], "177013")
        self.assertEqual(data["series_identifier"], "remote:nhentai:177013")

    def test_http_get_chapters_nhentai(self) -> None:
        headers, body, status = self.simulate_get("/api/chapters?series=remote:nhentai:177013")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "remote:nhentai:177013")
        self.assertEqual(data["chapter_count"], 1)
        self.assertEqual(data["chapters"][0]["name"], "177013")

    def test_http_get_images_nhentai(self) -> None:
        headers, body, status = self.simulate_get("/api/images?series=remote:nhentai:177013&chapter=177013")
        self.assertEqual(status, HTTPStatus.OK)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["image_count"], 4)
        self.assertEqual(data["images"][0]["filename"], "1.jpg")

    def test_http_stream_image_proxy_nhentai(self) -> None:
        url = "https://i.nhentai.net/galleries/995830/1.jpg"
        headers, body, status = self.simulate_get(f"/api/remote/image-proxy?url={url}&provider=nhentai")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("image/jpeg", headers.lower())
        self.assertEqual(body, TINY_JPEG)

    def test_http_rejects_ssrf_image_proxy_for_nhentai(self) -> None:
        # Disallowed host
        _, _, status1 = self.simulate_get("/api/remote/image-proxy?url=https://evil.com/fake.png&provider=nhentai")
        self.assertEqual(status1, HTTPStatus.BAD_REQUEST)

        # Insecure HTTP
        _, _, status2 = self.simulate_get("/api/remote/image-proxy?url=http://i.nhentai.net/plain.jpg&provider=nhentai")
        self.assertEqual(status2, HTTPStatus.BAD_REQUEST)

        # Loopback IP
        _, _, status3 = self.simulate_get("/api/remote/image-proxy?url=https://127.0.0.1/admin.png&provider=nhentai")
        self.assertEqual(status3, HTTPStatus.BAD_REQUEST)

    def test_http_progress_bookmark_and_style_nhentai(self) -> None:
        series_id = "remote:nhentai:177013"

        # Progress
        _, body, status = self.simulate_post(
            "/api/progress", {"series": series_id, "chapter": "177013", "image": "2.png"}
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(json.loads(body.decode("utf-8"))["progress"]["177013"], "2.png")

        # Bookmark
        _, body, status = self.simulate_post(
            "/api/bookmark", {"series": series_id, "chapter": "177013", "bookmarked": True}
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("177013", json.loads(body.decode("utf-8"))["bookmarks"])

        # Style
        _, body, status = self.simulate_post(
            "/api/style", {"series": series_id, "style": "seamless"}
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(json.loads(body.decode("utf-8"))["reader"]["style"], "seamless")


class TestNhentaiRegressions(unittest.TestCase):
    """Regression tests verifying WeebCentral and local manga library remain unaffected."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir) / "manga"
        self.lib_path.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Setup local manga library
        local_series = self.lib_path / "OnePiece"
        local_series.mkdir(parents=True, exist_ok=True)
        ch1 = local_series / "Chapter 1"
        ch1.mkdir(parents=True, exist_ok=True)
        (ch1 / "01.jpg").write_bytes(TINY_JPEG)
        (local_series / "cover.jpg").write_bytes(TINY_JPEG)

        self.library = MangaLibrary(str(self.lib_path))
        self.registry = ProviderRegistry()
        self.registry.register(WeebCentralProvider())
        self.registry.register(NhentaiProvider())
        self.registry.register(MockProvider())

        self.cache = ChapterPageCache()
        self.service = RemoteReaderService(
            registry=self.registry,
            cache=self.cache,
            state_dir=self.state_dir,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_provider_regression_intact(self) -> None:
        series = self.service.resolve_series("remote:mock:sololeveling")
        self.assertEqual(series["provider"], "mock")
        self.assertEqual(series["series_id"], "sololeveling")

    def test_weebcentral_provider_regression_intact(self) -> None:
        weeb = self.registry.get("weebcentral")
        self.assertIsNotNone(weeb)
        self.assertTrue(weeb.can_handle_url("https://weebcentral.com/series/01J76XY8CM99/chainsaw-man"))
        self.assertFalse(weeb.can_handle_url("https://nhentai.net/g/177013/"))

    def test_local_manga_library_unaffected(self) -> None:
        series_list = self.library.list_series()
        self.assertEqual(len(series_list), 1)
        self.assertEqual(series_list[0]["name"], "OnePiece")
        self.assertEqual(series_list[0]["chapter_count"], 1)

        chapters = self.library.list_chapters("OnePiece")
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0]["name"], "Chapter 1")

        images = self.library.list_images("OnePiece", "Chapter 1")
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0], "01.jpg")


if __name__ == "__main__":
    unittest.main()
