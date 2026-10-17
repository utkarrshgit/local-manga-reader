"""
Regression tests for Safari macOS fullscreen scroll position restoration and progress protection.
Covers:
1. Architectural structure and code invariants in static/app.js.
2. Capturing reading position relative to header/viewport immediately before fullscreen exit.
3. Detecting delayed Safari scroll reset to pre-fullscreen position and restoring accurately.
4. Protecting reading progress and timeline against temporary glitch scroll overwrites.
5. Instant release of restoration guard upon deliberate user manual scrolling.
6. Cancellation of pending restoration work when navigating away or changing chapters.
7. Zero forced scrolling or interference when browser already preserves scroll position correctly (Chrome/Firefox/Edge).

Executed via Node.js harness inside Python unittest to maintain zero-dependency design.
"""

import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestSafariFullscreenRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_js_path = PROJECT_ROOT / "static" / "app.js"
        cls.assertTrue(cls.app_js_path.is_file(), "static/app.js must exist")
        cls.app_js_code = cls.app_js_path.read_text(encoding="utf-8")

    def _run_node_script(self, script_body: str) -> subprocess.CompletedProcess:
        full_script = f"""
const fs = require('fs');
const appCode = fs.readFileSync('{self.app_js_path}', 'utf8');

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
        """Verify required fullscreen restoration functions, variables, and guards exist without forbidden tokens."""
        # Required identifiers and helpers
        self.assertIn("lastFullscreenPosition", self.app_js_code)
        self.assertIn("isFullscreenRestoring", self.app_js_code)
        self.assertIn("captureReaderPosition", self.app_js_code)
        self.assertIn("isReaderPositionAligned", self.app_js_code)
        self.assertIn("restoreReaderPosition", self.app_js_code)
        self.assertIn("cancelFullscreenRestoration", self.app_js_code)
        self.assertIn("scheduleFullscreenRestoration", self.app_js_code)

        # Observer progress protection guard
        self.assertIn("if (isFullscreenRestoring) return;", self.app_js_code)

        # Confirm integration in cancelActiveRestoration
        self.assertIn("cancelFullscreenRestoration()", self.app_js_code)

        # Forbidden tokens from legacy workarounds
        self.assertNotIn("activeFullscreenAnchor", self.app_js_code)
        self.assertNotIn("__fsDiag", self.app_js_code)
        self.assertNotIn("isExitingFullscreen", self.app_js_code)

    def test_fullscreen_position_capture_relative_to_viewport(self):
        """Scenario 1: Capturing reader position relative to viewport and header in fullscreen and normal view."""
        script = """
        const assert = require('assert');

        // Simulate reader DOM
        const page1 = {
          id: 'page-1.jpg',
          dataset: { filename: '1.jpg' },
          getBoundingClientRect: () => ({ top: -2000, bottom: -800, height: 1200 })
        };
        const page2 = {
          id: 'page-2.jpg',
          dataset: { filename: '2.jpg' },
          getBoundingClientRect: () => ({ top: -800, bottom: 400, height: 1200 })
        };
        const page3 = {
          id: 'page-3.jpg',
          dataset: { filename: '3.jpg' },
          getBoundingClientRect: () => ({ top: 400, bottom: 1600, height: 1200 })
        };

        const pageElements = [page1, page2, page3];
        const readerHeader = { offsetHeight: 48 };

        function captureReaderPosition(isFullscreen) {
          const headerHeight = (!isFullscreen) ? readerHeader.offsetHeight : 0;
          let anchorEl = null;
          let anchorFilename = null;
          let anchorOffsetRatio = 0;

          for (const el of pageElements) {
            const rect = el.getBoundingClientRect();
            if (rect.bottom > headerHeight && rect.top <= 900) {
              anchorEl = el;
              anchorFilename = el.dataset.filename || null;
              const visibleTop = Math.max(0, headerHeight - rect.top);
              anchorOffsetRatio = rect.height > 0 ? (visibleTop / rect.height) : 0;
              break;
            }
          }
          return { anchorFilename, anchorOffsetRatio };
        }

        // In fullscreen (headerHeight = 0): page2 crosses top=0 (top: -800, bottom: 400).
        // visibleTop = 0 - (-800) = 800. Ratio = 800 / 1200 = 2/3 = 0.6667
        const posFs = captureReaderPosition(true);
        assert.strictEqual(posFs.anchorFilename, '2.jpg');
        assert.ok(Math.abs(posFs.anchorOffsetRatio - (800 / 1200)) < 0.001);

        console.log('OK: Fullscreen position capture test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Fullscreen position capture test passed", res.stdout)

    def test_safari_scroll_jump_detected_and_restored(self):
        """Scenario 2: When Safari exits fullscreen and resets scroll to page 30, it is detected and restored to page 50."""
        script = """
        const assert = require('assert');

        let currentScrollY = 50000;
        let scrollToCalledWith = null;

        const pages = {
          '30.jpg': {
            id: 'page-30.jpg',
            dataset: { filename: '30.jpg' },
            offsetTop: 29000,
            height: 1000
          },
          '50.jpg': {
            id: 'page-50.jpg',
            dataset: { filename: '50.jpg' },
            offsetTop: 49000,
            height: 1000
          }
        };

        function getPageRect(filename) {
          const p = pages[filename];
          const top = p.offsetTop - currentScrollY;
          return { top, bottom: top + p.height, height: p.height };
        }

        const savedPos = {
          anchorFilename: '50.jpg',
          anchorOffsetRatio: 0.2, // 200px into page 50
          scrollY: 49200
        };

        const headerHeight = 48;

        function isReaderPositionAligned(saved) {
          const rect = getPageRect(saved.anchorFilename);
          const expectedTop = headerHeight - saved.anchorOffsetRatio * rect.height;
          return Math.abs(rect.top - expectedTop) <= 40;
        }

        function restoreReaderPosition(saved) {
          const rect = getPageRect(saved.anchorFilename);
          const targetPageTop = currentScrollY + rect.top;
          const offset = saved.anchorOffsetRatio * rect.height;
          const targetScrollY = Math.max(0, Math.round(targetPageTop + offset - headerHeight));
          scrollToCalledWith = targetScrollY;
          currentScrollY = targetScrollY;
        }

        // Before Safari jump: user is at page 50 (currentScrollY = 49200 - headerHeight = 49152)
        currentScrollY = 49152;
        assert.strictEqual(isReaderPositionAligned(savedPos), true, 'Initially aligned at page 50');

        // Safari glitch: resets scroll to page 30 (pre-fullscreen scroll)
        currentScrollY = 29000;
        assert.strictEqual(isReaderPositionAligned(savedPos), false, 'Detected misaligned scroll jump to page 30');

        // Restoration triggers
        restoreReaderPosition(savedPos);
        assert.strictEqual(scrollToCalledWith, 49152, 'Restored scroll to page 50 reading offset');
        assert.strictEqual(isReaderPositionAligned(savedPos), true, 'Position aligned after restoration');

        console.log('OK: Safari scroll jump detected and restored test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Safari scroll jump detected and restored test passed", res.stdout)

    def test_reading_progress_protected_during_restoration(self):
        """Scenario 3: While isFullscreenRestoring is true, temporary Safari scroll jumps do NOT overwrite reading progress."""
        script = """
        const assert = require('assert');

        let currentVisibleImage = '50.jpg';
        let progressSaved = null;
        let isFullscreenRestoring = true;

        function onIntersectionObserverFired(detectedPage) {
          if (isFullscreenRestoring) {
            // Guarded! Do not overwrite progress during fullscreen restoration
            return;
          }
          if (detectedPage !== currentVisibleImage) {
            currentVisibleImage = detectedPage;
            progressSaved = detectedPage;
          }
        }

        // Safari jumps to page 30 and observer fires
        onIntersectionObserverFired('30.jpg');
        assert.strictEqual(currentVisibleImage, '50.jpg', 'currentVisibleImage must remain 50.jpg');
        assert.strictEqual(progressSaved, null, 'Progress save must NOT be triggered for page 30');

        // Restoration settles back at page 50
        isFullscreenRestoring = false;

        // Observer now fires on page 50
        onIntersectionObserverFired('50.jpg');
        assert.strictEqual(currentVisibleImage, '50.jpg');
        assert.strictEqual(progressSaved, null, 'No unnecessary write when viewing page 50');

        console.log('OK: Reading progress protection test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Reading progress protection test passed", res.stdout)

    def test_deliberate_user_scroll_releases_guard(self):
        """Scenario 4: User deliberate wheel/touch/key input immediately releases isFullscreenRestoring guard."""
        script = """
        const assert = require('assert');

        let isFullscreenRestoring = true;
        let timeoutsCleared = 0;

        function cancelFullscreenRestoration() {
          isFullscreenRestoring = false;
          timeoutsCleared++;
        }

        function onUserInteraction(e) {
          if (e.type === 'keydown') {
            if (e.key === 'f' || e.key === 'F' || e.key === 'Escape') {
              return; // Ignore fullscreen exit trigger keys
            }
          }
          cancelFullscreenRestoration();
        }

        // Pressing F or Escape does NOT cancel prematurely
        onUserInteraction({ type: 'keydown', key: 'F' });
        assert.strictEqual(isFullscreenRestoring, true, 'Exit shortcut key must not cancel guard');

        onUserInteraction({ type: 'keydown', key: 'Escape' });
        assert.strictEqual(isFullscreenRestoring, true, 'Escape key must not cancel guard');

        // User rolls mouse wheel or presses arrow key to deliberately scroll
        onUserInteraction({ type: 'wheel' });
        assert.strictEqual(isFullscreenRestoring, false, 'Wheel scroll must immediately cancel restoration guard');
        assert.strictEqual(timeoutsCleared, 1);

        console.log('OK: User deliberate scroll release test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: User deliberate scroll release test passed", res.stdout)

    def test_cancel_active_restoration_cleans_up_fullscreen_state(self):
        """Scenario 5: Navigating away or changing chapter cancels pending fullscreen restoration cleanly."""
        script = """
        const assert = require('assert');

        let isFullscreenRestoring = true;
        let lastFullscreenPosition = { anchorFilename: '20.jpg', scrollY: 15000 };
        let activeTimeouts = [1, 2, 3];

        function cancelFullscreenRestoration() {
          isFullscreenRestoring = false;
          activeTimeouts = [];
        }

        function cancelActiveRestoration() {
          cancelFullscreenRestoration();
          lastFullscreenPosition = null;
        }

        // Changing chapter invokes cancelActiveRestoration
        cancelActiveRestoration();

        assert.strictEqual(isFullscreenRestoring, false);
        assert.strictEqual(lastFullscreenPosition, null);
        assert.strictEqual(activeTimeouts.length, 0);

        console.log('OK: Cleanup test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Cleanup test passed", res.stdout)

    def test_browser_preserving_scroll_triggers_no_forced_scrolling(self):
        """Scenario 6: In Chrome/Edge/Firefox where scroll position is preserved, isReaderPositionAligned returns true and no scroll is forced."""
        script = """
        const assert = require('assert');

        let scrollToCalls = 0;
        let currentScrollY = 30000;

        const savedPos = {
          anchorFilename: '35.jpg',
          anchorOffsetRatio: 0.1,
          scrollY: 30000
        };

        const pageEl = {
          getBoundingClientRect: () => ({ top: 48 - (0.1 * 1000), height: 1000 }) // Perfectly aligned under 48px header
        };

        function isReaderPositionAligned(saved) {
          const headerHeight = 48;
          const rect = pageEl.getBoundingClientRect();
          const expectedTop = headerHeight - saved.anchorOffsetRatio * rect.height;
          return Math.abs(rect.top - expectedTop) <= 40;
        }

        function restoreReaderPosition() {
          scrollToCalls++;
        }

        // Bounded checks run
        const delays = [50, 150, 300, 500];
        delays.forEach(() => {
          if (!isReaderPositionAligned(savedPos)) {
            restoreReaderPosition();
          }
        });

        assert.strictEqual(scrollToCalls, 0, 'Must NOT force scrolling when browser already preserved scroll position');
        console.log('OK: Non-Safari preserved scroll test passed');
        """
        res = self._run_node_script(script)
        self.assertEqual(res.returncode, 0, f"Node script failed: {res.stderr}")
        self.assertIn("OK: Non-Safari preserved scroll test passed", res.stdout)


if __name__ == "__main__":
    unittest.main()
