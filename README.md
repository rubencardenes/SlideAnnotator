# SlideAnnotator

A desktop annotation tool for multiplex immunofluorescence (mIF) whole-slide images. Built with PySide6, pyvips, and numpy.

## Features

- **Multi-channel viewer** — display and composite any number of fluorescence channels, each with an independently configurable colour, visibility toggle, and min/max intensity range.
- **Pyramid-aware tile renderer** — loads the correct pyramid level for the current zoom and streams tiles in background threads with an LRU cache, keeping the UI responsive on large images.
- **Cell marker tool** — click to place point annotations on any channel; markers render at a fixed screen size regardless of zoom.
- **Region tool** — freehand-draw polygon regions.
- **Select tool** — click or shift-click to select markers/regions, drag to reposition markers, press `D`/`Delete`/`Backspace` to delete.
- **Pan tool** — drag to pan; middle-mouse button pans in any mode.
- **Annotation persistence** — annotations are saved as a JSON sidecar file next to the image (`<image>.annotations.json`) and reloaded automatically on next open.
- **Unsaved-changes guard** — prompts to save before opening a new image or quitting.

## Supported file formats

| Format | Extension |
|--------|-----------|
| OME-TIFF / TIFF pyramid | `.tif`, `.tiff` |
| Aperio SVS | `.svs` |
| Hamamatsu NDPI | `.ndpi` |
| Leica SCN | `.scn` |
| PerkinElmer QPTIFF | `.qptiff` |

## Requirements

- Python ≥ 3.10
- [PySide6](https://pypi.org/project/PySide6/) ≥ 6.6
- [pyvips](https://pypi.org/project/pyvips/) ≥ 2.2 (requires libvips ≥ 8.9 for SubIFD pyramid support)
- [numpy](https://pypi.org/project/numpy/) ≥ 1.26

## Installation

```bash
# Clone and enter the repo
git clone <repo-url>
cd SlideAnnotator

# Create a virtual environment and install (uv recommended)
uv sync

# Or with plain pip
pip install -e .
```

## Usage

```bash
# Via the installed entry-point
slideannotator

# Or directly
python main.py
```

Open an image with **File → Open Image** (`Ctrl+O`).

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open image |
| `Ctrl+S` | Save annotations |
| `Ctrl+Q` | Quit |
| `D` / `Delete` | Delete selected annotation(s) |
| Scroll wheel | Zoom in / out |
| Middle mouse | Pan (works in all tool modes) |

## Project structure

```
slideannotator/
├── app.py                  # Entry point, logging setup
├── ui/
│   ├── main_window.py      # Main window, menu, file I/O
│   ├── annotation_toolbar.py
│   └── channel_panel.py    # Per-channel controls
├── readers/
│   ├── base.py             # ImageReader ABC + OME-XML helpers
│   ├── ome_tif.py          # ImageReaderOmeTif (pyvips)
│   ├── slide_reader.py     # OmeTifSlideReader — SlideReader protocol adapter
│   └── protocol.py         # SlideReader protocol + ChannelInfo
├── tiles/
│   ├── tile_manager.py     # Tile request dispatch + LRU caching
│   ├── tile_worker.py      # QRunnable background tile loader
│   └── tile_cache.py       # LRU cache
├── graphics/
│   ├── slide_scene.py      # QGraphicsScene with tile and annotation items
│   ├── slide_view.py       # QGraphicsView with zoom/pan
│   ├── cell_marker_item.py
│   ├── region_item.py
│   └── tile_item.py
├── compositing/
│   └── compositor.py       # Per-channel colour + intensity compositing
├── annotations/
│   ├── models.py           # CellMarker, RegionAnnotation, AnnotationStore
│   └── serializer.py       # JSON load/save
├── tools/
│   ├── pan_tool.py
│   ├── cell_marker_tool.py
│   ├── region_tool.py
│   └── select_tool.py
└── utils/
    └── colors.py           # Default channel colour assignment
```

## Annotation file format

Annotations are stored as a JSON sidecar next to the image:

```json
{
  "version": "1.0",
  "slide": "/path/to/image.tif",
  "annotations": [
    {"id": "<uuid>", "type": "cell_marker", "x": 1024.0, "y": 2048.0, "channel": "DAPI"},
    {"id": "<uuid>", "type": "region", "points": [[x1, y1], [x2, y2], "..."], "channel": "CD8"}
  ]
}
```

Coordinates are in level-0 (full-resolution) scene pixels.
