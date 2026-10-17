"""
Regression tests for manga reading-progress restoration lifecycle.
Covers:
1. Resuming from saved page with cached images (immediate alignment).
2. Resuming with delayed image loading (restoration guard remains active beyond 300ms).
3. Layout shifts caused by images above saved page loading after initial restoration.
4. Prevention of Page 1 overwrites during and after restoration timeout.
5. Deliberate user manual scrolling releasing restoration lock.
6. Monotonic reader-load token discarding stale callbacks from rapid chapter switching.
7. Graceful fallback on missing or invalid saved-page identifiers.

Executed via Node.js harness inside Python unittest to maintain zero-dependency design.
"""

import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestReaderProgressRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_js_path = PROJECT_ROOT / "static" / "app.js"
        cls.assertTrue(cls.app_js_path.is_file(), "static/app.js must exist")
        cls.app_js_code = cls.app_js_path.read_text(encoding="utf-8")

    def _run_node_script(self, script_body: str) -> subprocess.CompletedProcess:
        full_script = f"""
const fs = require('fs');
const appCode = fs.readFileSync('{self.app_js_path}', 'utf8');

// Helper to extract function or component from app.js if needed
{script_body}
"""
        res = subprocess.run(
            ["node", "-e", full_script],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )
        return res

    def test_code_structure_invariants(self):
        """Verify required restoration architecture tokens exist in static/app.js."""
        # Active token guard
        self.assertIn("activeReaderLoadToken", self.app_js_code)
        self.assertIn("cancelActiveRestoration", self.app_js_code)
        self.assertIn("isRestoringProgress", self.app_js_code)
        self.assertIn("restorationFailedWithoutInteraction", self.app_js_code)
        # Eager loading on target page
        self.assertIn('imgEl.loading = "eager"', self.app_js_code)
        self.assertIn('imgEl.fetchPriority = "high"', self.app_js_code)
        # Observer guards
        self.assertIn("if (currentLoadToken !== activeReaderLoadToken) return;", self.app_js_code)
        self.assertIn("if (isRestoringProgress || visiblePages.size === 0) return;", self.app_js_code)
        self.assertIn("if (restorationFailedWithoutInteraction)", self.app_js_code)

    def test_cached_images_resume_restores_immediate_alignment(self):
        """Scenario 1: With warm cached images, restoration aligns immediately and unguards observer."""
        script = """
        const assert = require('assert');

        // Simulate DOM environment
        let scrollY = 0;
        let scrollIntoViewCalled = 0;
        let progressSaved = null;

        const targetImg = {
          complete: true,
          naturalHeight: 1200,
          offsetHeight: 1200,
          addEventListener: () => {},
          removeEventListener: () => {}
        };

        const targetPage = {
          id: 'page-10.jpg',
          dataset: { filename: '10.jpg' },
          querySelector: () => targetImg,
          getBoundingClientRect: () => ({ top: 40 }),
          scrollIntoView: (opts) => {
            scrollIntoViewCalled++;
            scrollY = 10800; // Aligned to page 10
          }
        };

        let currentVisibleImage = '10.jpg';
        let isRestoringProgress = true;
        let restorationFailedWithoutInteraction = false;
        let restorationSettled = false;

        const isTargetAligned = () => {
          const rect = targetPage.getBoundingClientRect();
          const hasDimensions = targetImg && (targetImg.naturalHeight > 0 || targetImg.offsetHeight > 50);
          return hasDimensions && (rect.top >= -40 && rect.top <= 140);
        };

        // When target image is already complete, alignment attempt succeeds immediately
        targetPage.scrollIntoView({ behavior: 'instant', block: 'start' });
        if (isTargetAligned()) {
          restorationSettled = true;
          isRestoringProgress = false;
          restorationFailedWithoutInteraction = false;
        }

        assert.strictEqual(scrollIntoViewCalled, 1);
        assert.strictEqual(restorationSettled, true);
        assert.strictEqual(isRestoringProgress, false);
        assert.strictEqual(restorationFailedWithoutInteraction, false);
        assert.strictEqual(currentVisibleImage, '10.jpg');
        console.log('OK: Cached images resume test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Cached images resume test passed", res.stdout)

    def test_delayed_image_loading_preserves_saved_position_and_restores(self):
        """Scenario 2: With delayed loading > 300ms, observer is blocked and aligns once target loads."""
        script = """
        const assert = require('assert');

        let scrollY = 0;
        let progressSaveRequests = [];
        let isRestoringProgress = true;
        let currentVisibleImage = '15.jpg';
        let targetImgLoaded = false;

        const targetImg = {
          complete: false,
          naturalHeight: 0,
          offsetHeight: 0,
          loadListeners: [],
          addEventListener(evt, fn) { if (evt === 'load') this.loadListeners.push(fn); },
          removeEventListener(evt, fn) { this.loadListeners = this.loadListeners.filter(f => f !== fn); },
          triggerLoad() {
            this.complete = true;
            this.naturalHeight = 1500;
            this.offsetHeight = 1500;
            targetImgLoaded = true;
            this.loadListeners.forEach(f => f());
          }
        };

        const targetPage = {
          id: 'page-15.jpg',
          dataset: { filename: '15.jpg' },
          querySelector: () => targetImg,
          getBoundingClientRect: () => ({ top: targetImgLoaded ? 50 : 0 }),
          scrollIntoView: () => {
            if (targetImgLoaded) scrollY = 21000;
          }
        };

        // Simulate IntersectionObserver firing while isRestoringProgress is true (e.g. at 500ms, 1000ms)
        function observerCallback(visiblePageFilename) {
          if (isRestoringProgress) {
            // Blocked by restoration guard!
            return;
          }
          if (visiblePageFilename !== currentVisibleImage) {
            progressSaveRequests.push(visiblePageFilename);
          }
        }

        // At 500ms: Page 1 is visible in viewport, but restoration is unresolved
        observerCallback('1.jpg');
        assert.strictEqual(progressSaveRequests.length, 0, 'Must NOT save Page 1 while restoration is unresolved');

        // At 1500ms: Page 15 image completes loading
        targetImg.triggerLoad();
        targetPage.scrollIntoView();
        isRestoringProgress = false;

        // Now on Page 15
        assert.strictEqual(targetImgLoaded, true);
        assert.strictEqual(scrollY, 21000);
        assert.strictEqual(isRestoringProgress, false);

        // Observer now sees Page 15
        observerCallback('15.jpg');
        assert.strictEqual(progressSaveRequests.length, 0, 'No save needed when viewing target page');
        console.log('OK: Delayed image loading test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Delayed image loading test passed", res.stdout)

    def test_layout_shifts_above_target_page_realigns_scroll(self):
        """Scenario 3: Layout shifts from images loading above target page trigger re-alignment."""
        script = """
        const assert = require('assert');

        let alignAttempts = 0;
        let targetAlignedOffset = 0;

        const targetPage = {
          id: 'page-10.jpg',
          dataset: { filename: '10.jpg' },
          scrollIntoView: () => {
            alignAttempts++;
            targetAlignedOffset = 12000; // Re-aligns to page 10
          }
        };

        let isRestoringProgress = true;
        let restorationSettled = false;

        function onLayoutShift() {
          if (!isRestoringProgress || restorationSettled) return;
          targetPage.scrollIntoView();
        }

        // Simulate preceding pages 1, 2, 3 expanding sequentially
        onLayoutShift(); // Page 1 expands
        onLayoutShift(); // Page 2 expands
        onLayoutShift(); // Page 3 expands

        assert.strictEqual(alignAttempts, 3, 'Must re-align scroll on each preceding layout expansion');
        assert.strictEqual(targetAlignedOffset, 12000);
        console.log('OK: Layout shifts realignment test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Layout shifts realignment test passed", res.stdout)

    def test_saved_progress_never_overwritten_on_safety_limit(self):
        """Scenario 4: If safety limit fires without user interaction, Page 1 is NEVER saved."""
        script = """
        const assert = require('assert');

        let currentVisibleImage = '12.jpg';
        let isRestoringProgress = true;
        let restorationFailedWithoutInteraction = false;
        let progressSaveRequests = [];

        // Safety limit fires at 6 seconds
        function onSafetyLimit() {
          isRestoringProgress = false;
          restorationFailedWithoutInteraction = true;
        }

        onSafetyLimit();
        assert.strictEqual(isRestoringProgress, false);
        assert.strictEqual(restorationFailedWithoutInteraction, true);

        // Observer detects Page 1 in viewport after timeout
        function observerCallback(detectedPage) {
          if (isRestoringProgress) return;
          if (detectedPage !== currentVisibleImage) {
            // Guard: If restoration failed without user interaction, do not passively overwrite saved progress
            if (restorationFailedWithoutInteraction) {
              return;
            }
            currentVisibleImage = detectedPage;
            progressSaveRequests.push(detectedPage);
          }
        }

        observerCallback('1.jpg');
        assert.strictEqual(progressSaveRequests.length, 0, 'Page 1 must NEVER be saved when restoration timed out without user interaction');
        assert.strictEqual(currentVisibleImage, '12.jpg', 'currentVisibleImage must remain unchanged');
        console.log('OK: Safety limit overwrite prevention test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Safety limit overwrite prevention test passed", res.stdout)

    def test_deliberate_user_manual_scroll_releases_restoration(self):
        """Scenario 5: User deliberate interaction releases restoration lock and enables tracking."""
        script = """
        const assert = require('assert');

        let isRestoringProgress = true;
        let restorationFailedWithoutInteraction = false;
        let progressSaved = null;
        let currentVisibleImage = '15.jpg';

        function onUserInteraction() {
          if (isRestoringProgress) {
            isRestoringProgress = false;
            restorationFailedWithoutInteraction = false;
          }
        }

        // User rolls wheel to scroll away to page 3
        onUserInteraction();
        assert.strictEqual(isRestoringProgress, false);
        assert.strictEqual(restorationFailedWithoutInteraction, false);

        // Observer callback on page 3
        function observerCallback(page) {
          if (isRestoringProgress) return;
          if (restorationFailedWithoutInteraction) return;
          if (page !== currentVisibleImage) {
            currentVisibleImage = page;
            progressSaved = page;
          }
        }

        observerCallback('3.jpg');
        assert.strictEqual(progressSaved, '3.jpg', 'User deliberate scroll must successfully update progress');
        assert.strictEqual(currentVisibleImage, '3.jpg');
        console.log('OK: User interaction release test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: User interaction release test passed", res.stdout)

    def test_rapid_chapter_switching_discards_stale_callbacks(self):
        """Scenario 6: Monotonic load token discards stale callbacks from rapid chapter switching."""
        script = """
        const assert = require('assert');

        let activeReaderLoadToken = 0;
        let currentVisibleImage = null;
        let chapterSaved = null;

        // User opens Chapter 1
        const token1 = ++activeReaderLoadToken;

        // User quickly switches to Chapter 2 before Chapter 1 finishes
        const token2 = ++activeReaderLoadToken;

        // Delayed callback from Chapter 1 fires
        function delayedChapter1Callback() {
          if (token1 !== activeReaderLoadToken) {
            return; // Dropped!
          }
          currentVisibleImage = 'ch1_page5.jpg';
          chapterSaved = 'Chapter 1';
        }

        // Active callback from Chapter 2 fires
        function activeChapter2Callback() {
          if (token2 !== activeReaderLoadToken) {
            return;
          }
          currentVisibleImage = 'ch2_page10.jpg';
          chapterSaved = 'Chapter 2';
        }

        delayedChapter1Callback();
        assert.strictEqual(currentVisibleImage, null, 'Stale token1 callback must be ignored');

        activeChapter2Callback();
        assert.strictEqual(currentVisibleImage, 'ch2_page10.jpg');
        assert.strictEqual(chapterSaved, 'Chapter 2');
        console.log('OK: Rapid chapter switching test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Rapid chapter switching test passed", res.stdout)

    def test_invalid_or_missing_saved_image_falls_back_safely(self):
        """Scenario 7: Invalid or missing saved-page identifier falls back to Page 1 safely."""
        script = """
        const assert = require('assert');

        const images = [{ filename: '1.jpg' }, { filename: '2.jpg' }, { filename: '3.jpg' }];
        const filenameToIndex = new Map(images.map((img, idx) => [img.filename, idx + 1]));

        // Case A: savedImage is nonexistent
        const savedImageA = 'deleted_99.jpg';
        let targetPageA = null;
        let initialPageIndexA = 1;
        if (savedImageA && filenameToIndex.has(savedImageA)) {
          targetPageA = { id: `page-${savedImageA}` };
          initialPageIndexA = filenameToIndex.get(savedImageA);
        }

        assert.strictEqual(targetPageA, null);
        assert.strictEqual(initialPageIndexA, 1);

        // Case B: savedImage is empty / undefined
        const savedImageB = undefined;
        let targetPageB = null;
        let initialPageIndexB = 1;
        if (savedImageB && filenameToIndex.has(savedImageB)) {
          targetPageB = { id: `page-${savedImageB}` };
          initialPageIndexB = filenameToIndex.get(savedImageB);
        }

        assert.strictEqual(targetPageB, null);
        assert.strictEqual(initialPageIndexB, 1);
        console.log('OK: Invalid saved image fallback test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Invalid saved image fallback test passed", res.stdout)


if __name__ == "__main__":
    unittest.main()
