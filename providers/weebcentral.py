"""
providers/weebcentral.py - WeebCentral remote manga/manhwa provider implementation.

Implements the BaseProvider interface for WeebCentral (weebcentral.com) using
the existing SSRF-protected SecureHttpClient and zero external dependencies.

Observed Website Structure:
- Series URL: https://weebcentral.com/series/{series_id}/{slug} or /series/{series_id}
- Chapter URL: https://weebcentral.com/chapters/{chapter_id}
- Full chapter list fragment (HTMX): /series/{series_id}/full-chapter-list
- Media / CDN Domains:
  - weebcentral.com, *.weebcentral.com
  - *.lastation.us, *.lowee.us, *.planeptune.us, *.leanbox.us
  - *.compsci88.com, *.skylandcdn.com
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from providers.base import BaseProvider, RemoteChapter, RemotePage, RemoteSeries
from providers.security import (
    DisallowedHostError,
    InvalidSchemeError,
    SSRFSecurityError,
    SecureHttpClient,
    SecurityPolicy,
    validate_provider_target_url,
)


# Standard HTTP request headers for WeebCentral
WEEBCENTRAL_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
        "image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://weebcentral.com/",
}


class HTMLTagNode:
    """Lightweight representation of an HTML node parsed by MiniHTMLParser."""

    def __init__(
        self,
        tag: str,
        attrs: Dict[str, str],
        parent: Optional[HTMLTagNode] = None,
    ) -> None:
        self.tag = tag.lower()
        self.attrs = attrs
        self.parent = parent
        self.children: List[HTMLTagNode] = []
        self.text_fragments: List[str] = []

    @property
    def text(self) -> str:
        """Return combined text content of this node and all its descendants."""
        fragments = list(self.text_fragments)
        for child in self.children:
            fragments.append(child.text)
        return " ".join(" ".join(fragments).split())

    def find_all(
        self,
        tag: Optional[str] = None,
        attr_name: Optional[str] = None,
        attr_val: Optional[str] = None,
    ) -> List[HTMLTagNode]:
        """Find all matching descendant nodes."""
        results: List[HTMLTagNode] = []
        t = tag.lower() if tag else None
        an = attr_name.lower() if attr_name else None

        for child in self.children:
            match = True
            if t and child.tag != t:
                match = False
            if match and an:
                if an not in child.attrs:
                    match = False
                elif attr_val is not None and child.attrs[an] != attr_val:
                    match = False
            if match:
                results.append(child)
            results.extend(child.find_all(tag=tag, attr_name=attr_name, attr_val=attr_val))
        return results

    def find_first(
        self,
        tag: Optional[str] = None,
        attr_name: Optional[str] = None,
        attr_val: Optional[str] = None,
    ) -> Optional[HTMLTagNode]:
        """Find the first matching descendant node."""
        matches = self.find_all(tag=tag, attr_name=attr_name, attr_val=attr_val)
        return matches[0] if matches else None


class MiniHTMLTreeParser(HTMLParser):
    """
    Zero-dependency robust tree-building HTML parser built on html.parser.HTMLParser.
    Safely parses partial HTML fragments and full HTML documents.
    """

    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HTMLTagNode("root", {})
        self._current = self.root

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}
        node = HTMLTagNode(tag, attr_dict, parent=self._current)
        self._current.children.append(node)
        if tag.lower() not in self.VOID_TAGS:
            self._current = node

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        curr = self._current
        while curr is not None and curr is not self.root:
            if curr.tag == tag_lower:
                self._current = curr.parent or self.root
                break
            curr = curr.parent

    def handle_data(self, data: str) -> None:
        if data:
            self._current.text_fragments.append(data)


def parse_html_tree(html_text: str) -> HTMLTagNode:
    """Parse HTML string into an HTMLTagNode document root."""
    parser = MiniHTMLTreeParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass
    return parser.root


class WeebCentralProvider(BaseProvider):
    """
    Remote provider for WeebCentral (https://weebcentral.com).

    Enforces strict HTTPS and outbound domain allowlists for the main site
    and official image CDN subdomains.
    """

    id = "weebcentral"
    name = "WeebCentral"
    allowed_domains = (
        "weebcentral.com",
        "*.weebcentral.com",
        "*.lastation.us",
        "*.lowee.us",
        "*.planeptune.us",
        "*.leanbox.us",
        "*.compsci88.com",
        "*.skylandcdn.com",
    )

    BASE_URL = "https://weebcentral.com"

    def __init__(
        self,
        client: Optional[SecureHttpClient] = None,
        timeout: float = 12.0,
    ) -> None:
        self.policy = SecurityPolicy(allowed_hosts=self.allowed_domains)
        self.client = client if client is not None else SecureHttpClient(policy=self.policy, timeout=timeout)
        self.timeout = float(timeout)

    def can_handle_url(self, url: str) -> bool:
        """Check whether this provider can handle the given URL or series identifier."""
        if not url or not isinstance(url, str):
            return False
        s = url.strip()

        # Handle canonical remote identifier: remote:weebcentral:<id>
        if s.startswith("remote:weebcentral:"):
            return bool(s[len("remote:weebcentral:") :].strip())

        # Handle full URL
        try:
            parsed = urlsplit(s)
            if parsed.scheme.lower() != "https":
                return False
            host = (parsed.hostname or "").lower()
            if not self.policy.match_hostname(host):
                return False
            # Check path patterns for series or chapters
            path = parsed.path or ""
            return path.startswith("/series/") or path.startswith("/chapters/")
        except Exception:
            return False

    def _extract_series_id(self, url_or_id: str) -> str:
        """Extract series identifier from a URL, canonical prefix, or raw ID."""
        if not url_or_id or not isinstance(url_or_id, str):
            raise ValueError("Series identifier must be a non-empty string.")

        s = url_or_id.strip()
        if s.startswith("remote:weebcentral:"):
            raw_id = s[len("remote:weebcentral:") :].strip()
            if not raw_id:
                raise ValueError("Empty series ID in canonical identifier.")
            return raw_id

        if "://" in s:
            parsed = self.policy.validate_url(s)
            parts = [p for p in (parsed.path or "").split("/") if p]
            if len(parts) >= 2 and parts[0] == "series":
                return parts[1]
            raise ValueError(f"URL does not contain a valid WeebCentral series path: {s}")

        # If it's a raw identifier (e.g. 01J76XY7G... or alphanumeric slug)
        clean = s.strip("/")
        if not clean or any(c in clean for c in "/?#&\\"):
            raise ValueError(f"Invalid WeebCentral series identifier: {url_or_id}")
        return clean

    def _extract_chapter_id(self, url_or_id: str) -> str:
        """Extract chapter identifier from a chapter URL or raw ID."""
        if not url_or_id or not isinstance(url_or_id, str):
            raise ValueError("Chapter identifier must be a non-empty string.")

        s = url_or_id.strip()
        if "://" in s:
            parsed = self.policy.validate_url(s)
            parts = [p for p in (parsed.path or "").split("/") if p]
            if len(parts) >= 2 and parts[0] == "chapters":
                return parts[1]
            raise ValueError(f"URL does not contain a valid WeebCentral chapter path: {s}")

        clean = s.strip("/")
        if not clean or any(c in clean for c in "/?#&\\"):
            raise ValueError(f"Invalid WeebCentral chapter identifier: {url_or_id}")
        return clean

    def get_series(self, url_or_id: str) -> RemoteSeries:
        """
        Fetch remote series metadata and chapter listing for WeebCentral.

        Retrieves the main series page, extracts metadata (title, cover, description,
        author, status), and parses all chapters (requesting the HTMX full-chapter-list
        fragment when present).
        """
        series_id = self._extract_series_id(url_or_id)
        series_url = f"{self.BASE_URL}/series/{series_id}"

        # 1. Fetch main series page
        resp = self.client.get(series_url, headers=WEEBCENTRAL_HEADERS)
        if resp.status_code != 200:
            raise RuntimeError(f"WeebCentral series request returned HTTP {resp.status_code} for {series_url}")

        html_text = resp.text()
        tree = parse_html_tree(html_text)

        # 2. Extract series metadata
        title = self._parse_title(tree, series_id)
        cover_url = self._parse_cover_url(tree, series_url)
        description = self._parse_description(tree)
        author = self._parse_author(tree)
        status = self._parse_status(tree)

        # 3. Extract chapters (main page + HTMX full chapter fragment if present)
        chapters = self._parse_chapters(tree, series_id, series_url)

        return RemoteSeries(
            id=series_id,
            title=title,
            url=series_url,
            cover_url=cover_url,
            backdrop_url=None,
            description=description,
            author=author,
            status=status,
            chapters=chapters,
            metadata={"source": "weebcentral", "series_id": series_id},
        )

    def _parse_title(self, tree: HTMLTagNode, fallback_id: str) -> str:
        """Extract series title from page elements or OpenGraph meta tags."""
        # 1. OpenGraph meta tag
        for meta in tree.find_all("meta"):
            prop = meta.attrs.get("property", "").lower()
            if prop == "og:title" and meta.attrs.get("content"):
                candidate = meta.attrs["content"].strip()
                # Remove suffix like " | Weeb Central"
                clean = re.sub(r"\s*\|\s*Weeb\s*Central.*$", "", candidate, flags=re.IGNORECASE).strip()
                if clean:
                    return clean

        # 2. <h1> tag
        h1 = tree.find_first("h1")
        if h1 and h1.text.strip():
            return h1.text.strip()

        # 3. <title> tag
        title_tag = tree.find_first("title")
        if title_tag and title_tag.text.strip():
            clean = re.sub(r"\s*\|\s*Weeb\s*Central.*$", "", title_tag.text, flags=re.IGNORECASE).strip()
            if clean:
                return clean

        return fallback_id

    def _parse_cover_url(self, tree: HTMLTagNode, base_url: str) -> Optional[str]:
        """Extract series cover image URL, validating domain boundaries."""
        candidate_url: Optional[str] = None

        # 1. OpenGraph image meta tag
        for meta in tree.find_all("meta"):
            prop = meta.attrs.get("property", "").lower()
            if prop == "og:image" and meta.attrs.get("content"):
                candidate_url = meta.attrs["content"].strip()
                break

        # 2. Fallback to cover <img> tag in DOM
        if not candidate_url:
            for img in tree.find_all("img"):
                alt = img.attrs.get("alt", "").lower()
                src = img.attrs.get("src") or img.attrs.get("data-src")
                if src and ("cover" in alt or "cover" in src.lower() or "poster" in src.lower()):
                    candidate_url = src.strip()
                    break

        if not candidate_url:
            # First img inside <main> or <section>
            for section in tree.find_all("section") + tree.find_all("main"):
                img = section.find_first("img")
                if img:
                    src = img.attrs.get("src") or img.attrs.get("data-src")
                    if src and not src.startswith("data:"):
                        candidate_url = src.strip()
                        break

        if candidate_url:
            full_url = urljoin(base_url, candidate_url)
            try:
                validate_provider_target_url(full_url, self.allowed_domains)
                return full_url
            except Exception:
                return None
        return None

    def _parse_description(self, tree: HTMLTagNode) -> Optional[str]:
        """Extract series synopsis from meta tags or summary sections."""
        # 1. OpenGraph description
        for meta in tree.find_all("meta"):
            prop = meta.attrs.get("property", "").lower()
            name = meta.attrs.get("name", "").lower()
            if (prop == "og:description" or name == "description") and meta.attrs.get("content"):
                desc = meta.attrs["content"].strip()
                if desc and not desc.lower().startswith("read ") and len(desc) > 10:
                    return desc

        # 2. Paragraphs in summary/description container
        for node in tree.find_all(attr_name="id", attr_val="manga-summary") + tree.find_all(attr_name="id", attr_val="series-info"):
            p = node.find_first("p")
            if p and p.text.strip():
                return p.text.strip()

        # Look for section with summary-like content
        for sec in tree.find_all("section"):
            for p in sec.find_all("p"):
                txt = p.text.strip()
                if len(txt) > 30 and not txt.startswith("©"):
                    return txt

        return None

    def _parse_author(self, tree: HTMLTagNode) -> Optional[str]:
        """Extract author or artist information."""
        text = tree.text
        match = re.search(r"Author\s*:\s*([^\|\n\r\t]+?)(?:Artist|Status|Tags|Genres|\n|$)", text, re.IGNORECASE)
        if match:
            author_val = match.group(1).strip()
            if author_val and len(author_val) < 80:
                return author_val

        # Check list items with Author label
        for li in tree.find_all("li"):
            li_txt = li.text
            if "author" in li_txt.lower():
                parts = li_txt.split(":", 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    if val and len(val) < 80:
                        return val
        return None

    def _parse_status(self, tree: HTMLTagNode) -> Optional[str]:
        """Extract series status (Ongoing, Completed, Hiatus, Cancelled)."""
        text = tree.text
        match = re.search(r"Status\s*:\s*(Ongoing|Completed|Hiatus|Cancelled|Dropped)", text, re.IGNORECASE)
        if match:
            return match.group(1).capitalize()

        for li in tree.find_all("li"):
            li_txt = li.text
            if "status" in li_txt.lower():
                for candidate in ("Ongoing", "Completed", "Hiatus", "Cancelled"):
                    if candidate.lower() in li_txt.lower():
                        return candidate
        return None

    def _parse_chapters(
        self,
        tree: HTMLTagNode,
        series_id: str,
        series_url: str,
    ) -> List[RemoteChapter]:
        """
        Extract chapters for a series.
        If the page contains an HTMX fragment endpoint for full chapters,
        fetches and parses that fragment.
        """
        # Check for HTMX lazy-loading endpoint (hx-get)
        hx_endpoint: Optional[str] = None
        for tag in tree.find_all():
            hx_get = tag.attrs.get("hx-get", "").strip()
            if hx_get and ("chapter" in hx_get.lower() or "full-chapter-list" in hx_get.lower()):
                hx_endpoint = hx_get
                break

        # If no explicit hx-get found on element, check standard WeebCentral fragment route
        chapter_sources = [tree]
        if hx_endpoint:
            full_hx_url = urljoin(series_url, hx_endpoint)
            try:
                validate_provider_target_url(full_hx_url, self.allowed_domains)
                hx_resp = self.client.get(full_hx_url, headers=WEEBCENTRAL_HEADERS)
                if hx_resp.status_code == 200:
                    hx_tree = parse_html_tree(hx_resp.text())
                    chapter_sources.insert(0, hx_tree)
            except Exception:
                pass
        else:
            # Try fetching full-chapter-list fragment directly if main page has few or no chapters
            try:
                fragment_url = f"{self.BASE_URL}/series/{series_id}/full-chapter-list"
                validate_provider_target_url(fragment_url, self.allowed_domains)
                frag_resp = self.client.get(fragment_url, headers=WEEBCENTRAL_HEADERS)
                if frag_resp.status_code == 200:
                    frag_tree = parse_html_tree(frag_resp.text())
                    chapter_sources.insert(0, frag_tree)
            except Exception:
                pass

        seen_chapter_ids = set()
        chapters: List[RemoteChapter] = []

        for source_tree in chapter_sources:
            for a_tag in source_tree.find_all("a"):
                href = a_tag.attrs.get("href", "").strip()
                if not href or "/chapters/" not in href:
                    continue

                full_chapter_url = urljoin(series_url, href)
                try:
                    ch_id = self._extract_chapter_id(full_chapter_url)
                except ValueError:
                    continue

                if ch_id in seen_chapter_ids:
                    continue
                seen_chapter_ids.add(ch_id)

                title_text = a_tag.text.strip()
                if not title_text:
                    title_text = f"Chapter {ch_id}"

                ch_num = self._parse_chapter_number(title_text)

                # Look for date in descendant <time> or sibling/child elements
                date_str: Optional[str] = None
                time_tag = a_tag.find_first("time")
                if time_tag:
                    date_str = time_tag.attrs.get("datetime") or time_tag.text.strip()

                chapters.append(
                    RemoteChapter(
                        id=ch_id,
                        title=title_text,
                        chapter_number=ch_num,
                        url=full_chapter_url,
                        date=date_str,
                        pages=[],
                        metadata={"source": "weebcentral", "series_id": series_id},
                    )
                )

        # Sort naturally by chapter number if available, maintaining stable ordering
        chapters.sort(
            key=lambda c: (
                c.chapter_number if c.chapter_number is not None else float("inf"),
                c.title,
            )
        )
        return chapters

    def _parse_chapter_number(self, text: str) -> Optional[float]:
        """Extract floating-point chapter number from chapter title string."""
        if not text:
            return None
        if re.search(r"\bprologue\b", text, re.IGNORECASE):
            return 0.0
        # Match "Chapter 123", "Ch. 12.5", "Ep. 5", "Scene. 1", or numbers
        patterns = [
            r"(?:Chapter|Ch\.?|Episode|Ep\.?|Scene\.?|Act\.?)\s*([0-9]+(?:\.[0-9]+)?)",
            r"\b([0-9]+(?:\.[0-9]+)?)\b",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, TypeError):
                    continue
        return None

    def get_chapter_pages(self, chapter_url_or_id: str) -> List[RemotePage]:
        """
        Fetch normalized page URLs and headers for a WeebCentral chapter.

        Fetches the reader page, extracts all panel image tags in reading order,
        and validates image URLs against the approved provider domains.
        """
        chapter_id = self._extract_chapter_id(chapter_url_or_id)
        chapter_url = f"{self.BASE_URL}/chapters/{chapter_id}"

        resp = self.client.get(chapter_url, headers=WEEBCENTRAL_HEADERS)
        if resp.status_code != 200:
            raise RuntimeError(f"WeebCentral chapter request returned HTTP {resp.status_code} for {chapter_url}")

        html_text = resp.text()
        tree = parse_html_tree(html_text)

        # Look for images inside chapter images container or sections
        image_nodes: List[HTMLTagNode] = []
        for sec in tree.find_all(attr_name="id", attr_val="chapter-images"):
            imgs = sec.find_all("img")
            if imgs:
                image_nodes.extend(imgs)

        # If chapter-images container in main HTML has no images, WeebCentral loads
        # chapter images dynamically via /chapters/{chapter_id}/images
        if not image_nodes:
            images_url = f"{self.BASE_URL}/chapters/{chapter_id}/images"
            try:
                validate_provider_target_url(images_url, self.allowed_domains)
                img_resp = self.client.get(images_url, headers=WEEBCENTRAL_HEADERS)
                if img_resp.status_code == 200:
                    img_tree = parse_html_tree(img_resp.text())
                    image_nodes = img_tree.find_all("img")
            except Exception:
                pass

        if not image_nodes:
            for sec in tree.find_all("section") + tree.find_all("main"):
                imgs = sec.find_all("img")
                if imgs:
                    image_nodes.extend(imgs)

        if not image_nodes:
            # Fallback to all images in document
            image_nodes = tree.find_all("img")

        pages: List[RemotePage] = []
        seen_urls = set()
        page_index = 1

        for img in image_nodes:
            src = (
                img.attrs.get("src")
                or img.attrs.get("data-src")
                or img.attrs.get("data-original")
                or ""
            ).strip()

            if not src or src.startswith("data:"):
                continue

            full_img_url = urljoin(chapter_url, src)

            # Skip icons, logos, avatars, or external tracking pixels
            lower_url = full_img_url.lower()
            if any(token in lower_url for token in ("logo", "icon", "avatar", "favicon", "google-analytics", "brand")):
                continue

            # Validate against provider's authorized domains
            try:
                validate_provider_target_url(full_img_url, self.allowed_domains)
            except Exception:
                continue

            if full_img_url in seen_urls:
                continue
            seen_urls.add(full_img_url)

            pages.append(
                RemotePage(
                    index=page_index,
                    url=full_img_url,
                    headers={"Referer": "https://weebcentral.com/"},
                )
            )
            page_index += 1

        if not pages:
            # No valid pages found in markup
            return []

        return pages

    def get_image(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """Fetch image bytes through the SSRF-protected client."""
        validate_provider_target_url(url, self.allowed_domains)
        req_headers = dict(WEEBCENTRAL_HEADERS)
        if headers:
            req_headers.update(headers)
        resp = self.client.get(url, headers=req_headers)
        if resp.status_code != 200:
            raise RuntimeError(f"WeebCentral image fetch returned HTTP {resp.status_code} for {url}")
        return resp.body

