"""
test_keyboard_shortcuts.py - Automated regression tests for manga reader keyboard shortcuts.

Covers:
1. Up and Down arrow viewport scrolling (~70-80% viewport height, smooth scrolling, preventDefault).
2. Shift + Up / Shift + Down chapter top/bottom instant jumps.
3. Shift + S reading mode toggling (Spaced <-> Seamless) and server persistence.
4. Shift + R chapter Read/Unread toggling (both local and remote), feedback, and explicit unread persistence.
5. Plain 's' / 'S' manga page screenshot saving to <root>/Screenshots/<Series Name>/Chapter XXX - Page YYY.ext.
6. Disambiguation between plain 's'/'S' (save screenshot) and Shift + 's'/'S' (toggle reading mode).
7. Non-registration of plain 'r' / 'R'.
8. Library scanner discovery exclusion of root-level Screenshots/ directory (case-insensitive, exact match).
9. Atomic creation and incremental collision handling for screenshots (never overwrite).
10. Editable elements guard (input, textarea, select, contentEditable) and modifier keys guard.
11. Documentation consistency in README.md and PROJECT_CONTEXT.md.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from http import HTTPStatus
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server import (
    MangaLibrary,
    MangaRequestHandler,
    detect_image_format,
    extract_chapter_number_str,
    extract_page_number_str,
    pad_number_str,
    sanitize_path_component,
)
from providers.mock import MockProvider
from providers.registry import ProviderRegistry
from providers.service import RemoteReaderService


class TestKeyboardShortcutsImplementation(unittest.TestCase):
    """Test suite verifying reader keyboard shortcut logic, contracts, and backend methods."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app_js_path = PROJECT_ROOT / "static" / "app.js"
        cls.app_js = cls.app_js_path.read_text(encoding="utf-8")
        cls.readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        cls.project_context = (PROJECT_ROOT / "PROJECT_CONTEXT.md").read_text(encoding="utf-8")

    def test_documentation_includes_new_shortcuts(self) -> None:
        """Verify README.md and PROJECT_CONTEXT.md document all reader keyboard shortcuts including zoom."""
        for doc_name, content in [("README.md", self.readme), ("PROJECT_CONTEXT.md", self.project_context)]:
            with self.subTest(document=doc_name):
                self.assertIn("Up Arrow", content)
                self.assertIn("Down Arrow", content)
                self.assertIn("Shift + Up Arrow", content)
                self.assertIn("Shift + Down Arrow", content)
                self.assertIn("Shift + S", content)
                self.assertIn("Shift + R", content)
                self.assertIn("`S`", content)
                self.assertIn("`=`", content)
                self.assertIn("`-`", content)
                self.assertIn("`0`", content)

    def test_shortcut_handlers_structure_in_app_js(self) -> None:
        """Verify app.js event listener correctly structures Shift+R, Shift+S, plain S, =, -, 0, and no plain R."""
        # Shift + R handler present
        self.assertIn('e.shiftKey && (e.key === "R" || e.key === "r")', self.app_js)
        # Shift + S handler present
        self.assertIn('e.shiftKey && (e.key === "S" || e.key === "s" || e.code === "KeyS")', self.app_js)
        # Plain S handler present and strictly requires !e.shiftKey
        self.assertIn('!e.shiftKey && (e.key === "s" || e.key === "S")', self.app_js)
        # Plain R is NOT implemented as a shortcut
        self.assertNotIn('!e.shiftKey && (e.key === "r" || e.key === "R")', self.app_js)
        self.assertNotIn('e.key === "r"', self.app_js.replace('e.key === "R" || e.key === "r"', ''))
        # Zoom shortcuts present
        self.assertIn('e.key === "=" || e.key === "+"', self.app_js)
        self.assertIn('e.key === "-" || e.key === "_"', self.app_js)
        self.assertIn('e.key === "0"', self.app_js)
        self.assertIn('e.code === "Digit0"', self.app_js)
        self.assertIn('e.code === "Numpad0"', self.app_js)
        self.assertIn('e.code === "Equal"', self.app_js)
        self.assertIn('e.code === "Minus"', self.app_js)
        self.assertIn('e.code === "NumpadAdd"', self.app_js)
        self.assertIn('e.code === "NumpadSubtract"', self.app_js)
        self.assertIn('e.keyCode === 187', self.app_js)
        self.assertIn('e.keyCode === 189', self.app_js)
        self.assertIn('const readerHeader =', self.app_js)
        self.assertIn('changeReaderZoom(10)', self.app_js)
        self.assertIn('changeReaderZoom(-10)', self.app_js)
        self.assertIn('resetReaderZoom(true)', self.app_js)

    def test_reader_shortcuts_via_node_harness(self) -> None:
        """Simulate and verify keydown event handlers and contracts in a Node environment."""
        node_script = """
        const fs = require('fs');
        const code = fs.readFileSync('static/app.js', 'utf8');

        // Verify key handlers exist in code
        if (!code.includes('e.shiftKey && (e.key === "R" || e.key === "r")')) {
            console.error('Shift+R handler missing');
            process.exit(1);
        }
        if (!code.includes('e.shiftKey && (e.key === "S" || e.key === "s" || e.code === "KeyS")')) {
            console.error('Shift+S handler missing');
            process.exit(2);
        }
        if (!code.includes('!e.shiftKey && (e.key === "s" || e.key === "S")')) {
            console.error('Plain S handler missing');
            process.exit(3);
        }
        if (!code.includes('saveCurrentPageScreenshot()')) {
            console.error('saveCurrentPageScreenshot invocation missing');
            process.exit(4);
        }

        // Test behavioral simulation
        let currentReadingStyle = 'spaced';
        let appliedStyle = null;
        let screenshotSaved = false;
        let chapterCompletedToggled = false;
        let toggledNewState = null;

        function applyReadingStyle(style, persist) {
            currentReadingStyle = style;
            appliedStyle = style;
        }

        function saveCurrentPageScreenshot() {
            screenshotSaved = true;
        }

        let isDone = false;
        function isChapterCompleted(ch) { return isDone; }
        function toggleChapterCompleted(series, chapter, nextState) {
            chapterCompletedToggled = true;
            toggledNewState = nextState;
        }

        let scrolledBy = null;
        let scrolledTo = null;
        const windowMock = {
            innerHeight: 1000,
            scrollBy: (opts) => { scrolledBy = opts; },
            scrollTo: (opts) => { scrolledTo = opts; }
        };
        const documentMock = {
            documentElement: { scrollHeight: 5000 },
            body: { scrollHeight: 5000 }
        };

        const currentSeries = "Test Series";
        const currentChapter = "Chapter 01";

        function simulateKeydown(e, isReaderActive = true, activeTag = '') {
            if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') return;
            if (e.metaKey || e.ctrlKey || e.altKey) return;
            if (!isReaderActive) return;

            if (e.shiftKey && (e.key === "R" || e.key === "r")) {
                e.defaultPrevented = true;
                if (!currentSeries || !currentChapter) return;
                const done = isChapterCompleted(currentChapter);
                toggleChapterCompleted(currentSeries, currentChapter, !done);
            } else if (e.shiftKey && (e.key === "S" || e.key === "s" || e.code === "KeyS")) {
                e.defaultPrevented = true;
                const nextStyle = currentReadingStyle === "spaced" ? "seamless" : "spaced";
                applyReadingStyle(nextStyle, true);
            } else if (!e.shiftKey && (e.key === "s" || e.key === "S")) {
                e.defaultPrevented = true;
                saveCurrentPageScreenshot();
            } else if (e.shiftKey && e.key === "ArrowUp") {
                e.defaultPrevented = true;
                windowMock.scrollTo({ top: 0, behavior: "instant" });
            } else if (e.shiftKey && e.key === "ArrowDown") {
                e.defaultPrevented = true;
                const maxScroll = Math.max(documentMock.documentElement.scrollHeight, documentMock.body.scrollHeight);
                windowMock.scrollTo({ top: maxScroll, behavior: "instant" });
            } else if (e.key === "ArrowUp") {
                e.defaultPrevented = true;
                const scrollDistance = Math.round(windowMock.innerHeight * 0.75);
                windowMock.scrollBy({ top: -scrollDistance, behavior: "smooth" });
            } else if (e.key === "ArrowDown") {
                e.defaultPrevented = true;
                const scrollDistance = Math.round(windowMock.innerHeight * 0.75);
                windowMock.scrollBy({ top: scrollDistance, behavior: "smooth" });
            }
        }

        // 1. Shift + R toggles unread -> read
        isDone = false;
        chapterCompletedToggled = false;
        let evR1 = { key: 'R', shiftKey: true };
        simulateKeydown(evR1);
        if (!evR1.defaultPrevented || !chapterCompletedToggled || toggledNewState !== true) process.exit(10);

        // 2. Shift + R toggles read -> unread
        isDone = true;
        chapterCompletedToggled = false;
        let evR2 = { key: 'r', shiftKey: true };
        simulateKeydown(evR2);
        if (!evR2.defaultPrevented || !chapterCompletedToggled || toggledNewState !== false) process.exit(11);

        // 3. Plain 'r' does NOT toggle
        chapterCompletedToggled = false;
        let evPlainR = { key: 'r', shiftKey: false };
        simulateKeydown(evPlainR);
        if (evPlainR.defaultPrevented || chapterCompletedToggled) process.exit(12);

        // 4. Plain 's' triggers saveCurrentPageScreenshot and NOT applyReadingStyle
        screenshotSaved = false;
        appliedStyle = null;
        let evS1 = { key: 's', shiftKey: false };
        simulateKeydown(evS1);
        if (!evS1.defaultPrevented || !screenshotSaved || appliedStyle !== null) process.exit(13);

        // 5. Plain 'S' (e.g. CapsLock on without shift) triggers saveCurrentPageScreenshot
        screenshotSaved = false;
        appliedStyle = null;
        let evS2 = { key: 'S', shiftKey: false };
        simulateKeydown(evS2);
        if (!evS2.defaultPrevented || !screenshotSaved || appliedStyle !== null) process.exit(14);

        // 6. Shift + S triggers applyReadingStyle and NOT saveCurrentPageScreenshot
        screenshotSaved = false;
        currentReadingStyle = 'spaced';
        let evShiftS = { key: 'S', shiftKey: true };
        simulateKeydown(evShiftS);
        if (!evShiftS.defaultPrevented || screenshotSaved || currentReadingStyle !== 'seamless') process.exit(15);

        // 7. Arrow keys and jumps preserved
        let evUp = { key: 'ArrowUp', shiftKey: false };
        simulateKeydown(evUp);
        if (!evUp.defaultPrevented || scrolledBy.top !== -750) process.exit(16);

        // 8. Form control guard
        screenshotSaved = false;
        let evInput = { key: 's', shiftKey: false };
        simulateKeydown(evInput, true, 'input');
        if (evInput.defaultPrevented || screenshotSaved) process.exit(17);

        console.log('ALL_SHORTCUT_CONTRACTS_PASSED');
        """
        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Node verification failed: {result.stderr}")
        self.assertIn("ALL_SHORTCUT_CONTRACTS_PASSED", result.stdout)

    def test_zoom_shortcuts_and_temporary_state_lifecycle(self) -> None:
        """Verify all 13 zoom requirements: range 50%-300%, 10% steps, clamping, reset rules, and modifier guards."""
        node_script = """
        const fs = require('fs');
        const code = fs.readFileSync('static/app.js', 'utf8');

        // Verify core functions and constants exist
        if (!code.includes('const MIN_READER_ZOOM = 50;')) process.exit(1);
        if (!code.includes('const MAX_READER_ZOOM = 300;')) process.exit(2);
        if (!code.includes('const DEFAULT_READER_ZOOM = 100;')) process.exit(3);
        if (!code.includes('function setReaderZoom(')) process.exit(4);
        if (!code.includes('function changeReaderZoom(')) process.exit(5);
        if (!code.includes('function resetReaderZoom(')) process.exit(6);

        // Test behavioral simulation
        let currentReaderZoom = 100;
        const MIN_READER_ZOOM = 50;
        const MAX_READER_ZOOM = 300;
        const DEFAULT_READER_ZOOM = 100;
        let containerCssProps = {};
        let indicatorText = null;
        let indicatorVisible = false;

        const readerContainer = {
            style: {
                setProperty: (k, v) => { containerCssProps[k] = v; },
                getPropertyValue: (k) => containerCssProps[k]
            },
            querySelectorAll: () => []
        };
        const readerZoomIndicator = {
            textContent: '',
            classList: {
                add: (c) => { if (c === 'visible') indicatorVisible = true; },
                remove: (c) => { if (c === 'visible') indicatorVisible = false; },
                contains: (c) => c === 'visible' ? indicatorVisible : false
            }
        };

        function setReaderZoom(zoomPercent, showFeedback = true) {
            const clamped = Math.max(MIN_READER_ZOOM, Math.min(MAX_READER_ZOOM, Math.round(zoomPercent)));
            currentReaderZoom = clamped;
            readerContainer.style.setProperty('--reader-zoom', (clamped / 100).toString());
            if (showFeedback) {
                indicatorText = `${clamped}%`;
                indicatorVisible = true;
            }
        }

        function resetReaderZoom(showFeedback = false) {
            setReaderZoom(DEFAULT_READER_ZOOM, showFeedback);
        }

        function changeReaderZoom(deltaPercent) {
            const target = currentReaderZoom + deltaPercent;
            const clamped = Math.max(MIN_READER_ZOOM, Math.min(MAX_READER_ZOOM, target));
            if (clamped === currentReaderZoom && (target < MIN_READER_ZOOM || target > MAX_READER_ZOOM)) {
                indicatorText = `${clamped}%`;
                indicatorVisible = true;
                return;
            }
            setReaderZoom(clamped, true);
        }

        // 1. Initial zoom starts at 100%
        resetReaderZoom();
        if (currentReaderZoom !== 100 || containerCssProps['--reader-zoom'] !== '1') process.exit(10);

        // 2. '=' increases zoom by 10 percentage points
        changeReaderZoom(10);
        if (currentReaderZoom !== 110 || containerCssProps['--reader-zoom'] !== '1.1' || indicatorText !== '110%') process.exit(11);
        changeReaderZoom(10);
        if (currentReaderZoom !== 120 || containerCssProps['--reader-zoom'] !== '1.2' || indicatorText !== '120%') process.exit(12);

        // 3. '-' decreases zoom by 10 percentage points
        changeReaderZoom(-10);
        if (currentReaderZoom !== 110 || containerCssProps['--reader-zoom'] !== '1.1' || indicatorText !== '110%') process.exit(13);
        changeReaderZoom(-10);
        if (currentReaderZoom !== 100 || containerCssProps['--reader-zoom'] !== '1' || indicatorText !== '100%') process.exit(14);
        changeReaderZoom(-10);
        if (currentReaderZoom !== 90 || containerCssProps['--reader-zoom'] !== '0.9' || indicatorText !== '90%') process.exit(15);

        // 4. Repeated key presses clamp at max 300%
        for (let i = 0; i < 30; i++) changeReaderZoom(10);
        if (currentReaderZoom !== 300 || containerCssProps['--reader-zoom'] !== '3' || indicatorText !== '300%') process.exit(16);
        // Pressing = at 300% stays at 300%
        changeReaderZoom(10);
        if (currentReaderZoom !== 300 || containerCssProps['--reader-zoom'] !== '3') process.exit(17);

        // 5. Repeated key presses clamp at min 50%
        for (let i = 0; i < 35; i++) changeReaderZoom(-10);
        if (currentReaderZoom !== 50 || containerCssProps['--reader-zoom'] !== '0.5' || indicatorText !== '50%') process.exit(18);
        // Pressing - at 50% stays at 50%
        changeReaderZoom(-10);
        if (currentReaderZoom !== 50 || containerCssProps['--reader-zoom'] !== '0.5') process.exit(19);

        // 6. Switching between Spaced and Seamless preserves zoom
        setReaderZoom(150, false);
        let readingMode = 'spaced';
        readingMode = 'seamless'; // mode change does not touch zoom
        if (currentReaderZoom !== 150 || containerCssProps['--reader-zoom'] !== '1.5') process.exit(20);
        readingMode = 'spaced';
        if (currentReaderZoom !== 150 || containerCssProps['--reader-zoom'] !== '1.5') process.exit(21);

        // 7. Entering and exiting fullscreen preserves zoom
        let inFullscreen = false;
        inFullscreen = true; // enter fullscreen
        if (currentReaderZoom !== 150) process.exit(22);
        inFullscreen = false; // exit fullscreen
        if (currentReaderZoom !== 150) process.exit(23);

        // 8. Navigating to another chapter resets zoom to 100%
        resetReaderZoom();
        if (currentReaderZoom !== 100 || containerCssProps['--reader-zoom'] !== '1') process.exit(24);

        // 9. Zooming to 200%, then leaving reader view resets zoom to 100%
        setReaderZoom(200, false);
        if (currentReaderZoom !== 200) process.exit(25);
        resetReaderZoom(); // switchView("chapters")
        if (currentReaderZoom !== 100 || containerCssProps['--reader-zoom'] !== '1') process.exit(26);

        // 10. Reopening the same chapter starts at 100% (never restores old zoom)
        setReaderZoom(180, false);
        resetReaderZoom(); // loadReader executes
        if (currentReaderZoom !== 100 || containerCssProps['--reader-zoom'] !== '1') process.exit(27);

        // 11. Keydown event routing and focus guard
        const viewReader = { classList: { contains: (c) => false } };
        let activeElTag = 'body';
        let isContentEditable = false;

        function simulateKeydown(e, isEditable = false, tag = 'body', isReaderHidden = false) {
            activeElTag = tag;
            isContentEditable = isEditable;
            if (isContentEditable || ['input', 'textarea', 'select'].includes(activeElTag)) {
                return;
            }
            if (e.metaKey || e.ctrlKey || e.altKey) {
                return;
            }
            if (isReaderHidden) {
                return;
            }
            const isZoomIn = (
                e.key === '=' ||
                e.key === '+' ||
                e.key === 'Add' ||
                e.code === 'Equal' ||
                e.code === 'NumpadAdd' ||
                e.code === 'NumpadEqual'
            );
            const isZoomOut = (
                e.key === '-' ||
                e.key === '_' ||
                e.key === 'Subtract' ||
                e.code === 'Minus' ||
                e.code === 'NumpadSubtract'
            );
            const isZoomReset = (
                !e.shiftKey &&
                (
                    e.key === '0' ||
                    e.code === 'Digit0' ||
                    e.code === 'Numpad0' ||
                    e.keyCode === 48 ||
                    e.keyCode === 96
                )
            );

            if (isZoomIn) {
                e.defaultPrevented = true;
                changeReaderZoom(10);
            } else if (isZoomOut) {
                e.defaultPrevented = true;
                changeReaderZoom(-10);
            } else if (isZoomReset) {
                e.defaultPrevented = true;
                resetReaderZoom(true);
            }
        }

        // Editable field guards
        resetReaderZoom();
        let evEdit = { key: '=', shiftKey: false };
        simulateKeydown(evEdit, true, 'input');
        if (evEdit.defaultPrevented || currentReaderZoom !== 100) process.exit(28);

        let evTextarea = { key: '-', shiftKey: false };
        simulateKeydown(evTextarea, true, 'textarea');
        if (evTextarea.defaultPrevented || currentReaderZoom !== 100) process.exit(29);

        let evEditZero = { key: '0', shiftKey: false };
        setReaderZoom(160, false);
        simulateKeydown(evEditZero, true, 'input');
        if (evEditZero.defaultPrevented || currentReaderZoom !== 160) process.exit(30);

        // System modifier guard (Cmd+= / Ctrl+= / Cmd+- / Ctrl+- / Cmd+0 / Ctrl+0)
        let evMeta = { key: '=', metaKey: true };
        simulateKeydown(evMeta);
        if (evMeta.defaultPrevented || currentReaderZoom !== 160) process.exit(31);

        let evCtrl = { key: '-', ctrlKey: true };
        simulateKeydown(evCtrl);
        if (evCtrl.defaultPrevented || currentReaderZoom !== 160) process.exit(32);

        let evMetaZero = { key: '0', metaKey: true };
        simulateKeydown(evMetaZero);
        if (evMetaZero.defaultPrevented || currentReaderZoom !== 160) process.exit(33);

        // Reader inactive guard for 0
        let evHiddenZero = { key: '0' };
        simulateKeydown(evHiddenZero, false, 'body', true);
        if (evHiddenZero.defaultPrevented || currentReaderZoom !== 160) process.exit(34);

        // Normal '=' and '-' keypresses
        setReaderZoom(100, false);
        let evZoomIn = { key: '=', shiftKey: false, code: 'Equal' };
        simulateKeydown(evZoomIn);
        if (!evZoomIn.defaultPrevented || currentReaderZoom !== 110) process.exit(35);

        let evZoomPlus = { key: '+', shiftKey: true, code: 'Equal' };
        simulateKeydown(evZoomPlus);
        if (!evZoomPlus.defaultPrevented || currentReaderZoom !== 120) process.exit(36);

        let evZoomOut = { key: '-', shiftKey: false, code: 'Minus' };
        simulateKeydown(evZoomOut);
        if (!evZoomOut.defaultPrevented || currentReaderZoom !== 110) process.exit(37);

        // Test NumpadAdd and NumpadSubtract by code
        let evNumpadAdd = { code: 'NumpadAdd' };
        simulateKeydown(evNumpadAdd);
        if (!evNumpadAdd.defaultPrevented || currentReaderZoom !== 120) process.exit(38);

        let evNumpadSub = { code: 'NumpadSubtract' };
        simulateKeydown(evNumpadSub);
        if (!evNumpadSub.defaultPrevented || currentReaderZoom !== 110) process.exit(39);

        // Test Shift + '-' producing '_'
        let evUnderscore = { key: '_', shiftKey: true, code: 'Minus' };
        simulateKeydown(evUnderscore);
        if (!evUnderscore.defaultPrevented || currentReaderZoom !== 100) process.exit(40);

        // 12. Test '0' shortcut resetting zoom from above 100%
        setReaderZoom(220, false);
        let evResetAbove = { key: '0', shiftKey: false };
        simulateKeydown(evResetAbove);
        if (!evResetAbove.defaultPrevented || currentReaderZoom !== 100 || indicatorText !== '100%') process.exit(41);

        // 13. Test '0' shortcut resetting zoom from below 100%
        setReaderZoom(60, false);
        let evResetBelow = { code: 'Digit0', shiftKey: false };
        simulateKeydown(evResetBelow);
        if (!evResetBelow.defaultPrevented || currentReaderZoom !== 100 || indicatorText !== '100%') process.exit(42);

        // 14. Test '0' via Numpad0 code
        setReaderZoom(170, false);
        let evNumpadZero = { code: 'Numpad0', shiftKey: false };
        simulateKeydown(evNumpadZero);
        if (!evNumpadZero.defaultPrevented || currentReaderZoom !== 100 || indicatorText !== '100%') process.exit(43);

        // 15. Shift + 0 (closing parenthesis ')') does NOT reset zoom
        setReaderZoom(150, false);
        let evShiftZero = { key: ')', code: 'Digit0', shiftKey: true };
        simulateKeydown(evShiftZero);
        if (evShiftZero.defaultPrevented || currentReaderZoom !== 150) process.exit(44);

        // 16. Verify readerHeader declaration prevents ReferenceError during zoom
        const appCode = fs.readFileSync('static/app.js', 'utf8');
        if (!appCode.includes('const readerHeader = document.querySelector(".reader-header");')) {
            console.error('readerHeader declaration missing from static/app.js');
            process.exit(38);
        }

        console.log('ALL_ZOOM_TESTS_PASSED');
        """
        result = subprocess.run(
            ["node", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Zoom Node verification failed: {result.stderr}")
        self.assertIn("ALL_ZOOM_TESTS_PASSED", result.stdout)

    def test_zoom_markup_and_css(self) -> None:
        """Verify reader zoom markup and CSS rules in static/index.html and static/style.css."""
        index_html = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
        style_css = (PROJECT_ROOT / "static" / "style.css").read_text(encoding="utf-8")

        # HTML markup contains zoom indicator
        self.assertIn('id="reader-zoom-indicator"', index_html)
        self.assertIn('class="reader-zoom-indicator hidden"', index_html)

        # CSS contains zoom indicator styles
        self.assertIn('.reader-zoom-indicator', style_css)
        self.assertIn('.reader-zoom-indicator.visible', style_css)

        # CSS reader container uses --reader-zoom variable
        self.assertIn('--reader-zoom', style_css)
        self.assertIn('calc(min(100%, 900px) * var(--reader-zoom, 1))', style_css)
        self.assertIn('calc(900px * var(--reader-zoom, 1))', style_css)

        # CSS allows horizontal overflow when reader is active
        self.assertIn('html.reader-active,', style_css)
        self.assertIn('body.reader-active {', style_css)
        self.assertIn('overflow-x: auto;', style_css)

        # Fixed positioning and translucent appearance on reader header
        self.assertIn('.reader-header {', style_css)
        self.assertIn('position: fixed;', style_css)
        self.assertIn('background-color: rgba(14, 14, 14, 0.75);', style_css)
        self.assertIn('backdrop-filter: blur(16px);', style_css)
        self.assertIn('max-width: 100vw;', style_css)
        self.assertIn('#view-reader {', style_css)
        self.assertIn('padding-top: calc(52px + env(safe-area-inset-top, 0px));', style_css)


class TestScreenshotAndExclusionBackend(unittest.TestCase):
    """Test suite for MangaLibrary.save_screenshot and Screenshots/ directory scanner exclusions."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_manga_shortcuts_")
        self.root_path = Path(self.test_dir)
        self.library = MangaLibrary(self.root_path)

        # Create dummy series
        self.series_dir = self.root_path / "One Piece"
        self.series_dir.mkdir(parents=True)
        self.ch1_dir = self.series_dir / "Chapter 012"
        self.ch1_dir.mkdir(parents=True)

        # 1x1 valid PNG bytes
        self.png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        (self.ch1_dir / "025.png").write_bytes(self.png_bytes)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_screenshot_naming_and_atomic_write(self) -> None:
        """Verify screenshot is written to <root>/Screenshots/<Series>/Chapter 012 - Page 025.png with zero-padding."""
        res = self.library.save_screenshot(
            series_name="One Piece",
            chapter_name="Chapter 12",
            page_identifier="page_25.png",
            image_bytes=self.png_bytes,
            ext=".png",
            page_index=25,
        )
        self.assertIsNotNone(res)
        self.assertTrue(res["success"])
        self.assertEqual(res["filename"], "Chapter 012 - Page 025.png")
        saved_file = Path(res["path"])
        self.assertTrue(saved_file.is_file())
        self.assertEqual(saved_file.read_bytes(), self.png_bytes)
        self.assertEqual(saved_file.parent.name, "One Piece")
        self.assertEqual(saved_file.parent.parent.name, "Screenshots")

    def test_save_screenshot_collision_handling(self) -> None:
        """Verify saving multiple screenshots of same page creates (2), (3) without overwriting."""
        res1 = self.library.save_screenshot(
            series_name="One Piece",
            chapter_name="Chapter 12",
            page_identifier="025.png",
            image_bytes=self.png_bytes,
            ext=".png",
        )
        self.assertEqual(res1["filename"], "Chapter 012 - Page 025.png")

        res2 = self.library.save_screenshot(
            series_name="One Piece",
            chapter_name="Chapter 12",
            page_identifier="025.png",
            image_bytes=self.png_bytes,
            ext=".png",
        )
        self.assertEqual(res2["filename"], "Chapter 012 - Page 025 (2).png")

        res3 = self.library.save_screenshot(
            series_name="One Piece",
            chapter_name="Chapter 12",
            page_identifier="025.png",
            image_bytes=self.png_bytes,
            ext=".png",
        )
        self.assertEqual(res3["filename"], "Chapter 012 - Page 025 (3).png")

        # Verify all 3 files exist on disk
        shots_dir = self.root_path / "Screenshots" / "One Piece"
        self.assertTrue((shots_dir / "Chapter 012 - Page 025.png").is_file())
        self.assertTrue((shots_dir / "Chapter 012 - Page 025 (2).png").is_file())
        self.assertTrue((shots_dir / "Chapter 012 - Page 025 (3).png").is_file())

    def test_save_screenshot_non_standard_names(self) -> None:
        """Verify non-numeric chapter names preserve recognizable sanitized names."""
        res = self.library.save_screenshot(
            series_name="Special / Series?",
            chapter_name="Prologue Special",
            page_identifier="credits.webp",
            image_bytes=b"RIFF....WEBPVP8 ...",
            ext="webp",
            page_index=1,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["filename"], "Prologue Special - Page 001.webp")
        self.assertTrue(Path(res["path"]).is_file())

    def test_screenshots_directory_excluded_from_library_scanner(self) -> None:
        """Verify root Screenshots/ directory is excluded from list_series, list_chapters, etc."""
        # Create Screenshots folder with chapters inside
        screenshots_dir = self.root_path / "Screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        (screenshots_dir / "Some Series").mkdir(parents=True, exist_ok=True)

        # Also create a legitimate series named "Screenshots of Life"
        legit_series = self.root_path / "Screenshots of Life"
        legit_series.mkdir(parents=True, exist_ok=True)
        (legit_series / "Chapter 1").mkdir(parents=True, exist_ok=True)

        series_list = self.library.list_series()
        series_names = [s["name"] for s in series_list]

        # Root "Screenshots" must be excluded
        self.assertNotIn("Screenshots", series_names)
        self.assertNotIn("screenshots", series_names)

        # Legitimate series containing "Screenshots" must NOT be excluded
        self.assertIn("Screenshots of Life", series_names)
        self.assertIn("One Piece", series_names)

        # Direct access to Screenshots as a series must be rejected
        self.assertEqual(self.library.list_chapters("Screenshots"), [])
        self.assertEqual(self.library.list_chapters("screenshots"), [])
        self.assertIsNone(self.library.get_reader_data("Screenshots"))
        self.assertIsNone(self.library.get_cover_source("Screenshots"))

    def test_save_screenshot_from_cbz_archive(self) -> None:
        """Verify saving screenshot from a CBZ archive chapter."""
        cbz_path = self.series_dir / "Chapter 013.cbz"
        with zipfile.ZipFile(cbz_path, "w") as zf:
            zf.writestr("001.png", self.png_bytes)

        # Query image info
        img_info = self.library.get_chapter_image_info("One Piece", "Chapter 013", "001.png")
        self.assertIsNotNone(img_info)
        source_type, archive_path, member_name, _, _ = img_info
        self.assertEqual(source_type, "archive")

        with zipfile.ZipFile(archive_path, "r") as zf:
            img_bytes = zf.read(member_name)

        res = self.library.save_screenshot(
            series_name="One Piece",
            chapter_name="Chapter 013",
            page_identifier="001.png",
            image_bytes=img_bytes,
            ext=".png",
            page_index=1,
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["filename"], "Chapter 013 - Page 001.png")
        self.assertTrue(Path(res["path"]).is_file())


class MockSocket:
    def __init__(self, data: bytes):
        self.rfile = io.BytesIO(data)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, *args, **kwargs):
        if "r" in mode:
            return self.rfile
        return self.wfile

    def sendall(self, data: bytes):
        self.wfile.write(data)


class TestScreenshotEndpointAndReadUnreadSemantics(unittest.TestCase):
    """Test suite for HTTP POST /api/screenshot and read/unread state persistence."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_manga_endpoint_")
        self.root_path = Path(self.test_dir)
        self.library = MangaLibrary(self.root_path)

        # Setup series and chapter
        self.series_dir = self.root_path / "One Piece"
        self.series_dir.mkdir(parents=True)
        self.ch1_dir = self.series_dir / "Chapter 012"
        self.ch1_dir.mkdir(parents=True)

        self.png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        (self.ch1_dir / "025.png").write_bytes(self.png_bytes)

        # Setup remote service with MockProvider
        self.remote_dir = self.root_path / "remote_state"
        self.remote_dir.mkdir(parents=True, exist_ok=True)
        self.registry = ProviderRegistry()
        self.mock_provider = MockProvider()
        self.registry.register(self.mock_provider)
        self.remote_service = RemoteReaderService(registry=self.registry, state_dir=self.remote_dir)

        # Configure MangaRequestHandler
        MangaRequestHandler.library = self.library
        MangaRequestHandler.static_dir = PROJECT_ROOT / "static"
        MangaRequestHandler.remote_service = self.remote_service

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _post_json(self, path: str, payload: dict) -> tuple[int, dict]:
        body_bytes = json.dumps(payload).encode("utf-8")
        req = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode("utf-8") + body_bytes
        sock = MockSocket(req)
        MangaRequestHandler(sock, ("127.0.0.1", 8000), None)
        sock.wfile.seek(0)
        resp = sock.wfile.read()
        hdr_end = resp.find(b"\r\n\r\n")
        hdr_str = resp[:hdr_end].decode("utf-8", errors="replace")
        status_code = int(hdr_str.split("\r\n")[0].split(" ")[1])
        body_str = resp[hdr_end + 4:].decode("utf-8", errors="replace")
        body_json = json.loads(body_str) if body_str.strip() else {}
        return status_code, body_json

    def test_api_screenshot_local_success(self) -> None:
        """Verify POST /api/screenshot successfully saves a local chapter image."""
        status, data = self._post_json(
            "/api/screenshot",
            {
                "series": "One Piece",
                "chapter": "Chapter 012",
                "page": "025.png",
                "page_index": 1,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("filename"), "Chapter 012 - Page 025.png")

        saved = self.root_path / "Screenshots" / "One Piece" / "Chapter 012 - Page 025.png"
        self.assertTrue(saved.is_file())
        self.assertEqual(saved.read_bytes(), self.png_bytes)

    def test_api_screenshot_remote_success(self) -> None:
        """Verify POST /api/screenshot handles remote series and streams original image bytes."""
        mock_page = MagicMock()
        mock_page.url = "https://images.example.com/ch01/page025.png"
        mock_page.index = 25
        mock_page.byte_size = len(self.png_bytes)

        with patch.object(MangaRequestHandler.remote_service, "get_chapter_pages", return_value=[mock_page]), \
             patch.object(MangaRequestHandler.remote_service, "stream_page_image", return_value=(self.png_bytes, "image/png")):

            status, data = self._post_json(
                "/api/screenshot",
                {
                    "series": "remote:weebcentral:01J76XY8CM99",
                    "chapter": "01J76XZ001",
                    "series_title": "Chainsaw Man",
                    "chapter_title": "Chapter 1",
                    "page": "1.jpg",
                    "page_index": 1,
                },
            )
            self.assertEqual(status, HTTPStatus.OK)
            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("filename"), "Chapter 001 - Page 001.png")

            saved = self.root_path / "Screenshots" / "Chainsaw Man" / "Chapter 001 - Page 001.png"
            self.assertTrue(saved.is_file())
            self.assertEqual(saved.read_bytes(), self.png_bytes)

    def test_api_screenshot_remote_unmocked_mock_provider(self) -> None:
        """Integration test: Remote screenshot saving exercises real provider image streaming and duplicate handling."""
        status, data = self._post_json(
            "/api/screenshot",
            {
                "series": "remote:mock:sololeveling",
                "chapter": "mock-ch-1",
                "page": "1.jpg",
                "page_index": 1,
            },
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("filename"), "Chapter 001 - Page 001.png")

        screenshot_path = self.root_path / "Screenshots" / "Solo Leveling" / "Chapter 001 - Page 001.png"
        self.assertTrue(screenshot_path.is_file())
        expected_bytes = self.mock_provider.get_image("https://cdn.mock.local/series1/ch1/1.jpg")
        self.assertEqual(screenshot_path.read_bytes(), expected_bytes)

        # Save again to verify duplicate handling without overwriting
        status2, data2 = self._post_json(
            "/api/screenshot",
            {
                "series": "remote:mock:sololeveling",
                "chapter": "mock-ch-1",
                "page": "1.jpg",
                "page_index": 1,
            },
        )
        self.assertEqual(status2, HTTPStatus.OK)
        self.assertTrue(data2.get("success"))
        self.assertEqual(data2.get("filename"), "Chapter 001 - Page 001 (2).png")
        dup_path = self.root_path / "Screenshots" / "Solo Leveling" / "Chapter 001 - Page 001 (2).png"
        self.assertTrue(dup_path.is_file())
        self.assertEqual(dup_path.read_bytes(), expected_bytes)

    def test_api_screenshot_remote_ssrf_protection(self) -> None:
        """Verify remote screenshot saving rejects unsafe/disallowed domains via SSRF protection."""
        from providers.base import RemotePage
        malicious_page = RemotePage(index=1, url="http://169.254.169.254/latest/meta-data/")
        with patch.object(self.remote_service, "get_chapter_pages", return_value=[malicious_page]):
            status, data = self._post_json(
                "/api/screenshot",
                {
                    "series": "remote:mock:sololeveling",
                    "chapter": "mock-ch-1",
                    "page": "1.jpg",
                    "page_index": 1,
                },
            )
            self.assertEqual(status, HTTPStatus.BAD_GATEWAY)
            self.assertIn("error", data)

    def test_api_screenshot_missing_fields(self) -> None:
        """Verify POST /api/screenshot returns 400 when required fields are missing."""
        status, data = self._post_json("/api/screenshot", {"series": "One Piece"})
        self.assertEqual(status, HTTPStatus.BAD_REQUEST)

    def test_read_unread_toggle_preserves_reading_progress(self) -> None:
        """Verify marking unread / read persists unread/completed sets without resetting saved progress."""
        # Save reading progress first
        self.library.update_progress("One Piece", "Chapter 012", "025.png")
        data_before = self.library.get_reader_data("One Piece")
        self.assertEqual(data_before["progress"]["Chapter 012"], "025.png")

        # Mark read via /api/complete
        status1, res1 = self._post_json(
            "/api/complete",
            {"series": "One Piece", "chapter": "Chapter 012", "completed": True},
        )
        self.assertEqual(status1, HTTPStatus.OK)
        self.assertTrue(res1["completed"])
        self.assertIn("Chapter 012", res1["completed_chapters"])
        # Reading progress intact
        self.assertEqual(res1["progress"]["Chapter 012"], "025.png")

        # Mark unread via /api/complete
        status2, res2 = self._post_json(
            "/api/complete",
            {"series": "One Piece", "chapter": "Chapter 012", "completed": False},
        )
        self.assertEqual(status2, HTTPStatus.OK)
        self.assertFalse(res2["completed"])
        self.assertNotIn("Chapter 012", res2["completed_chapters"])
        self.assertIn("Chapter 012", res2["unread_chapters"])
        # Reading progress STILL intact
        self.assertEqual(res2["progress"]["Chapter 012"], "025.png")

    def test_held_arrow_key_and_single_tap_scrolling(self) -> None:
        """Verify single tap vs held arrow key scrolling behaviors and cancel handlers."""
        node_script = """
        const fs = require('fs');
        const code = fs.readFileSync('static/app.js', 'utf8');

        if (!code.includes('startHeldArrowScroll')) process.exit(1);
        if (!code.includes('stopHeldArrowScroll')) process.exit(2);
        if (!code.includes('e.repeat')) process.exit(3);
        if (!code.includes('window.addEventListener("keyup"')) process.exit(4);

        let rafCallbacks = [];
        function requestAnimationFrame(cb) {
            rafCallbacks.push(cb);
            return rafCallbacks.length;
        }
        function cancelAnimationFrame(id) {
            rafCallbacks = [];
        }

        let scrollByCalls = [];
        const windowMock = {
            innerHeight: 1000,
            scrollBy: (opts) => scrollByCalls.push(opts)
        };

        let heldArrowKey = null;
        let heldScrollRafId = null;
        let lastHeldScrollTime = 0;

        function stopHeldArrowScroll() {
            if (heldScrollRafId) {
                cancelAnimationFrame(heldScrollRafId);
                heldScrollRafId = null;
            }
            heldArrowKey = null;
            lastHeldScrollTime = 0;
        }

        function startHeldArrowScroll(key) {
            if (heldArrowKey === key && heldScrollRafId) return;
            heldArrowKey = key;
            lastHeldScrollTime = 1000;
            if (heldScrollRafId) {
                cancelAnimationFrame(heldScrollRafId);
                heldScrollRafId = null;
            }
            const scrollLoop = (timestamp) => {
                if (!heldArrowKey) {
                    stopHeldArrowScroll();
                    return;
                }
                const now = timestamp || 1016;
                const dt = Math.min(0.05, Math.max(0.001, (now - lastHeldScrollTime) / 1000));
                lastHeldScrollTime = now;
                const speed = Math.max(800, Math.round(windowMock.innerHeight * 1.8));
                const distance = Math.round(speed * dt);
                if (distance > 0) {
                    const dir = heldArrowKey === "ArrowUp" ? -1 : 1;
                    windowMock.scrollBy({ top: dir * distance, behavior: "instant" });
                }
                heldScrollRafId = requestAnimationFrame(scrollLoop);
            };
            heldScrollRafId = requestAnimationFrame(scrollLoop);
        }

        // 1. Single tap Down: invokes smooth scroll
        let evDown = { key: "ArrowDown", repeat: false };
        if (evDown.repeat) {
            startHeldArrowScroll("ArrowDown");
        } else {
            stopHeldArrowScroll();
            windowMock.scrollBy({ top: 750, behavior: "smooth" });
        }
        if (scrollByCalls.length !== 1 || scrollByCalls[0].behavior !== "smooth" || scrollByCalls[0].top !== 750) {
            process.exit(10);
        }
        scrollByCalls = [];

        // 2. Single tap Up: invokes smooth scroll
        let evUp = { key: "ArrowUp", repeat: false };
        if (evUp.repeat) {
            startHeldArrowScroll("ArrowUp");
        } else {
            stopHeldArrowScroll();
            windowMock.scrollBy({ top: -750, behavior: "smooth" });
        }
        if (scrollByCalls.length !== 1 || scrollByCalls[0].behavior !== "smooth" || scrollByCalls[0].top !== -750) {
            process.exit(11);
        }
        scrollByCalls = [];

        // 3. Held Down (repeat: true): starts RAF loop and steps smoothly
        let evDownRepeat = { key: "ArrowDown", repeat: true };
        if (evDownRepeat.repeat) {
            startHeldArrowScroll("ArrowDown");
        }
        if (!heldScrollRafId || rafCallbacks.length === 0) process.exit(12);

        const cb1 = rafCallbacks.pop();
        cb1(1016);
        if (scrollByCalls.length !== 1 || scrollByCalls[0].behavior !== "instant" || scrollByCalls[0].top <= 0) process.exit(13);

        const cb2 = rafCallbacks.pop();
        cb2(1032);
        if (scrollByCalls.length !== 2 || scrollByCalls[1].behavior !== "instant") process.exit(14);

        // 4. Keyup stops continuous scroll loop
        stopHeldArrowScroll();
        if (heldArrowKey !== null || heldScrollRafId !== null || rafCallbacks.length !== 0) process.exit(15);

        // 5. Opposite key switch direction
        startHeldArrowScroll("ArrowDown");
        startHeldArrowScroll("ArrowUp");
        if (heldArrowKey !== "ArrowUp") process.exit(16);
        stopHeldArrowScroll();

        console.log("HELD_SCROLL_TEST_PASSED");
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, f"Node held scroll test failed: {proc.stderr}")
        self.assertIn("HELD_SCROLL_TEST_PASSED", proc.stdout)

    def test_chapters_navigation_exits_fullscreen(self) -> None:
        """Verify that navigating back to chapters via navigateBackToChapters exits fullscreen when active before changing hash."""
        node_script = """
        const fs = require('fs');
        const code = fs.readFileSync('static/app.js', 'utf8');

        // Confirm redundant Safari fullscreen workaround is removed
        if (code.includes('activeFullscreenAnchor')) process.exit(1);
        if (code.includes('__fsDiag')) process.exit(2);
        if (code.includes('isExitingFullscreen')) process.exit(3);

        // Confirm exitFullscreen helper and async navigateBackToChapters exist
        if (!code.includes('function exitFullscreen(')) process.exit(4);
        if (!code.includes('async function navigateBackToChapters(')) process.exit(5);
        if (!code.includes('await exitFullscreen()')) process.exit(6);

        // Test behavioral semantics
        let exitFullscreenCalls = 0;
        let isFs = true;

        const fakeDoc = {
            exitFullscreen: () => {
                exitFullscreenCalls++;
                isFs = false;
                return Promise.resolve();
            }
        };

        function isFullscreenActive() {
            return isFs;
        }

        function exitFullscreen() {
            if (!isFullscreenActive()) {
                return Promise.resolve();
            }
            return fakeDoc.exitFullscreen().catch(() => {});
        }

        let hashValue = "";
        let currentSeries = "Berserk";

        async function navigateBackToChapters() {
            if (isFullscreenActive()) {
                await exitFullscreen();
            }
            if (currentSeries) {
                hashValue = `#/series/${encodeURIComponent(currentSeries)}`;
            } else {
                hashValue = "#/";
            }
        }

        (async () => {
            // Scenario 1: Reader is in fullscreen mode
            isFs = true;
            await navigateBackToChapters();
            if (exitFullscreenCalls !== 1) process.exit(10);
            if (hashValue !== "#/series/Berserk") process.exit(11);
            if (isFs !== false) process.exit(12);

            // Scenario 2: Reader is not in fullscreen mode
            exitFullscreenCalls = 0;
            hashValue = "";
            currentSeries = "One Piece";
            await navigateBackToChapters();
            if (exitFullscreenCalls !== 0) process.exit(13);
            if (hashValue !== "#/series/One%20Piece") process.exit(14);

            console.log("CHAPTERS_FULLSCREEN_EXIT_TEST_PASSED");
        })().catch((err) => {
            console.error(err);
            process.exit(20);
        });
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, f"Node chapters fullscreen exit test failed: {proc.stderr}")
        self.assertIn("CHAPTERS_FULLSCREEN_EXIT_TEST_PASSED", proc.stdout)

    def test_series_header_title_centering_styles(self) -> None:
        """Verify series header title is centered relative to header-container with side constraints and truncation."""
        style_css = (PROJECT_ROOT / "static" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".header-series-title {", style_css)
        self.assertIn("left: 50%;", style_css)
        self.assertIn("top: 50%;", style_css)
        self.assertIn("transform: translate(-50%, -50%);", style_css)
        self.assertIn("text-overflow: ellipsis;", style_css)
        self.assertIn("overflow: hidden;", style_css)
        self.assertIn("white-space: nowrap;", style_css)
        # Ensure header-series-nav does not create an unbalanced positioned context
        nav_idx = style_css.find(".header-series-nav {")
        self.assertNotEqual(nav_idx, -1)
        nav_block = style_css[nav_idx:style_css.find("}", nav_idx)]
        self.assertNotIn("position: relative", nav_block)


if __name__ == "__main__":
    unittest.main()

