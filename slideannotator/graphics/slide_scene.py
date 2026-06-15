from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QGraphicsPolygonItem, QGraphicsScene

from ..annotations.models import AnnotationStore, CellMarker, FOVAnnotation, RegionAnnotation
from ..compositing.compositor import ChannelSettings
from ..tiles.tile_cache import TileKey
from ..tiles.tile_manager import TileManager
from .cell_det_cross_item import CellDetCrossItem
from .cell_marker_item import CellMarkerItem
from .fov_item import FOVItem
from .region_item import RegionItem
from .tile_item import TileItem


class SlideScene(QGraphicsScene):
    def __init__(
        self,
        tile_manager: TileManager,
        store: AnnotationStore,
        channel_settings: list[ChannelSettings],
    ) -> None:
        super().__init__()
        self._tile_manager = tile_manager
        self._store = store
        self._channel_settings = channel_settings

        self._tile_items: dict[TileKey, TileItem] = {}
        self._marker_items: dict[str, CellMarkerItem] = {}
        self._region_items: dict[str, RegionItem] = {}
        self._fov_items: dict[str, FOVItem] = {}
        self._stardist_items: list[QGraphicsPolygonItem] = []
        self._cell_det_items: list[CellDetCrossItem] = []
        self._annotations_visible = True
        self._stardist_visible = True
        self._stardist_color = QColor(0, 230, 180)
        self._stardist_width = 2
        self._cell_det_visible = True
        self._cell_det_color = QColor(255, 100, 80)
        self._marker_show_box = False

        self._region_fill_opacity: float = 40 / 255
        self._active_channel: str = ""

        self._current_viewport: QRectF | None = None
        self._current_zoom: float = 1.0
        self._current_level: int = 0
        self._thumbnail_item: TileItem | None = None

        # Connect tile manager
        tile_manager.tile_ready.connect(self.on_tile_ready)

        # Connect annotation store
        store.annotation_added.connect(self._on_annotation_added)
        store.annotation_removed.connect(self._on_annotation_removed)
        store.annotation_moved.connect(self._on_annotation_moved)
        store.selection_changed.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    def load_slide(self, reader) -> None:
        self.clear()
        self._tile_items.clear()
        self._marker_items.clear()
        self._region_items.clear()
        self._fov_items.clear()
        self._stardist_items.clear()
        self._cell_det_items.clear()
        self._current_level = 0
        self._thumbnail_item = None
        w, h = reader.dimensions
        self.setSceneRect(0, 0, w, h)
        self._setup_thumbnail()

    def update_viewport(self, viewport_rect: QRectF, zoom: float) -> None:
        self._current_viewport = viewport_rect
        self._current_zoom = zoom
        downsample = max(1.0 / max(zoom, 1e-6), 1.0)
        self._current_level = self._tile_manager._reader.get_best_level(downsample)
        coarsest = self._tile_manager._reader.level_count - 1
        if self._current_level == coarsest and self._thumbnail_item is not None:
            # Thumbnail already covers the whole image at this level.
            self._cleanup_distant_tiles(viewport_rect)
            return
        self._tile_manager.request_tiles(viewport_rect, zoom, self._channel_settings)
        self._cleanup_distant_tiles(viewport_rect)

    def set_channel_settings(self, settings: list[ChannelSettings]) -> None:
        self._channel_settings = settings

    def refresh_thumbnail(self) -> None:
        if self._thumbnail_item is not None:
            self.removeItem(self._thumbnail_item)
            self._thumbnail_item = None
        self._setup_thumbnail()

    def sync_from_store(self) -> None:
        """Create scene items for any store annotations that don't have one yet."""
        for ann in self._store.all_annotations():
            if isinstance(ann, CellMarker) and ann.id not in self._marker_items:
                self._add_marker_item(ann)
            elif isinstance(ann, RegionAnnotation) and ann.id not in self._region_items:
                self._add_region_item(ann)
            elif isinstance(ann, FOVAnnotation) and ann.id not in self._fov_items:
                self._add_fov_item(ann)

    def set_marker_show_box(self, show: bool) -> None:
        self._marker_show_box = show
        for item in self._marker_items.values():
            item.set_show_box(show)

    def _channel_visible(self, channel: str) -> bool:
        return self._annotations_visible and (
            not self._active_channel or channel == self._active_channel
        )

    def set_active_channel(self, channel: str) -> None:
        self._active_channel = channel
        for ann_id, item in self._marker_items.items():
            ann = self._store.get_marker(ann_id)
            item.setVisible(self._channel_visible(ann.channel if ann else ""))
        for ann_id, item in self._region_items.items():
            ann = self._store.get_region(ann_id)
            item.setVisible(self._channel_visible(ann.channel if ann else ""))
        for ann_id, item in self._fov_items.items():
            ann = self._store.get_fov(ann_id)
            item.setVisible(self._channel_visible(ann.channel if ann else ""))

    def set_annotations_visible(self, visible: bool) -> None:
        self._annotations_visible = visible
        for ann_id, item in self._marker_items.items():
            ann = self._store.get_marker(ann_id)
            item.setVisible(self._channel_visible(ann.channel if ann else ""))
        for ann_id, item in self._region_items.items():
            ann = self._store.get_region(ann_id)
            item.setVisible(self._channel_visible(ann.channel if ann else ""))
        for ann_id, item in self._fov_items.items():
            ann = self._store.get_fov(ann_id)
            item.setVisible(self._channel_visible(ann.channel if ann else ""))

    def set_stardist_polygons(self, polygons: list[list[tuple[float, float]]]) -> None:
        for item in self._stardist_items:
            self.removeItem(item)
        self._stardist_items.clear()

        pen = self._make_stardist_pen()
        for poly in polygons:
            qpoly = QPolygonF()
            for px, py in poly:
                qpoly.append(QPointF(px, py))
            item = QGraphicsPolygonItem(qpoly)
            item.setPen(pen)
            item.setBrush(Qt.BrushStyle.NoBrush)
            item.setZValue(15)
            item.setVisible(self._stardist_visible)
            self._stardist_items.append(item)
            self.addItem(item)

    def set_stardist_visible(self, visible: bool) -> None:
        self._stardist_visible = visible
        for item in self._stardist_items:
            item.setVisible(visible)

    def set_stardist_style(self, color: QColor, width: int) -> None:
        self._stardist_color = QColor(color)
        self._stardist_width = width
        pen = self._make_stardist_pen()
        for item in self._stardist_items:
            item.setPen(pen)
        for item in self._cell_det_items:
            item.set_screen_width(width)

    def set_cell_det_points(self, points: list[tuple[float, float]]) -> None:
        for item in self._cell_det_items:
            self.removeItem(item)
        self._cell_det_items.clear()

        for cx, cy in points:
            item = CellDetCrossItem(self._cell_det_color, self._stardist_width)
            item.setPos(cx, cy)
            item.setVisible(self._cell_det_visible)
            self._cell_det_items.append(item)
            self.addItem(item)

    def set_cell_det_visible(self, visible: bool) -> None:
        self._cell_det_visible = visible
        for item in self._cell_det_items:
            item.setVisible(visible)

    def _make_stardist_pen(self) -> QPen:
        pen = QPen(self._stardist_color)
        pen.setCosmetic(True)
        pen.setWidth(self._stardist_width)
        return pen

    # ------------------------------------------------------------------
    def on_tile_ready(self, key: TileKey, qimage) -> None:
        ts = self._tile_manager._reader.tile_size
        ds = self._tile_manager._reader.level_downsamples[key.level]
        scene_x = key.tile_x * ts * ds
        scene_y = key.tile_y * ts * ds

        if key in self._tile_items:
            item = self._tile_items[key]
        else:
            item = TileItem(scene_x, scene_y, ds)
            self._tile_items[key] = item
            self.addItem(item)

        item.setPixmap(QPixmap.fromImage(qimage))

    # ------------------------------------------------------------------
    def _on_annotation_added(self, ann_id: str) -> None:
        ann = self._store.get_annotation(ann_id)
        if ann is None:
            return
        if isinstance(ann, CellMarker):
            self._add_marker_item(ann)
        elif isinstance(ann, RegionAnnotation):
            self._add_region_item(ann)
        elif isinstance(ann, FOVAnnotation):
            self._add_fov_item(ann)

    def _add_marker_item(self, ann: CellMarker) -> None:
        color = self._channel_color(ann.channel)
        item = CellMarkerItem(ann.id, color)
        item.setPos(ann.x, ann.y)
        item.set_show_box(self._marker_show_box)
        item.setVisible(self._channel_visible(ann.channel))
        self._marker_items[ann.id] = item
        self.addItem(item)

    def set_region_fill_opacity(self, opacity: float) -> None:
        self._region_fill_opacity = opacity
        for item in self._region_items.values():
            item.set_fill_opacity(opacity)

    def _add_region_item(self, ann: RegionAnnotation) -> None:
        color = self._channel_color(ann.channel)
        item = RegionItem(ann.id, color, fill_opacity=self._region_fill_opacity)
        polygon = QPolygonF()
        for x, y in ann.points:
            polygon.append(QPointF(x, y))
        item.setPolygon(polygon)
        item.setVisible(self._channel_visible(ann.channel))
        self._region_items[ann.id] = item
        self.addItem(item)

    def _add_fov_item(self, ann: FOVAnnotation) -> None:
        color = self._channel_color(ann.channel)
        item = FOVItem(ann.id, ann.x, ann.y, ann.w, ann.h, color, label=ann.channel)
        item.setVisible(self._channel_visible(ann.channel))
        self._fov_items[ann.id] = item
        self.addItem(item)

    def _on_annotation_removed(self, ann_id: str) -> None:
        for items in (self._marker_items, self._region_items, self._fov_items):
            if ann_id in items:
                self.removeItem(items.pop(ann_id))
                return

    def _on_annotation_moved(self, ann_id: str) -> None:
        ann = self._store.get_marker(ann_id)
        if ann and ann_id in self._marker_items:
            self._marker_items[ann_id].setPos(ann.x, ann.y)
            return
        fov = self._store.get_fov(ann_id)
        if fov and ann_id in self._fov_items:
            self._fov_items[ann_id].setRect(fov.x, fov.y, fov.w, fov.h)
            return
        region = self._store.get_region(ann_id)
        if region and ann_id in self._region_items:
            polygon = QPolygonF()
            for x, y in region.points:
                polygon.append(QPointF(x, y))
            self._region_items[ann_id].setPolygon(polygon)

    def _on_selection_changed(self, selected: object) -> None:
        selected_set = set(selected) if selected else set()
        for ann_id, item in self._marker_items.items():
            item.set_selected(ann_id in selected_set)
        for ann_id, item in self._region_items.items():
            item.set_selected(ann_id in selected_set)
        for ann_id, item in self._fov_items.items():
            item.set_selected(ann_id in selected_set)

    # ------------------------------------------------------------------
    def _setup_thumbnail(self) -> None:
        result = self._tile_manager.load_thumbnail_sync(self._channel_settings)
        if result is None:
            return
        qimage, ds = result
        item = TileItem(0.0, 0.0, ds)
        item.setPixmap(QPixmap.fromImage(qimage))
        item.setZValue(-2)
        self._thumbnail_item = item
        self.addItem(item)

    def _cleanup_distant_tiles(self, viewport: QRectF) -> None:
        margin_w = viewport.width() * 1.5
        margin_h = viewport.height() * 1.5
        keep_rect = viewport.adjusted(-margin_w, -margin_h, margin_w, margin_h)
        to_remove = [
            key
            for key, item in self._tile_items.items()
            if key.level != self._current_level
            or not keep_rect.intersects(item.sceneBoundingRect())
        ]
        for key in to_remove:
            self.removeItem(self._tile_items.pop(key))

    def _channel_color(self, channel_name: str) -> QColor:
        for ch in self._tile_manager._reader.channels:
            if ch.name == channel_name:
                r, g, b = ch.color
                return QColor(r, g, b)
        return QColor(200, 200, 200)
