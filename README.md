![anime gif](https://raw.githubusercontent.com/utkarrshgit/temp_media/refs/heads/main/local_manga_reader/intro.gif?token=GHSAT0AAAAAAEK4KANW4EC4YM3WUB5WHZQ22WAKZ6Q)

# { index }

A local manga and manhwa reader that runs in your web browser.

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

## Preview

![Library](https://github.com/utkarrshgit/temp_media/blob/775e243b4dc67da77e56ce9e8e6a4b22bc5bfff8/local_manga_reader/Screenshot%201.png)

![Series page](https://raw.githubusercontent.com/utkarrshgit/temp_media/refs/heads/main/local_manga_reader/Screenshot%202.png?token=GHSAT0AAAAAAEK4KANWG3N4W5CKGR4UZC342WAK3DQ)

![Reader](https://raw.githubusercontent.com/utkarrshgit/temp_media/refs/heads/main/local_manga_reader/Screenshot%203.png?token=GHSAT0AAAAAAEK4KANX5ZPSNSY3SY3V2HMQ2WAK3JQ)

![Reading demo](https://github.com/utkarrshgit/temp_media/raw/refs/heads/main/local_manga_reader/demo.webm)

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
