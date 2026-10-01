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

    def test_api_status(self):
        headers, body = self._simulate_get("/api/status")
        self.assertIn("200 OK", headers)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "online")


if __name__ == "__main__":
    unittest.main()
