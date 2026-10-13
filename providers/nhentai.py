"""
providers/nhentai.py - nhentai remote manga/gallery provider implementation.

Implements the BaseProvider interface for nhentai (https://nhentai.net) using
the existing SSRF-protected SecureHttpClient and zero external dependencies.

Observed Website Structure:
- Gallery URL: https://nhentai.net/g/{gallery_id}/ or /g/{gallery_id}
- Page View URL: https://nhentai.net/g/{gallery_id}/{page_number}/
- JSON API Endpoint: https://nhentai.net/api/gallery/{gallery_id}
- Canonical Identifier: remote:nhentai:{gallery_id}
- Media / CDN Domains:
  - nhentai.net (primary web pages and JSON API)
  - i.nhentai.net, i1.nhentai.net, i2.nhentai.net, i3.nhentai.net, i4.nhentai.net, i5.nhentai.net, i7.nhentai.net (full-resolution page images)
  - t.nhentai.net, t1.nhentai.net, t2.nhentai.net, t3.nhentai.net, t4.nhentai.net, t5.nhentai.net, t7.nhentai.net (cover & page thumbnails)
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from providers.base import BaseProvider, RemoteChapter, RemotePage, RemoteSeries
from providers.security import (
    DisallowedHostError,
    InvalidSchemeError,
    SSRFSecurityError,
    SecureHttpClient,
    SecurityPolicy,
    validate_provider_target_url,
)


NHENTAI_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://nhentai.net/",
}

# Image type shorthand code to file extension mapping used by nhentai API
IMAGE_TYPE_MAP: Dict[str, str] = {
    "j": "jpg",
    "p": "png",
    "g": "gif",
    "w": "webp",
    "jpg": "jpg",
    "jpeg": "jpg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
}


class HTMLTagNode:
    """Lightweight representation of an HTML node parsed by MiniHTMLTreeParser."""

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
                elif attr_val is not None:
                    if an == "class":
                        classes = child.attrs[an].split()
                        if attr_val.lower() not in [c.lower() for c in classes]:
                            match = False
                    elif child.attrs[an] != attr_val:
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


class NhentaiProvider(BaseProvider):
    """
    Remote provider for nhentai (https://nhentai.net).

    Enforces strict HTTPS and an explicit, minimal outbound domain allowlist
    covering only verified gallery and image hosting endpoints.
    """

    id = "nhentai"
    name = "nhentai"
    supported_url_types = "Gallery URL"
    url_pattern = "nhentai.net/g/…"
    is_public = True

    # Explicit minimal allowlist of verified nhentai hostnames
    allowed_domains = (
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
    )

    BASE_URL = "https://nhentai.net"

    def __init__(
        self,
        client: Optional[SecureHttpClient] = None,
        timeout: float = 12.0,
    ) -> None:
        self.policy = SecurityPolicy(allowed_hosts=self.allowed_domains)
        self.client = (
            client
            if client is not None
            else SecureHttpClient(policy=self.policy, timeout=timeout)
        )
        self.timeout = float(timeout)

    def can_handle_url(self, url: str) -> bool:
        """Check whether this provider can resolve and handle the given URL."""
        if not url or not isinstance(url, str):
            return False
        s = url.strip()

        # Canonical remote identifier: remote:nhentai:<id>
        if s.startswith("remote:nhentai:"):
            tail = s[len("remote:nhentai:") :].strip()
            return bool(tail and tail.isdigit())

        # URL validation
        try:
            parsed = urlsplit(s)
            if parsed.scheme.lower() != "https":
                return False
            host = (parsed.hostname or "").lower()
            if not self.policy.match_hostname(host):
                return False
            # Path must start with /g/<digits>, /api/gallery/<digits>, or /api/v2/galleries/<digits>
            path = parsed.path or ""
            return bool(re.match(r"^/(?:g|api/gallery|api/v2/galleries)/\d+", path))
        except Exception:
            return False

    def _extract_gallery_id(self, url_or_id: str) -> str:
        """
        Extract numeric gallery identifier from a URL, canonical identifier, or raw ID.

        Raises:
            ValueError: If identifier is missing, malformed, or invalid.
        """
        if not url_or_id or not isinstance(url_or_id, str):
            raise ValueError("Gallery identifier must be a non-empty string.")

        s = url_or_id.strip()
        if s.startswith("remote:nhentai:"):
            raw_id = s[len("remote:nhentai:") :].strip()
            if not raw_id or not raw_id.isdigit():
                raise ValueError(f"Invalid gallery ID in canonical identifier: {url_or_id}")
            return raw_id

        if "://" in s:
            parsed = self.policy.validate_url(s)
            path = parsed.path or ""
            m = re.match(r"^/(?:g|api/gallery|api/v2/galleries)/(\d+)", path)
            if m:
                return m.group(1)
            raise ValueError(f"URL does not contain a valid nhentai gallery path: {s}")

        clean = s.strip("/")
        if not clean or not clean.isdigit():
            raise ValueError(f"Invalid nhentai gallery identifier: {url_or_id}")
        return clean

    # Alias to maintain symmetry with RemoteReaderService._normalize_series_key
    _extract_series_id = _extract_gallery_id

    def get_series(self, url_or_id: str) -> RemoteSeries:
        """
        Fetch remote series metadata for an nhentai gallery.

        Treats the gallery as one readable remote item with its ordered pages.
        """
        gallery_id = self._extract_gallery_id(url_or_id)
        gallery_url = f"{self.BASE_URL}/g/{gallery_id}/"

        # 1. Primary strategy: Query official public API v2 endpoint.
        # nhentai's public API v2 provides structured gallery metadata and image paths
        # without triggering Cloudflare HTML challenges.
        api_v2_url = f"{self.BASE_URL}/api/v2/galleries/{gallery_id}"
        try:
            api_v2_resp = self.client.get(api_v2_url, headers=NHENTAI_HEADERS)
            if api_v2_resp.status_code == 200:
                try:
                    data = json.loads(api_v2_resp.text())
                    if isinstance(data, dict) and ("pages" in data or "images" in data or "id" in data):
                        return self._build_series_from_json(gallery_id, gallery_url, data)
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Fallback strategy: Query gallery HTML page (/g/{gallery_id}/)
        resp = self.client.get(gallery_url, headers=NHENTAI_HEADERS)
        if resp.status_code == 404:
            raise RuntimeError(f"nhentai gallery not found (HTTP 404) for {gallery_url}")
        if resp.status_code in (403, 503):
            raise RuntimeError(
                f"nhentai request blocked or rate-limited (HTTP {resp.status_code}) for {gallery_url}"
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"nhentai gallery request returned HTTP {resp.status_code} for {gallery_url}"
            )

        body_text = resp.text()

        # Check if the response body is raw JSON (e.g. from /api/gallery/)
        content_type = resp.headers.get("content-type", "").lower()
        if "application/json" in content_type or body_text.strip().startswith("{"):
            try:
                data = json.loads(body_text)
                if isinstance(data, dict) and ("images" in data or "pages" in data):
                    return self._build_series_from_json(gallery_id, gallery_url, data)
            except Exception:
                pass

        # Check for embedded window._gallery script variable in HTML
        embedded_json = self._extract_embedded_gallery_json(body_text)
        if embedded_json:
            return self._build_series_from_json(gallery_id, gallery_url, embedded_json)

        # Fallback: Parse HTML document via DOM tree parser
        tree = parse_html_tree(body_text)
        return self._build_series_from_html_tree(gallery_id, gallery_url, tree)

    def _extract_embedded_gallery_json(self, html_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract embedded JSON gallery object from script tags.

        nhentai embeds gallery data in scripts as:
        window._gallery = JSON.parse("{\"id\": ...}");
        or:
        window._gallery = {...};
        """
        # Case A: window._gallery = JSON.parse("...");
        match_parse_double = re.search(
            r'window\._gallery\s*=\s*JSON\.parse\(\s*(".*?")\s*\);',
            html_text,
            re.DOTALL,
        )
        if match_parse_double:
            try:
                inner_str = json.loads(match_parse_double.group(1))
                parsed = json.loads(inner_str)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        # Case B: window._gallery = JSON.parse('...');
        match_parse_single = re.search(
            r"window\._gallery\s*=\s*JSON\.parse\(\s*('(?:\\.|[^'])*')\s*\);",
            html_text,
            re.DOTALL,
        )
        if match_parse_single:
            try:
                # Wrap single-quoted string safely into JSON string syntax
                raw = match_parse_single.group(1)[1:-1]
                # Unescape single quotes and re-parse
                unescaped = raw.replace("\\'", "'")
                parsed = json.loads(unescaped)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        # Case C: window._gallery = { ... };
        match_literal = re.search(
            r"window\._gallery\s*=\s*(\{.*?\})\s*;",
            html_text,
            re.DOTALL,
        )
        if match_literal:
            try:
                parsed = json.loads(match_literal.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        return None

    def _build_series_from_json(
        self,
        gallery_id: str,
        gallery_url: str,
        data: Dict[str, Any],
    ) -> RemoteSeries:
        """Construct normalized RemoteSeries from an nhentai gallery dictionary."""
        media_id = str(data.get("media_id") or gallery_id)
        title_dict = data.get("title") if isinstance(data.get("title"), dict) else {}

        def _clean_str(v: Any) -> str:
            return str(v).strip() if v is not None else ""

        english_title = _clean_str(title_dict.get("english"))
        japanese_title = _clean_str(title_dict.get("japanese"))
        pretty_title = _clean_str(title_dict.get("pretty"))

        # Primary title preference: English -> Pretty -> Japanese -> Fallback
        primary_title = english_title or pretty_title or japanese_title or f"Gallery {gallery_id}"

        # Alternate title: Japanese or Pretty when distinct from primary
        alternate_title: Optional[str] = None
        if japanese_title and japanese_title != primary_title:
            alternate_title = japanese_title
        elif pretty_title and pretty_title != primary_title:
            alternate_title = pretty_title

        # Cover image URL
        cover_url: Optional[str] = None
        images_dict = data.get("images") if isinstance(data.get("images"), dict) else {}

        # 1. Check API v2 cover / thumbnail path
        v2_cover = data.get("cover") if isinstance(data.get("cover"), dict) else {}
        v2_thumb = data.get("thumbnail") if isinstance(data.get("thumbnail"), dict) else {}
        cover_path = v2_cover.get("path") or v2_thumb.get("path")

        if cover_path and isinstance(cover_path, str):
            c_path = cover_path.strip()
            if c_path.startswith("http://") or c_path.startswith("https://"):
                candidate_cover = c_path
            elif c_path.startswith("/"):
                candidate_cover = f"https://t.nhentai.net{c_path}"
            else:
                candidate_cover = f"https://t.nhentai.net/{c_path}"
            try:
                validate_provider_target_url(candidate_cover, self.allowed_domains)
                cover_url = candidate_cover
            except Exception:
                cover_url = None

        # 2. Check API v1 images.cover object
        if not cover_url:
            cover_info = (
                images_dict.get("cover")
                if isinstance(images_dict.get("cover"), dict)
                else {}
            )
            if cover_info and cover_info.get("t"):
                cover_ext = IMAGE_TYPE_MAP.get(str(cover_info["t"]).lower(), "jpg")
                candidate_cover = f"https://t.nhentai.net/galleries/{media_id}/cover.{cover_ext}"
                try:
                    validate_provider_target_url(candidate_cover, self.allowed_domains)
                    cover_url = candidate_cover
                except Exception:
                    cover_url = None

        # Tags and metadata categorization
        raw_tags = data.get("tags") if isinstance(data.get("tags"), list) else []
        artists: List[str] = []
        tags: List[str] = []
        languages: List[str] = []
        categories: List[str] = []
        characters: List[str] = []
        parodies: List[str] = []
        groups: List[str] = []

        for item in raw_tags:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            tag_type = (item.get("type") or "").strip().lower()
            if not name:
                continue

            if tag_type == "artist":
                artists.append(name)
            elif tag_type == "tag":
                tags.append(name)
            elif tag_type == "language":
                languages.append(name)
            elif tag_type == "category":
                categories.append(name)
            elif tag_type == "character":
                characters.append(name)
            elif tag_type == "parody":
                parodies.append(name)
            elif tag_type == "group":
                groups.append(name)

        author: Optional[str] = None
        if artists:
            author = ", ".join(artists)
        elif groups:
            author = ", ".join(groups)

        # Build ordered page list
        pages: List[RemotePage] = []
        v2_pages = data.get("pages") if isinstance(data.get("pages"), list) else None

        if v2_pages is not None:
            # Sort pages numerically by 'number' if present
            indexed_pages: List[Tuple[int, Dict[str, Any]]] = []
            for fallback_idx, p_entry in enumerate(v2_pages, start=1):
                if isinstance(p_entry, dict):
                    raw_num = p_entry.get("number", fallback_idx)
                    try:
                        p_num = int(raw_num)
                    except (ValueError, TypeError):
                        p_num = fallback_idx
                    indexed_pages.append((p_num, p_entry))
            indexed_pages.sort(key=lambda x: x[0])

            for order_idx, (_, page_data) in enumerate(indexed_pages, start=1):
                p_path = (page_data.get("path") or "").strip()
                if not p_path:
                    continue
                if p_path.startswith("http://") or p_path.startswith("https://"):
                    page_url = p_path
                elif p_path.startswith("/"):
                    page_url = f"https://i.nhentai.net{p_path}"
                else:
                    page_url = f"https://i.nhentai.net/{p_path}"

                # Strict validation against domain allowlist
                validate_provider_target_url(page_url, self.allowed_domains)

                pages.append(
                    RemotePage(
                        index=order_idx,
                        url=page_url,
                        headers={"Referer": gallery_url},
                    )
                )
        else:
            pages_info = (
                images_dict.get("pages")
                if isinstance(images_dict.get("pages"), list)
                else []
            )
            for idx, page_data in enumerate(pages_info, start=1):
                t_code = (
                    page_data.get("t", "j")
                    if isinstance(page_data, dict)
                    else "j"
                )
                ext = IMAGE_TYPE_MAP.get(str(t_code).lower(), "jpg")
                page_url = f"https://i.nhentai.net/galleries/{media_id}/{idx}.{ext}"

                # Strict validation against domain allowlist
                validate_provider_target_url(page_url, self.allowed_domains)

                pages.append(
                    RemotePage(
                        index=idx,
                        url=page_url,
                        headers={"Referer": gallery_url},
                    )
                )

        # Single readable remote item representing the gallery
        chapter_date = str(data["upload_date"]) if data.get("upload_date") is not None else None
        chapter = RemoteChapter(
            id=gallery_id,
            title=pretty_title or primary_title,
            chapter_number=None,
            url=gallery_url,
            date=chapter_date,
            pages=pages,
            metadata={
                "gallery_id": gallery_id,
                "media_id": media_id,
                "num_pages": len(pages),
            },
        )

        return RemoteSeries(
            id=gallery_id,
            title=primary_title,
            url=gallery_url,
            cover_url=cover_url,
            backdrop_url=None,
            description=None,  # No fabricated description
            author=author,
            status=None,
            chapters=[chapter],
            metadata={
                "source": "nhentai",
                "gallery_id": gallery_id,
                "media_id": media_id,
                "alternate_title": alternate_title,
                "artists": artists,
                "tags": tags,
                "languages": languages,
                "categories": categories,
                "characters": characters,
                "parodies": parodies,
                "groups": groups,
                "num_pages": len(pages),
                "links": {"nhentai": gallery_url},
            },
        )

    def _build_series_from_html_tree(
        self,
        gallery_id: str,
        gallery_url: str,
        tree: HTMLTagNode,
    ) -> RemoteSeries:
        """Construct normalized RemoteSeries from an HTML document tree."""
        # 1. Primary title
        primary_title: Optional[str] = None
        h1 = tree.find_first("h1")
        if h1 and h1.text.strip():
            primary_title = h1.text.strip()

        if not primary_title:
            for meta in tree.find_all("meta"):
                if meta.attrs.get("property", "").lower() == "og:title":
                    cand = meta.attrs.get("content", "").strip()
                    cand = re.sub(r"\s*»\s*nhentai.*$", "", cand, flags=re.IGNORECASE).strip()
                    if cand:
                        primary_title = cand
                        break

        if not primary_title:
            title_tag = tree.find_first("title")
            if title_tag and title_tag.text.strip():
                cand = re.sub(r"\s*»\s*nhentai.*$", "", title_tag.text.strip(), flags=re.IGNORECASE).strip()
                if cand:
                    primary_title = cand

        if not primary_title:
            primary_title = f"Gallery {gallery_id}"

        # 2. Alternate title (typically h2)
        alternate_title: Optional[str] = None
        h2 = tree.find_first("h2")
        if h2 and h2.text.strip() and h2.text.strip() != primary_title:
            alternate_title = h2.text.strip()

        # 3. Cover URL
        cover_url: Optional[str] = None
        cover_div = tree.find_first(attr_name="id", attr_val="cover")
        if cover_div:
            c_img = cover_div.find_first("img")
            if c_img:
                src = c_img.attrs.get("data-src") or c_img.attrs.get("src")
                if src and not src.startswith("data:"):
                    cover_url = src.strip()

        if not cover_url:
            for meta in tree.find_all("meta"):
                if meta.attrs.get("property", "").lower() == "og:image":
                    c_src = meta.attrs.get("content", "").strip()
                    if c_src:
                        cover_url = c_src
                        break

        if cover_url:
            try:
                validate_provider_target_url(cover_url, self.allowed_domains)
            except Exception:
                cover_url = None

        # 4. Tags and author
        artists: List[str] = []
        tags: List[str] = []
        languages: List[str] = []
        categories: List[str] = []
        characters: List[str] = []
        parodies: List[str] = []
        groups: List[str] = []

        tags_section = tree.find_first(attr_name="id", attr_val="tags")
        if tags_section:
            for container in tags_section.find_all(attr_name="class", attr_val="tag-container"):
                # Determine section label (e.g. Tags:, Artists:, etc.)
                label_node = container.find_first(attr_name="class", attr_val="name")
                label_text = label_node.text.strip().lower() if label_node else ""

                for a_tag in container.find_all("a"):
                    # Tag name is inside span.name or anchor text
                    name_span = a_tag.find_first(attr_name="class", attr_val="name")
                    t_name = name_span.text.strip() if name_span else a_tag.text.strip()
                    if not t_name:
                        continue

                    # Filter out purely numeric count badges
                    t_name = re.sub(r"\s*\d+[\d,]*\s*$", "", t_name).strip()
                    if not t_name:
                        continue

                    href = a_tag.attrs.get("href", "").lower()
                    if "/artist/" in href or "artists:" in label_text:
                        artists.append(t_name)
                    elif "/tag/" in href or "tags:" in label_text:
                        tags.append(t_name)
                    elif "/language/" in href or "languages:" in label_text:
                        languages.append(t_name)
                    elif "/category/" in href or "categories:" in label_text:
                        categories.append(t_name)
                    elif "/character/" in href or "characters:" in label_text:
                        characters.append(t_name)
                    elif "/parody/" in href or "parodies:" in label_text:
                        parodies.append(t_name)
                    elif "/group/" in href or "groups:" in label_text:
                        groups.append(t_name)

        author: Optional[str] = None
        if artists:
            author = ", ".join(artists)
        elif groups:
            author = ", ".join(groups)

        # 5. Extract pages from thumbnail container
        pages: List[RemotePage] = []
        thumb_container = tree.find_first(attr_name="id", attr_val="thumbnail-container")
        thumb_imgs: List[HTMLTagNode] = []
        if thumb_container:
            thumb_imgs = thumb_container.find_all("img")
        else:
            for thumb in tree.find_all(attr_name="class", attr_val="thumb"):
                img = thumb.find_first("img")
                if img:
                    thumb_imgs.append(img)

        # Extract media ID from cover or thumbnail if possible
        media_id = gallery_id
        parsed_pages: List[Tuple[int, str]] = []

        for img in thumb_imgs:
            src = (img.attrs.get("data-src") or img.attrs.get("src") or "").strip()
            if not src or src.startswith("data:"):
                continue

            # Validate thumbnail origin host if absolute URL
            if "://" in src:
                try:
                    validate_provider_target_url(src, self.allowed_domains)
                except Exception:
                    continue

            # Thumb URL format: https://t.nhentai.net/galleries/{media_id}/{page}t.{ext}
            m = re.search(r"/galleries/(\d+)/(\d+)t?\.([a-zA-Z]+)", src)
            if m:
                media_id = m.group(1)
                page_num = int(m.group(2))
                ext = m.group(3).lower()
                full_page_url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
                try:
                    validate_provider_target_url(full_page_url, self.allowed_domains)
                    parsed_pages.append((page_num, full_page_url))
                except Exception:
                    continue

        # Sort pages numerically by page index
        parsed_pages.sort(key=lambda item: item[0])

        for idx, (_, p_url) in enumerate(parsed_pages, start=1):
            pages.append(
                RemotePage(
                    index=idx,
                    url=p_url,
                    headers={"Referer": gallery_url},
                )
            )

        chapter = RemoteChapter(
            id=gallery_id,
            title=primary_title,
            chapter_number=None,
            url=gallery_url,
            date=None,
            pages=pages,
            metadata={
                "gallery_id": gallery_id,
                "media_id": media_id,
                "num_pages": len(pages),
            },
        )

        return RemoteSeries(
            id=gallery_id,
            title=primary_title,
            url=gallery_url,
            cover_url=cover_url,
            backdrop_url=None,
            description=None,
            author=author,
            status=None,
            chapters=[chapter],
            metadata={
                "source": "nhentai",
                "gallery_id": gallery_id,
                "media_id": media_id,
                "alternate_title": alternate_title,
                "artists": artists,
                "tags": tags,
                "languages": languages,
                "categories": categories,
                "characters": characters,
                "parodies": parodies,
                "groups": groups,
                "num_pages": len(pages),
                "links": {"nhentai": gallery_url},
            },
        )

    def get_chapter_pages(self, chapter_url_or_id: str) -> List[RemotePage]:
        """
        Fetch normalized page URLs and headers for an nhentai gallery.
        """
        gallery_id = self._extract_gallery_id(chapter_url_or_id)
        series = self.get_series(gallery_id)
        if not series.chapters:
            return []
        return series.chapters[0].pages

    def get_image(self, url: str, headers: Optional[Dict[str, str]] = None) -> bytes:
        """Fetch image bytes through the SSRF-protected client."""
        validate_provider_target_url(url, self.allowed_domains)
        req_headers = dict(NHENTAI_HEADERS)
        if headers:
            req_headers.update(headers)
        resp = self.client.get(url, headers=req_headers)
        if resp.status_code != 200:
            raise RuntimeError(
                f"nhentai image fetch returned HTTP {resp.status_code} for {url}"
            )
        return resp.body
