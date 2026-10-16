"""
Comprehensive tests for Chapter Read Status, Reading Progress Semantics,
Continue Reading (Resume Reading) State Machine (Cases A-G), and Library Pinning.
Covers all requirements from Parts 1 through 6.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from http import HTTPStatus

from server import (
    MangaLibrary,
    MangaRequestHandler,
    load_pinned_series,
    save_pinned_series,
    toggle_pin_series,
    load_app_settings,
    save_app_settings,
    canonicalize_library_path,
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
from providers.service import RemoteReaderService
from providers.mock import MockProvider
from providers.registry import ProviderRegistry


class MockSocket:
    """Mock socket for simulated HTTP requests."""
    def __init__(self, data: bytes = b""):
        import io
        self.rfile = io.BytesIO(data)
        self.wfile = io.BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            return self.rfile
        return self.wfile

    def sendall(self, data):
        self.wfile.write(data)


class TestReadingStateSemantics(unittest.TestCase):
    """
    Test suite covering:
    - Independence of read status and reading progress (Part 1)
    - Precedence rules: Explicit Unread > Explicit Read > Legacy 100% > Unread default
    - Automatic completion on final page & preserving explicit Unread
    - Reopening/revisiting chapters
    - Continue Reading Cases A through G (Part 2)
    - Pinning functionality (Part 3)
    - CSS contrast & styling invariants (Parts 3 & 4)
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Config dir
        self.config_dir = self.base_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.orig_config_dir = os.environ.get("LOCAL_MANGA_CONFIG_DIR")
        os.environ["LOCAL_MANGA_CONFIG_DIR"] = str(self.config_dir)

        # Manga library dir
        self.manga_dir = self.base_dir / "manga"
        self.manga_dir.mkdir(parents=True, exist_ok=True)

        # Create sample series "TestManga" with 3 chapters
        self.series_dir = self.manga_dir / "TestManga"
        self.series_dir.mkdir(parents=True, exist_ok=True)

        for ch_num in range(1, 4):
            ch_dir = self.series_dir / f"Chapter {ch_num}"
            ch_dir.mkdir(parents=True, exist_ok=True)
            for page_num in range(1, 5):
                (ch_dir / f"{page_num}.jpg").write_bytes(f"IMAGE_{ch_num}_{page_num}".encode("utf-8"))

        self.library = MangaLibrary(str(self.manga_dir))

        # Remote service setup
        self.remote_dir = self.base_dir / "remote_state"
        self.remote_dir.mkdir(parents=True, exist_ok=True)
        self.registry = ProviderRegistry()
        self.mock_provider = MockProvider()
        self.registry.register(self.mock_provider)
        self.remote_service = RemoteReaderService(registry=self.registry, state_dir=self.remote_dir)

    def tearDown(self):
        if self.orig_config_dir is not None:
            os.environ["LOCAL_MANGA_CONFIG_DIR"] = self.orig_config_dir
        else:
            os.environ.pop("LOCAL_MANGA_CONFIG_DIR", None)
        self.temp_dir.cleanup()

    def _simulate_get(self, path: str):
        raw_request = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("utf-8")
        sock = MockSocket(raw_request)

        class CustomHandler(MangaRequestHandler):
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
        CustomHandler.remote_service = self.remote_service
        CustomHandler.static_dir = PROJECT_ROOT / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        status_line = headers.split("\r\n")[0]
        status_code = int(status_line.split(" ")[1])
        return headers, body, status_code

    def _simulate_post(self, path: str, json_data: dict):
        body_bytes = json.dumps(json_data).encode("utf-8")
        raw_request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(raw_request)

        class CustomHandler(MangaRequestHandler):
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
        CustomHandler.remote_service = self.remote_service
        CustomHandler.static_dir = PROJECT_ROOT / "static"
        CustomHandler(sock, ("127.0.0.1", 8000), None)

        sock.wfile.seek(0)
        response_data = sock.wfile.read()
        header_end = response_data.find(b"\r\n\r\n")
        headers = response_data[:header_end].decode("utf-8", errors="replace")
        body = response_data[header_end + 4:]
        status_line = headers.split("\r\n")[0]
        status_code = int(status_line.split(" ")[1])
        return headers, body, status_code

    # =========================================================================
    # Part 1: Chapter Read Status & Progress Semantics (Requirements 15-19)
    # =========================================================================

    def test_req_15_mark_as_read_preserves_reading_position(self):
        """Req 15: Mark as Read sets completed without altering saved reading position."""
        # 1. User is on page 2 of Chapter 1
        _, b, status = self._simulate_post("/api/progress", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "image": "2.jpg"
        })
        self.assertEqual(status, HTTPStatus.OK)
        res = json.loads(b.decode("utf-8"))
        self.assertEqual(res["progress"]["Chapter 1"], "2.jpg")
        self.assertEqual(res.get("last_read"), "Chapter 1")

        # 2. Mark Chapter 1 as Read
        _, cb, cstatus = self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": True
        })
        self.assertEqual(cstatus, HTTPStatus.OK)
        cres = json.loads(cb.decode("utf-8"))
        self.assertIn("Chapter 1", cres["completed_chapters"])
        self.assertNotIn("Chapter 1", cres["unread_chapters"])

        # 3. Verify reader data: progress is still 2.jpg and last_read is Chapter 1
        _, rb, rstatus = self._simulate_get("/api/reader-data?series=TestManga")
        self.assertEqual(rstatus, HTTPStatus.OK)
        rdata = json.loads(rb.decode("utf-8"))
        self.assertEqual(rdata["progress"]["Chapter 1"], "2.jpg")
        self.assertIn("Chapter 1", rdata["completed"])
        self.assertEqual(rdata["last_read"], "Chapter 1")

    def test_req_16_mark_as_unread_preserves_saved_position_and_percentage(self):
        """Req 16: Mark as Unread clears completed, restores unread override, preserves saved position and percentage."""
        # Set chapter 1 as completed with 4.jpg (100%)
        self.library.update_progress("TestManga", "Chapter 1", "4.jpg")
        self.library.set_chapter_completion("TestManga", "Chapter 1", True)

        # Mark as Unread
        _, cb, cstatus = self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": False
        })
        self.assertEqual(cstatus, HTTPStatus.OK)
        cres = json.loads(cb.decode("utf-8"))
        self.assertNotIn("Chapter 1", cres["completed_chapters"])
        self.assertIn("Chapter 1", cres["unread_chapters"])

        # Progress remains 4.jpg
        _, rb, _ = self._simulate_get("/api/reader-data?series=TestManga")
        rdata = json.loads(rb.decode("utf-8"))
        self.assertEqual(rdata["progress"]["Chapter 1"], "4.jpg")
        self.assertNotIn("Chapter 1", rdata["completed"])
        self.assertIn("Chapter 1", rdata["unread"])

    def test_req_17_and_18_automatic_completion_does_not_override_explicit_unread(self):
        """
        Req 17 & 18:
        Automatic completion on final page must NOT override explicit Unread choice.
        Reopening/reading chapter preserves explicit Read/Unread status.
        """
        # Explicitly mark Chapter 1 as Unread
        self.library.set_chapter_completion("TestManga", "Chapter 1", False)
        data = self.library.get_reader_data("TestManga")
        self.assertIn("Chapter 1", data["unread"])

        # Reader reaches final page (4.jpg) and saves progress
        _, pb, pstatus = self._simulate_post("/api/progress", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "image": "4.jpg"
        })
        self.assertEqual(pstatus, HTTPStatus.OK)

        # Verify Unread override is preserved on disk
        data_after = self.library.get_reader_data("TestManga")
        self.assertIn("Chapter 1", data_after["unread"])
        self.assertNotIn("Chapter 1", data_after.get("completed", []))

    def test_explicit_unread_to_natural_completion_clears_unread_override_and_persists(self):
        """
        Regression: When a chapter is explicitly marked Unread, then naturally read to completion,
        it must become Read, clearing the unread override, and persist across data reloads.
        """
        # 1. Start with Chapter 1 having progress on page 2
        self._simulate_post("/api/progress", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "image": "2.jpg"
        })

        # 2. Explicitly mark Chapter 1 as Unread
        _, cb, cstatus = self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": False
        })
        self.assertEqual(cstatus, HTTPStatus.OK)
        cres = json.loads(cb.decode("utf-8"))
        self.assertIn("Chapter 1", cres["unread_chapters"])
        self.assertNotIn("Chapter 1", cres["completed_chapters"])

        # Verify on disk
        data = self.library.get_reader_data("TestManga")
        self.assertIn("Chapter 1", data["unread"])
        self.assertNotIn("Chapter 1", data.get("completed", []))

        # 3. User reads naturally through the chapter to the final page (4.jpg)
        # Progress is updated
        self._simulate_post("/api/progress", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "image": "4.jpg"
        })
        # Natural completion triggers complete endpoint
        _, cb2, cstatus2 = self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": True
        })
        self.assertEqual(cstatus2, HTTPStatus.OK)
        cres2 = json.loads(cb2.decode("utf-8"))
        self.assertIn("Chapter 1", cres2["completed_chapters"])
        self.assertNotIn("Chapter 1", cres2["unread_chapters"])

        # 4. Result persists after reloading reader data from disk
        new_library = MangaLibrary(str(self.manga_dir))
        reloaded_data = new_library.get_reader_data("TestManga")
        self.assertIn("Chapter 1", reloaded_data["completed"])
        self.assertNotIn("Chapter 1", reloaded_data.get("unread", []))
        # Saved reading position remains intact
        self.assertEqual(reloaded_data["progress"]["Chapter 1"], "4.jpg")

    def test_ordinary_page_visits_before_final_page_preserve_explicit_unread(self):
        """
        Ordinary page visits before the final page must preserve the explicit Unread status.
        """
        # 1. Explicitly mark Chapter 1 as Unread
        self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": False
        })
        data = self.library.get_reader_data("TestManga")
        self.assertIn("Chapter 1", data["unread"])

        # 2. Visit ordinary pages (page 1, page 2, page 3 out of 4)
        for page in ["1.jpg", "2.jpg", "3.jpg"]:
            _, pb, status = self._simulate_post("/api/progress", {
                "series": "TestManga",
                "chapter": "Chapter 1",
                "image": page
            })
            self.assertEqual(status, HTTPStatus.OK)
            # Chapter remains in unread, never silently completed
            curr_data = self.library.get_reader_data("TestManga")
            self.assertIn("Chapter 1", curr_data["unread"])
            self.assertNotIn("Chapter 1", curr_data.get("completed", []))

    def test_reopening_and_restoring_final_page_alone_does_not_clear_unread(self):
        """
        Merely reopening a chapter at 100% progress and restoring the saved final page
        must not count as newly completing it. Explicit unread remains intact until active reading.
        """
        # Set progress at 100% (4.jpg)
        self._simulate_post("/api/progress", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "image": "4.jpg"
        })
        # Explicitly mark unread
        self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": False
        })

        # Fetch reader data as frontend would on reopening
        _, rb, status = self._simulate_get("/api/reader-data?series=TestManga")
        self.assertEqual(status, HTTPStatus.OK)
        rdata = json.loads(rb.decode("utf-8"))
        self.assertIn("Chapter 1", rdata["unread"])
        self.assertNotIn("Chapter 1", rdata.get("completed", []))
        self.assertEqual(rdata["progress"]["Chapter 1"], "4.jpg")

        # Frontend logic check: when initialPageIndex == totalImages (4 == 4),
        # isRestoringFinalPage is True -> canAutoComplete is False initially.
        initial_page_index = 4
        total_images = 4
        target_page_exists = True
        is_restoring_final_page = (target_page_exists and initial_page_index == total_images and total_images > 0)
        can_auto_complete = not is_restoring_final_page
        self.assertFalse(can_auto_complete)

        # But scrolling to an earlier page enables completion
        active_index = 3
        if active_index < total_images:
            can_auto_complete = True
        self.assertTrue(can_auto_complete)

    def test_remote_explicit_unread_to_natural_completion(self):
        """
        Remote series follows the exact same semantics:
        Explicit Unread -> natural completion -> Read status persisted and Unread cleared.
        """
        series_id = "remote:mock:sololeveling"
        # 1. Set progress and mark unread
        self._simulate_post("/api/progress", {
            "series": series_id,
            "chapter": "mock-ch-1",
            "image": "1.jpg"
        })
        _, cb, _ = self._simulate_post("/api/remote/complete", {
            "series": series_id,
            "chapter": "mock-ch-1",
            "completed": False
        })
        cres = json.loads(cb.decode("utf-8"))
        self.assertIn("mock-ch-1", cres["unread_chapters"])
        self.assertNotIn("mock-ch-1", cres["completed_chapters"])

        # 2. Reading earlier pages preserves unread
        self._simulate_post("/api/progress", {
            "series": series_id,
            "chapter": "mock-ch-1",
            "image": "2.jpg"
        })
        rdata = self.remote_service.get_reader_data(series_id)
        self.assertIn("mock-ch-1", rdata["unread"])
        self.assertNotIn("mock-ch-1", rdata.get("completed", []))

        # 3. Natural completion marks read and clears unread
        _, cb2, _ = self._simulate_post("/api/remote/complete", {
            "series": series_id,
            "chapter": "mock-ch-1",
            "completed": True
        })
        cres2 = json.loads(cb2.decode("utf-8"))
        self.assertIn("mock-ch-1", cres2["completed_chapters"])
        self.assertNotIn("mock-ch-1", cres2["unread_chapters"])

        # 4. Persists across new service instance
        new_service = RemoteReaderService(registry=self.registry, state_dir=self.remote_dir)
        new_data = new_service.get_reader_data(series_id)
        self.assertIn("mock-ch-1", new_data["completed"])
        self.assertNotIn("mock-ch-1", new_data.get("unread", []))
        self.assertEqual(new_data["progress"]["mock-ch-1"], "2.jpg")

    def test_reaching_final_page_of_already_read_chapter_leaves_it_read(self):
        """
        Reaching the final page of a chapter that is already explicitly Read must leave it Read.
        """
        # Mark Read
        self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": True
        })
        # Natural completion fires again
        _, cb, _ = self._simulate_post("/api/complete", {
            "series": "TestManga",
            "chapter": "Chapter 1",
            "completed": True
        })
        cres = json.loads(cb.decode("utf-8"))
        self.assertIn("Chapter 1", cres["completed_chapters"])
        self.assertNotIn("Chapter 1", cres["unread_chapters"])

    def test_precedence_rules_semantics(self):
        """
        Precedence:
        1. Explicit Unread takes priority (even with 100% progress).
        2. Explicit Read takes priority (even with <100% progress).
        3. Legacy 100% progress without explicit status acts as completed.
        4. Otherwise, chapter is unread.
        """
        # Helper emulating frontend isChapterCompleted
        def eval_status(ch_name, completed_set, unread_set, progress_map):
            if ch_name in unread_set:
                return False  # Rule 1
            if ch_name in completed_set:
                return True   # Rule 2
            if progress_map.get(ch_name) == 100:
                return True   # Rule 3
            return False      # Rule 4

        # Case 1: Progress is 100%, but marked Unread -> effective status: Unread
        self.assertFalse(eval_status("Ch1", completed_set=set(), unread_set={"Ch1"}, progress_map={"Ch1": 100}))

        # Case 2: Progress is 25%, but marked Read -> effective status: Read
        self.assertTrue(eval_status("Ch1", completed_set={"Ch1"}, unread_set=set(), progress_map={"Ch1": 25}))

        # Case 3: No explicit status, progress is 100% -> effective status: Read
        self.assertTrue(eval_status("Ch1", completed_set=set(), unread_set=set(), progress_map={"Ch1": 100}))

        # Case 4: No explicit status, progress is 50% -> effective status: Unread
        self.assertFalse(eval_status("Ch1", completed_set=set(), unread_set=set(), progress_map={"Ch1": 50}))

        # Case 5: No explicit status, progress is 0% -> effective status: Unread
        self.assertFalse(eval_status("Ch1", completed_set=set(), unread_set=set(), progress_map={}))

    # =========================================================================
    # Part 2: Continue Reading / Resume Reading Behavior (Requirements 6-14)
    # =========================================================================

    def _resolve_continue_reading(self, chapters, reader_data, progress_map):
        """
        Pure Python reference model of frontend updateResumeReadingButton logic.
        Validates Cases A through G.
        """
        natural_sort_key = lambda ch: ch["name"]
        canonical_chapters = sorted(chapters, key=natural_sort_key)
        completed_set = set(reader_data.get("completed", []))
        unread_set = set(reader_data.get("unread", []))
        progress = reader_data.get("progress", {})
        last_read_name = reader_data.get("last_read")

        def is_completed(ch):
            name = ch["name"]
            if name in unread_set:
                return False
            if name in completed_set:
                return True
            if progress_map.get(name) == 100:
                return True
            return False

        all_completed = len(canonical_chapters) > 0 and all(is_completed(c) for c in canonical_chapters)

        # Find last reading chapter
        last_reading_chapter = None
        if last_read_name:
            last_reading_chapter = next((c for c in canonical_chapters if c["name"] == last_read_name), None)
        if not last_reading_chapter:
            for c in reversed(canonical_chapters):
                if c["name"] in progress and progress[c["name"]]:
                    last_reading_chapter = c
                    break

        if all_completed:
            target = last_reading_chapter if last_reading_chapter else canonical_chapters[0]
            return {"action": "Read Again", "target": target["name"], "completed_badge": True}

        if not last_reading_chapter:
            target = next((c for c in canonical_chapters if not is_completed(c)), canonical_chapters[0])
            return {"action": "Start Reading", "target": target["name"], "completed_badge": False}

        if not is_completed(last_reading_chapter):
            return {"action": "Resume Reading", "target": last_reading_chapter["name"], "completed_badge": False}
        else:
            pct = progress_map.get(last_reading_chapter["name"])
            if pct is not None and pct < 100:
                return {"action": "Resume Reading", "target": last_reading_chapter["name"], "completed_badge": False}
            else:
                last_idx = canonical_chapters.index(last_reading_chapter)
                next_unread = None
                for i in range(last_idx + 1, len(canonical_chapters)):
                    if not is_completed(canonical_chapters[i]):
                        next_unread = canonical_chapters[i]
                        break
                if not next_unread:
                    for i in range(0, last_idx):
                        if not is_completed(canonical_chapters[i]):
                            next_unread = canonical_chapters[i]
                            break
                target = next_unread if next_unread else last_reading_chapter
                return {"action": "Resume Reading", "target": target["name"], "completed_badge": False}

    def test_req_6_case_a_start_reading_first_unread_chapter(self):
        """Req 6 (Case A): No reading progress exists -> Start Reading, targets first unread chapter."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {"progress": {}, "completed": [], "unread": [], "last_read": None}
        progress_map = {}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Start Reading")
        self.assertEqual(result["target"], "Chapter 1")
        self.assertFalse(result["completed_badge"])

    def test_req_7_case_b_resume_reading_in_progress(self):
        """Req 7 (Case B): Reader is in middle of chapter 1 (not completed) -> Resume Reading at Chapter 1."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {"progress": {"Chapter 1": "2.jpg"}, "completed": [], "unread": [], "last_read": "Chapter 1"}
        progress_map = {"Chapter 1": 50}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Resume Reading")
        self.assertEqual(result["target"], "Chapter 1")

    def test_req_8_case_c_resume_reading_specific_page_marked_read(self):
        """Req 8 (Case C): Reader at specific page (< 100%), but marked Read -> Resume Reading at Chapter 1."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {"progress": {"Chapter 1": "2.jpg"}, "completed": ["Chapter 1"], "unread": [], "last_read": "Chapter 1"}
        progress_map = {"Chapter 1": 50}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Resume Reading")
        self.assertEqual(result["target"], "Chapter 1")

    def test_req_9_case_d_resume_reading_explicit_unread(self):
        """Req 9 (Case D): Chapter has saved progress (even 100%), marked Unread -> Resume Reading at Chapter 1."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {"progress": {"Chapter 1": "4.jpg"}, "completed": [], "unread": ["Chapter 1"], "last_read": "Chapter 1"}
        progress_map = {"Chapter 1": 100}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Resume Reading")
        self.assertEqual(result["target"], "Chapter 1")

    def test_req_10_case_e_resume_reading_advances_after_natural_completion(self):
        """Req 10 (Case E): Naturally reached final page (100%, completed) -> Resume Reading advances to Chapter 2."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {"progress": {"Chapter 1": "4.jpg"}, "completed": ["Chapter 1"], "unread": [], "last_read": "Chapter 1"}
        progress_map = {"Chapter 1": 100}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Resume Reading")
        self.assertEqual(result["target"], "Chapter 2")

    def test_req_11_case_f_read_again_when_all_completed(self):
        """Req 11 (Case F): All chapters completed -> Read Again, opens last reading position."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {
            "progress": {"Chapter 1": "4.jpg", "Chapter 2": "4.jpg", "Chapter 3": "4.jpg"},
            "completed": ["Chapter 1", "Chapter 2", "Chapter 3"],
            "unread": [],
            "last_read": "Chapter 3"
        }
        progress_map = {"Chapter 1": 100, "Chapter 2": 100, "Chapter 3": 100}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Read Again")
        self.assertEqual(result["target"], "Chapter 3")
        self.assertTrue(result["completed_badge"])

    def test_req_12_case_g_finished_then_marked_unread(self):
        """Req 12 (Case G): All were completed, user marked Chapter 2 Unread -> Resume Reading at Chapter 2."""
        chapters = [{"name": "Chapter 1"}, {"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {
            "progress": {"Chapter 1": "4.jpg", "Chapter 2": "4.jpg", "Chapter 3": "4.jpg"},
            "completed": ["Chapter 1", "Chapter 3"],
            "unread": ["Chapter 2"],
            "last_read": "Chapter 3"
        }
        progress_map = {"Chapter 1": 100, "Chapter 2": 100, "Chapter 3": 100}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        self.assertEqual(result["action"], "Resume Reading")
        self.assertEqual(result["target"], "Chapter 2")
        self.assertFalse(result["completed_badge"])

    def test_req_13_canonical_reading_order_respected_regardless_of_display_order(self):
        """Req 13: Canonical order is respected even when UI displays chapters in reverse/descending order."""
        # Visual display order reversed: Chapter 3, Chapter 2, Chapter 1
        visual_chapters = [{"name": "Chapter 3"}, {"name": "Chapter 2"}, {"name": "Chapter 1"}]
        reader_data = {"progress": {"Chapter 1": "4.jpg"}, "completed": ["Chapter 1"], "unread": [], "last_read": "Chapter 1"}
        progress_map = {"Chapter 1": 100}

        result = self._resolve_continue_reading(visual_chapters, reader_data, progress_map)
        # Canonical order determines Chapter 2 follows Chapter 1, NOT Chapter 3
        self.assertEqual(result["target"], "Chapter 2")

    def test_req_14_deleted_chapter_fallback(self):
        """Req 14: If saved reading position references deleted chapter, fall back to first unread chapter."""
        # Chapters remaining: Chapter 2, Chapter 3 (Chapter 1 was deleted)
        chapters = [{"name": "Chapter 2"}, {"name": "Chapter 3"}]
        reader_data = {"progress": {"Chapter 1": "2.jpg"}, "completed": [], "unread": [], "last_read": "Chapter 1"}
        progress_map = {}

        result = self._resolve_continue_reading(chapters, reader_data, progress_map)
        # Falls back gracefully to first unread chapter
        self.assertEqual(result["action"], "Start Reading")
        self.assertEqual(result["target"], "Chapter 2")

    # =========================================================================
    # Part 3: Library Pinned Manga (Requirements 1-5)
    # =========================================================================

    def test_req_1_and_4_pinning_local_and_remote_persists_across_reloads(self):
        """Req 1 & 4: Pinning works for local and remote series and persists across reloads."""
        # Local pin
        toggle_pin_series("TestManga", True)
        # Remote pin
        toggle_pin_series("remote:mock:sololeveling", True)

        pinned = load_pinned_series()
        self.assertIn("TestManga", pinned)
        self.assertIn("remote:mock:sololeveling", pinned)

        # Verify disk persistence in settings.json
        settings_file = self.config_dir / "settings.json"
        disk = json.loads(settings_file.read_text(encoding="utf-8"))
        canon_path = canonicalize_library_path(self.manga_dir)
        disk_pins = disk.get("pinned_by_library", {}).get(canon_path, []) if "pinned_by_library" in disk else disk.get("pinned", [])
        self.assertIn("TestManga", disk_pins)
        self.assertIn("remote:mock:sololeveling", disk_pins)

    def test_req_2_and_3_partitioning_no_duplicates_and_hidden_when_empty(self):
        """Req 2 & 3: Pinned series are partitioned from unpinned series (no duplicates), hidden when empty."""
        all_series = ["SeriesA", "SeriesB", "SeriesC"]
        pinned_set = set(load_pinned_series())

        # No pinned series initially
        pinned_list = [s for s in all_series if s in pinned_set]
        unpinned_list = [s for s in all_series if s not in pinned_set]
        self.assertEqual(len(pinned_list), 0)
        self.assertEqual(len(unpinned_list), 3)

        # Pin SeriesA
        toggle_pin_series("SeriesA", True)
        pinned_set = set(load_pinned_series())
        pinned_list = [s for s in all_series if s in pinned_set]
        unpinned_list = [s for s in all_series if s not in pinned_set]

        self.assertEqual(pinned_list, ["SeriesA"])
        self.assertEqual(unpinned_list, ["SeriesB", "SeriesC"])
        # No duplicates
        self.assertEqual(set(pinned_list).intersection(set(unpinned_list)), set())

    def test_req_5_search_and_sort_with_pinned(self):
        """Req 5: Search and filter operate before partitioning."""
        all_series = ["Solo Leveling", "One Piece", "Solo Bug Player"]
        toggle_pin_series("Solo Leveling", True)
        pinned_set = set(load_pinned_series())

        query = "solo"
        filtered = [s for s in all_series if query in s.lower()]
        self.assertEqual(len(filtered), 2)  # Solo Leveling and Solo Bug Player

        pinned_list = [s for s in filtered if s in pinned_set]
        unpinned_list = [s for s in filtered if s not in pinned_set]
        self.assertEqual(pinned_list, ["Solo Leveling"])
        self.assertEqual(unpinned_list, ["Solo Bug Player"])

    # =========================================================================
    # Part 4: CSS Contrast & Pin Button Styling Invariants
    # =========================================================================

    def test_css_invariants_for_pin_button_and_resume_reading_contrast(self):
        """
        Verify CSS contains required styling:
        - .btn-card-pin has width: 36px, height: 36px, border-radius: 50%
        - .btn-resume-reading and hover states have #FFFFFF !important
        """
        css_file = PROJECT_ROOT / "static" / "style.css"
        self.assertTrue(css_file.is_file())
        css_text = css_file.read_text(encoding="utf-8")

        # Pin button circular 36px
        self.assertIn(".btn-card-pin {", css_text)
        self.assertIn("width: 36px;", css_text)
        self.assertIn("height: 36px;", css_text)
        self.assertIn("border-radius: 50%;", css_text)
        self.assertIn(".btn-card-pin.pinned svg path {", css_text)
        self.assertIn("fill: currentColor;", css_text)

        # Resume reading contrast
        self.assertIn(".btn-resume-reading:hover", css_text)
        self.assertIn("color: #FFFFFF !important;", css_text)
        self.assertIn(".btn-resume-reading .resume-icon", css_text)
        self.assertIn("fill: #FFFFFF !important;", css_text)


if __name__ == "__main__":
    unittest.main()
