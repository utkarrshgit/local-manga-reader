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
SERVER_URL="http://localhost:${PORT}"

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

# 4. Handle clean shutdown when launcher is closed or interrupted
SERVER_PID=""
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

# 5. Start server.py in the background
echo "============================================================"
echo "  Starting Local Manga Reader..."
echo "============================================================"
echo "Server URL : $SERVER_URL"
echo "============================================================"
echo ""

python3 server.py --port "$PORT" "$@" &
SERVER_PID=$!

# 6. Wait until server has successfully started and listens on port
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

# 7. Open Safari once server is confirmed ready
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

# 8. Keep server process running while launcher is active
wait "$SERVER_PID"
