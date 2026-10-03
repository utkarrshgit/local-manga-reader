#!/bin/bash
# ==============================================================================
# Local Manga & Manhwa Reader - macOS One-Click Launcher
# ==============================================================================

# 1. Determine project directory dynamically from the script's own location
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
cd "$PROJECT_DIR" || {
    echo "Error: Cannot change directory to $PROJECT_DIR"
    exit 1
}

# 2. Port configuration
PORT="${PORT:-8000}"
SERVER_URL="http://127.0.0.1:${PORT}"

# 3. Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "============================================================"
    echo "  [ERROR] Python 3 is not installed or not in PATH."
    echo "============================================================"
    echo "Python 3 is required to run the local manga reader."
    echo "Please install Python 3 (https://www.python.org or via Homebrew)."
    echo "============================================================"
    echo ""
    if [ -t 0 ]; then
        read -r -p "Press [Enter] to exit..." _
    fi
    exit 1
fi

# 4. Local configuration path (stored completely outside git repository)
CONFIG_DIR="${LOCAL_MANGA_CONFIG_DIR:-"$HOME/Library/Application Support/LocalMangaReader"}"
CONFIG_FILE="${LOCAL_MANGA_CONFIG_FILE:-"$CONFIG_DIR/library_path"}"

# Helper function to invoke macOS native folder picker via osascript
choose_folder_with_osascript() {
    local prompt_msg="$1"
    if [ -n "$MOCK_FOLDER_PICKER_RESULT" ]; then
        echo "$MOCK_FOLDER_PICKER_RESULT"
        return 0
    fi

    local result
    result="$(osascript <<EOF 2>/dev/null
tell application "System Events"
    activate
end tell
try
    set selectedFolder to choose folder with prompt "$prompt_msg"
    return POSIX path of selectedFolder
on error number -128
    return ""
end try
EOF
)"
    local status=$?
    if [ $status -ne 0 ]; then
        return 1
    fi
    echo "$result"
}

# 5. Resolve manga directory
TARGET_MANGA_DIR=""

# Check if explicit MANGA_DIR environment variable is provided (for dev/testing)
if [ -n "$MANGA_DIR" ]; then
    if [ ! -d "$MANGA_DIR" ]; then
        echo ""
        echo "============================================================"
        echo "  [ERROR] Specified MANGA_DIR does not exist!"
        echo "============================================================"
        echo "Path: $MANGA_DIR"
        echo "============================================================"
        echo ""
        if [ -t 0 ]; then
            read -r -p "Press [Enter] to exit..." _
        fi
        exit 1
    fi
    TARGET_MANGA_DIR="$MANGA_DIR"
# Check if a directory path argument was passed via CLI
elif [ -n "$1" ] && [ "$1" != "--choose-dir" ] && [ -d "$1" ]; then
    TARGET_MANGA_DIR="$1"
else
    FORCE_CHOOSE=0
    if [ "$1" = "--choose-dir" ]; then
        FORCE_CHOOSE=1
    fi

    SAVED_PATH=""
    if [ -f "$CONFIG_FILE" ]; then
        SAVED_PATH="$(head -n 1 "$CONFIG_FILE" 2>/dev/null | tr -d '\r\n')"
    fi

    # If saved path exists on disk and user did not request re-selection
    if [ $FORCE_CHOOSE -eq 0 ] && [ -n "$SAVED_PATH" ] && [ -d "$SAVED_PATH" ]; then
        TARGET_MANGA_DIR="$SAVED_PATH"
    else
        if [ $FORCE_CHOOSE -eq 1 ]; then
            PICKER_PROMPT="Select your Manga library folder:"
        elif [ -n "$SAVED_PATH" ]; then
            echo "Previous manga directory no longer exists:"
            echo "  $SAVED_PATH"
            echo "Please choose a new manga library folder..."
            PICKER_PROMPT="Previous folder not found. Select your Manga library folder:"
        else
            echo "No manga library configured yet."
            echo "Please choose your manga library folder..."
            PICKER_PROMPT="Select your Manga library folder:"
        fi

        RAW_SELECTION="$(choose_folder_with_osascript "$PICKER_PROMPT")"
        PICKER_STATUS=$?

        # Clean trailing newlines / carriage returns
        CLEAN_SELECTION="$(echo "$RAW_SELECTION" | tr -d '\r\n')"
        # Strip trailing slash if present (unless root directory)
        if [ "$CLEAN_SELECTION" != "/" ]; then
            CLEAN_SELECTION="${CLEAN_SELECTION%/}"
        fi

        # If native picker failed (e.g. headless environment) and stdin is available
        if [ $PICKER_STATUS -ne 0 ] && [ -z "$CLEAN_SELECTION" ]; then
            if [ -t 0 ]; then
                echo "Native folder picker could not be displayed."
                read -r -p "Enter path to manga library folder: " CLEAN_SELECTION
                CLEAN_SELECTION="$(echo "$CLEAN_SELECTION" | tr -d '\r\n')"
            fi
        fi

        if [ -z "$CLEAN_SELECTION" ]; then
            echo ""
            echo "============================================================"
            echo "  No manga library folder selected."
            echo "============================================================"
            echo "The reader cannot start without a manga library folder."
            echo "Launch this script again whenever you are ready."
            echo "============================================================"
            echo ""
            if [ -t 0 ]; then
                read -r -p "Press [Enter] to exit..." _
            fi
            exit 0
        fi

        if [ ! -d "$CLEAN_SELECTION" ]; then
            echo ""
            echo "============================================================"
            echo "  [ERROR] Selected folder does not exist: $CLEAN_SELECTION"
            echo "============================================================"
            echo ""
            if [ -t 0 ]; then
                read -r -p "Press [Enter] to exit..." _
            fi
            exit 1
        fi

        # Save selected path outside the git repository
        mkdir -p "$CONFIG_DIR"
        echo "$CLEAN_SELECTION" > "$CONFIG_FILE"
        TARGET_MANGA_DIR="$CLEAN_SELECTION"
        echo "Manga library saved: $TARGET_MANGA_DIR"
    fi
fi

# 6. Handle clean shutdown when launcher is closed or interrupted
cleanup() {
    trap - INT TERM HUP EXIT
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        echo ""
        echo "Shutting down manga reader server..."
        kill -INT "$SERVER_PID" 2>/dev/null
        for _ in 1 2 3 4 5; do
            if ! kill -0 "$SERVER_PID" 2>/dev/null; then
                break
            fi
            sleep 0.2
        done
        if kill -0 "$SERVER_PID" 2>/dev/null; then
            kill -TERM "$SERVER_PID" 2>/dev/null
        fi
        wait "$SERVER_PID" 2>/dev/null
    fi
}
trap cleanup INT TERM HUP EXIT

# 7. Start server.py in the background
echo "============================================================"
echo "  Starting Local Manga Reader..."
echo "============================================================"
echo "Library Directory : $TARGET_MANGA_DIR"
echo "Server URL        : $SERVER_URL"
echo "============================================================"
echo ""

if [ "$PORT" = "8000" ]; then
    python3 server.py --dir "$TARGET_MANGA_DIR" &
else
    python3 server.py --dir "$TARGET_MANGA_DIR" --port "$PORT" &
fi
SERVER_PID=$!

# 8. Wait until server has successfully started and listens on port
echo "Waiting for server to become ready on port ${PORT}..."
MAX_ATTEMPTS=40
ATTEMPT=0
SERVER_READY=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    # Check if server exited prematurely
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo ""
        echo "============================================================"
        echo "  [ERROR] Server failed to start or exited unexpectedly."
        echo "============================================================"
        wait "$SERVER_PID" 2>/dev/null || true
        if [ -t 0 ]; then
            read -r -p "Press [Enter] to exit..." _
        fi
        exit 1
    fi

    # Check if server is responding on port
    if curl -s -f "${SERVER_URL}/api/status" >/dev/null 2>&1; then
        SERVER_READY=1
        break
    fi

    sleep 0.25
    ATTEMPT=$((ATTEMPT + 1))
done

# 9. Open Safari once server is confirmed ready
if [ $SERVER_READY -eq 1 ]; then
    echo "Server is ready! Opening Safari to ${SERVER_URL}..."
    if command -v open >/dev/null 2>&1; then
        open -a Safari "${SERVER_URL}"
    fi
else
    echo "Warning: Timeout waiting for server response. Opening Safari..."
    if command -v open >/dev/null 2>&1; then
        open -a Safari "${SERVER_URL}"
    fi
fi

# 10. Keep server process running while launcher is active
wait "$SERVER_PID"
