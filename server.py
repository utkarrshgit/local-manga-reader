#!/usr/bin/env python3
"""
Local Manga & Manhwa Reader - Core Server (Phase 1)
Zero external dependencies; uses only Python standard library.
"""

import argparse
import json
import mimetypes
import os
import re
import sys
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

DEFAULT_PORT = 8000
DEFAULT_LIBRARY_DIR = os.path.expanduser("~/Manga")

IMAGE_EXTENSIONS = {".jpg", ".jpeg"}


def natural_sort_key(text: str):
    """
    Sort strings containing numbers naturally:
    e.g. ['1.jpg', '2.jpg', '10.jpg'] instead of ['1.jpg', '10.jpg', '2.jpg']
    """
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


class MangaLibrary:
    """Manages filesystem scanning and resolution of manga series, chapters, and images."""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).expanduser().resolve()

    def exists(self) -> bool:
        return self.root_path.exists() and self.root_path.is_dir()

    def _is_safe_child(self, path: Path) -> bool:
        """Prevent directory traversal attacks."""
        try:
            resolved = path.resolve()
            return self.root_path in resolved.parents or resolved == self.root_path
        except (ValueError, RuntimeError):
            return False

    def list_series(self) -> list:
        """
        Discovers all manga/manhwa series in the library root.
        Ignores hidden folders (starting with '.').
        """
        if not self.exists():
            return []

        series_list = []
        for entry in os.scandir(self.root_path):
            if entry.is_dir() and not entry.name.startswith("."):
                # Count valid chapters inside
                chapter_count = 0
                for ch in os.scandir(entry.path):
                    if ch.is_dir() and not ch.name.startswith("."):
                        chapter_count += 1

                series_list.append({
                    "name": entry.name,
                    "chapter_count": chapter_count
                })

        series_list.sort(key=lambda s: natural_sort_key(s["name"]))
        return series_list

    def list_chapters(self, series_name: str) -> list:
        """
        Discovers and naturally sorts all chapters inside a series directory.
        Ignores hidden folders (like .reader).
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return []

        chapters = []
        for entry in os.scandir(series_dir):
            if entry.is_dir() and not entry.name.startswith("."):
                # Count image files in chapter
                img_count = sum(
                    1 for f in os.scandir(entry.path)
                    if f.is_file() and Path(f.name).suffix.lower() in IMAGE_EXTENSIONS
                )
                chapters.append({
                    "name": entry.name,
                    "image_count": img_count
                })

        chapters.sort(key=lambda c: natural_sort_key(c["name"]))
        return chapters

    def list_images(self, series_name: str, chapter_name: str) -> list:
        """
        Discovers and naturally sorts all JPG images inside a chapter directory.
        """
        chapter_dir = self.root_path / series_name / chapter_name
        if not self._is_safe_child(chapter_dir) or not chapter_dir.is_dir():
            return []

        image_files = []
        for entry in os.scandir(chapter_dir):
            if entry.is_file() and not entry.name.startswith("."):
                if Path(entry.name).suffix.lower() in IMAGE_EXTENSIONS:
                    image_files.append(entry.name)

        image_files.sort(key=natural_sort_key)
        return image_files

    def get_image_path(self, series_name: str, chapter_name: str, file_name: str) -> Path | None:
        """Resolves the absolute path of an image securely."""
        target_path = self.root_path / series_name / chapter_name / file_name
        if not self._is_safe_child(target_path):
            return None
        if target_path.is_file() and target_path.suffix.lower() in IMAGE_EXTENSIONS:
            return target_path
        return None

    def get_reader_data(self, series_name: str) -> dict | None:
        """
        Retrieves reader data (bookmarks and progress) for a given series.
        Returns default dict if file does not exist or is malformed.
        Returns None if series_name is invalid or unsafe.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        default_data = {
            "progress": {},
            "bookmarks": []
        }

        reader_file = series_dir / ".reader" / "reader_data.json"
        if not reader_file.is_file():
            return default_data

        try:
            content = reader_file.read_text(encoding="utf-8")
            data = json.loads(content)
            if not isinstance(data, dict):
                return default_data

            progress = data.get("progress")
            if not isinstance(progress, dict):
                progress = {}

            bookmarks = data.get("bookmarks")
            if not isinstance(bookmarks, list):
                bookmarks = []

            return {
                "progress": progress,
                "bookmarks": bookmarks
            }
        except Exception:
            return default_data

    def save_reader_data(self, series_name: str, data: dict) -> bool:
        """
        Saves reader data for a series inside <Series>/.reader/reader_data.json.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return False

        reader_dir = series_dir / ".reader"
        reader_dir.mkdir(parents=True, exist_ok=True)
        reader_file = reader_dir / "reader_data.json"
        temp_file = reader_dir / "reader_data.json.tmp"

        clean_data = {
            "progress": data.get("progress", {}),
            "bookmarks": data.get("bookmarks", [])
        }

        try:
            temp_file.write_text(json.dumps(clean_data, indent=2), encoding="utf-8")
            temp_file.replace(reader_file)
            return True
        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            return False

    def update_progress(self, series_name: str, chapter_name: str, image_name: str) -> dict | None:
        """
        Updates the last read image for a chapter in a series.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        chapter_dir = series_dir / chapter_name
        if not self._is_safe_child(chapter_dir) or not chapter_dir.is_dir():
            return None

        # Validate image filename (must not contain path separators)
        if not image_name or "/" in image_name or "\\" in image_name or ".." in image_name:
            return None

        data = self.get_reader_data(series_name)
        if data is None:
            return None

        data["progress"][chapter_name] = image_name
        if self.save_reader_data(series_name, data):
            return data
        return None

    def toggle_bookmark(self, series_name: str, chapter_name: str, bookmarked: bool | None = None) -> dict | None:
        """
        Adds, removes, or toggles bookmark for a chapter in a series.
        """
        series_dir = self.root_path / series_name
        if not self._is_safe_child(series_dir) or not series_dir.is_dir():
            return None

        chapter_dir = series_dir / chapter_name
        if not self._is_safe_child(chapter_dir) or not chapter_dir.is_dir():
            return None

        data = self.get_reader_data(series_name)
        if data is None:
            return None

        bookmarks = set(data.get("bookmarks", []))
        if bookmarked is None:
            if chapter_name in bookmarks:
                bookmarks.remove(chapter_name)
            else:
                bookmarks.add(chapter_name)
        elif bookmarked:
            bookmarks.add(chapter_name)
        else:
            bookmarks.discard(chapter_name)

        data["bookmarks"] = sorted(list(bookmarks), key=natural_sort_key)
        if self.save_reader_data(series_name, data):
            return data
        return None


class MangaRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for serving manga API endpoints and static assets."""

    library: MangaLibrary
    static_dir: Path

    def _send_json(self, data, status: int = HTTPStatus.OK):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message: str, status: int = HTTPStatus.NOT_FOUND):
        self._send_json({"error": message}, status=status)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Helper to get single query parameter
        def get_param(name: str):
            vals = query.get(name)
            return vals[0] if vals else None

        # 1. API: List all series
        if path == "/api/series":
            series = self.library.list_series()
            self._send_json({
                "library_path": str(self.library.root_path),
                "series_count": len(series),
                "series": series
            })
            return

        # 2. API: List chapters for a series (/api/chapters?series=...)
        if path == "/api/chapters":
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required query parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            chapters = self.library.list_chapters(series_name)
            self._send_json({
                "series": series_name,
                "chapter_count": len(chapters),
                "chapters": chapters
            })
            return

        # 3. API: List images in a chapter (/api/images?series=...&chapter=...)
        if path == "/api/images":
            series_name = get_param("series")
            chapter_name = get_param("chapter")
            if not series_name or not chapter_name:
                self._send_error("Missing required query parameters: 'series' and 'chapter'", HTTPStatus.BAD_REQUEST)
                return

            images = self.library.list_images(series_name, chapter_name)
            # Build image URLs for convenient frontend consumption
            image_items = [
                {
                    "filename": img,
                    "url": f"/api/image-file?series={unquote(series_name)}&chapter={unquote(chapter_name)}&file={img}"
                }
                for img in images
            ]
            self._send_json({
                "series": series_name,
                "chapter": chapter_name,
                "image_count": len(image_items),
                "images": image_items
            })
            return

        # 4. API: Serve single image file (/api/image-file?series=...&chapter=...&file=...)
        if path == "/api/image-file":
            series_name = get_param("series")
            chapter_name = get_param("chapter")
            file_name = get_param("file")

            if not series_name or not chapter_name or not file_name:
                self._send_error("Missing required query parameters: 'series', 'chapter', 'file'", HTTPStatus.BAD_REQUEST)
                return

            image_path = self.library.get_image_path(series_name, chapter_name, file_name)
            if not image_path:
                self._send_error(f"Image not found: {file_name}", HTTPStatus.NOT_FOUND)
                return

            try:
                mime_type, _ = mimetypes.guess_type(str(image_path))
                if not mime_type:
                    mime_type = "image/jpeg"

                file_size = image_path.stat().st_size
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()

                with open(image_path, "rb") as f:
                    # Stream in 64KB chunks to keep memory usage minimal
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # 5. API: Get reader data (bookmarks and progress) for a series (/api/reader-data?series=...)
        if path == "/api/reader-data":
            series_name = get_param("series")
            if not series_name:
                self._send_error("Missing required query parameter: 'series'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.get_reader_data(series_name)
            if data is None:
                self._send_error(f"Series not found or invalid: {series_name}", HTTPStatus.NOT_FOUND)
                return

            self._send_json({
                "series": series_name,
                "progress": data["progress"],
                "bookmarks": data["bookmarks"]
            })
            return

        # 6. Static Assets (index.html, style.css, app.js)
        clean_path = path.lstrip("/")
        if clean_path.startswith("static/"):
            clean_path = clean_path[len("static/"):]
        if not clean_path:
            clean_path = "index.html"

        candidate_file = (self.static_dir / clean_path).resolve()
        # Verify candidate_file is strictly within static_dir
        if (self.static_dir in candidate_file.parents or candidate_file == self.static_dir) and candidate_file.is_file():
            mime_type, _ = mimetypes.guess_type(str(candidate_file))
            if not mime_type:
                mime_type = "text/plain"

            content_type = f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type or "json" in mime_type else mime_type
            data = candidate_file.read_bytes()

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return

        # 7. Status / Health Check endpoint
        if path == "/api/status":
            self._send_json({
                "status": "online",
                "app": "Local Manga Reader (Phase 4)",
                "library_path": str(self.library.root_path),
                "library_exists": self.library.exists(),
                "endpoints": [
                    "/api/series",
                    "/api/chapters?series=<series_name>",
                    "/api/images?series=<series_name>&chapter=<chapter_name>",
                    "/api/image-file?series=<series_name>&chapter=<chapter_name>&file=<filename>",
                    "/api/reader-data?series=<series_name>",
                    "POST /api/progress",
                    "POST /api/bookmark"
                ]
            })
            return

        # Default 404
        self._send_error("Endpoint not found", HTTPStatus.NOT_FOUND)

    def _read_json_body(self) -> dict | None:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return None
            body_bytes = self.rfile.read(content_length)
            data = json.loads(body_bytes.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 1. API: Update reading progress (/api/progress)
        if path == "/api/progress":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            chapter = body.get("chapter")
            image = body.get("image")

            if not series or not chapter or not image:
                self._send_error("Missing required fields: 'series', 'chapter', 'image'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.update_progress(series, chapter, image)
            if data is None:
                self._send_error("Invalid series, chapter, or image filename", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "chapter": chapter,
                "progress": data["progress"],
                "bookmarks": data["bookmarks"]
            })
            return

        # 2. API: Toggle chapter bookmark (/api/bookmark)
        if path == "/api/bookmark":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            chapter = body.get("chapter")
            bookmarked = body.get("bookmarked")

            if not series or not chapter:
                self._send_error("Missing required fields: 'series', 'chapter'", HTTPStatus.BAD_REQUEST)
                return

            data = self.library.toggle_bookmark(series, chapter, bookmarked)
            if data is None:
                self._send_error("Invalid series or chapter name", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "chapter": chapter,
                "bookmarked": chapter in data["bookmarks"],
                "progress": data["progress"],
                "bookmarks": data["bookmarks"]
            })
            return

        # 3. API: Unified reader data endpoint (/api/reader-data)
        if path == "/api/reader-data":
            body = self._read_json_body()
            if not body:
                self._send_error("Invalid or missing JSON body", HTTPStatus.BAD_REQUEST)
                return

            series = body.get("series")
            chapter = body.get("chapter")
            action = body.get("action")

            if not series or not chapter:
                self._send_error("Missing required fields: 'series', 'chapter'", HTTPStatus.BAD_REQUEST)
                return

            if action == "progress" or "image" in body:
                image = body.get("image")
                if not image:
                    self._send_error("Missing required field: 'image'", HTTPStatus.BAD_REQUEST)
                    return
                data = self.library.update_progress(series, chapter, image)
            elif action == "bookmark" or "bookmarked" in body:
                bookmarked = body.get("bookmarked")
                data = self.library.toggle_bookmark(series, chapter, bookmarked)
            else:
                self._send_error("Unrecognized action or missing payload in /api/reader-data", HTTPStatus.BAD_REQUEST)
                return

            if data is None:
                self._send_error("Failed to update reader data (invalid input)", HTTPStatus.BAD_REQUEST)
                return

            self._send_json({
                "success": True,
                "series": series,
                "progress": data["progress"],
                "bookmarks": data["bookmarks"]
            })
            return

        self._send_error("Endpoint not found", HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Custom concise logging format."""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def run_server(library_dir: str, port: int = DEFAULT_PORT):
    library = MangaLibrary(library_dir)
    print("=" * 60)
    print("  Local Manga & Manhwa Reader - Core Server (Phase 1)")
    print("=" * 60)
    print(f"Library Directory : {library.root_path}")
    print(f"Directory Exists  : {'Yes' if library.exists() else 'No (directory will be scanned once created)'}")
    print(f"Server URL        : http://localhost:{port}")
    print("=" * 60)
    print("Available API endpoints:")
    print(f"  • Status check   : http://localhost:{port}/api/status")
    print(f"  • Series list    : http://localhost:{port}/api/series")
    print(f"  • Chapters list  : http://localhost:{port}/api/chapters?series=<series_name>")
    print(f"  • Images list    : http://localhost:{port}/api/images?series=<series_name>&chapter=<chapter_name>")
    print("=" * 60)
    print("Press Ctrl+C to stop the server.\n")

    MangaRequestHandler.library = library
    MangaRequestHandler.static_dir = Path(__file__).parent / "static"

    server = HTTPServer(("127.0.0.1", port), MangaRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(
        description="Local web-based manga/manhwa reader server (Phase 1)"
    )
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default=DEFAULT_LIBRARY_DIR,
        help=f"Path to your manga library folder (default: {DEFAULT_LIBRARY_DIR})"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind the HTTP server to (default: {DEFAULT_PORT})"
    )
    args = parser.parse_args()
    run_server(library_dir=args.dir, port=args.port)


if __name__ == "__main__":
    main()
