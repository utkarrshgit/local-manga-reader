#!/bin/bash
# ==============================================================================
# Local Manga & Manhwa Reader - Linux One-Click Launcher
# ==============================================================================

# 1. Determine project directory dynamically from the script's own location
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
cd "$PROJECT_DIR" || {
    echo "Error: Cannot change directory to $PROJECT_DIR"
    exit 1
}

# 2. Port configuration
PORT="${PORT:-8000}"
SERVER_URL="http://localhost:${PORT}"

# 3. Check for Python 3 (prefer python3, fallback to python if Python 3)
PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    if python -c 'import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="python"
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    echo ""
    echo "============================================================"
    echo "  [ERROR] Python 3 is required but could not be found."
    echo "============================================================"
    echo "Python 3 is required to run the local manga reader."
    echo "Please install Python 3 using your package manager, e.g.:"
    echo "  Debian/Ubuntu/Mint:  sudo apt install python3"
    echo "  Fedora/RHEL:         sudo dnf install python3"
    echo "  Arch Linux:          sudo pacman -S python"
    echo "============================================================"
    echo ""
    if [ -t 0 ]; then
        read -r -p "Press [Enter] to exit..." _
    fi
    exit 1
fi

# 4. Local configuration path (stored outside git repository)
CONFIG_DIR="${LOCAL_MANGA_CONFIG_DIR:-"${XDG_CONFIG_HOME:-"$HOME/.config"}/LocalMangaReader"}"
CONFIG_FILE="${LOCAL_MANGA_CONFIG_FILE:-"$CONFIG_DIR/library_path"}"

# Helper function to prompt for folder on Linux
choose_folder_linux() {
    local prompt_msg="$1"

    # Testing mock override
    if [ -n "$MOCK_FOLDER_PICKER_RESULT" ]; then
        echo "$MOCK_FOLDER_PICKER_RESULT"
        return 0
    fi

    local selected=""

    # 1. Try zenity (GNOME / GTK / universal) if graphical session exists
    if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
        if command -v zenity >/dev/null 2>&1; then
            selected="$(zenity --file-selection --directory --title="$prompt_msg" 2>/dev/null)"
            local z_status=$?
            if [ $z_status -eq 0 ]; then
                echo "$selected"
                return 0
            elif [ $z_status -eq 1 ]; then
                # User deliberately canceled
                return 1
            fi
            # Return code > 1 indicates execution error; continue to fallback
        fi

        # 2. Try kdialog (KDE / Qt)
        if command -v kdialog >/dev/null 2>&1; then
            selected="$(kdialog --getexistingdirectory "$HOME" --title "$prompt_msg" 2>/dev/null)"
            local k_status=$?
            if [ $k_status -eq 0 ]; then
                echo "$selected"
                return 0
            elif [ $k_status -eq 1 ]; then
                # User deliberately canceled
                return 1
            fi
            # Return code > 1 indicates execution error; continue to fallback
        fi
    fi

    # 3. Terminal-based fallback if stdin is available
    if [ -t 0 ]; then
        echo ""
        echo "============================================================"
        echo "  $prompt_msg"
        echo "============================================================"
        echo "Enter the full path to your Manga library folder"
        echo "(or press Enter without typing anything to cancel):"
        read -r -p "> " selected
        selected="$(echo "$selected" | tr -d '\r\n')"
        # Expand ~ if present at start of path
        selected="${selected/#\~/$HOME}"
        if [ -n "$selected" ]; then
            echo "$selected"
            return 0
        fi
        return 1
    fi

    return 1
}

# Helper function to open browser with xdg-open preferred
open_browser() {
    local url="$1"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    elif command -v sensible-browser >/dev/null 2>&1; then
        sensible-browser "$url" >/dev/null 2>&1 &
    elif command -v gio >/dev/null 2>&1; then
        gio open "$url" >/dev/null 2>&1 &
    elif [ -n "$PYTHON_BIN" ]; then
        "$PYTHON_BIN" -m webbrowser "$url" >/dev/null 2>&1 &
    fi
}

# Helper function to test server status endpoint
check_server_status() {
    local url="$1"
    if command -v curl >/dev/null 2>&1; then
        curl -s -f "$url" >/dev/null 2>&1
        return $?
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O - "$url" >/dev/null 2>&1
        return $?
    else
        "$PYTHON_BIN" -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('$url').getcode() == 200 else 1)" >/dev/null 2>&1
        return $?
    fi
}

# 5. Resolve manga directory
TARGET_MANGA_DIR=""

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

        RAW_SELECTION="$(choose_folder_linux "$PICKER_PROMPT")"
        PICKER_STATUS=$?

        CLEAN_SELECTION="$(echo "$RAW_SELECTION" | tr -d '\r\n')"
        if [ "$CLEAN_SELECTION" != "/" ]; then
            CLEAN_SELECTION="${CLEAN_SELECTION%/}"
        fi

        if [ $PICKER_STATUS -ne 0 ] || [ -z "$CLEAN_SELECTION" ]; then
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
    "$PYTHON_BIN" server.py --dir "$TARGET_MANGA_DIR" &
else
    "$PYTHON_BIN" server.py --dir "$TARGET_MANGA_DIR" --port "$PORT" &
fi
SERVER_PID=$!

# 8. Wait until server has successfully started and listens on port
echo "Waiting for server to become ready on port ${PORT}..."
MAX_ATTEMPTS=40
ATTEMPT=0
SERVER_READY=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
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

    if check_server_status "${SERVER_URL}/api/status"; then
        SERVER_READY=1
        break
    fi

    sleep 0.25
    ATTEMPT=$((ATTEMPT + 1))
done

# 9. Open default browser once server is confirmed ready
if [ $SERVER_READY -eq 1 ]; then
    echo "Server is ready! Opening default browser to ${SERVER_URL}..."
    open_browser "${SERVER_URL}"
else
    echo "Warning: Timeout waiting for server response. Opening browser..."
    open_browser "${SERVER_URL}"
fi

# 10. Keep server process running while launcher is active
wait "$SERVER_PID"
