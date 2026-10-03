import unittest
from pathlib import Path
import tempfile
import shutil
import json
import os
import sys
import subprocess
import time
import zipfile
from server import MangaLibrary, natural_sort_key


class TestMangaLibrary(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir)

        # Create series: "Solo Leveling" and "Berserk"
        (self.lib_path / "Solo Leveling" / "Chapter 1").mkdir(parents=True)
        (self.lib_path / "Solo Leveling" / "Chapter 2").mkdir(parents=True)
        (self.lib_path / "Solo Leveling" / "Chapter 10").mkdir(parents=True)
        (self.lib_path / "Solo Leveling" / ".reader").mkdir(parents=True)  # Should be ignored

        # Add image files to Chapter 1
        ch1 = self.lib_path / "Solo Leveling" / "Chapter 1"
        (ch1 / "1.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        (ch1 / "2.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        (ch1 / "10.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        (ch1 / ".DS_Store").write_bytes(b"dummy")  # Should be ignored
        (ch1 / "notes.txt").write_bytes(b"dummy")  # Should be ignored

        self.library = MangaLibrary(str(self.lib_path))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_natural_sort_key(self):
        items = ["10.jpg", "1.jpg", "2.jpg"]
        sorted_items = sorted(items, key=natural_sort_key)
        self.assertEqual(sorted_items, ["1.jpg", "2.jpg", "10.jpg"])

    def test_series_discovery_and_hiding_dotfiles(self):
        series = self.library.list_series()
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["name"], "Solo Leveling")
        self.assertEqual(series[0]["chapter_count"], 3)  # Chapter 1, 2, 10 (.reader ignored)

    def test_chapter_discovery_natural_sort(self):
        chapters = self.library.list_chapters("Solo Leveling")
        self.assertEqual([c["name"] for c in chapters], ["Chapter 1", "Chapter 2", "Chapter 10"])
        self.assertEqual(chapters[0]["image_count"], 3)

    def test_image_discovery_natural_sort(self):
        images = self.library.list_images("Solo Leveling", "Chapter 1")
        self.assertEqual(images, ["1.jpg", "2.jpg", "10.jpg"])

    def test_path_traversal_protection(self):
        self.assertIsNone(self.library.get_image_path("..", "..", "etc/passwd"))


class MockSocket:
    def __init__(self, data_bytes: bytes):
        import io
        self.rfile = io.BytesIO(data_bytes)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            elif "w" in mode:
                return self.wfile
        raise ValueError("Unsupported mode")

    def sendall(self, data):
        self.wfile.write(data)


class TestHTTPHandler(unittest.TestCase):
    def setUp(self):
        from server import MangaRequestHandler
        self.MangaRequestHandler = MangaRequestHandler
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir)
        ch1 = self.lib_path / "OnePiece" / "Chapter 1"
        ch1.mkdir(parents=True)
        (ch1 / "1.jpg").write_bytes(b"JPG_IMAGE_DATA_1")
        (ch1 / "10.jpg").write_bytes(b"JPG_IMAGE_DATA_10")
        (ch1 / "2.jpg").write_bytes(b"JPG_IMAGE_DATA_2")
        self.library = MangaLibrary(str(self.lib_path))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _simulate_get(self, path: str):
        raw_request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        return headers, body

    def _simulate_post(self, path: str, json_data: dict):
        body_bytes = json.dumps(json_data).encode("utf-8")
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        return headers, body

    def _simulate_post_binary(self, path: str, raw_bytes: bytes, content_type: str = "image/jpeg"):
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(raw_bytes)}\r\n\r\n"
        ).encode("utf-8") + raw_bytes
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        return headers, body

    def _simulate_delete(self, path: str):
        raw_request = (
            f"DELETE {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n\r\n"
        ).encode("utf-8")
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        return headers, body

    def test_get_series(self):
        headers, body = self._simulate_get("/api/series")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series_count"], 1)
        self.assertEqual(data["series"][0]["name"], "OnePiece")

    def test_get_chapters(self):
        headers, body = self._simulate_get("/api/chapters?series=OnePiece")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["chapters"][0]["name"], "Chapter 1")

    def test_get_images_natural_order(self):
        headers, body = self._simulate_get("/api/images?series=OnePiece&chapter=Chapter%201")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        filenames = [img["filename"] for img in data["images"]]
        self.assertEqual(filenames, ["1.jpg", "2.jpg", "10.jpg"])

    def test_get_image_file(self):
        headers, body = self._simulate_get("/api/image-file?series=OnePiece&chapter=Chapter%201&file=10.jpg")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/jpeg", headers)
        self.assertEqual(body, b"JPG_IMAGE_DATA_10")

    def test_serve_static_index(self):
        headers, body = self._simulate_get("/")
        self.assertIn("200 OK", headers)
        self.assertIn("text/html", headers)
        self.assertIn(b"<title>{ index }</title>", body)
        self.assertIn(b'href="/index-mark.svg"', body)
        # Phase 3 reader elements
        self.assertIn(b"view-reader", body)
        self.assertIn(b"reader-container", body)
        self.assertIn(b"btn-style-spaced", body)
        self.assertIn(b"btn-style-seamless", body)
        self.assertIn(b"reader-loading", body)
        self.assertIn(b"reader-empty", body)
        # Phase 4 bookmark button
        self.assertIn(b"btn-reader-bookmark", body)
        # Phase 5 fullscreen & chapter navigation
        self.assertIn(b"btn-reader-fullscreen", body)
        self.assertIn(b"btn-reader-prev", body)
        self.assertIn(b"btn-reader-next", body)
        self.assertIn(b"btn-reader-footer-prev", body)
        self.assertIn(b"btn-reader-footer-next", body)

    def test_serve_static_css(self):
        headers, body = self._simulate_get("/style.css")
        self.assertIn("200 OK", headers)
        self.assertIn("text/css", headers)
        self.assertIn(b"--bg-primary", body)
        # Utility and Phase 3 reader CSS
        self.assertIn(b".hidden", body)
        self.assertIn(b"display: none !important", body)
        self.assertIn(b"mode-spaced", body)
        self.assertIn(b"mode-seamless", body)
        self.assertIn(b"reader-image", body)
        # Phase 4 bookmark CSS
        self.assertIn(b"btn-bookmark", body)
        self.assertIn(b"badge-bookmark", body)
        # Phase 5 polish CSS
        self.assertIn(b"object-fit: contain", body)
        self.assertIn(b"btn-fullscreen", body)
        self.assertIn(b"btn-chapter-nav", body)
        self.assertIn(b"reader-chapter-pagination", body)

    def test_serve_static_index_mark_svg(self):
        headers, body = self._simulate_get("/index-mark.svg")
        self.assertIn("200 OK", headers)
        self.assertIn("image/svg+xml", headers)
        self.assertIn(b"<svg", body)
        self.assertIn(b"viewBox", body)

    def test_serve_static_js(self):
        headers, body = self._simulate_get("/app.js")
        self.assertIn("200 OK", headers)
        self.assertIn("javascript", headers)
        self.assertIn(b"loadLibrary", body)
        # Phase 3 reader JS
        self.assertIn(b"loadReader", body)
        self.assertIn(b"applyReadingStyle", body)
        self.assertIn(b"dataset.filename", body)
        self.assertIn(b"readerLoading", body)
        self.assertIn(b"readerEmpty", body)
        # Phase 4 reader JS
        self.assertIn(b"fetchReaderData", body)
        self.assertIn(b"toggleBookmark", body)
        self.assertIn(b"btnReaderBookmark", body)
        # Phase 5 reader JS
        self.assertIn(b"toggleFullscreen", body)
        self.assertIn(b"updateChapterNavButtons", body)
        self.assertIn(b"ArrowLeft", body)
        self.assertIn(b"ArrowRight", body)

    def test_api_status(self):
        headers, body = self._simulate_get("/api/status")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "online")

    # ==========================================
    # Phase 4 Specific Tests
    # ==========================================

    def test_reader_data_endpoint_default_when_missing(self):
        """1. Reader data endpoint returns default data when no file exists."""
        headers, body = self._simulate_get("/api/reader-data?series=OnePiece")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["series"], "OnePiece")
        self.assertEqual(data["progress"], {})
        self.assertEqual(data["bookmarks"], [])

    def test_reader_data_can_be_saved_and_retrieved(self):
        """2. Reader data can be saved and retrieved."""
        payload = {
            "progress": {"Chapter 1": "2.jpg"},
            "bookmarks": ["Chapter 1"]
        }
        success = self.library.save_reader_data("OnePiece", payload)
        self.assertTrue(success)

        headers, body = self._simulate_get("/api/reader-data?series=OnePiece")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["progress"], {"Chapter 1": "2.jpg"})
        self.assertEqual(data["bookmarks"], ["Chapter 1"])

    def test_progress_stored_by_chapter_and_filename(self):
        """3. Progress is stored by chapter and filename."""
        headers, body = self._simulate_post("/api/progress", {
            "series": "OnePiece",
            "chapter": "Chapter 1",
            "image": "10.jpg"
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertTrue(resp["success"])
        self.assertEqual(resp["progress"]["Chapter 1"], "10.jpg")

        # Verify on filesystem via GET
        headers, body = self._simulate_get("/api/reader-data?series=OnePiece")
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["progress"]["Chapter 1"], "10.jpg")

    def test_bookmark_can_be_added_and_removed(self):
        """4. Bookmarks can be added and removed."""
        # Add bookmark
        headers, body = self._simulate_post("/api/bookmark", {
            "series": "OnePiece",
            "chapter": "Chapter 1",
            "bookmarked": True
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertTrue(resp["bookmarked"])
        self.assertIn("Chapter 1", resp["bookmarks"])

        # Remove bookmark
        headers, body = self._simulate_post("/api/bookmark", {
            "series": "OnePiece",
            "chapter": "Chapter 1",
            "bookmarked": False
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertFalse(resp["bookmarked"])
        self.assertNotIn("Chapter 1", resp["bookmarks"])

    def test_multiple_chapters_independent_progress(self):
        """5. Multiple chapters can have independent progress."""
        # Create Chapter 2
        ch2 = self.lib_path / "OnePiece" / "Chapter 2"
        ch2.mkdir(parents=True, exist_ok=True)
        (ch2 / "01.jpg").write_bytes(b"dummy")

        self.library.update_progress("OnePiece", "Chapter 1", "2.jpg")
        self.library.update_progress("OnePiece", "Chapter 2", "01.jpg")

        data = self.library.get_reader_data("OnePiece")
        self.assertEqual(data["progress"]["Chapter 1"], "2.jpg")
        self.assertEqual(data["progress"]["Chapter 2"], "01.jpg")

    def test_multiple_chapters_bookmarked(self):
        """6. Multiple chapters can be bookmarked."""
        ch2 = self.lib_path / "OnePiece" / "Chapter 2"
        ch2.mkdir(parents=True, exist_ok=True)
        (ch2 / "01.jpg").write_bytes(b"dummy")

        self.library.toggle_bookmark("OnePiece", "Chapter 1", True)
        self.library.toggle_bookmark("OnePiece", "Chapter 2", True)

        data = self.library.get_reader_data("OnePiece")
        self.assertEqual(data["bookmarks"], ["Chapter 1", "Chapter 2"])

    def test_missing_reader_data_handled_correctly(self):
        """7. Missing .reader/reader_data.json is handled correctly."""
        reader_file = self.lib_path / "OnePiece" / ".reader" / "reader_data.json"
        if reader_file.exists():
            reader_file.unlink()

        data = self.library.get_reader_data("OnePiece")
        self.assertEqual(data, {"progress": {}, "bookmarks": [], "reader": {"style": "spaced"}})

    def test_malformed_json_handled_gracefully(self):
        """8. Malformed JSON is handled gracefully."""
        reader_dir = self.lib_path / "OnePiece" / ".reader"
        reader_dir.mkdir(parents=True, exist_ok=True)
        (reader_dir / "reader_data.json").write_text("{corrupt-json", encoding="utf-8")

        data = self.library.get_reader_data("OnePiece")
        self.assertEqual(data, {"progress": {}, "bookmarks": [], "reader": {"style": "spaced"}})

    def test_path_traversal_and_invalid_inputs_rejected(self):
        """9. Path traversal / invalid series or chapter input is rejected."""
        # Unsafe GET
        headers, _ = self._simulate_get("/api/reader-data?series=../../etc")
        self.assertIn("404", headers)

        # Unsafe progress series
        headers, _ = self._simulate_post("/api/progress", {
            "series": "../../etc",
            "chapter": "Chapter 1",
            "image": "1.jpg"
        })
        self.assertIn("400", headers)

        # Unsafe progress image filename
        headers, _ = self._simulate_post("/api/progress", {
            "series": "OnePiece",
            "chapter": "Chapter 1",
            "image": "../../../etc/passwd"
        })
        self.assertIn("400", headers)

        # Unsafe bookmark series
        headers, _ = self._simulate_post("/api/bookmark", {
            "series": "../OnePiece",
            "chapter": "Chapter 1",
            "bookmarked": True
        })
        self.assertIn("400", headers)


class TestPhase6Features(unittest.TestCase):
    def setUp(self):
        from server import MangaRequestHandler
        self.MangaRequestHandler = MangaRequestHandler
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir).resolve()
        self.library = MangaLibrary(str(self.lib_path))
        self.MangaRequestHandler.library = self.library

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def _simulate_get(self, path: str):
        raw_request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

        CustomHandler.library = getattr(self.MangaRequestHandler, "library", self.library)
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)
        self.library = CustomHandler.library

        output = sock.wfile.getvalue()
        parts = output.split(b"\r\n\r\n", 1)
        headers = parts[0].decode("utf-8", errors="replace")
        body = parts[1] if len(parts) > 1 else b""
        return headers, body

    def _simulate_post(self, path: str, json_body: dict):
        body_bytes = json.dumps(json_body).encode("utf-8")
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

        CustomHandler.library = getattr(self.MangaRequestHandler, "library", self.library)
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)
        self.library = CustomHandler.library

        output = sock.wfile.getvalue()
        parts = output.split(b"\r\n\r\n", 1)
        headers = parts[0].decode("utf-8", errors="replace")
        body = parts[1] if len(parts) > 1 else b""
        return headers, body

    def _simulate_post_binary(self, path: str, raw_bytes: bytes, content_type: str = "image/jpeg"):
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(raw_bytes)}\r\n\r\n"
        ).encode("utf-8") + raw_bytes
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        output = sock.wfile.getvalue()
        parts = output.split(b"\r\n\r\n", 1)
        headers = parts[0].decode("utf-8", errors="replace")
        body = parts[1] if len(parts) > 1 else b""
        return headers, body

    def _simulate_delete(self, path: str):
        raw_request = (
            f"DELETE {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n\r\n"
        ).encode("utf-8")
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        output = sock.wfile.getvalue()
        parts = output.split(b"\r\n\r\n", 1)
        headers = parts[0].decode("utf-8", errors="replace")
        body = parts[1] if len(parts) > 1 else b""
        return headers, body

    def test_series_cover_jpg_priority(self):
        """1. <SeriesDirectory>/cover.jpg is used when it exists."""
        series_dir = self.lib_path / "Solo Leveling"
        ch1 = series_dir / "Chapter 1"
        ch1.mkdir(parents=True)
        (ch1 / "1.jpg").write_bytes(b"PAGE_1")
        cover_file = series_dir / "cover.jpg"
        cover_file.write_bytes(b"DIRECT_COVER")

        cover_path = self.library.get_cover_path("Solo Leveling")
        self.assertEqual(cover_path, cover_file)

    def test_series_cover_fallback_to_first_chapter_first_image(self):
        """2. When cover.jpg does NOT exist, use first image from first chapter."""
        series_dir = self.lib_path / "Solo Leveling"
        ch1 = series_dir / "Chapter 1"
        ch1.mkdir(parents=True)
        img1 = ch1 / "1.jpg"
        img1.write_bytes(b"PAGE_1")

        cover_path = self.library.get_cover_path("Solo Leveling")
        self.assertEqual(cover_path, img1)

    def test_series_cover_fallback_respects_natural_sorting(self):
        """3. Fallback respects natural sorting of chapters and images."""
        series_dir = self.lib_path / "Naruto"
        # Create Chapter 10 first, then Chapter 2
        (series_dir / "Chapter 10").mkdir(parents=True)
        ((series_dir / "Chapter 10") / "1.jpg").write_bytes(b"CH10_PAGE1")

        ch2 = series_dir / "Chapter 2"
        ch2.mkdir(parents=True)
        (ch2 / "10.jpg").write_bytes(b"CH2_PAGE10")
        (ch2 / "2.jpg").write_bytes(b"CH2_PAGE2")
        (ch2 / "1.jpg").write_bytes(b"CH2_PAGE1")

        # Natural sort: Chapter 2 comes before Chapter 10
        # In Chapter 2: 1.jpg comes before 2.jpg and 10.jpg
        cover_path = self.library.get_cover_path("Naruto")
        self.assertEqual(cover_path, ch2 / "1.jpg")

    def test_series_cover_empty_series_returns_none(self):
        """4. Series with no cover.jpg and no images returns None."""
        (self.lib_path / "EmptySeries").mkdir()
        cover_path = self.library.get_cover_path("EmptySeries")
        self.assertIsNone(cover_path)

    def test_cover_jpg_not_counted_as_chapter(self):
        """5. cover.jpg is NOT counted as a chapter in list_chapters."""
        series_dir = self.lib_path / "Berserk"
        series_dir.mkdir(parents=True)
        (series_dir / "cover.jpg").write_bytes(b"COVER")
        (series_dir / "Chapter 1").mkdir()
        ((series_dir / "Chapter 1") / "1.jpg").write_bytes(b"IMG")

        chapters = self.library.list_chapters("Berserk")
        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0]["name"], "Chapter 1")

    def test_cover_jpg_not_in_chapter_images(self):
        """6. cover.jpg does not appear in chapter image lists."""
        series_dir = self.lib_path / "Berserk"
        series_dir.mkdir(parents=True)
        (series_dir / "cover.jpg").write_bytes(b"COVER")
        ch1 = series_dir / "Chapter 1"
        ch1.mkdir()
        (ch1 / "1.jpg").write_bytes(b"IMG")

        images = self.library.list_images("Berserk", "Chapter 1")
        self.assertEqual(images, ["1.jpg"])
        self.assertNotIn("cover.jpg", images)

    def test_api_cover_endpoint_serves_image(self):
        """7. GET /api/cover?series=... serves the image with 200 OK."""
        series_dir = self.lib_path / "Bleach"
        series_dir.mkdir(parents=True)
        (series_dir / "cover.jpg").write_bytes(b"JPG_DATA_BLEACH")

        headers, body = self._simulate_get("/api/cover?series=Bleach")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/jpeg", headers)
        self.assertIn("Cache-Control: no-cache", headers)
        self.assertEqual(body, b"JPG_DATA_BLEACH")

    def test_api_cover_endpoint_no_cache_policy_regression(self):
        """Regression test: /api/cover uses 'no-cache' and not 'public, max-age=86400'."""
        series_dir = self.lib_path / "Bleach"
        series_dir.mkdir(parents=True, exist_ok=True)
        (series_dir / "cover.jpg").write_bytes(b"JPG_DATA_BLEACH")

        headers, _ = self._simulate_get("/api/cover?series=Bleach")
        self.assertIn("200 OK", headers)
        self.assertIn("Cache-Control: no-cache", headers)
        self.assertNotIn("public, max-age=86400", headers)
        self.assertNotIn("max-age", headers)

    def test_api_cover_endpoint_404_when_no_cover(self):
        """8. GET /api/cover?series=... returns 404 when no cover/images exist."""
        (self.lib_path / "EmptyBleach").mkdir()
        headers, body = self._simulate_get("/api/cover?series=EmptyBleach")
        self.assertIn("404", headers)

    def test_api_cover_endpoint_path_traversal_blocked(self):
        """9. Path traversal on /api/cover is blocked."""
        headers, _ = self._simulate_get("/api/cover?series=../../etc")
        self.assertIn("404", headers)

    def test_api_series_includes_cover_metadata(self):
        """10. /api/series includes has_cover and cover_url."""
        series_dir = self.lib_path / "OnePiece"
        ch1 = series_dir / "Chapter 1"
        ch1.mkdir(parents=True)
        (ch1 / "1.jpg").write_bytes(b"IMG")

        (self.lib_path / "NoCoverSeries").mkdir()

        headers, body = self._simulate_get("/api/series")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        series_map = {s["name"]: s for s in data["series"]}

        self.assertTrue(series_map["OnePiece"]["has_cover"])
        self.assertIn("/api/cover?series=OnePiece", series_map["OnePiece"]["cover_url"])

        self.assertFalse(series_map["NoCoverSeries"]["has_cover"])
        self.assertIsNone(series_map["NoCoverSeries"]["cover_url"])

    def test_reader_data_default_style_spaced(self):
        """11. Default style is 'spaced' when no reader data exists."""
        (self.lib_path / "TestSeries").mkdir()
        data = self.library.get_reader_data("TestSeries")
        self.assertEqual(data["reader"]["style"], "spaced")

    def test_reader_data_save_and_retrieve_style(self):
        """12. Style updates persist to reader_data.json and preserve progress/bookmarks."""
        series_dir = self.lib_path / "TestSeries"
        (series_dir / "Chapter 1").mkdir(parents=True)
        ((series_dir / "Chapter 1") / "1.jpg").write_bytes(b"IMG")

        # Set progress & bookmark first
        self.library.update_progress("TestSeries", "Chapter 1", "1.jpg")
        self.library.toggle_bookmark("TestSeries", "Chapter 1", True)

        # Update style
        result = self.library.update_reader_style("TestSeries", "seamless")
        self.assertIsNotNone(result)
        self.assertEqual(result["reader"]["style"], "seamless")
        self.assertEqual(result["progress"]["Chapter 1"], "1.jpg")
        self.assertEqual(result["bookmarks"], ["Chapter 1"])

        # Re-read directly from disk
        saved = self.library.get_reader_data("TestSeries")
        self.assertEqual(saved["reader"]["style"], "seamless")
        self.assertEqual(saved["progress"]["Chapter 1"], "1.jpg")
        self.assertEqual(saved["bookmarks"], ["Chapter 1"])

    def test_reader_data_invalid_style_rejected_or_fallback(self):
        """13. Invalid style rejected in update, or falls back to 'spaced' if file corrupted."""
        (self.lib_path / "TestSeries").mkdir()
        # Direct call with invalid value
        res = self.library.update_reader_style("TestSeries", "invalid_style")
        self.assertIsNone(res)

        # Corrupted reader_data.json with invalid style
        reader_dir = self.lib_path / "TestSeries" / ".reader"
        reader_dir.mkdir(parents=True, exist_ok=True)
        (reader_dir / "reader_data.json").write_text(
            json.dumps({"progress": {}, "bookmarks": [], "reader": {"style": "bogus"}}),
            encoding="utf-8"
        )
        data = self.library.get_reader_data("TestSeries")
        self.assertEqual(data["reader"]["style"], "spaced")

    def test_api_style_post_endpoint(self):
        """14. POST /api/style updates style and returns JSON response."""
        (self.lib_path / "TestSeries").mkdir()
        headers, body = self._simulate_post("/api/style", {
            "series": "TestSeries",
            "style": "seamless"
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertTrue(resp["success"])
        self.assertEqual(resp["style"], "seamless")
        self.assertEqual(resp["reader"]["style"], "seamless")

        # Verify invalid style yields 400
        headers_err, _ = self._simulate_post("/api/style", {
            "series": "TestSeries",
            "style": "invalid"
        })
        self.assertIn("400", headers_err)

    def test_series_background_priority_and_fallback(self):
        """15. Background selection priority: background.jpg -> cover.jpg -> None."""
        series_dir = self.lib_path / "HeroSeries"
        series_dir.mkdir(parents=True)
        bg_file = series_dir / "background.jpg"
        cover_file = series_dir / "cover.jpg"

        # Neither exists
        self.assertIsNone(self.library.get_background_path("HeroSeries"))

        # cover.jpg exists (fallback)
        cover_file.write_bytes(b"COVER_DATA")
        self.assertEqual(self.library.get_background_path("HeroSeries"), cover_file)

        # background.jpg exists (priority 1)
        bg_file.write_bytes(b"BACKGROUND_DATA")
        self.assertEqual(self.library.get_background_path("HeroSeries"), bg_file)

    def test_api_background_endpoint_serves_image(self):
        """16. GET /api/background?series=... serves image with 200 OK and no-cache."""
        series_dir = self.lib_path / "HeroSeries"
        series_dir.mkdir(parents=True, exist_ok=True)
        (series_dir / "background.jpg").write_bytes(b"BG_JPG_DATA")

        headers, body = self._simulate_get("/api/background?series=HeroSeries")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/jpeg", headers)
        self.assertIn("Cache-Control: no-cache", headers)
        self.assertEqual(body, b"BG_JPG_DATA")

    def test_api_background_endpoint_404_and_traversal(self):
        """17. GET /api/background 404s when not found and blocks traversal."""
        (self.lib_path / "NoBgSeries").mkdir()
        headers, _ = self._simulate_get("/api/background?series=NoBgSeries")
        self.assertIn("404", headers)

        headers, _ = self._simulate_get("/api/background?series=../../etc")
        self.assertIn("404", headers)

    def test_reader_data_summary_preservation(self):
        """18. reader_data.json preserves optional summary field safely."""
        series_dir = self.lib_path / "SummarySeries"
        series_dir.mkdir(parents=True)

        payload = {
            "summary": "An epic journey in an editorial digital reader.",
            "progress": {"Chapter 1": "1.jpg"},
            "bookmarks": ["Chapter 1"],
            "reader": {"style": "spaced"}
        }
        self.library.save_reader_data("SummarySeries", payload)

        data = self.library.get_reader_data("SummarySeries")
        self.assertEqual(data["summary"], "An epic journey in an editorial digital reader.")
        self.assertEqual(data["progress"], {"Chapter 1": "1.jpg"})
        self.assertEqual(data["bookmarks"], ["Chapter 1"])
        self.assertEqual(data["reader"]["style"], "spaced")

    # ==========================================
    # Series Metadata Feature Tests
    # ==========================================

    def test_metadata_persistence_and_retrieval(self):
        """19. Metadata (summary, author, links) persists and retrieves correctly while preserving reader state."""
        series_dir = self.lib_path / "MetaSeries"
        chapter_dir = series_dir / "Chapter 1"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        (chapter_dir / "001.jpg").write_bytes(b"DATA")

        # Set initial progress and bookmark
        self.library.update_progress("MetaSeries", "Chapter 1", "001.jpg")
        self.library.toggle_bookmark("MetaSeries", "Chapter 1", True)

        # Update metadata via library method
        links = {
            "AniList": "https://anilist.co/manga/105398",
            "MyAnimeList": "https://myanimelist.net/manga/121496",
            "MangaDex": "https://mangadex.org/title/sololeveling"
        }
        res = self.library.update_metadata(
            "MetaSeries",
            summary="A hunter rises from the weakest rank.",
            author="Chugong",
            links=links
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["summary"], "A hunter rises from the weakest rank.")
        self.assertEqual(res["author"], "Chugong")
        self.assertEqual(res["links"], links)
        # Verify reader state preserved
        self.assertEqual(res["progress"], {"Chapter 1": "001.jpg"})
        self.assertEqual(res["bookmarks"], ["Chapter 1"])

        # Check raw json file on disk
        json_file = series_dir / ".reader" / "reader_data.json"
        self.assertTrue(json_file.is_file())
        file_data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertEqual(file_data["author"], "Chugong")
        self.assertEqual(file_data["summary"], "A hunter rises from the weakest rank.")
        self.assertEqual(file_data["links"], links)
        self.assertEqual(file_data["progress"], {"Chapter 1": "001.jpg"})
        self.assertEqual(file_data["bookmarks"], ["Chapter 1"])

        # Retrieve via GET /api/reader-data
        headers, body = self._simulate_get("/api/reader-data?series=MetaSeries")
        self.assertIn("200 OK", headers)
        get_data = json.loads(body.decode("utf-8"))
        self.assertEqual(get_data["author"], "Chugong")
        self.assertEqual(get_data["summary"], "A hunter rises from the weakest rank.")
        self.assertEqual(get_data["links"], links)

    def test_metadata_endpoint_post_and_get(self):
        """20. POST /api/reader-data with action='metadata' updates metadata successfully."""
        series_dir = self.lib_path / "ApiMetaSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "series": "ApiMetaSeries",
            "action": "metadata",
            "author": "DUBU (REDICE STUDIO)",
            "summary": "10 years ago, gates connected the real world with the magic realm.",
            "links": {
                "Official": "https://tapas.io/series/solo-leveling"
            }
        }
        headers, body = self._simulate_post("/api/reader-data", payload)
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertTrue(resp["success"])
        self.assertEqual(resp["author"], "DUBU (REDICE STUDIO)")
        self.assertEqual(resp["summary"], "10 years ago, gates connected the real world with the magic realm.")
        self.assertEqual(resp["links"]["Official"], "https://tapas.io/series/solo-leveling")

        # GET check
        headers, body = self._simulate_get("/api/reader-data?series=ApiMetaSeries")
        get_data = json.loads(body.decode("utf-8"))
        self.assertEqual(get_data["author"], "DUBU (REDICE STUDIO)")
        self.assertEqual(get_data["links"]["Official"], "https://tapas.io/series/solo-leveling")

    def test_metadata_missing_fields_defaults(self):
        """21. Missing metadata fields return clean default values without crashing."""
        series_dir = self.lib_path / "BlankSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # No .reader folder exists yet
        headers, body = self._simulate_get("/api/reader-data?series=BlankSeries")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["author"], "")
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["links"], {})

        # Partial metadata saved (only author)
        self.library.update_metadata("BlankSeries", author="Solo Author")
        headers, body = self._simulate_get("/api/reader-data?series=BlankSeries")
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["author"], "Solo Author")
        self.assertEqual(data["summary"], "")
        self.assertEqual(data["links"], {})

    def test_metadata_malformed_data_validation(self):
        """22. Malformed metadata (non-string author/summary, non-dict links) is rejected with 400 Bad Request."""
        series_dir = self.lib_path / "ValidationSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Invalid author (number)
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "ValidationSeries",
            "action": "metadata",
            "author": 12345
        })
        self.assertIn("400", headers)

        # Invalid summary (boolean)
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "ValidationSeries",
            "action": "metadata",
            "summary": True
        })
        self.assertIn("400", headers)

        # Invalid links (array instead of dictionary)
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "ValidationSeries",
            "action": "metadata",
            "links": ["https://anilist.co"]
        })
        self.assertIn("400", headers)

        # Missing series name
        headers, _ = self._simulate_post("/api/reader-data", {
            "action": "metadata",
            "author": "Author"
        })
        self.assertIn("400", headers)

    def test_metadata_link_validation(self):
        """23. Link URLs must be valid HTTP/HTTPS URLs and support arbitrary labels."""
        series_dir = self.lib_path / "LinkValSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Arbitrary labels with valid http and https URLs
        valid_links = {
            "My Favorite Site": "https://example.com/manga",
            "Wiki (Community)": "http://wiki.example.org/entry",
            "Custom Platform #1": "https://platform.io/read?id=42"
        }
        headers, body = self._simulate_post("/api/reader-data", {
            "series": "LinkValSeries",
            "action": "metadata",
            "links": valid_links
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertEqual(resp["links"], valid_links)

        # Invalid protocol: ftp://
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "LinkValSeries",
            "action": "metadata",
            "links": {"FTP Link": "ftp://files.example.com"}
        })
        self.assertIn("400", headers)

        # Invalid protocol: javascript:
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "LinkValSeries",
            "action": "metadata",
            "links": {"XSS": "javascript:alert(1)"}
        })
        self.assertIn("400", headers)

        # Invalid URL: not a URL
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "LinkValSeries",
            "action": "metadata",
            "links": {"Malformed": "not_a_valid_url"}
        })
        self.assertIn("400", headers)

        # Empty label
        headers, _ = self._simulate_post("/api/reader-data", {
            "series": "LinkValSeries",
            "action": "metadata",
            "links": {"": "https://valid.com"}
        })
        self.assertIn("400", headers)

    def test_metadata_link_add_and_remove(self):
        """24. Links can be added and subsequently removed."""
        series_dir = self.lib_path / "LinkLifecycle"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Add 2 links
        headers, body = self._simulate_post("/api/reader-data", {
            "series": "LinkLifecycle",
            "action": "metadata",
            "links": {
                "Link A": "https://a.com",
                "Link B": "https://b.com"
            }
        })
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data["links"]), 2)

        # Remove Link A by saving only Link B
        headers, body = self._simulate_post("/api/reader-data", {
            "series": "LinkLifecycle",
            "action": "metadata",
            "links": {
                "Link B": "https://b.com"
            }
        })
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["links"], {"Link B": "https://b.com"})
        self.assertNotIn("Link A", data["links"])

        # Remove all links
        headers, body = self._simulate_post("/api/reader-data", {
            "series": "LinkLifecycle",
            "action": "metadata",
            "links": {}
        })
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["links"], {})

    def test_metadata_ui_static_elements(self):
        """25. Static HTML, CSS, and JS include metadata display and inline editor elements."""
        # Check index.html
        _, html_body = self._simulate_get("/")
        self.assertIn(b"btn-edit-metadata", html_body)
        self.assertIn(b"series-metadata-editor", html_body)
        self.assertIn(b"editor-author", html_body)
        self.assertIn(b"editor-summary", html_body)
        self.assertIn(b"btn-add-link", html_body)
        self.assertIn(b"btn-save-metadata", html_body)

        # Check style.css
        _, css_body = self._simulate_get("/style.css")
        self.assertIn(b"series-metadata-editor", css_body)
        self.assertIn(b"btn-edit-metadata", css_body)
        self.assertIn(b"series-link-item", css_body)

        # Check app.js
        _, js_body = self._simulate_get("/app.js")
        self.assertIn(b"renderSeriesMetadata", js_body)
        self.assertIn(b"saveSeriesMetadata", js_body)
        self.assertIn(b"openMetadataEditor", js_body)

    def test_cover_image_replacement_and_normalization(self):
        """26. Cover image upload replaces/creates cover.jpg and normalizes filename to cover.jpg."""
        series_dir = self.lib_path / "CoverNormSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Upload a valid PNG image
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 20
        headers, body = self._simulate_post_binary("/api/cover?series=CoverNormSeries", png_bytes, "image/png")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])

        # Check stored filename on disk is strictly cover.jpg
        cover_file = series_dir / "cover.jpg"
        self.assertTrue(cover_file.is_file())
        self.assertEqual(cover_file.read_bytes(), png_bytes)

        # Check GET /api/cover serves it with correct image/png Content-Type
        get_headers, get_body = self._simulate_get("/api/cover?series=CoverNormSeries")
        self.assertIn("200 OK", get_headers)
        self.assertIn("Content-Type: image/png", get_headers)
        self.assertEqual(get_body, png_bytes)

        # Upload a valid JPEG image via JSON base64
        import base64
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 20
        b64_str = base64.b64encode(jpeg_bytes).decode("ascii")
        headers, body = self._simulate_post("/api/cover", {
            "series": "CoverNormSeries",
            "image": b64_str
        })
        self.assertIn("200 OK", headers)
        self.assertEqual(cover_file.read_bytes(), jpeg_bytes)

        # Verify GET /api/cover now serves JPEG
        get_headers, get_body = self._simulate_get("/api/cover?series=CoverNormSeries")
        self.assertIn("200 OK", get_headers)
        self.assertIn("Content-Type: image/jpeg", get_headers)
        self.assertEqual(get_body, jpeg_bytes)

    def test_background_image_replacement_and_normalization(self):
        """27. Background image upload replaces/creates background.jpg and normalizes filename."""
        series_dir = self.lib_path / "BgNormSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Upload a valid WebP image
        webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 20
        headers, body = self._simulate_post_binary("/api/background?series=BgNormSeries", webp_bytes, "image/webp")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])

        # Check stored filename on disk is strictly background.jpg
        bg_file = series_dir / "background.jpg"
        self.assertTrue(bg_file.is_file())
        self.assertEqual(bg_file.read_bytes(), webp_bytes)

        # Check GET /api/background serves it with image/webp Content-Type
        get_headers, get_body = self._simulate_get("/api/background?series=BgNormSeries")
        self.assertIn("200 OK", get_headers)
        self.assertIn("Content-Type: image/webp", get_headers)
        self.assertEqual(get_body, webp_bytes)

    def test_background_image_removal_and_fallback(self):
        """28. Background removal removes background.jpg and falls back to cover."""
        series_dir = self.lib_path / "BgRemoveSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        cover_bytes = b"\xff\xd8\xff\xe0" + b"COVER_DATA" * 5
        bg_bytes = b"\xff\xd8\xff\xe0" + b"BG_DATA" * 5

        (series_dir / "cover.jpg").write_bytes(cover_bytes)
        (series_dir / "background.jpg").write_bytes(bg_bytes)

        # Check background initially serves bg_bytes
        get_headers, get_body = self._simulate_get("/api/background?series=BgRemoveSeries")
        self.assertEqual(get_body, bg_bytes)

        # Check reader-data reports has_background: True
        r_headers, r_body = self._simulate_get("/api/reader-data?series=BgRemoveSeries")
        r_data = json.loads(r_body.decode("utf-8"))
        self.assertTrue(r_data["has_background"])
        self.assertTrue(r_data["has_cover"])

        # Remove background via action=remove
        post_headers, post_body = self._simulate_post("/api/background?series=BgRemoveSeries&action=remove", {})
        self.assertIn("200 OK", post_headers)

        # Verify background.jpg is deleted
        self.assertFalse((series_dir / "background.jpg").exists())

        # Verify background GET now falls back to cover.jpg
        get_headers, get_body = self._simulate_get("/api/background?series=BgRemoveSeries")
        self.assertIn("200 OK", get_headers)
        self.assertEqual(get_body, cover_bytes)

        # Check reader-data now reports has_background: False
        r_headers, r_body = self._simulate_get("/api/reader-data?series=BgRemoveSeries")
        r_data = json.loads(r_body.decode("utf-8"))
        self.assertFalse(r_data["has_background"])

        # Put background back, then test removal via DELETE method
        (series_dir / "background.jpg").write_bytes(bg_bytes)
        self.assertTrue((series_dir / "background.jpg").exists())
        del_headers, del_body = self._simulate_delete("/api/background?series=BgRemoveSeries")
        self.assertIn("200 OK", del_headers)
        self.assertFalse((series_dir / "background.jpg").exists())

    def test_invalid_image_upload_rejected(self):
        """29. Invalid or non-image files are rejected with 400 Bad Request."""
        series_dir = self.lib_path / "InvalidUploadSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Plain text
        headers, _ = self._simulate_post_binary("/api/cover?series=InvalidUploadSeries", b"Plain text not an image", "text/plain")
        self.assertIn("400", headers)

        # Random bytes
        headers, _ = self._simulate_post_binary("/api/background?series=InvalidUploadSeries", b"\x00\x01\x02\x03\x04\x05\x06\x07", "application/octet-stream")
        self.assertIn("400", headers)

        # Empty body
        headers, _ = self._simulate_post_binary("/api/cover?series=InvalidUploadSeries", b"", "image/jpeg")
        self.assertIn("400", headers)

    def test_path_safety_and_directory_traversal(self):
        """30. Path traversal attacks on image endpoints are safely rejected."""
        valid_jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 20

        # Traversal on POST /api/cover
        headers, _ = self._simulate_post_binary("/api/cover?series=../../etc", valid_jpeg)
        self.assertIn("400", headers)

        # Traversal on POST /api/background
        headers, _ = self._simulate_post_binary("/api/background?series=../../etc", valid_jpeg)
        self.assertIn("400", headers)

        # Traversal on DELETE /api/background
        headers, _ = self._simulate_delete("/api/background?series=../../etc")
        self.assertIn("400", headers)

        # Missing series parameter
        headers, _ = self._simulate_post_binary("/api/cover", valid_jpeg)
        self.assertIn("400", headers)

        headers, _ = self._simulate_post_binary("/api/background", valid_jpeg)
        self.assertIn("400", headers)

        headers, _ = self._simulate_delete("/api/background")
        self.assertIn("400", headers)

    def test_image_cache_control_headers(self):
        """31. Cover and background responses provide strong anti-cache headers for Safari."""
        series_dir = self.lib_path / "CacheHeaderSeries"
        series_dir.mkdir(parents=True, exist_ok=True)
        (series_dir / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        (series_dir / "background.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

        headers, _ = self._simulate_get("/api/cover?series=CacheHeaderSeries")
        self.assertIn("200 OK", headers)
        self.assertIn("Cache-Control: no-cache, no-store, must-revalidate", headers)
        self.assertIn("Pragma: no-cache", headers)
        self.assertIn("Expires: 0", headers)

        headers, _ = self._simulate_get("/api/background?series=CacheHeaderSeries")
        self.assertIn("200 OK", headers)
        self.assertIn("Cache-Control: no-cache, no-store, must-revalidate", headers)
        self.assertIn("Pragma: no-cache", headers)
        self.assertIn("Expires: 0", headers)

    def test_reader_data_reports_has_cover_and_has_background(self):
        """32. /api/reader-data correctly reports has_cover and has_background flags."""
        series_dir = self.lib_path / "FlagSeries"
        series_dir.mkdir(parents=True, exist_ok=True)

        # Neither exists
        headers, body = self._simulate_get("/api/reader-data?series=FlagSeries")
        data = json.loads(body.decode("utf-8"))
        self.assertFalse(data["has_cover"])
        self.assertFalse(data["has_background"])

        # Add cover only
        (series_dir / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        headers, body = self._simulate_get("/api/reader-data?series=FlagSeries")
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["has_cover"])
        self.assertFalse(data["has_background"])

        # Add background
        (series_dir / "background.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        headers, body = self._simulate_get("/api/reader-data?series=FlagSeries")
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["has_cover"])
        self.assertTrue(data["has_background"])

    def test_image_management_ui_static_elements(self):
        """33. Static HTML, CSS, and JS include cover and background image management elements."""
        # Check index.html
        _, html_body = self._simulate_get("/")
        self.assertIn(b"editor-cover-file", html_body)
        self.assertIn(b"editor-bg-file", html_body)
        self.assertIn(b"btn-remove-bg", html_body)
        self.assertIn(b"editor-cover-preview", html_body)
        self.assertIn(b"editor-bg-preview", html_body)

        # Check style.css
        _, css_body = self._simulate_get("/style.css")
        self.assertIn(b"editor-image-section", css_body)
        self.assertIn(b"cover-preview-wrapper", css_body)
        self.assertIn(b"bg-preview-wrapper", css_body)
        self.assertIn(b"btn-file-select", css_body)
        self.assertIn(b"btn-remove-image", css_body)

        # Check app.js
        _, js_body = self._simulate_get("/app.js")
        self.assertIn(b"uploadSeriesImage", js_body)
        self.assertIn(b"removeSeriesBackground", js_body)
        self.assertIn(b"editorCoverFile", js_body)
        self.assertIn(b"editorBgFile", js_body)
        self.assertIn(b"btnRemoveBg", js_body)

    def test_external_links_under_cover_and_vertical_styling(self):
        """34. External links are placed in the cover column beneath the cover thumbnail with vertical layout."""
        _, html_body = self._simulate_get("/")
        html_str = html_body.decode("utf-8")

        # Verify series-cover-column exists and contains both cover thumb wrapper and links panel
        self.assertIn('class="series-cover-column"', html_str)
        cover_col_start = html_str.find('class="series-cover-column"')
        info_panel_start = html_str.find('class="series-info-panel"')
        self.assertLess(cover_col_start, info_panel_start)

        # Verify series-links-panel is within cover column and before info panel
        links_panel_pos = html_str.find('id="series-links-panel"')
        self.assertGreater(links_panel_pos, cover_col_start)
        self.assertLess(links_panel_pos, info_panel_start)

        # Check style.css has column display for links
        _, css_body = self._simulate_get("/style.css")
        css_str = css_body.decode("utf-8")
        self.assertIn(".series-cover-column", css_str)
        self.assertIn("flex-direction: column", css_str)

    def test_get_library_endpoint(self):
        """35. GET /api/library returns current library path, exists status, and series count."""
        headers, body = self._simulate_get("/api/library")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["library_path"], str(self.lib_path.resolve()))
        self.assertTrue(data["library_exists"])
        self.assertIsInstance(data["series_count"], int)

    def test_change_library_by_path_and_persist(self):
        """36. POST /api/library with valid path updates active library and saves config file."""
        with tempfile.TemporaryDirectory() as new_lib_dir, tempfile.TemporaryDirectory() as new_conf_dir:
            conf_file = os.path.join(new_conf_dir, "library_path")
            os.environ["LOCAL_MANGA_CONFIG_FILE"] = conf_file

            # Create a sample series in new library
            series_path = Path(new_lib_dir) / "OnePiece"
            series_path.mkdir(parents=True)
            ch1 = series_path / "Chapter 1"
            ch1.mkdir()
            (ch1 / "1.jpg").write_bytes(b"DATA")

            headers, body = self._simulate_post("/api/library", {"path": new_lib_dir})
            self.assertIn("200 OK", headers)
            res = json.loads(body.decode("utf-8"))
            self.assertTrue(res["success"])
            self.assertEqual(res["library_path"], str(Path(new_lib_dir).resolve()))
            self.assertTrue(res["library_exists"])
            self.assertEqual(res["series_count"], 1)

            # Check config file was written
            self.assertTrue(os.path.isfile(conf_file))
            with open(conf_file) as f:
                saved = f.read().strip()
            self.assertEqual(saved, str(Path(new_lib_dir).resolve()))

            # Check GET /api/series returns the new series
            _, s_body = self._simulate_get("/api/series")
            s_data = json.loads(s_body.decode("utf-8"))
            self.assertEqual(s_data["series_count"], 1)
            self.assertEqual(s_data["series"][0]["name"], "OnePiece")

            # Restore original library for remaining tests
            self.MangaRequestHandler.library = self.library
            os.environ.pop("LOCAL_MANGA_CONFIG_FILE", None)

    def test_change_library_by_native_select_and_cancellation(self):
        """37. POST /api/library with action='select' handles selection and cancellation."""
        with tempfile.TemporaryDirectory() as new_lib_dir, tempfile.TemporaryDirectory() as new_conf_dir:
            conf_file = os.path.join(new_conf_dir, "library_path")
            os.environ["LOCAL_MANGA_CONFIG_FILE"] = conf_file

            # Test selection via mock
            os.environ["MOCK_FOLDER_PICKER_RESULT"] = new_lib_dir
            headers, body = self._simulate_post("/api/library", {"action": "select"})
            self.assertIn("200 OK", headers)
            res = json.loads(body.decode("utf-8"))
            self.assertTrue(res["success"])
            self.assertEqual(res["library_path"], str(Path(new_lib_dir).resolve()))

            # Test cancellation
            os.environ["MOCK_FOLDER_PICKER_RESULT"] = ""
            headers2, body2 = self._simulate_post("/api/library", {"action": "select"})
            self.assertIn("200 OK", headers2)
            res2 = json.loads(body2.decode("utf-8"))
            self.assertFalse(res2["success"])
            self.assertTrue(res2["cancelled"])

            # Clean up env
            os.environ.pop("MOCK_FOLDER_PICKER_RESULT", None)
            os.environ.pop("LOCAL_MANGA_CONFIG_FILE", None)
            self.MangaRequestHandler.library = self.library

    def test_change_library_validation_errors(self):
        """38. POST /api/library rejects nonexistent paths, non-directories, and invalid payloads."""
        # Nonexistent path
        headers1, _ = self._simulate_post("/api/library", {"path": "/path/to/nonexistent/manga_999"})
        self.assertIn("400", headers1)

        # Path is a file, not a directory
        with tempfile.NamedTemporaryFile() as tf:
            headers2, _ = self._simulate_post("/api/library", {"path": tf.name})
            self.assertIn("400", headers2)

        # Missing path or action
        headers3, _ = self._simulate_post("/api/library", {"foo": "bar"})
        self.assertIn("400", headers3)

        # Empty path
        headers4, _ = self._simulate_post("/api/library", {"path": "   "})
        self.assertIn("400", headers4)

    def test_missing_configured_directory_reporting(self):
        """39. Missing configured library directory reports library_exists=False without crashing."""
        deleted_dir = tempfile.mkdtemp()
        shutil.rmtree(deleted_dir)

        orig_lib = self.MangaRequestHandler.library
        self.MangaRequestHandler.library = MangaLibrary(deleted_dir)
        try:
            # GET /api/library
            _, lib_body = self._simulate_get("/api/library")
            lib_data = json.loads(lib_body.decode("utf-8"))
            self.assertFalse(lib_data["library_exists"])
            self.assertEqual(lib_data["series_count"], 0)

            # GET /api/series
            _, s_body = self._simulate_get("/api/series")
            s_data = json.loads(s_body.decode("utf-8"))
            self.assertFalse(s_data["library_exists"])
            self.assertEqual(s_data["series_count"], 0)
            self.assertEqual(s_data["series"], [])
        finally:
            self.MangaRequestHandler.library = orig_lib

    def test_switching_libraries_preserves_reader_data(self):
        """40. Switching between libraries does NOT alter or delete existing reader_data.json."""
        with tempfile.TemporaryDirectory() as lib1, tempfile.TemporaryDirectory() as lib2:
            s1 = Path(lib1) / "Series1"
            s1.mkdir()
            (s1 / "Chapter 1").mkdir()
            ((s1 / "Chapter 1") / "1.jpg").write_bytes(b"IMG")

            s2 = Path(lib2) / "Series2"
            s2.mkdir()
            (s2 / "Chapter 1").mkdir()
            ((s2 / "Chapter 1") / "1.jpg").write_bytes(b"IMG")

            # Set progress in Library 1
            l1 = MangaLibrary(lib1)
            l1.update_progress("Series1", "Chapter 1", "1.jpg")
            l1.toggle_bookmark("Series1", "Chapter 1", True)

            # Switch to Library 2
            self.MangaRequestHandler.library = MangaLibrary(lib2)
            _, body2 = self._simulate_get("/api/series")
            s2_data = json.loads(body2.decode("utf-8"))
            self.assertEqual(s2_data["series"][0]["name"], "Series2")

            # Switch back to Library 1
            self.MangaRequestHandler.library = l1
            data1 = l1.get_reader_data("Series1")
            self.assertEqual(data1["progress"], {"Chapter 1": "1.jpg"})
            self.assertEqual(data1["bookmarks"], ["Chapter 1"])

            self.MangaRequestHandler.library = self.library

    def test_change_folder_ui_elements(self):
        """41. UI contains Change folder button and unavailable state elements."""
        _, html_body = self._simulate_get("/")
        html_str = html_body.decode("utf-8")
        self.assertIn('id="btn-change-folder"', html_str)
        self.assertIn('id="library-unavailable"', html_str)
        self.assertIn('id="unavailable-folder-path"', html_str)
        self.assertIn('id="btn-reconnect-folder"', html_str)

        _, css_body = self._simulate_get("/style.css")
        css_str = css_body.decode("utf-8")
        self.assertIn(".btn-change-folder", css_str)
        self.assertIn("#library-unavailable", css_str)
        self.assertIn(".unavailable-path", css_str)
        self.assertIn(".btn-reconnect-folder", css_str)

        _, js_body = self._simulate_get("/app.js")
        js_str = js_body.decode("utf-8")
        self.assertIn("changeMangaFolder", js_str)
        self.assertIn("btnChangeFolder", js_str)
        self.assertIn("libraryUnavailable", js_str)
        self.assertIn("btnReconnectFolder", js_str)


class TestMacOSLauncher(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(__file__).parent.resolve()
        self.launcher_path = self.project_dir / "start-mac.command"

    def test_launcher_attributes_and_no_hardcoded_paths(self):
        """Verify start-mac.command existence, executable permissions, and no hardcoded personal paths."""
        self.assertTrue(self.launcher_path.exists(), "start-mac.command does not exist")
        self.assertTrue(os.access(self.launcher_path, os.X_OK), "start-mac.command is not executable")

        content = self.launcher_path.read_text(encoding="utf-8")
        # Must not contain user's personal absolute paths
        self.assertNotIn("/Users/utkarshjaiswal", content)
        # Must not default to <project>/Manga
        self.assertNotIn('"$PROJECT_DIR/Manga"', content)
        self.assertNotIn("PROJECT_DIR/Manga", content)
        # Must reference osascript for native folder selection
        self.assertIn("osascript", content)
        self.assertIn("choose folder", content)

    def test_launcher_configuration_lifecycle(self):
        """Test first launch, config persistence, missing folder handling, and MANGA_DIR override."""
        with tempfile.TemporaryDirectory() as base_tmp:
            config_dir = os.path.join(base_tmp, "config")
            config_file = os.path.join(config_dir, "library_path")
            lib1 = os.path.join(base_tmp, "library1")
            lib2 = os.path.join(base_tmp, "library2")
            os.makedirs(lib1)
            os.makedirs(lib2)

            mock_bin = os.path.join(base_tmp, "mock_bin")
            os.makedirs(mock_bin)

            open_log = os.path.join(base_tmp, "open.log")
            with open(os.path.join(mock_bin, "open"), "w") as f:
                f.write(f'#!/bin/sh\necho "$@" >> {open_log}\n')
            os.chmod(os.path.join(mock_bin, "open"), 0o755)

            # Mock curl to simulate immediate server readiness
            with open(os.path.join(mock_bin, "curl"), "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(os.path.join(mock_bin, "curl"), 0o755)

            # Mock python3 to act as server.py
            server_log = os.path.join(base_tmp, "server.log")
            with open(os.path.join(mock_bin, "python3"), "w") as f:
                f.write(f"""#!/bin/sh
if [ "$1" = "server.py" ]; then
    echo "SERVER STARTED: $@" >> {server_log}
    trap "echo SERVER_SHUTDOWN >> {server_log}; exit 0" INT TERM
    while true; do sleep 0.1; done
else
    exec {sys.executable} "$@"
fi
""")
            os.chmod(os.path.join(mock_bin, "python3"), 0o755)

            base_env = dict(os.environ)
            base_env.pop("MANGA_DIR", None)
            base_env["LOCAL_MANGA_CONFIG_DIR"] = config_dir
            base_env["PATH"] = mock_bin + ":" + base_env.get("PATH", "")

            # 1. First launch with no configuration
            env1 = dict(base_env)
            env1["MOCK_FOLDER_PICKER_RESULT"] = lib1 + "/"
            p1 = subprocess.Popen([str(self.launcher_path)], env=env1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.4)
            p1.terminate()
            p1.wait(timeout=3)
            p1.stdout.close()
            p1.stderr.close()

            self.assertTrue(os.path.exists(config_file), "Config file was not created on first launch")
            with open(config_file) as f:
                saved = f.read().strip()
            self.assertEqual(saved, lib1)
            with open(open_log) as f:
                self.assertIn("-a Safari http://localhost:8000", f.read())
            with open(server_log) as f:
                slog = f.read()
                self.assertIn(f"--dir {lib1}", slog)
                self.assertIn("SERVER_SHUTDOWN", slog)

            # 2. Subsequent launch with saved configuration (does not re-pick)
            os.remove(open_log)
            os.remove(server_log)
            env2 = dict(base_env)
            env2["MOCK_FOLDER_PICKER_RESULT"] = "/should/not/be/used"
            p2 = subprocess.Popen([str(self.launcher_path)], env=env2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.4)
            p2.terminate()
            p2.wait(timeout=3)
            p2.stdout.close()
            p2.stderr.close()

            with open(config_file) as f:
                self.assertEqual(f.read().strip(), lib1)
            with open(server_log) as f:
                self.assertIn(f"--dir {lib1}", f.read())

            # 3. Missing/deleted configured folder prompts picker again and updates config
            os.remove(open_log)
            os.remove(server_log)
            shutil.rmtree(lib1)
            env3 = dict(base_env)
            env3["MOCK_FOLDER_PICKER_RESULT"] = lib2
            p3 = subprocess.Popen([str(self.launcher_path)], env=env3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.4)
            p3.terminate()
            p3.wait(timeout=3)
            p3.stdout.close()
            p3.stderr.close()

            with open(config_file) as f:
                self.assertEqual(f.read().strip(), lib2)
            with open(server_log) as f:
                self.assertIn(f"--dir {lib2}", f.read())

            # 4. External manga directory via MANGA_DIR environment variable
            os.remove(open_log)
            os.remove(server_log)
            ext_lib = os.path.join(base_tmp, "ext_manga")
            os.makedirs(ext_lib)
            env4 = dict(base_env)
            env4["MANGA_DIR"] = ext_lib
            p4 = subprocess.Popen([str(self.launcher_path)], env=env4, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.4)
            p4.terminate()
            p4.wait(timeout=3)
            p4.stdout.close()
            p4.stderr.close()

            with open(config_file) as f:
                self.assertEqual(f.read().strip(), lib2, "MANGA_DIR should not overwrite config file")
            with open(server_log) as f:
                self.assertIn(f"--dir {ext_lib}", f.read())

            # 5. Invalid MANGA_DIR shows clear error and exits with 1
            env5 = dict(base_env)
            env5["MANGA_DIR"] = "/nonexistent/manga_dir_test_404"
            r5 = subprocess.run([str(self.launcher_path)], env=env5, capture_output=True, text=True, input="")
            self.assertEqual(r5.returncode, 1)
            self.assertIn("[ERROR] Specified MANGA_DIR does not exist!", r5.stdout)

            # 6. User cancellation on initial launch exits cleanly
            os.remove(config_file)
            env6 = dict(base_env)
            env6["MOCK_FOLDER_PICKER_RESULT"] = ""
            r6 = subprocess.run([str(self.launcher_path)], env=env6, capture_output=True, text=True, input="")
            self.assertEqual(r6.returncode, 0)
            self.assertIn("No manga library folder selected.", r6.stdout)


class TestWindowsLauncher(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(__file__).parent.resolve()
        self.batch_path = self.project_dir / "start-windows.bat"

    def test_windows_launcher_attributes_and_no_hardcoded_paths(self):
        """Verify start-windows.bat existence, dynamic path resolution, and no hardcoded personal paths."""
        self.assertTrue(self.batch_path.exists(), "start-windows.bat does not exist")

        content = self.batch_path.read_text(encoding="utf-8")
        # Must not contain user's personal absolute paths
        self.assertNotIn("/Users/utkarshjaiswal", content)
        self.assertNotIn("utkarshjaiswal", content)

        # Must locate project relative to script using %~dp0
        self.assertIn("%~dp0", content)

        # Must configure outside git repo under %LOCALAPPDATA%\LocalMangaReader\library_path
        self.assertIn("LocalMangaReader", content)
        self.assertIn("library_path", content)
        self.assertIn("LOCALAPPDATA", content)

        # Must support Python detection (py -3 and python)
        self.assertIn("py -3", content)
        self.assertIn("python", content)

        # Must support native Windows folder picker via PowerShell
        self.assertIn("FolderBrowserDialog", content)

        # Must poll /api/status before opening browser
        self.assertIn("/api/status", content)
        self.assertIn("http://localhost:", content)

        # Must run server.py with --dir
        self.assertIn("server.py", content)
        self.assertIn("--dir", content)

    def test_server_windows_config_path_resolution(self):
        """Verify get_config_file_path() resolves to %LOCALAPPDATA%\\LocalMangaReader\\library_path on win32."""
        from server import get_config_file_path
        orig_platform = sys.platform
        orig_env_file = os.environ.get("LOCAL_MANGA_CONFIG_FILE")
        orig_env_dir = os.environ.get("LOCAL_MANGA_CONFIG_DIR")
        orig_localappdata = os.environ.get("LOCALAPPDATA")

        try:
            sys.platform = "win32"
            os.environ.pop("LOCAL_MANGA_CONFIG_FILE", None)
            os.environ.pop("LOCAL_MANGA_CONFIG_DIR", None)
            os.environ["LOCALAPPDATA"] = r"C:\Users\SampleUser\AppData\Local"

            resolved = get_config_file_path()
            expected = Path(r"C:\Users\SampleUser\AppData\Local") / "LocalMangaReader" / "library_path"
            self.assertEqual(resolved, expected)
        finally:
            sys.platform = orig_platform
            if orig_env_file:
                os.environ["LOCAL_MANGA_CONFIG_FILE"] = orig_env_file
            if orig_env_dir:
                os.environ["LOCAL_MANGA_CONFIG_DIR"] = orig_env_dir
            if orig_localappdata:
                os.environ["LOCALAPPDATA"] = orig_localappdata
            else:
                os.environ.pop("LOCALAPPDATA", None)


class TestLinuxLauncher(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(__file__).parent.resolve()
        self.launcher_path = self.project_dir / "start-linux.sh"

    def test_linux_launcher_attributes_and_no_hardcoded_paths(self):
        """Verify start-linux.sh existence, executable permissions, and dynamic paths."""
        self.assertTrue(self.launcher_path.exists(), "start-linux.sh does not exist")
        self.assertTrue(os.access(self.launcher_path, os.X_OK), "start-linux.sh is not executable")

        content = self.launcher_path.read_text(encoding="utf-8")
        self.assertNotIn("/Users/utkarshjaiswal", content)
        self.assertNotIn("utkarshjaiswal", content)

        # Dynamic location
        self.assertIn('dirname "$0"', content)

        # Config location
        self.assertIn("LocalMangaReader", content)
        self.assertIn("library_path", content)
        self.assertIn(".config", content)

        # Python 3 detection
        self.assertIn("python3", content)

        # Native Linux pickers and fallback
        self.assertIn("zenity", content)
        self.assertIn("kdialog", content)

        # Readiness polling & xdg-open browser
        self.assertIn("/api/status", content)
        self.assertIn("xdg-open", content)

        # Server invocation
        self.assertIn("server.py", content)
        self.assertIn("--dir", content)

    def test_server_linux_config_path_resolution(self):
        """Verify get_config_file_path() resolves to ~/.config/LocalMangaReader/library_path on Linux."""
        from server import get_config_file_path
        orig_platform = sys.platform
        orig_env_file = os.environ.get("LOCAL_MANGA_CONFIG_FILE")
        orig_env_dir = os.environ.get("LOCAL_MANGA_CONFIG_DIR")
        orig_xdg = os.environ.get("XDG_CONFIG_HOME")

        try:
            sys.platform = "linux"
            os.environ.pop("LOCAL_MANGA_CONFIG_FILE", None)
            os.environ.pop("LOCAL_MANGA_CONFIG_DIR", None)

            # Test with custom XDG_CONFIG_HOME
            os.environ["XDG_CONFIG_HOME"] = "/custom/xdg_config"
            resolved = get_config_file_path()
            self.assertEqual(resolved, Path("/custom/xdg_config/LocalMangaReader/library_path"))

            # Test default ~/.config
            os.environ.pop("XDG_CONFIG_HOME", None)
            resolved_default = get_config_file_path()
            self.assertEqual(resolved_default, Path(os.path.expanduser("~/.config/LocalMangaReader/library_path")))
        finally:
            sys.platform = orig_platform
            if orig_env_file:
                os.environ["LOCAL_MANGA_CONFIG_FILE"] = orig_env_file
            if orig_env_dir:
                os.environ["LOCAL_MANGA_CONFIG_DIR"] = orig_env_dir
            if orig_xdg:
                os.environ["XDG_CONFIG_HOME"] = orig_xdg
            else:
                os.environ.pop("XDG_CONFIG_HOME", None)

    def test_linux_launcher_lifecycle(self):
        """Test start-linux.sh lifecycle: first launch, config persistence, missing folder, MANGA_DIR, and cancellation."""
        with tempfile.TemporaryDirectory() as base_tmp:
            config_dir = os.path.join(base_tmp, "config")
            config_file = os.path.join(config_dir, "library_path")
            lib1 = os.path.join(base_tmp, "library1")
            lib2 = os.path.join(base_tmp, "library2")
            os.makedirs(lib1)
            os.makedirs(lib2)

            mock_bin = os.path.join(base_tmp, "mock_bin")
            os.makedirs(mock_bin)

            browser_log = os.path.join(base_tmp, "browser.log")
            with open(os.path.join(mock_bin, "xdg-open"), "w") as f:
                f.write(f'#!/bin/sh\necho "$@" >> {browser_log}\n')
            os.chmod(os.path.join(mock_bin, "xdg-open"), 0o755)

            # Mock curl for instant status
            with open(os.path.join(mock_bin, "curl"), "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(os.path.join(mock_bin, "curl"), 0o755)

            # Mock server execution via python3 wrapper
            server_log = os.path.join(base_tmp, "server.log")
            with open(os.path.join(mock_bin, "python3"), "w") as f:
                f.write(f"""#!/bin/sh
if [ "$1" = "server.py" ]; then
    echo "SERVER STARTED: $@" >> {server_log}
    trap "echo SERVER_SHUTDOWN >> {server_log}; exit 0" INT TERM
    while true; do sleep 0.1; done
else
    exec {sys.executable} "$@"
fi
""")
            os.chmod(os.path.join(mock_bin, "python3"), 0o755)

            base_env = dict(os.environ)
            base_env.pop("MANGA_DIR", None)
            base_env["LOCAL_MANGA_CONFIG_DIR"] = config_dir
            base_env["PATH"] = mock_bin + ":" + base_env.get("PATH", "")

            def wait_for_file(filepath, timeout=2.5):
                start = time.time()
                while time.time() - start < timeout:
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        return True
                    time.sleep(0.05)
                return False

            # 1. First launch with no configuration
            env1 = dict(base_env)
            env1["MOCK_FOLDER_PICKER_RESULT"] = lib1 + "/"
            p1 = subprocess.Popen([str(self.launcher_path)], env=env1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            wait_for_file(server_log)
            p1.terminate()
            p1.wait(timeout=3)
            p1.stdout.close()
            p1.stderr.close()

            self.assertTrue(os.path.exists(config_file), "Config file was not created on first launch")
            with open(config_file) as f:
                saved = f.read().strip()
            self.assertEqual(saved, lib1)
            with open(browser_log) as f:
                self.assertIn("http://localhost:8000", f.read())
            with open(server_log) as f:
                slog = f.read()
                self.assertIn(f"--dir {lib1}", slog)
                self.assertIn("SERVER_SHUTDOWN", slog)

            # 2. Subsequent launch with saved configuration
            os.remove(browser_log)
            os.remove(server_log)
            env2 = dict(base_env)
            env2["MOCK_FOLDER_PICKER_RESULT"] = "/should/not/be/used"
            p2 = subprocess.Popen([str(self.launcher_path)], env=env2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            wait_for_file(server_log)
            p2.terminate()
            p2.wait(timeout=3)
            p2.stdout.close()
            p2.stderr.close()

            with open(config_file) as f:
                self.assertEqual(f.read().strip(), lib1)
            with open(server_log) as f:
                self.assertIn(f"--dir {lib1}", f.read())

            # 3. Missing/deleted configured folder prompts picker again and updates config
            os.remove(browser_log)
            os.remove(server_log)
            shutil.rmtree(lib1)
            env3 = dict(base_env)
            env3["MOCK_FOLDER_PICKER_RESULT"] = lib2
            p3 = subprocess.Popen([str(self.launcher_path)], env=env3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            wait_for_file(server_log)
            p3.terminate()
            p3.wait(timeout=3)
            p3.stdout.close()
            p3.stderr.close()

            with open(config_file) as f:
                self.assertEqual(f.read().strip(), lib2)
            with open(server_log) as f:
                self.assertIn(f"--dir {lib2}", f.read())

            # 4. External manga directory via MANGA_DIR environment variable
            os.remove(browser_log)
            os.remove(server_log)
            ext_lib = os.path.join(base_tmp, "ext_manga")
            os.makedirs(ext_lib)
            env4 = dict(base_env)
            env4["MANGA_DIR"] = ext_lib
            p4 = subprocess.Popen([str(self.launcher_path)], env=env4, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            wait_for_file(server_log)
            p4.terminate()
            p4.wait(timeout=3)
            p4.stdout.close()
            p4.stderr.close()

            with open(config_file) as f:
                self.assertEqual(f.read().strip(), lib2, "MANGA_DIR should not overwrite config file")
            with open(server_log) as f:
                self.assertIn(f"--dir {ext_lib}", f.read())

            # 5. Invalid MANGA_DIR shows clear error and exits with 1
            env5 = dict(base_env)
            env5["MANGA_DIR"] = "/nonexistent/manga_dir_test_404"
            r5 = subprocess.run([str(self.launcher_path)], env=env5, capture_output=True, text=True, input="")
            self.assertEqual(r5.returncode, 1)
            self.assertIn("[ERROR] Specified MANGA_DIR does not exist!", r5.stdout)

            # 6. User cancellation on initial launch exits cleanly
            os.remove(config_file)
            env6 = dict(base_env)
            env6["MOCK_FOLDER_PICKER_RESULT"] = ""
            r6 = subprocess.run([str(self.launcher_path)], env=env6, capture_output=True, text=True, input="")
            self.assertEqual(r6.returncode, 0)
            self.assertIn("No manga library folder selected.", r6.stdout)


class TestArchiveAndFlexibleDiscovery(unittest.TestCase):
    """Unit tests for flexible chapter/image discovery and .cbz / .zip archive support."""

    def setUp(self):
        from server import MangaRequestHandler
        self.MangaRequestHandler = MangaRequestHandler
        self.temp_dir = tempfile.mkdtemp()
        self.lib_path = Path(self.temp_dir)
        self.library = MangaLibrary(str(self.lib_path))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _simulate_get(self, path: str):
        raw_request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        return headers, body

    def _simulate_post(self, path: str, json_data: dict):
        body_bytes = json.dumps(json_data).encode("utf-8")
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(raw_request)

        class CustomHandler(self.MangaRequestHandler):
            def __init__(self, request, client_address, server):
                self.request = request
                self.client_address = client_address
                self.server = server
                self.setup()
                try:
                    self.handle()
                finally:
                    self.finish()

            def log_message(self, format, *args):
                pass

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        return headers, body

    def test_arbitrary_chapter_directory_names(self):
        """1. Directory chapters with arbitrary naming schemes are discovered and naturally sorted."""
        series_dir = self.lib_path / "ArbitraryChapters"
        series_dir.mkdir(parents=True)

        names = [
            "Chapter 001 - The Beginning",
            "chapter-002",
            "003",
            "Volume 4",
            "My First Chapter",
            "10. Final Chapter"
        ]
        for name in names:
            ch_dir = series_dir / name
            ch_dir.mkdir()
            (ch_dir / "001.jpg").write_bytes(b"JPEG_DATA")

        chapters = self.library.list_chapters("ArbitraryChapters")
        chapter_names = [c["name"] for c in chapters]
        # Verify natural sort order
        expected_order = [
            "003",
            "10. Final Chapter",
            "Chapter 001 - The Beginning",
            "chapter-002",
            "My First Chapter",
            "Volume 4"
        ]
        self.assertEqual(chapter_names, expected_order)
        for c in chapters:
            self.assertEqual(c["image_count"], 1)

    def test_arbitrary_image_filenames(self):
        """2. Image files with arbitrary naming schemes are discovered and naturally sorted."""
        ch_dir = self.lib_path / "SeriesA" / "Chapter 1"
        ch_dir.mkdir(parents=True)

        img_names = [
            "001.jpg",
            "page_002.png",
            "img_0003.webp",
            "abc.gif",
            "004 - page.jpg",
            "10.jpg"
        ]
        for name in img_names:
            (ch_dir / name).write_bytes(b"TEST_IMAGE_BYTES")

        images = self.library.list_images("SeriesA", "Chapter 1")
        # Verify natural sort
        self.assertEqual(images, [
            "001.jpg",
            "004 - page.jpg",
            "10.jpg",
            "abc.gif",
            "img_0003.webp",
            "page_002.png"
        ])

        # Test serving through HTTP handler
        headers, body = self._simulate_get("/api/image-file?series=SeriesA&chapter=Chapter%201&file=004%20-%20page.jpg")
        self.assertIn("200 OK", headers)
        self.assertEqual(body, b"TEST_IMAGE_BYTES")

    def test_cbz_and_zip_discovery_and_natural_sorting(self):
        """3. .cbz and .zip archive files are discovered and sorted alongside directory chapters."""
        series_dir = self.lib_path / "MixedSeries"
        series_dir.mkdir(parents=True)

        # Directory chapter
        (series_dir / "Chapter 1").mkdir()
        ((series_dir / "Chapter 1") / "001.jpg").write_bytes(b"IMG1")

        # .cbz archive chapter
        cbz_path = series_dir / "Chapter 2.cbz"
        with zipfile.ZipFile(cbz_path, "w") as zf:
            zf.writestr("001.jpg", b"CBZ_IMG_1")
            zf.writestr("002.png", b"CBZ_IMG_2")

        # .zip archive chapter
        zip_path = series_dir / "Chapter 3.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("001.jpg", b"ZIP_IMG_1")

        # Higher numbered cbz
        cbz10_path = series_dir / "Chapter 10.cbz"
        with zipfile.ZipFile(cbz10_path, "w") as zf:
            zf.writestr("001.jpg", b"CBZ10_IMG_1")

        chapters = self.library.list_chapters("MixedSeries")
        self.assertEqual([c["name"] for c in chapters], ["Chapter 1", "Chapter 2", "Chapter 3", "Chapter 10"])
        self.assertEqual([c["image_count"] for c in chapters], [1, 2, 1, 1])

    def test_serving_images_directly_from_archives_without_extraction(self):
        """4. Images are streamed on the fly from archives without creating extracted files on disk."""
        series_dir = self.lib_path / "StreamSeries"
        series_dir.mkdir(parents=True)
        cbz_path = series_dir / "Chapter 1.cbz"

        dummy_png = b"\x89PNG\r\n\x1a\n" + b"TEST_PNG_CONTENT"
        dummy_jpeg = b"\xff\xd8\xff\xe0" + b"TEST_JPEG_CONTENT"

        with zipfile.ZipFile(cbz_path, "w") as zf:
            zf.writestr("page_001.jpg", dummy_jpeg)
            zf.writestr("page_002.png", dummy_png)

        # List images via API
        headers, body = self._simulate_get("/api/images?series=StreamSeries&chapter=Chapter%201.cbz")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["image_count"], 2)
        self.assertEqual([img["filename"] for img in data["images"]], ["page_001.jpg", "page_002.png"])

        # Fetch JPEG
        headers, body = self._simulate_get("/api/image-file?series=StreamSeries&chapter=Chapter%201.cbz&file=page_001.jpg")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/jpeg", headers)
        self.assertEqual(body, dummy_jpeg)

        # Fetch PNG
        headers, body = self._simulate_get("/api/image-file?series=StreamSeries&chapter=Chapter%201.cbz&file=page_002.png")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/png", headers)
        self.assertEqual(body, dummy_png)

        # Verify extensionless chapter resolution works
        headers, body = self._simulate_get("/api/image-file?series=StreamSeries&chapter=Chapter%201&file=page_001.jpg")
        self.assertIn("200 OK", headers)
        self.assertEqual(body, dummy_jpeg)

        # CRITICAL: Verify NO files were extracted to disk anywhere in series_dir
        series_entries = list(series_dir.iterdir())
        self.assertEqual(len(series_entries), 1)
        self.assertEqual(series_entries[0].name, "Chapter 1.cbz")

    def test_archive_nested_directory_and_macos_metadata_handling(self):
        """5. Handles archives containing internal subfolders and ignores __MACOSX / .DS_Store."""
        series_dir = self.lib_path / "NestedArchiveSeries"
        series_dir.mkdir(parents=True)
        zip_path = series_dir / "Chapter 1.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("__MACOSX/._001.jpg", b"MAC_METADATA")
            zf.writestr(".DS_Store", b"DS_STORE")
            zf.writestr("subfolder/.hidden.jpg", b"HIDDEN")
            zf.writestr("subfolder/001.jpg", b"IMG_1")
            zf.writestr("subfolder/002.jpg", b"IMG_2")
            zf.writestr("notes.txt", b"NOT AN IMAGE")

        images = self.library.list_images("NestedArchiveSeries", "Chapter 1.zip")
        self.assertEqual(images, ["001.jpg", "002.jpg"])

        # Fetch nested image by bare filename
        headers, body = self._simulate_get("/api/image-file?series=NestedArchiveSeries&chapter=Chapter%201.zip&file=001.jpg")
        self.assertIn("200 OK", headers)
        self.assertEqual(body, b"IMG_1")

    def test_unsupported_loose_files_ignored(self):
        """6. Loose files in series directory (.txt, .pdf, .nfo, loose images) are ignored as chapters."""
        series_dir = self.lib_path / "LooseFileSeries"
        series_dir.mkdir(parents=True)

        (series_dir / "notes.txt").write_text("notes")
        (series_dir / "info.nfo").write_text("info")
        (series_dir / "manga.pdf").write_bytes(b"%PDF-1.4")
        (series_dir / "loose_page.jpg").write_bytes(b"JPEG")
        (series_dir / ".hidden_folder").mkdir()
        (series_dir / "ValidChapter").mkdir()
        ((series_dir / "ValidChapter") / "001.jpg").write_bytes(b"IMG")

        chapters = self.library.list_chapters("LooseFileSeries")
        self.assertEqual([c["name"] for c in chapters], ["ValidChapter"])

    def test_corrupt_and_empty_archives(self):
        """7. Corrupt and empty archives are handled gracefully without server crashes."""
        series_dir = self.lib_path / "BrokenSeries"
        series_dir.mkdir(parents=True)

        # Corrupt file disguised as cbz
        (series_dir / "CorruptChapter.cbz").write_bytes(b"THIS IS NOT A VALID ZIP ARCHIVE")

        # Empty valid zip
        with zipfile.ZipFile(series_dir / "EmptyChapter.zip", "w") as _:
            pass

        chapters = self.library.list_chapters("BrokenSeries")
        self.assertEqual(len(chapters), 2)
        for ch in chapters:
            self.assertEqual(ch["image_count"], 0)

        # Requesting images for corrupt archive returns empty list
        self.assertEqual(self.library.list_images("BrokenSeries", "CorruptChapter.cbz"), [])

        # Requesting image file from corrupt archive returns 404
        headers, _ = self._simulate_get("/api/image-file?series=BrokenSeries&chapter=CorruptChapter.cbz&file=001.jpg")
        self.assertIn("404", headers)

    def test_archive_path_traversal_rejection(self):
        """8. Archive member traversal attacks (.. or leading /) are rejected."""
        series_dir = self.lib_path / "SecuritySeries"
        series_dir.mkdir(parents=True)
        zip_path = series_dir / "HackedChapter.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("../../../etc/passwd.jpg", b"MALICIOUS")
            zf.writestr("/absolute/path.jpg", b"MALICIOUS")
            zf.writestr("safe_001.jpg", b"SAFE")

        images = self.library.list_images("SecuritySeries", "HackedChapter.zip")
        self.assertEqual(images, ["safe_001.jpg"])

        # Attempt to request traversal via API returns 404 (Not Found)
        headers, _ = self._simulate_get("/api/image-file?series=SecuritySeries&chapter=HackedChapter.zip&file=..%2F..%2Fetc%2Fpasswd.jpg")
        self.assertIn("404", headers)

    def test_cover_detection_from_first_archive_chapter(self):
        """9. Series without top-level cover.jpg detects cover from first archive chapter."""
        series_dir = self.lib_path / "ArchiveCoverSeries"
        series_dir.mkdir(parents=True)

        cbz_path = series_dir / "Chapter 01.cbz"
        dummy_cover = b"\xff\xd8\xff\xe0" + b"ARCHIVE_COVER_JPEG"
        with zipfile.ZipFile(cbz_path, "w") as zf:
            zf.writestr("001.jpg", dummy_cover)

        series_list = self.library.list_series()
        s = next(s for s in series_list if s["name"] == "ArchiveCoverSeries")
        self.assertTrue(s["has_cover"])
        self.assertIn("/api/cover?series=ArchiveCoverSeries", s["cover_url"])

        # Fetch cover via API
        headers, body = self._simulate_get("/api/cover?series=ArchiveCoverSeries")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/jpeg", headers)
        self.assertEqual(body, dummy_cover)

    def test_reading_progress_and_bookmarks_with_archives(self):
        """10. Reading progress and bookmarks work seamlessly with .cbz and .zip chapters."""
        series_dir = self.lib_path / "ArchiveProgressSeries"
        series_dir.mkdir(parents=True)

        cbz_path = series_dir / "Chapter 1.cbz"
        with zipfile.ZipFile(cbz_path, "w") as zf:
            zf.writestr("001.jpg", b"IMG")

        # Save progress using stripped display name
        headers, body = self._simulate_post("/api/progress", {
            "series": "ArchiveProgressSeries",
            "chapter": "Chapter 1",
            "image": "001.jpg"
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertEqual(resp["progress"]["Chapter 1"], "001.jpg")
        self.assertEqual(resp["progress"]["Chapter 1.cbz"], "001.jpg")

        # Bookmark chapter using stripped display name
        headers, body = self._simulate_post("/api/bookmark", {
            "series": "ArchiveProgressSeries",
            "chapter": "Chapter 1",
            "bookmarked": True
        })
        self.assertIn("200 OK", headers)
        resp = json.loads(body.decode("utf-8"))
        self.assertTrue(resp["bookmarked"])

        # Fetch reader-data
        headers, body = self._simulate_get("/api/reader-data?series=ArchiveProgressSeries")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["progress"]["Chapter 1"], "001.jpg")
        self.assertIn("Chapter 1", data["bookmarks"])
        self.assertIn("Chapter 1.cbz", data["bookmarks"])

    def test_background_fallback_to_first_image_of_cbz(self):
        """11. Background falls back to the first image of a .cbz archive when no background or cover exists."""
        series_dir = self.lib_path / "BgCbzSeries"
        series_dir.mkdir(parents=True)

        cbz_path = series_dir / "Chapter 1.cbz"
        dummy_img = b"\xff\xd8\xff\xe0" + b"CBZ_BG_JPEG"
        with zipfile.ZipFile(cbz_path, "w") as zf:
            zf.writestr("001.jpg", dummy_img)
            zf.writestr("002.jpg", b"IMG_2")

        headers, body = self._simulate_get("/api/background?series=BgCbzSeries")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/jpeg", headers)
        self.assertEqual(body, dummy_img)

    def test_background_fallback_to_first_image_of_zip(self):
        """12. Background falls back to the first image of a .zip archive when no background or cover exists."""
        series_dir = self.lib_path / "BgZipSeries"
        series_dir.mkdir(parents=True)

        zip_path = series_dir / "Chapter 1.zip"
        dummy_img = b"\x89PNG\r\n\x1a\n" + b"ZIP_BG_PNG"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("001.png", dummy_img)

        headers, body = self._simulate_get("/api/background?series=BgZipSeries")
        self.assertIn("200 OK", headers)
        self.assertIn("Content-Type: image/png", headers)
        self.assertEqual(body, dummy_img)

    def test_background_priority_background_jpg_over_cover_and_archive(self):
        """13. background.jpg takes priority over cover.jpg and archive chapter image."""
        series_dir = self.lib_path / "BgPrioSeries"
        series_dir.mkdir(parents=True)

        bg_bytes = b"\xff\xd8\xff\xe0" + b"PRIO_BACKGROUND_JPG"
        cover_bytes = b"\xff\xd8\xff\xe0" + b"PRIO_COVER_JPG"
        archive_img = b"\xff\xd8\xff\xe0" + b"PRIO_ARCHIVE_IMG"

        (series_dir / "background.jpg").write_bytes(bg_bytes)
        (series_dir / "cover.jpg").write_bytes(cover_bytes)
        with zipfile.ZipFile(series_dir / "Chapter 1.cbz", "w") as zf:
            zf.writestr("001.jpg", archive_img)

        headers, body = self._simulate_get("/api/background?series=BgPrioSeries")
        self.assertIn("200 OK", headers)
        self.assertEqual(body, bg_bytes)

    def test_background_priority_cover_jpg_over_archive_image(self):
        """14. cover.jpg takes priority over the first chapter archive image when background.jpg is absent."""
        series_dir = self.lib_path / "CoverPrioSeries"
        series_dir.mkdir(parents=True)

        cover_bytes = b"\xff\xd8\xff\xe0" + b"COVER_OVER_ARCHIVE_JPG"
        archive_img = b"\xff\xd8\xff\xe0" + b"ARCHIVE_CHAPTER_IMG"

        (series_dir / "cover.jpg").write_bytes(cover_bytes)
        with zipfile.ZipFile(series_dir / "Chapter 1.cbz", "w") as zf:
            zf.writestr("001.jpg", archive_img)

        headers, body = self._simulate_get("/api/background?series=CoverPrioSeries")
        self.assertIn("200 OK", headers)
        self.assertEqual(body, cover_bytes)

    def test_background_blank_when_no_usable_image_exists(self):
        """15. Background returns 404 (blank) when no usable image exists anywhere in the series."""
        series_dir = self.lib_path / "BgEmptySeries"
        series_dir.mkdir(parents=True)

        # Empty chapter zip with 0 images
        with zipfile.ZipFile(series_dir / "Chapter 1.zip", "w") as _:
            pass

        headers, _ = self._simulate_get("/api/background?series=BgEmptySeries")
        self.assertIn("404", headers)

    def test_archive_extensions_removed_from_chapter_names(self):
        """16. .cbz and .zip extensions are removed from chapter display names while folder names remain intact."""
        series_dir = self.lib_path / "NameStripSeries"
        series_dir.mkdir(parents=True)

        # Create folder chapter
        (series_dir / "Chapter 1").mkdir()
        ((series_dir / "Chapter 1") / "001.jpg").write_bytes(b"F1")

        # Create .cbz and .zip chapters with varied casing and numbering
        with zipfile.ZipFile(series_dir / "Chapter 2.cbz", "w") as zf:
            zf.writestr("001.jpg", b"C2")
        with zipfile.ZipFile(series_dir / "Volume 03.cbz", "w") as zf:
            zf.writestr("001.jpg", b"V3")
        with zipfile.ZipFile(series_dir / "Chapter 4.zip", "w") as zf:
            zf.writestr("001.jpg", b"Z4")

        chapters = self.library.list_chapters("NameStripSeries")
        names = [c["name"] for c in chapters]
        # Folder chapter remains 'Chapter 1'
        self.assertIn("Chapter 1", names)
        # .cbz and .zip stripped
        self.assertIn("Chapter 2", names)
        self.assertIn("Volume 03", names)
        self.assertIn("Chapter 4", names)
        for n in names:
            self.assertFalse(n.endswith(".cbz"))
            self.assertFalse(n.endswith(".zip"))

        # Natural sorting order check
        expected_order = ["Chapter 1", "Chapter 2", "Chapter 4", "Volume 03"]
        self.assertEqual(names, expected_order)

        # Confirm images can be listed and retrieved using the extensionless display name
        images = self.library.list_images("NameStripSeries", "Chapter 2")
        self.assertEqual(images, ["001.jpg"])
        headers, body = self._simulate_get("/api/image-file?series=NameStripSeries&chapter=Chapter%202&file=001.jpg")
        self.assertIn("200 OK", headers)
        self.assertEqual(body, b"C2")


if __name__ == "__main__":
    unittest.main()

