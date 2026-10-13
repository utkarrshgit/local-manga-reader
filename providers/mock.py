"""
providers/mock.py - Mock remote provider implementation for testing and isolated verification.

Provides a fully functioning in-memory provider adhering to the BaseProvider
interface, populated with deterministic sample manga data.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlsplit

from providers.base import BaseProvider, RemoteChapter, RemotePage, RemoteSeries


class MockProvider(BaseProvider):
    """
    Mock remote provider serving deterministic test data.
    """

    id = "mock"
    name = "Mock Manga Provider"
    allowed_domains = ("mock.local", "cdn.mock.local")

    def __init__(
        self,
        series_data: Optional[Dict[str, RemoteSeries]] = None,
        simulate_error: bool = False,
        images_data: Optional[Dict[str, bytes]] = None,
    ) -> None:
        self.simulate_error = simulate_error
        self._series: Dict[str, RemoteSeries] = {}
        self._images: Dict[str, bytes] = dict(images_data or {})

        if series_data is not None:
            self._series = dict(series_data)
        else:
            self._init_fixtures()

    def get_image(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """Return image bytes for a mock image URL or default 1x1 PNG."""
        if self.simulate_error:
            raise RuntimeError("Simulated provider error")
        from providers.security import validate_provider_target_url
        validate_provider_target_url(url, self.allowed_domains)
        if not self.can_handle_url(url):
            raise ValueError(f"URL '{url}' is not handled by this provider.")
        if url in self._images:
            return self._images[url]
        # Return deterministic 1x1 transparent PNG bytes
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00"
            b"\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    def _init_fixtures(self) -> None:
        """Initialize mock series fixtures."""
        ch1_pages = [
            RemotePage(index=1, url="https://cdn.mock.local/series1/ch1/1.jpg"),
            RemotePage(index=2, url="https://cdn.mock.local/series1/ch1/2.jpg"),
            RemotePage(index=3, url="https://cdn.mock.local/series1/ch1/3.jpg"),
        ]
        ch2_pages = [
            RemotePage(index=1, url="https://cdn.mock.local/series1/ch2/1.jpg"),
            RemotePage(index=2, url="https://cdn.mock.local/series1/ch2/2.jpg"),
        ]

        ch1 = RemoteChapter(
            id="mock-ch-1",
            title="Chapter 1: The Awakening",
            chapter_number=1.0,
            url="https://mock.local/series/sololeveling/chapter-1",
            date="2026-01-01",
            pages=ch1_pages,
            metadata={"scanlator": "MockScans"},
        )
        ch2 = RemoteChapter(
            id="mock-ch-2",
            title="Chapter 2: The Next Trial",
            chapter_number=2.0,
            url="https://mock.local/series/sololeveling/chapter-2",
            date="2026-01-08",
            pages=ch2_pages,
            metadata={"scanlator": "MockScans"},
        )

        series1 = RemoteSeries(
            id="sololeveling",
            title="Solo Leveling",
            url="https://mock.local/series/sololeveling",
            cover_url="https://cdn.mock.local/covers/sololeveling.jpg",
            backdrop_url="https://cdn.mock.local/backdrops/sololeveling.jpg",
            description="In a world where hunters must battle deadly monsters...",
            author="Chugong",
            status="Completed",
            chapters=[ch1, ch2],
            metadata={"rating": 9.8},
        )
        self._series["sololeveling"] = series1

    def can_handle_url(self, url: str) -> bool:
        """Check if URL belongs to mock.local or cdn.mock.local."""
        if not url:
            return False
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        return host in self.allowed_domains

    def get_series(self, url_or_id: str) -> RemoteSeries:
        """Fetch remote series by ID or URL."""
        if self.simulate_error:
            raise RuntimeError("Simulated provider error")

        series_id = self._extract_series_id(url_or_id)
        if series_id not in self._series:
            raise KeyError(f"Mock series '{series_id}' not found.")

        # Return a copy of the series
        series = self._series[series_id]
        return RemoteSeries.from_dict(series.to_dict())

    def get_chapters(self, url_or_id: str) -> List[RemoteChapter]:
        """Fetch chapters for a series."""
        series = self.get_series(url_or_id)
        return series.chapters

    def get_chapter_pages(self, chapter_url_or_id: str) -> List[RemotePage]:
        """Fetch pages for a chapter ID or URL."""
        if self.simulate_error:
            raise RuntimeError("Simulated provider error")

        target_id = self._extract_chapter_id(chapter_url_or_id)

        # Search across all series for the chapter
        for series in self._series.values():
            for ch in series.chapters:
                if ch.id == target_id or ch.url == chapter_url_or_id:
                    return [RemotePage.from_dict(p.to_dict()) for p in ch.pages]

        raise KeyError(f"Mock chapter '{chapter_url_or_id}' not found.")

    def _extract_series_id(self, url_or_id: str) -> str:
        """Extract series ID from URL or return raw ID."""
        if "://" in url_or_id:
            parsed = urlsplit(url_or_id)
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] == "series":
                return parts[1]
        return url_or_id.strip()

    def _extract_chapter_id(self, url_or_id: str) -> str:
        """Extract chapter ID from URL or return raw ID."""
        if "://" in url_or_id:
            parsed = urlsplit(url_or_id)
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 3 and parts[0] == "series":
                slug = parts[2]
                if slug.startswith("chapter-"):
                    num = slug.replace("chapter-", "")
                    return f"mock-ch-{num}"
        return url_or_id.strip()
