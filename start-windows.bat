@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Local Manga & Manhwa Reader - Windows One-Click Launcher
:: ============================================================================

:: 1. Determine project directory dynamically from script's own location
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: 2. Port configuration
if not defined PORT set "PORT=8000"

:: 3. Detect Python 3 (prefer 'py -3', fallback to 'python')
set "PYTHON_CMD="
py -3 -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    python -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo ============================================================
    echo   [ERROR] Python 3 is not installed or not found in PATH!
    echo ============================================================
    echo Python 3 is required to run the local manga reader.
    echo Please install Python 3 from:
    echo   https://www.python.org/
    echo.
    echo Note: During installation, be sure to check:
    echo   "Add python.exe to PATH"
    echo ============================================================
    echo.
    pause
    exit /b 1
)

:: 4. Resolve configuration path (%LOCALAPPDATA%\LocalMangaReader\library_path)
if not defined LOCALAPPDATA (
    set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
)
set "CONFIG_DIR=%LOCALAPPDATA%\LocalMangaReader"
set "CONFIG_FILE=%CONFIG_DIR%\settings.json"
set "LEGACY_CONFIG_FILE=%CONFIG_DIR%\library_path"

:: 5. Resolve manga directory
set "TARGET_MANGA_DIR="

:: Check if MANGA_DIR environment variable is set (development/testing override)
if defined MANGA_DIR (
    if exist "%MANGA_DIR%\" (
        set "TARGET_MANGA_DIR=%MANGA_DIR%"
    ) else (
        echo.
        echo ============================================================
        echo   [ERROR] Specified MANGA_DIR does not exist!
        echo ============================================================
        echo Path: %MANGA_DIR%
        echo ============================================================
        echo.
        pause
        exit /b 1
    )
)

:: Check if a custom path or --choose-dir was passed via command line
if not defined TARGET_MANGA_DIR (
    if "%~1"=="--choose-dir" (
        set "FORCE_CHOOSE=1"
    ) else if not "%~1"=="" (
        if exist "%~1\" (
            set "TARGET_MANGA_DIR=%~1"
        )
    )
)

:: If not specified via environment or CLI argument, check saved configuration
if not defined TARGET_MANGA_DIR (
    set "SAVED_PATH="
    if exist "%CONFIG_FILE%" (
        for /f "usebackq delims=" %%I in (`%PYTHON_CMD% -c "import json, sys; (lambda: print(json.load(open(sys.argv[1], encoding='utf-8')).get('library_path') or ''))()" "%CONFIG_FILE%" 2^>nul`) do (
            set "SAVED_PATH=%%I"
        )
    )
    if not defined SAVED_PATH (
        if exist "%LEGACY_CONFIG_FILE%" (
            set /p SAVED_PATH=<"%LEGACY_CONFIG_FILE%"
        )
    )

    if defined SAVED_PATH (
        if not defined FORCE_CHOOSE (
            if exist "!SAVED_PATH!\" (
                set "TARGET_MANGA_DIR=!SAVED_PATH!"
            ) else (
                echo Previous manga directory no longer exists:
                echo   !SAVED_PATH!
                echo Opening folder picker to select a new directory...
            )
        )
    )

    :: Prompt for folder selection if not yet configured or no longer exists
    if not defined TARGET_MANGA_DIR (
        if not defined SAVED_PATH (
            echo No manga library configured yet.
            echo Please choose your manga library folder...
        )

        set "CHOSEN_PATH="
        for /f "usebackq delims=" %%I in (`powershell -STA -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = 'Select your Manga library folder'; $d.ShowNewFolderButton = $true; if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $d.SelectedPath }"`) do (
            set "CHOSEN_PATH=%%I"
        )

        if not defined CHOSEN_PATH (
            echo.
            echo ============================================================
            echo   No manga library folder selected.
            echo ============================================================
            echo The reader cannot start without a manga library folder.
            echo Launch start-windows.bat again whenever you are ready.
            echo ============================================================
            echo.
            pause
            exit /b 0
        )

        if not exist "!CHOSEN_PATH!\" (
            echo.
            echo ============================================================
            echo   [ERROR] Selected path does not exist or is not a directory:
            echo   !CHOSEN_PATH!
            echo ============================================================
            echo.
            pause
            exit /b 1
        )

        :: Save the selected path outside the git repository in settings.json
        if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"
        %PYTHON_CMD% -c "import json, os, sys; c, leg, p = sys.argv[1:4]; d = {}; (lambda: exec('try:\n d.update(json.load(open(c, encoding=\'utf-8\')))\nexcept: pass'))() if os.path.isfile(c) else None; d['library_path'] = p; open(c + '.tmp', 'w', encoding='utf-8').write(json.dumps(d, indent=2)); os.replace(c + '.tmp', c); (os.remove(leg) if os.path.isfile(leg) else None)" "%CONFIG_FILE%" "%LEGACY_CONFIG_FILE%" "!CHOSEN_PATH!" 2>nul
        set "TARGET_MANGA_DIR=!CHOSEN_PATH!"
        echo Manga library saved: !TARGET_MANGA_DIR!
    )
)

:: 6. Launch background readiness poller to open default browser once server is responsive
start "" /B powershell -NoProfile -Command "$url = 'http://localhost:%PORT%/api/status'; for ($i = 0; $i -lt 40; $i++) { Start-Sleep -Milliseconds 250; try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { Start-Process 'http://localhost:%PORT%'; exit 0 } } catch {} }; exit 1"

:: 7. Start server in foreground so logs are visible and process terminates cleanly
echo.
echo ============================================================
echo   Starting Local Manga Reader...
echo ============================================================
echo Project Directory : %PROJECT_DIR%
echo Library Directory : %TARGET_MANGA_DIR%
echo Server URL        : http://localhost:%PORT%
echo ============================================================
echo.

if "%PORT%"=="8000" (
    %PYTHON_CMD% server.py --dir "%TARGET_MANGA_DIR%"
) else (
    %PYTHON_CMD% server.py --dir "%TARGET_MANGA_DIR%" --port %PORT%
)

if errorlevel 1 (
    echo.
    echo Server terminated with exit code %ERRORLEVEL%.
    pause
)

endlocal
