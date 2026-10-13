"""
providers/base.py - Normalized remote data models and base provider interface.

Defines the normalized models for remote manga/manhwa resources:
- RemotePage: Represents a single page image with URL and optional request headers.
- RemoteChapter: Represents a chapter with identifier, title, number, and pages.
- RemoteSeries: Represents a series with identifier, title, cover, and chapter list.
- BaseProvider: Abstract interface that all remote providers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RemotePage:
    """Normalized representation of a single remote manga/manhwa page."""

    index: int
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    byte_size: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert page model to a JSON-serializable dictionary."""
        d: Dict[str, Any] = {
            "index": self.index,
            "url": self.url,
            "headers": dict(self.headers),
        }
        if self.byte_size is not None:
            d["byte_size"] = self.byte_size
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RemotePage:
        """Construct a RemotePage instance from a dictionary."""
        return cls(
            index=int(data["index"]),
            url=str(data["url"]),
            headers=dict(data.get("headers", {})),
            byte_size=data.get("byte_size"),
        )


@dataclass
class RemoteChapter:
    """Normalized representation of a remote chapter."""

    id: str
    title: str
    chapter_number: Optional[float] = None
    url: str = ""
    date: Optional[str] = None
    pages: List[RemotePage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter model to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "chapter_number": self.chapter_number,
            "url": self.url,
            "date": self.date,
            "pages": [p.to_dict() for p in self.pages],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RemoteChapter:
        """Construct a RemoteChapter instance from a dictionary."""
        pages = [RemotePage.from_dict(p) for p in data.get("pages", [])]
        raw_num = data.get("chapter_number")
        chapter_number: Optional[float] = None
        if raw_num is not None and raw_num != "":
            try:
                chapter_number = float(raw_num)
            except (ValueError, TypeError):
                chapter_number = None
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            chapter_number=chapter_number,
            url=str(data.get("url", "")),
            date=data.get("date"),
            pages=pages,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class RemoteSeries:
    """Normalized representation of a remote series."""

    id: str
    title: str
    url: str = ""
    cover_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None
    chapters: List[RemoteChapter] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert series model to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "cover_url": self.cover_url,
            "backdrop_url": self.backdrop_url,
            "description": self.description,
            "author": self.author,
            "status": self.status,
            "chapters": [c.to_dict() for c in self.chapters],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RemoteSeries:
        """Construct a RemoteSeries instance from a dictionary."""
        chapters = [RemoteChapter.from_dict(c) for c in data.get("chapters", [])]
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            url=str(data.get("url", "")),
            cover_url=data.get("cover_url"),
            backdrop_url=data.get("backdrop_url"),
            description=data.get("description"),
            author=data.get("author"),
            status=data.get("status"),
            chapters=chapters,
            metadata=dict(data.get("metadata", {})),
        )


class BaseProvider(ABC):
    """
    Abstract base class for all remote providers.

    Subclasses must declare their unique identifier, display name, and
    an allowlist of authorized hostnames/domains for security enforcement.
    """

    id: str = ""
    name: str = ""
    allowed_domains: Tuple[str, ...] = ()
    supported_url_types: str = "Series URL"
    url_pattern: str = ""
    is_public: bool = True

    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        """Check whether this provider can resolve and handle the given URL."""
        pass

    @abstractmethod
    def get_series(self, url_or_id: str) -> RemoteSeries:
        """Fetch remote series metadata, including chapter listing."""
        pass

    @abstractmethod
    def get_chapter_pages(self, chapter_url_or_id: str) -> List[RemotePage]:
        """Fetch remote page URLs and headers for a single chapter."""
        pass

    def get_image(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """
        Fetch image bytes for a remote URL through the SSRF-protected SecureHttpClient.
        Subclasses can override if they provide in-memory fixtures (like MockProvider).
        """
        from providers.security import SecurityPolicy, SecureHttpClient, validate_provider_target_url
        validate_provider_target_url(url, self.allowed_domains)
        policy = SecurityPolicy(allowed_hosts=self.allowed_domains)
        client = SecureHttpClient(policy=policy)
        resp = client.get(url, headers=headers)
        return resp.body
