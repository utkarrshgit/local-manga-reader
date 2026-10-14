"""
test_weebcentral_provider.py - Deterministic test suite for WeebCentral provider.

Tests:
1. URL resolution, can_handle_url, identifier extraction, and invalid URL rejection.
2. Series metadata extraction (title, cover, description, author, status).
3. Chapter extraction, identifiers, numbering, ordering, and HTMX lazy loading fragment.
4. Chapter page extraction and image URL resolution in correct reading order.
5. Missing or malformed HTML, empty series, unavailable chapters, and unexpected responses.
6. Redirect and host validation, SSRF rejection, and unsafe image URL filtering.
7. Image payload validation and network failures.
8. Provider registry and RemoteReaderService integration.
9. Reader data persistence (progress, bookmarks, reading style) for WeebCentral series.
10. Regression protection for the mock provider and local reader.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.base import RemoteChapter, RemotePage, RemoteSeries
from providers.cache import ChapterPageCache
from providers.mock import MockProvider
from providers.registry import ProviderRegistry, default_registry
from providers.security import (
    BlockedIPError,
    DisallowedHostError,
    InvalidSchemeError,
    SSRFSecurityError,
    SecureHttpClient,
    SecureResponse,
    SecurityPolicy,
)
from providers.service import RemoteReaderService
from providers.weebcentral import (
    MiniHTMLTreeParser,
    WeebCentralProvider,
    parse_html_tree,
)


# ---------------------------------------------------------------------------
# Deterministic HTML Fixtures (Simulating WeebCentral Public Structure)
# ---------------------------------------------------------------------------

FIXTURE_SERIES_MAIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Chainsaw Man | Weeb Central</title>
    <meta property="og:title" content="Chainsaw Man | Weeb Central">
    <meta property="og:description" content="Denji is a teenage boy living with a Chainsaw Devil named Pochita. Due to the debt his father left behind, he has been living a rock-bottom life while repaying his debt.">
    <meta property="og:image" content="https://temp.compsci88.com/cover/Chainsaw-Man.jpg">
</head>
<body>
    <main>
        <section id="series-info" class="flex flex-col md:flex-row gap-4 p-4">
            <div class="cover-wrapper">
                <img src="https://temp.compsci88.com/cover/Chainsaw-Man.jpg" alt="Chainsaw Man Cover" class="rounded shadow">
            </div>
            <div class="details-wrapper">
                <h1 class="text-2xl font-bold">Chainsaw Man</h1>
                <ul class="list-none space-y-1">
                    <li><span class="font-semibold">Author:</span> <span class="text-muted">Tatsuki Fujimoto</span></li>
                    <li><span class="font-semibold">Artist:</span> <span class="text-muted">Tatsuki Fujimoto</span></li>
                    <li><span class="font-semibold">Status:</span> <span class="text-muted">Ongoing</span></li>
                    <li><span class="font-semibold">Type:</span> <span class="text-muted">Manga</span></li>
                </ul>
                <div id="manga-summary" class="mt-4">
                    <p>Denji is a teenage boy living with a Chainsaw Devil named Pochita. Due to the debt his father left behind, he has been living a rock-bottom life while repaying his debt.</p>
                </div>
            </div>
        </section>

        <!-- HTMX Trigger for full chapter list fragment -->
        <section class="chapter-list-section mt-6">
            <button hx-get="/series/01J76XY8CM99/full-chapter-list" hx-target="#chapter-list-container" class="btn-load-all">
                Show All Chapters
            </button>
            <div id="chapter-list-container">
                <!-- Preview of chapters on main page -->
                <div class="chapter-item">
                    <a href="/chapters/01J76XZ002" class="flex justify-between p-2 hover:bg-neutral">
                        <span class="font-medium">Chapter 2 - The Dog & The Chainsaw</span>
                        <time datetime="2026-01-08">Jan 08, 2026</time>
                    </a>
                </div>
            </div>
        </section>
    </main>
</body>
</html>
"""

FIXTURE_FULL_CHAPTER_LIST_FRAGMENT = """<div class="flex flex-col divide-y divide-neutral-800">
    <div class="chapter-row">
        <a href="/chapters/01J76XZ001" class="flex justify-between items-center py-2 px-3">
            <span class="font-medium">Chapter 1 - Dog & Chainsaw</span>
            <time datetime="2026-01-01T00:00:00Z">Jan 01, 2026</time>
        </a>
    </div>
    <div class="chapter-row">
        <a href="/chapters/01J76XZ002" class="flex justify-between items-center py-2 px-3">
            <span class="font-medium">Chapter 2 - Arrival in Tokyo</span>
            <time datetime="2026-01-08T00:00:00Z">Jan 08, 2026</time>
        </a>
    </div>
    <div class="chapter-row">
        <a href="/chapters/01J76XZ002_5" class="flex justify-between items-center py-2 px-3">
            <span class="font-medium">Chapter 2.5 - Special Omake</span>
            <time datetime="2026-01-11T00:00:00Z">Jan 11, 2026</time>
        </a>
    </div>
    <div class="chapter-row">
        <a href="/chapters/01J76XZ003" class="flex justify-between items-center py-2 px-3">
            <span class="font-medium">Chapter 3 - Power's Rescue</span>
            <time datetime="2026-01-15T00:00:00Z">Jan 15, 2026</time>
        </a>
    </div>
</div>
"""

FIXTURE_CHAPTER_PAGES_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Chainsaw Man Chapter 1 | Weeb Central</title>
</head>
<body>
    <header>
        <img src="https://weebcentral.com/static/brand-logo.png" alt="Weeb Central Logo">
    </header>
    <main>
        <section id="chapter-images" class="flex flex-col items-center">
            <img src="https://scans.lastation.us/manga/Chainsaw-Man/0001-001.png" alt="Page 1" class="manga-page">
            <img src="https://scans.lastation.us/manga/Chainsaw-Man/0001-002.png" alt="Page 2" class="manga-page">
            <img data-src="https://scans.lastation.us/manga/Chainsaw-Man/0001-003.png" alt="Page 3" class="manga-page">
            <!-- Unsafe tracking image that must be ignored -->
            <img src="https://evil-analytics.com/track.gif" alt="Tracker">
        </section>
    </main>
</body>
</html>
"""

FIXTURE_EMPTY_SERIES_HTML = """<!DOCTYPE html>
<html>
<head><title>Empty Manga | Weeb Central</title></head>
<body>
    <main>
        <h1>Empty Manga</h1>
        <div id="manga-summary"><p>No description provided.</p></div>
    </main>
</body>
</html>
"""

FIXTURE_MALFORMED_HTML = """
<div class="broken-page"
    <h1 Chainsaw Man Without Closing Tag
    <img src="https://scans.lastation.us/broken.jpg"
    <a href="/chapters/bad_ch" Broken Chapter Link
    <script>alert('xss')</script>
"""

SAMPLE_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
    b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MockSecureHttpClient:
    """Mock HTTP client returning canned responses for WeebCentral endpoints."""

    def __init__(self, responses: Optional[Dict[str, SecureResponse]] = None) -> None:
        self.responses: Dict[str, SecureResponse] = dict(responses or {})
        self.requested_urls: List[str] = []

    def set_response(self, url: str, status_code: int, body: bytes, headers: Optional[Dict[str, str]] = None) -> None:
        self.responses[url] = SecureResponse(
            status_code=status_code,
            headers=headers or {"content-type": "text/html; charset=utf-8"},
            body=body,
            url=url,
        )

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> SecureResponse:
        self.requested_urls.append(url)
        if url in self.responses:
            return self.responses[url]
        # Return 404 by default
        return SecureResponse(
            status_code=404,
            headers={"content-type": "text/html"},
            body=b"<html><body>404 Not Found</body></html>",
            url=url,
        )


class TestWeebCentralProvider(unittest.TestCase):
    """Unit tests for WeebCentralProvider."""

    def setUp(self) -> None:
        self.mock_client = MockSecureHttpClient()

        # Seed standard WeebCentral endpoints
        series_url = "https://weebcentral.com/series/01J76XY8CM99"
        frag_url = "https://weebcentral.com/series/01J76XY8CM99/full-chapter-list"
        ch1_url = "https://weebcentral.com/chapters/01J76XZ001"

        self.mock_client.set_response(series_url, 200, FIXTURE_SERIES_MAIN_HTML.encode("utf-8"))
        self.mock_client.set_response(frag_url, 200, FIXTURE_FULL_CHAPTER_LIST_FRAGMENT.encode("utf-8"))
        self.mock_client.set_response(ch1_url, 200, FIXTURE_CHAPTER_PAGES_HTML.encode("utf-8"))

        # Seed page images
        for i in range(1, 4):
            img_url = f"https://scans.lastation.us/manga/Chainsaw-Man/0001-00{i}.png"
            self.mock_client.set_response(
                img_url,
                200,
                SAMPLE_PNG_BYTES,
                headers={"content-type": "image/png"},
            )

        cover_url = "https://temp.compsci88.com/cover/Chainsaw-Man.jpg"
        self.mock_client.set_response(
            cover_url,
            200,
            SAMPLE_PNG_BYTES,
            headers={"content-type": "image/jpeg"},
        )

        self.provider = WeebCentralProvider(client=self.mock_client)

    # -----------------------------------------------------------------------
    # 1. URL Recognition & Rejection
    # -----------------------------------------------------------------------

    def test_can_handle_url_valid_patterns(self):
        valid_urls = [
            "https://weebcentral.com/series/01J76XY8CM99",
            "https://weebcentral.com/series/01J76XY8CM99/chainsaw-man",
            "https://weebcentral.com/chapters/01J76XZ001",
            "remote:weebcentral:01J76XY8CM99",
        ]
        for url in valid_urls:
            self.assertTrue(self.provider.can_handle_url(url), f"Should handle: {url}")

    def test_can_handle_url_invalid_patterns(self):
        invalid_urls = [
            "http://weebcentral.com/series/01J76XY8CM99",  # insecure http
            "https://evil.com/series/01J76XY8CM99",        # unapproved host
            "https://weebcentral.com.evil.com/series/1",  # suffix spoofing
            "https://weebcentral.com/user/profile",       # non-series/chapter path
            "remote:mock:sololeveling",                   # other provider
            "",
            None,
        ]
        for url in invalid_urls:
            self.assertFalse(self.provider.can_handle_url(url), f"Should NOT handle: {url}")

    def test_extract_series_id(self):
        self.assertEqual(
            self.provider._extract_series_id("https://weebcentral.com/series/01J76XY8CM99"),
            "01J76XY8CM99",
        )
        self.assertEqual(
            self.provider._extract_series_id("https://weebcentral.com/series/01J76XY8CM99/chainsaw-man"),
            "01J76XY8CM99",
        )
        self.assertEqual(
            self.provider._extract_series_id("remote:weebcentral:01J76XY8CM99"),
            "01J76XY8CM99",
        )
        self.assertEqual(
            self.provider._extract_series_id("01J76XY8CM99"),
            "01J76XY8CM99",
        )

    def test_extract_series_id_invalid_raises(self):
        with self.assertRaises(ValueError):
            self.provider._extract_series_id("")
        with self.assertRaises(ValueError):
            self.provider._extract_series_id("remote:weebcentral:")
        with self.assertRaises(SSRFSecurityError):
            self.provider._extract_series_id("https://evil.com/series/123")
        with self.assertRaises(InvalidSchemeError):
            self.provider._extract_series_id("http://weebcentral.com/series/123")

    # -----------------------------------------------------------------------
    # 2. Series Metadata Extraction
    # -----------------------------------------------------------------------

    def test_get_series_metadata(self):
        series = self.provider.get_series("01J76XY8CM99")
        self.assertEqual(series.id, "01J76XY8CM99")
        self.assertEqual(series.title, "Chainsaw Man")
        self.assertEqual(series.author, "Tatsuki Fujimoto")
        self.assertEqual(series.status, "Ongoing")
        self.assertIn("Denji is a teenage boy", series.description or "")
        self.assertEqual(series.cover_url, "https://temp.compsci88.com/cover/Chainsaw-Man.jpg")
        self.assertEqual(series.url, "https://weebcentral.com/series/01J76XY8CM99")

    # -----------------------------------------------------------------------
    # 3. Chapter Extraction, Numbering, & HTMX Fragment
    # -----------------------------------------------------------------------

    def test_get_series_chapters_extraction_and_ordering(self):
        series = self.provider.get_series("01J76XY8CM99")
        chapters = series.chapters
        self.assertEqual(len(chapters), 4)

        # Check natural sorting and numbering
        ch_numbers = [c.chapter_number for c in chapters]
        self.assertEqual(ch_numbers, [1.0, 2.0, 2.5, 3.0])

        # Verify chapter attributes
        ch1 = chapters[0]
        self.assertEqual(ch1.id, "01J76XZ001")
        self.assertIn("Chapter 1", ch1.title)
        self.assertEqual(ch1.url, "https://weebcentral.com/chapters/01J76XZ001")
        self.assertIsNotNone(ch1.date)

        ch2_5 = chapters[2]
        self.assertEqual(ch2_5.id, "01J76XZ002_5")
        self.assertEqual(ch2_5.chapter_number, 2.5)

    def test_series_with_no_htmx_button_parses_main_page_chapters(self):
        """When no HTMX fragment exists, chapters on the main page are extracted directly."""
        html_no_htmx = """<!DOCTYPE html>
        <html><body>
            <h1>Direct Chapters Series</h1>
            <a href="/chapters/ch_10">Chapter 10</a>
            <a href="/chapters/ch_11">Chapter 11</a>
        </body></html>"""
        self.mock_client.set_response(
            "https://weebcentral.com/series/no_htmx",
            200,
            html_no_htmx.encode("utf-8"),
        )
        series = self.provider.get_series("no_htmx")
        self.assertEqual(len(series.chapters), 2)
        self.assertEqual(series.chapters[0].id, "ch_10")
        self.assertEqual(series.chapters[1].id, "ch_11")

    def test_chapter_ordering_with_decimals_duplicates_and_specials(self):
        """Verify sorting handles decimals (1.5), duplicates (Ch 2 Part 1/2), Prologue (0), and specials."""
        html_complex = """<!DOCTYPE html>
        <html><body>
            <h1>Complex Series</h1>
            <a href="/chapters/ch_prologue">Prologue</a>
            <a href="/chapters/ch_1">Chapter 1</a>
            <a href="/chapters/ch_1_5">Chapter 1.5 - Side Story</a>
            <a href="/chapters/ch_2_part1">Chapter 2 - Part 1</a>
            <a href="/chapters/ch_2_part2">Chapter 2 - Part 2</a>
            <a href="/chapters/ch_act1">Act. 3 - The Battle</a>
            <a href="/chapters/ch_scene4">Scene. 4 - The Climax</a>
            <a href="/chapters/ch_special">Special Omake (No Number)</a>
        </body></html>"""
        self.mock_client.set_response(
            "https://weebcentral.com/series/complex",
            200,
            html_complex.encode("utf-8"),
        )
        series = self.provider.get_series("complex")
        ordered_ids = [c.id for c in series.chapters]
        # Prologue (0.0) -> Ch 1 (1.0) -> Ch 1.5 (1.5) -> Ch 2 Part 1 (2.0) -> Ch 2 Part 2 (2.0) -> Act 3 (3.0) -> Scene 4 (4.0) -> Special (None/inf)
        expected_ids = [
            "ch_prologue",
            "ch_1",
            "ch_1_5",
            "ch_2_part1",
            "ch_2_part2",
            "ch_act1",
            "ch_scene4",
            "ch_special",
        ]
        self.assertEqual(ordered_ids, expected_ids)
        self.assertEqual(series.chapters[0].chapter_number, 0.0)
        self.assertEqual(series.chapters[2].chapter_number, 1.5)
        self.assertEqual(series.chapters[3].chapter_number, 2.0)
        self.assertEqual(series.chapters[4].chapter_number, 2.0)
        self.assertIsNone(series.chapters[7].chapter_number)

    def test_get_chapter_pages_dynamic_endpoint(self):
        """When reader page has empty chapter-images container, fetches /chapters/{id}/images fragment."""
        empty_reader_html = """<!DOCTYPE html>
        <html><body>
            <section id="chapter-images" class="min-h-screen"></section>
        </body></html>"""
        images_frag_html = """<div class="pages-wrapper">
            <img src="https://official.lowee.us/manga/Title/0001-001.png" alt="Page 1">
            <img src="https://official.lowee.us/manga/Title/0001-002.png" alt="Page 2">
        </div>"""
        self.mock_client.set_response("https://weebcentral.com/chapters/dynamic_ch", 200, empty_reader_html.encode("utf-8"))
        self.mock_client.set_response("https://weebcentral.com/chapters/dynamic_ch/images", 200, images_frag_html.encode("utf-8"))

        pages = self.provider.get_chapter_pages("dynamic_ch")
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0].url, "https://official.lowee.us/manga/Title/0001-001.png")
        self.assertEqual(pages[1].url, "https://official.lowee.us/manga/Title/0001-002.png")


    # -----------------------------------------------------------------------
    # 4. Chapter Pages & Reading Order
    # -----------------------------------------------------------------------

    def test_get_chapter_pages_reading_order(self):
        pages = self.provider.get_chapter_pages("01J76XZ001")
        self.assertEqual(len(pages), 3)

        # Verified sequential index (1-based)
        self.assertEqual([p.index for p in pages], [1, 2, 3])
        self.assertEqual(pages[0].url, "https://scans.lastation.us/manga/Chainsaw-Man/0001-001.png")
        self.assertEqual(pages[1].url, "https://scans.lastation.us/manga/Chainsaw-Man/0001-002.png")
        self.assertEqual(pages[2].url, "https://scans.lastation.us/manga/Chainsaw-Man/0001-003.png")

        # Headers check
        self.assertIn("Referer", pages[0].headers)
        self.assertEqual(pages[0].headers["Referer"], "https://weebcentral.com/")

    def test_get_chapter_pages_filters_out_unapproved_domains_and_logos(self):
        """Pages must not include branding logos or images hosted on unapproved hosts (evil-analytics.com)."""
        pages = self.provider.get_chapter_pages("01J76XZ001")
        for p in pages:
            self.assertNotIn("evil-analytics.com", p.url)
            self.assertNotIn("brand-logo.png", p.url)

    # -----------------------------------------------------------------------
    # 5. Missing / Malformed HTML & Error Handling
    # -----------------------------------------------------------------------

    def test_empty_series_page(self):
        self.mock_client.set_response(
            "https://weebcentral.com/series/empty_series",
            200,
            FIXTURE_EMPTY_SERIES_HTML.encode("utf-8"),
        )
        series = self.provider.get_series("empty_series")
        self.assertEqual(series.id, "empty_series")
        self.assertEqual(series.title, "Empty Manga")
        self.assertEqual(len(series.chapters), 0)
        self.assertIsNone(series.cover_url)

    def test_malformed_html_does_not_crash(self):
        self.mock_client.set_response(
            "https://weebcentral.com/series/broken",
            200,
            FIXTURE_MALFORMED_HTML.encode("utf-8"),
        )
        series = self.provider.get_series("broken")
        self.assertEqual(series.id, "broken")
        # Should gracefully extract whatever is valid without crashing
        self.assertIsInstance(series.chapters, list)

    def test_series_http_error_raises_runtime_error(self):
        self.mock_client.set_response("https://weebcentral.com/series/not_found", 404, b"Not Found")
        with self.assertRaises(RuntimeError):
            self.provider.get_series("not_found")

    def test_chapter_http_error_raises_runtime_error(self):
        self.mock_client.set_response("https://weebcentral.com/chapters/not_found_ch", 500, b"Server Error")
        with self.assertRaises(RuntimeError):
            self.provider.get_chapter_pages("not_found_ch")

    # -----------------------------------------------------------------------
    # 5b. Chapter Title Parsing & UI Metadata Exclusion
    # -----------------------------------------------------------------------

    def test_parse_chapter_title_excludes_last_read_and_timestamp(self):
        """Verify 'Last Read' metadata and <time> ISO timestamp are excluded from chapter title."""
        html = """<!DOCTYPE html>
        <html><body>
            <h1>Chainsaw Man</h1>
            <div id="chapter-list">
                <a href="/chapters/01J76XZ001" class="flex justify-between items-center py-2 px-3">
                    <span class="flex items-center gap-2">
                        <span class="">Chapter 1</span>
                    </span>
                    <div class="flex items-center gap-2">
                        <span class="text-xs text-muted">Last Read</span>
                        <time datetime="2024-09-07T17:04:15.717343Z">2024-09-07T17:04:15.717343Z</time>
                    </div>
                </a>
            </div>
        </body></html>"""
        self.mock_client.set_response(
            "https://weebcentral.com/series/01J_LAST_READ",
            200,
            html.encode("utf-8"),
        )
        series = self.provider.get_series("01J_LAST_READ")
        self.assertEqual(len(series.chapters), 1)
        ch = series.chapters[0]
        self.assertEqual(ch.id, "01J76XZ001")
        self.assertEqual(ch.title, "Chapter 1")
        self.assertEqual(ch.chapter_number, 1.0)
        self.assertEqual(ch.date, "2024-09-07T17:04:15.717343Z")

    def test_parse_chapter_title_preserves_legitimate_extra_text(self):
        """Preserve legitimate subtitles, specials, decimals, and words like 'Last Stand' or 'Prologue'."""
        html = """<!DOCTYPE html>
        <html><body>
            <h1>Complex Titles Series</h1>
            <a href="/chapters/ch_prologue">
                <span class="flex items-center gap-2">
                    <span>Prologue: The Awakening</span>
                </span>
                <time datetime="2024-01-01T00:00:00Z">2024-01-01T00:00:00Z</time>
            </a>
            <a href="/chapters/ch_1_5">
                <span class="flex items-center gap-2">
                    <span>Chapter 1.5 - Special Omake</span>
                </span>
                <time datetime="2024-01-02T00:00:00Z">2024-01-02T00:00:00Z</time>
            </a>
            <a href="/chapters/ch_50">
                <span class="flex items-center gap-2">
                    <span>Chapter 50 - The Last Stand</span>
                </span>
                <div>
                    <span>Last Read</span>
                    <time datetime="2024-09-07T17:04:15.717343Z">2024-09-07T17:04:15.717343Z</time>
                </div>
            </a>
            <a href="/chapters/ch_100">
                <span class="flex items-center gap-2">
                    <span>Chapter 100: The Last Hero of 2024</span>
                </span>
                <time datetime="2024-12-31T23:59:59Z">2024-12-31T23:59:59Z</time>
            </a>
        </body></html>"""
        self.mock_client.set_response(
            "https://weebcentral.com/series/01J_LEGIT_TITLES",
            200,
            html.encode("utf-8"),
        )
        series = self.provider.get_series("01J_LEGIT_TITLES")
        self.assertEqual(len(series.chapters), 4)

        titles = [c.title for c in series.chapters]
        numbers = [c.chapter_number for c in series.chapters]

        self.assertEqual(
            titles,
            [
                "Prologue: The Awakening",
                "Chapter 1.5 - Special Omake",
                "Chapter 50 - The Last Stand",
                "Chapter 100: The Last Hero of 2024",
            ],
        )
        self.assertEqual(numbers, [0.0, 1.5, 50.0, 100.0])

    def test_parse_chapter_title_unread_weebcentral_row(self):
        """Unread WeebCentral row with <time> tag does not leak timestamp into title."""
        html = """<!DOCTYPE html>
        <html><body>
            <h1>Unread Series</h1>
            <a href="/chapters/01J76XZ002" class="flex justify-between items-center py-2 px-3">
                <span class="flex items-center gap-2">
                    <span>Chapter 2 - Arrival in Tokyo</span>
                </span>
                <time datetime="2024-09-08T12:00:00Z">2024-09-08T12:00:00Z</time>
            </a>
        </body></html>"""
        self.mock_client.set_response(
            "https://weebcentral.com/series/01J_UNREAD",
            200,
            html.encode("utf-8"),
        )
        series = self.provider.get_series("01J_UNREAD")
        self.assertEqual(len(series.chapters), 1)
        ch = series.chapters[0]
        self.assertEqual(ch.title, "Chapter 2 - Arrival in Tokyo")
        self.assertEqual(ch.chapter_number, 2.0)
        self.assertEqual(ch.date, "2024-09-08T12:00:00Z")

    def test_parse_chapter_title_flat_text_fallback(self):
        """Flat anchor markup without nested spans cleanly strips Last Read metadata."""
        html = """<!DOCTYPE html>
        <html><body>
            <h1>Flat Series</h1>
            <a href="/chapters/ch_flat">Chapter 1 Last Read 2024-09-07T17:04:15.717343Z</a>
        </body></html>"""
        self.mock_client.set_response(
            "https://weebcentral.com/series/01J_FLAT",
            200,
            html.encode("utf-8"),
        )
        series = self.provider.get_series("01J_FLAT")
        self.assertEqual(len(series.chapters), 1)
        self.assertEqual(series.chapters[0].title, "Chapter 1")
        self.assertEqual(series.chapters[0].chapter_number, 1.0)

    # -----------------------------------------------------------------------
    # 6. Security & SSRF Protection
    # -----------------------------------------------------------------------

    def test_security_allowlist_matches_subdomains_and_cdns(self):
        policy = self.provider.policy
        # Main site
        self.assertTrue(policy.match_hostname("weebcentral.com"))
        self.assertTrue(policy.match_hostname("img.weebcentral.com"))
        # Hyperdimension Neptunia image CDNs
        self.assertTrue(policy.match_hostname("scans.lastation.us"))
        self.assertTrue(policy.match_hostname("scans.lowee.us"))
        self.assertTrue(policy.match_hostname("scans.planeptune.us"))
        self.assertTrue(policy.match_hostname("scans-hot.leanbox.us"))
        # Heritage image hosts
        self.assertTrue(policy.match_hostname("temp.compsci88.com"))
        self.assertTrue(policy.match_hostname("ib.skylandcdn.com"))

        # Block unauthorized domains
        self.assertFalse(policy.match_hostname("evil.com"))
        self.assertFalse(policy.match_hostname("weebcentral.com.attacker.com"))
        self.assertFalse(policy.match_hostname("fake-lastation.us"))

    def test_get_image_rejects_disallowed_host_or_insecure_scheme(self):
        with self.assertRaises(DisallowedHostError):
            self.provider.get_image("https://evil.com/image.jpg")
        with self.assertRaises(InvalidSchemeError):
            self.provider.get_image("http://weebcentral.com/image.jpg")
        with self.assertRaises(DisallowedHostError):
            self.provider.get_image("https://127.0.0.1/admin.png")
        with self.assertRaises(DisallowedHostError):
            self.provider.get_image("https://169.254.169.254/metadata.png")

    # -----------------------------------------------------------------------
    # 7. HTML Tree Parser Edge Cases
    # -----------------------------------------------------------------------

    def test_mini_html_parser_void_tags_and_nesting(self):
        snippet = """<div><img src="1.jpg"><br><input type="text"><p>Hello <span>World</span></p></div>"""
        tree = parse_html_tree(snippet)
        div = tree.find_first("div")
        self.assertIsNotNone(div)
        self.assertEqual(len(div.children), 4)  # img, br, input, p
        self.assertEqual(div.find_first("p").text, "Hello World")


class TestWeebCentralServiceIntegration(unittest.TestCase):
    """Integration tests connecting WeebCentralProvider to RemoteReaderService."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.registry = ProviderRegistry()
        self.cache = ChapterPageCache(max_entries=20, max_total_pages=200)

        # Mock HTTP client for WeebCentral
        self.mock_client = MockSecureHttpClient()
        series_url = "https://weebcentral.com/series/01J76XY8CM99"
        frag_url = "https://weebcentral.com/series/01J76XY8CM99/full-chapter-list"
        ch1_url = "https://weebcentral.com/chapters/01J76XZ001"

        self.mock_client.set_response(series_url, 200, FIXTURE_SERIES_MAIN_HTML.encode("utf-8"))
        self.mock_client.set_response(frag_url, 200, FIXTURE_FULL_CHAPTER_LIST_FRAGMENT.encode("utf-8"))
        self.mock_client.set_response(ch1_url, 200, FIXTURE_CHAPTER_PAGES_HTML.encode("utf-8"))

        for i in range(1, 4):
            img_url = f"https://scans.lastation.us/manga/Chainsaw-Man/0001-00{i}.png"
            self.mock_client.set_response(img_url, 200, SAMPLE_PNG_BYTES, headers={"content-type": "image/png"})

        cover_url = "https://temp.compsci88.com/cover/Chainsaw-Man.jpg"
        self.mock_client.set_response(cover_url, 200, SAMPLE_PNG_BYTES, headers={"content-type": "image/jpeg"})

        self.weeb_provider = WeebCentralProvider(client=self.mock_client)
        self.registry.register(self.weeb_provider)

        # Also register mock provider for regression checks
        self.mock_provider = MockProvider()
        self.registry.register(self.mock_provider)

        self.service = RemoteReaderService(
            registry=self.registry,
            cache=self.cache,
            state_dir=self.state_dir,
        )

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_service_resolves_weebcentral_series_by_url(self):
        resolved = self.service.resolve_series("https://weebcentral.com/series/01J76XY8CM99/chainsaw-man")
        self.assertEqual(resolved["provider"], "weebcentral")
        self.assertEqual(resolved["series_id"], "01J76XY8CM99")
        self.assertEqual(resolved["series_identifier"], "remote:weebcentral:01J76XY8CM99")
        self.assertEqual(resolved["series"]["title"], "Chainsaw Man")

    def test_service_resolves_weebcentral_series_by_canonical_identifier(self):
        resolved = self.service.resolve_series("remote:weebcentral:01J76XY8CM99")
        self.assertEqual(resolved["provider"], "weebcentral")
        self.assertEqual(resolved["series_id"], "01J76XY8CM99")
        self.assertEqual(resolved["series"]["title"], "Chainsaw Man")

    def test_service_get_chapters_for_weebcentral(self):
        data = self.service.get_chapters("remote:weebcentral:01J76XY8CM99")
        self.assertEqual(data["series"], "remote:weebcentral:01J76XY8CM99")
        self.assertEqual(data["title"], "Chainsaw Man")
        self.assertEqual(data["chapter_count"], 4)
        self.assertEqual(data["chapters"][0]["name"], "01J76XZ001")
        self.assertEqual(data["chapters"][0]["chapter_number"], 1.0)

    def test_service_get_chapter_pages_and_cache(self):
        # 1. Fetch pages
        pages = self.service.get_chapter_pages("remote:weebcentral:01J76XY8CM99", "01J76XZ001")
        self.assertEqual(len(pages), 3)

        # 2. Check cache was populated
        cache_key = "remote:weebcentral:01J76XY8CM99:01J76XZ001"
        cached = self.cache.get(cache_key)
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 3)

    def test_service_chapter_images_for_reader(self):
        data = self.service.get_chapter_images_for_reader("remote:weebcentral:01J76XY8CM99", "01J76XZ001")
        self.assertEqual(data["series"], "remote:weebcentral:01J76XY8CM99")
        self.assertEqual(data["chapter"], "01J76XZ001")
        self.assertEqual(data["image_count"], 3)
        self.assertEqual(data["images"][0]["filename"], "1.jpg")
        self.assertIn("/api/remote/image-proxy?", data["images"][0]["url"])
        self.assertIn("provider=weebcentral", data["images"][0]["url"])

    def test_service_stream_page_image_and_cover(self):
        cover = self.service.get_cover("remote:weebcentral:01J76XY8CM99")
        self.assertIsNotNone(cover)
        data, mime = cover
        self.assertEqual(mime, "image/png")
        self.assertEqual(data, SAMPLE_PNG_BYTES)

    def test_service_progress_bookmarks_and_style(self):
        series_id = "remote:weebcentral:01J76XY8CM99"

        # Update progress
        self.service.update_progress(series_id, "01J76XZ001", "2.jpg")
        # Toggle bookmark
        self.service.toggle_bookmark(series_id, "01J76XZ001", bookmarked=True)
        # Update reading style
        self.service.update_reader_style(series_id, "seamless")

        # Read back
        reader_data = self.service.get_reader_data(series_id)
        self.assertEqual(reader_data["progress"]["01J76XZ001"], "2.jpg")
        self.assertIn("01J76XZ001", reader_data["bookmarks"])
        self.assertEqual(reader_data["reader"]["style"], "seamless")

    def test_mock_provider_regression_intact(self):
        """Mock provider remains fully functional and isolated."""
        mock_series = self.service.resolve_series("remote:mock:sololeveling")
        self.assertEqual(mock_series["series"]["title"], "Solo Leveling")
        mock_pages = self.service.get_chapter_pages("remote:mock:sololeveling", "mock-ch-1")
        self.assertEqual(len(mock_pages), 3)

    def test_stream_page_image_rejects_non_image_payload(self):
        """Proxy strictly enforces binary image magic bytes, rejecting text/HTML payloads."""
        self.mock_client.set_response(
            "https://scans.lastation.us/fake_html.png",
            200,
            b"<html><body>Not an image</body></html>",
            headers={"content-type": "text/html"},
        )
        with self.assertRaises(ValueError):
            self.service.stream_page_image("weebcentral", "https://scans.lastation.us/fake_html.png")

    def test_stream_page_image_rejects_unauthorized_host(self):
        """Attempting to stream from unapproved host raises DisallowedHostError."""
        with self.assertRaises(DisallowedHostError):
            self.service.stream_page_image("weebcentral", "https://evil.com/fake.png")


class MockSocket:
    """Mock socket for simulated HTTP communication."""

    def __init__(self, data_bytes: bytes) -> None:
        import io
        self.rfile = io.BytesIO(data_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, *args: Any, **kwargs: Any):
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            elif "w" in mode:
                return self.wfile
        raise ValueError(f"Unsupported socket mode: {mode}")

    def sendall(self, data: bytes) -> None:
        self.wfile.write(data)


class TestWeebCentralHTTPHandlerIntegration(unittest.TestCase):
    """Simulate HTTP API endpoints for WeebCentral through MangaRequestHandler."""

    def setUp(self) -> None:
        import io
        from server import MangaLibrary, MangaRequestHandler

        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir) / "manga"
        self.lib_path.mkdir(parents=True, exist_ok=True)
        self.state_dir = Path(self.temp_dir) / "config"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.library = MangaLibrary(str(self.lib_path))
        self.registry = ProviderRegistry()

        self.mock_client = MockSecureHttpClient()
        series_url = "https://weebcentral.com/series/01J76XY8CM99"
        frag_url = "https://weebcentral.com/series/01J76XY8CM99/full-chapter-list"
        ch1_url = "https://weebcentral.com/chapters/01J76XZ001"

        self.mock_client.set_response(series_url, 200, FIXTURE_SERIES_MAIN_HTML.encode("utf-8"))
        self.mock_client.set_response(frag_url, 200, FIXTURE_FULL_CHAPTER_LIST_FRAGMENT.encode("utf-8"))
        self.mock_client.set_response(ch1_url, 200, FIXTURE_CHAPTER_PAGES_HTML.encode("utf-8"))

        for i in range(1, 4):
            img_url = f"https://scans.lastation.us/manga/Chainsaw-Man/0001-00{i}.png"
            self.mock_client.set_response(img_url, 200, SAMPLE_PNG_BYTES, headers={"content-type": "image/png"})

        cover_url = "https://temp.compsci88.com/cover/Chainsaw-Man.jpg"
        self.mock_client.set_response(cover_url, 200, SAMPLE_PNG_BYTES, headers={"content-type": "image/jpeg"})

        self.weeb_provider = WeebCentralProvider(client=self.mock_client)
        self.registry.register(self.weeb_provider)
        self.registry.register(MockProvider())

        self.service = RemoteReaderService(
            registry=self.registry,
            cache=ChapterPageCache(),
            state_dir=self.state_dir,
        )

        self.HandlerClass = MangaRequestHandler
        self.HandlerClass.library = self.library
        self.HandlerClass.static_dir = PROJECT_ROOT / "static"
        self.HandlerClass.remote_service = self.service

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def simulate_get(self, path: str):
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

    def simulate_post(self, path: str, json_data: Dict[str, Any]):
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

    def test_http_resolve_weebcentral_series(self):
        url = "/api/remote/resolve?url=https://weebcentral.com/series/01J76XY8CM99/chainsaw-man"
        headers, body, status = self.simulate_get(url)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["provider"], "weebcentral")
        self.assertEqual(data["series_id"], "01J76XY8CM99")
        self.assertEqual(data["series"]["title"], "Chainsaw Man")

    def test_http_get_chapters_weebcentral(self):
        url = "/api/chapters?series=remote:weebcentral:01J76XY8CM99"
        headers, body, status = self.simulate_get(url)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["chapter_count"], 4)
        self.assertEqual(data["chapters"][0]["name"], "01J76XZ001")

    def test_http_get_images_weebcentral(self):
        url = "/api/images?series=remote:weebcentral:01J76XY8CM99&chapter=01J76XZ001"
        headers, body, status = self.simulate_get(url)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["image_count"], 3)
        self.assertEqual(data["images"][0]["filename"], "1.jpg")
        self.assertIn("/api/remote/image-proxy?", data["images"][0]["url"])

    def test_http_stream_image_proxy_weebcentral(self):
        img_url = "https://scans.lastation.us/manga/Chainsaw-Man/0001-001.png"
        url = f"/api/remote/image-proxy?url={img_url}&provider=weebcentral"
        headers, body, status = self.simulate_get(url)
        self.assertEqual(status, 200)
        self.assertEqual(body, SAMPLE_PNG_BYTES)

    def test_http_cover_stream_weebcentral(self):
        url = "/api/cover?series=remote:weebcentral:01J76XY8CM99"
        headers, body, status = self.simulate_get(url)
        self.assertEqual(status, 200)
        self.assertEqual(body, SAMPLE_PNG_BYTES)

    def test_http_progress_bookmark_and_style_weebcentral(self):
        series_id = "remote:weebcentral:01J76XY8CM99"
        # Progress
        _, p_body, p_status = self.simulate_post("/api/progress", {"series": series_id, "chapter": "01J76XZ001", "image": "2.jpg"})
        self.assertEqual(p_status, 200)
        # Bookmark
        _, b_body, b_status = self.simulate_post("/api/bookmark", {"series": series_id, "chapter": "01J76XZ001", "bookmarked": True})
        self.assertEqual(b_status, 200)
        # Style
        _, s_body, s_status = self.simulate_post("/api/style", {"series": series_id, "style": "seamless"})
        self.assertEqual(s_status, 200)

        # Retrieve reader-data
        _, r_body, r_status = self.simulate_get(f"/api/reader-data?series={series_id}")
        self.assertEqual(r_status, 200)
        r_data = json.loads(r_body.decode("utf-8"))
        self.assertEqual(r_data["progress"]["01J76XZ001"], "2.jpg")
        self.assertIn("01J76XZ001", r_data["bookmarks"])
        self.assertEqual(r_data["reader"]["style"], "seamless")

    def test_http_rejects_ssrf_image_proxy_for_weebcentral(self):
        bad_urls = [
            "https://evil.com/fake.png",
            "http://scans.lastation.us/plain.png",
            "https://127.0.0.1/admin.png",
            "https://169.254.169.254/secret.png",
        ]
        for bad_url in bad_urls:
            url = f"/api/remote/image-proxy?url={bad_url}&provider=weebcentral"
            headers, body, status = self.simulate_get(url)
            self.assertEqual(status, 400, f"Should reject {bad_url} with 400")


if __name__ == "__main__":
    unittest.main()

