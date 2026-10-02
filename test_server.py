import unittest
from pathlib import Path
import tempfile
import shutil
import json
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
        self.assertIn(b"Manga Reader", body)
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

        CustomHandler.library = self.library
        CustomHandler.static_dir = Path(__file__).parent / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

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


if __name__ == "__main__":
    unittest.main()
