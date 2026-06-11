# SlideAnnotator

A desktop annotation tool for multiplex immunofluorescence (mIF) whole-slide images. Built with PySide6, pyvips, and numpy.

## Features

- **Multi-channel viewer** — display and composite any number of fluorescence channels, each with an independently configurable colour, visibility toggle, and min/max intensity range.
- **Pyramid-aware tile renderer** — loads the correct pyramid level for the current zoom and streams tiles in background threads with an LRU cache, keeping the UI responsive on large images.
- **Cell marker tool** — click to place point annotations on any channel; markers render at a fixed screen size regardless of zoom. Toggle `B` or the toolbar button to switch between dot display and bounding-box display.
- **Region tool** — freehand-draw polygon regions.
- **Select tool** — click or shift-click to select markers/regions/FOVs, drag to reposition, press `D`/`Delete`/`Backspace` to delete.
- **Selection in annotation mode** — while the cell-marker or region tool is active, hold `Shift` to select, move, and delete annotations without switching tools:
  - **Shift+click** on an annotation to select it (click again to deselect).
  - **Shift+drag** on a selected annotation to move it (all selected annotations move together). Works for markers, regions, and FOVs.
  - **Shift+drag** on empty canvas to draw a rubber-band rectangle and select everything inside it.
  - `D` / `Delete` / `Backspace` deletes all currently selected annotations.
- **Pan tool** — drag to pan; right-click drag pans in any tool mode.
- **Field-of-View (FOV) annotations** — press `F` to stamp a 512 × 512 px rectangle centred on the cursor. FOVs are saved as part of the annotation sidecar.
- **FOV image export** — **File → Save FOV Images…** crops each FOV at full resolution and saves a PNG per FOV in an `images/` folder next to the slide. Channel assignment follows fluorescence conventions: DAPI or Hoechst → blue; remaining visible channels → red / green.
- **Cell marker export** — **File → Export Cell Markers (txt)…** writes a text file listing, for every FOV, the bounding boxes of all markers that fall inside it.
- **Annotation visibility toggle** — press `Space` or click the eye button in the toolbar to show / hide all annotations instantly.
- **Annotation persistence** — annotations are saved as JSON files in a configurable directory and can be reloaded with the toolbar load button or on the next session.
- **View settings persistence** — per-image channel visibility, colour, and intensity range are saved automatically to `viewsettings.json` next to the slide and restored when reopening.
- **Configurable settings** — `settings.yaml` at the project root (or `~/.config/slideannotator/settings.yaml`) controls application-level behaviour such as the annotations output directory.
- **Unsaved-changes guard** — prompts to save before opening a new image or quitting.
- **Colorful icon toolbar** — tool buttons use crisp QPainter-drawn icons (pan, marker, region, select, eye, box-marker, save, load, quit) instead of text characters, avoiding platform emoji rendering issues.

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
- [PyYAML](https://pypi.org/project/PyYAML/) ≥ 6.0

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
| `Ctrl+E` | Export cell markers to txt |
| `Ctrl+Q` | Quit |
| `Space` | Toggle annotation visibility |
| `B` | Toggle markers between dot and bounding-box display |
| `F` | Place FOV rectangle centred on cursor |
| `D` / `Delete` | Delete selected annotation(s) |
| `Shift+click` | Select / deselect annotation (works in all tool modes) |
| `Shift+drag` on annotation | Move selected annotation(s) (works in all tool modes) |
| `Shift+drag` on canvas | Rubber-band rectangle selection (works in all tool modes) |
| Scroll wheel | Zoom in / out |
| Right-click drag | Pan (works in all tool modes) |

## Configuration

SlideAnnotator reads `settings.yaml` from the project root directory first, then from `~/.config/slideannotator/settings.yaml`. A minimal file looks like:

```yaml
annotations_dir: ~/data/annotations
```

| Key | Default | Description |
|-----|---------|-------------|
| `annotations_dir` | `~/data/annotations` | Directory where annotation JSON files are saved and loaded from. |

## FOV image export

**File → Save FOV Images…** exports each FOV as a PNG into an `images/` folder next to the slide file. File names follow the pattern `<image_stem>_<x>_<y>_512.png` where `x` and `y` are the top-left level-0 pixel coordinates.

Channel assignment uses at most 3 channels (the currently visible ones):

| Visible channels | Blue | Green | Red |
|-----------------|------|-------|-----|
| 1 | — | — | — (grayscale PNG) |
| 2 | DAPI / Hoechst | — | other channel |
| 3+ | DAPI / Hoechst | 2nd other | 1st other |

If no DAPI or Hoechst channel is visible the last visible channel is assigned to blue.

## Cell marker export format

**File → Export Cell Markers (txt)…** produces a plain-text file. Each line covers one FOV that contains at least one marker:

```
<image_stem>_<fov_x>_<fov_y>: x1,y1,x2,y2 x1,y1,x2,y2 ...
```

Each bounding box is a 20 × 20 px square centred on the marker, in level-0 pixel coordinates.

## Project structure

```
slideannotator/
├── app.py                  # Entry point, logging setup
├── settings.py             # App-level settings loaded from settings.yaml
├── viewsettings.py         # Per-image channel view settings (save / restore)
├── ui/
│   ├── main_window.py      # Main window, menus, file I/O
│   ├── annotation_toolbar.py  # Icon toolbar (QPainter-drawn icons)
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
│   ├── slide_view.py       # QGraphicsView with zoom/pan/key handling
│   ├── cell_marker_item.py
│   ├── fov_item.py         # FOV rectangle item
│   ├── region_item.py
│   └── tile_item.py
├── compositing/
│   └── compositor.py       # Per-channel colour + intensity compositing
├── annotations/
│   ├── models.py           # CellMarker, RegionAnnotation, FOVAnnotation, AnnotationStore
│   └── serializer.py       # JSON load/save + txt export
├── tools/
│   ├── base_tool.py
│   ├── shift_select_mixin.py  # Shared Shift+select/move/rubber-band/delete behaviour
│   ├── pan_tool.py
│   ├── cell_marker_tool.py
│   ├── region_tool.py
│   └── select_tool.py
└── utils/
    └── colors.py           # Default channel colour assignment
```

## Annotation file format

Annotations are stored as a JSON sidecar in the configured `annotations_dir`:

```json
{
  "version": "1.0",
  "slide": "/path/to/image.tif",
  "annotations": [
    {"id": "<uuid>", "type": "cell_marker", "x": 1024.0, "y": 2048.0, "channel": "DAPI"},
    {"id": "<uuid>", "type": "region", "points": [[x1, y1], [x2, y2], "..."], "channel": "CD8"},
    {"id": "<uuid>", "type": "fov", "x": 4096.0, "y": 8192.0, "w": 512.0, "h": 512.0}
  ]
}
```

Coordinates are in level-0 (full-resolution) scene pixels.
