# { index }

A fast, lightweight local manga and manhwa reader that runs entirely in your web browser.

## Features

- **Vertical reading**: Smooth, continuous vertical scroll experience.
- **Manga & manhwa reading modes**: Switch between seamless webtoon view and single-page framed view.
- **Reading progress**: Automatically remembers current chapter, page, and reading completion.
- **Bookmarks**: Save favorite pages and jump back to them anytime.
- **Series covers and metadata**: Manage cover images, background art, summaries, author details, and external links.
- **Persistent library folder**: Remembers your configured manga folder across sessions.

## Requirements

- **Python 3**
- **Modern web browser** (Safari, Chrome, Firefox, Edge, etc.)
- **No external Python packages required** (uses only the standard library)

## Quick Start

Run the one-click launcher for your operating system:

- **macOS**: Double-click `start-mac.command`
- **Windows**: Double-click `start-windows.bat`
- **Linux**: Run `./start-linux.sh`

On first launch, a native folder picker will prompt you to select your manga library folder. The selected folder is remembered for future launches and opens automatically in your default browser.

## Manga Library Structure

Your manga library can be stored anywhere on your computer and does not need to be inside the project folder. Organize your folders by series and chapter:

```text
Manga/
├── One Piece/
│   ├── Chapter 1/
│   │   ├── 001.jpg
│   │   └── 002.jpg
│   └── Chapter 2/
│       └── 001.jpg
└── Berserk/
    └── Chapter 1/
        ├── 001.jpg
        └── 002.jpg
```

Common image formats (`.jpg`, `.jpeg`, `.png`, `.webp`, etc.) and natural chapter numbering are supported automatically.

## Changing the Library Folder

You can change your manga folder at any time. Click **Change manga folder** in the top navigation bar of the library page to select a different directory. The library will reload immediately.

## Data & Privacy

- **100% Local**: Runs completely on your computer with no telemetry or external network calls.
- **Safe**: Manga files are never copied, moved, or deleted by the application.
- **Portable**: Reading progress, bookmarks, and series metadata are stored locally in each series' `.reader` folder.

## Troubleshooting

- **Python 3 not installed**: Ensure Python 3 is installed and accessible from your system command line.
- **Launcher permission (macOS / Linux)**: If running the launcher fails with a permission error, make it executable in your terminal:
  - macOS: `chmod +x start-mac.command`
  - Linux: `chmod +x start-linux.sh`
