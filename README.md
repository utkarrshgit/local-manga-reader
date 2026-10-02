# { index }

A local manga and manhwa reader that runs in your web browser.

![anime gif](https://i.pinimg.com/originals/1a/71/58/1a7158689e5ce37e5d78d97c332a003f.gif)

## Features

- Vertical scrolling reader
- Manga and manhwa reading modes
- Reading progress and resume
- Chapter bookmarks
- Series covers and backgrounds
- Series metadata and external links
- Persistent manga library selection
- Keyboard shortcuts
- Safari/mobile-friendly interface

## Quick Start

Start the launcher for your system:

- **macOS**: `start-mac.command`
- **Windows**: `start-windows.bat`
- **Linux**: `start-linux.sh`

On first launch, you will be prompted to select your manga library folder. Your folder selection is remembered for future launches.

## Manga Library Structure

Organize your library by series and chapter folders:

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

Your manga library can be stored anywhere on your computer and does not need to be inside the project folder.

## Changing the Library Folder

You can switch to another library at any time by clicking "Change Manga Folder" on the library page.

## Reading

- **Spaced mode**: Pages have gaps between them, suited for traditional manga.
- **Seamless mode**: Pages form one continuous vertical strip, suited for webtoons and manhwa.
- Reading progress is saved automatically as you scroll.
- Bookmarks can be added while reading to quickly return to specific pages.

## Data & Privacy

- The app runs entirely on your local machine.
- Your manga files are never copied, moved, or modified.
- Reading progress, bookmarks, and series metadata are stored locally inside each series' `.reader` folder.

## Troubleshooting

- **Python 3 is not installed**: Install Python 3 and ensure it is available in your command line / PATH.
- **Launcher permission (macOS / Linux)**: If running the script gives a permission error, make it executable:
  - macOS: `chmod +x start-mac.command`
  - Linux: `chmod +x start-linux.sh`
