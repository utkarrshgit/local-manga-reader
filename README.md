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

![Reading demo](assets/demo.webm)

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

The selected folder is saved locally so you don't have to choose it every time you launch the app.

Your manga files are never copied into the project.

## Reading

### Spaced

Adds space between pages, suitable for traditional manga.

### Seamless

Removes gaps between pages for continuous scrolling, suitable for manhwa/webtoons.

Reading progress is saved automatically and the reader resumes from the last page you reached.

## Data & Privacy

This app runs locally.

Your manga files, reading progress, bookmarks, and series metadata stay on your computer.

No account or cloud service is required.

## Troubleshooting

If the app does not open:

- Make sure Python 3 is installed.
- Make sure your selected manga library folder still exists.
- Try launching the platform-specific script again.
- Check the terminal window for error messages.
