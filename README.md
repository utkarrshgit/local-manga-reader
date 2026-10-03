![background gif](assets/background.gif)

# { index }

A local manga and manhwa reader that runs in your web browser.

## Features

- Vertical scrolling for manga and manhwa
- Spaced and seamless reading modes
- Automatic reading progress and resume
- Chapter bookmarks
- Series covers and backgrounds
- Series metadata and external links
- Persistent manga library folder
- Keyboard shortcuts
- Safari and mobile-friendly interface

## Preview

![Library](assets/library.png)

![Series page](assets/series.png)

![Reader](assets/reader.png)

![Reading demo](assets/demo.gif)

## Quick Start

### macOS

Double-click `start-mac.command`.

On the first launch, select your manga library folder.

### Windows

Double-click `start-windows.bat`.

On the first launch, select your manga library folder.

### Linux

Run:

```bash
./start-linux.sh
```

On the first launch, select your manga library folder.

The app will open in your default web browser.

## Manga Library Structure

Your manga library should be organized like this:

```text
Manga/
├── Solo Leveling/
│   ├── cover.jpg
│   ├── background.jpg
│   ├── Chapter 1/
│   │   ├── 1.jpg
│   │   ├── 2.jpg
│   │   └── ...
│   └── Chapter 2/
│       ├── 1.jpg
│       ├── 2.jpg
│       └── ...
│
└── Kagurabachi/
    ├── cover.jpg
    ├── background.jpg
    ├── Chapter 1/
    │   ├── 1.jpg
    │   ├── 2.jpg
    │   └── ...
    └── Chapter 2/
        ├── 1.jpg
        ├── 2.jpg
        └── ...
```

`cover.jpg` and `background.jpg` are optional.

Reader data is stored separately inside each series in a `.reader` folder.

## Changing the Library Folder

You can change the manga library folder from the Library page using **Change Manga Folder**.
Your manga library can be stored anywhere on your computer and does not need to be inside the project folder.

The selected folder is saved locally so you don't have to choose it every time you launch the app.

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

If the app does not open:

- **Python 3 is not installed**: Install Python 3 and ensure it is available in your command line / PATH.
- **Launcher permission (macOS / Linux)**: If running the script gives a permission error, make it executable:
  - macOS: `chmod +x start-mac.command`
  - Linux: `chmod +x start-linux.sh`
