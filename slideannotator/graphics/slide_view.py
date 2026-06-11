from __future__ import annotations

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QGraphicsView

from .slide_scene import SlideScene


class SlideView(QGraphicsView):
    ZOOM_FACTOR = 1.15
    MIN_ZOOM = 0.002
    MAX_ZOOM = 40.0

    fov_requested = Signal(object)   # QPointF scene position
    space_pressed = Signal()
    b_pressed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True
        )
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
        )
        self.setRenderHint(self.renderHints())
        self.setBackgroundRole(self.backgroundRole())
        self.setStyleSheet("background: #1a1a1a;")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self._tool = None
        self._panning = False
        self._pan_start = None
        self._pan_hbar = 0
        self._pan_vbar = 0
        self._last_scene_pos = QPointF(0, 0)

    # ------------------------------------------------------------------
    def set_tool(self, tool) -> None:
        self._tool = tool
        if tool is not None and getattr(tool, "is_pan", False):
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)

    def fit_to_slide(self) -> None:
        if self.scene():
            self.resetTransform()
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._on_viewport_changed()

    # ------------------------------------------------------------------
    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
        current = self.transform().m11()
        new_zoom = current * factor
        if new_zoom < self.MIN_ZOOM or new_zoom > self.MAX_ZOOM:
            return
        self.scale(factor, factor)
        self._on_viewport_changed()
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self._pan_hbar = self.horizontalScrollBar().value()
            self._pan_vbar = self.verticalScrollBar().value()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if self._tool and not getattr(self._tool, "is_pan", False):
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self._tool.mouse_press(event, scene_pos)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self._last_scene_pos = self.mapToScene(event.position().toPoint())

        if self._panning:
            delta = event.position().toPoint() - self._pan_start
            self.horizontalScrollBar().setValue(self._pan_hbar - delta.x())
            self.verticalScrollBar().setValue(self._pan_vbar - delta.y())
            event.accept()
            return

        if self._tool:
            self._tool.mouse_move(event, self._last_scene_pos)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton and self._panning:
            self._panning = False
            if self._tool and not getattr(self._tool, "is_pan", False):
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        if self._tool and not getattr(self._tool, "is_pan", False):
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self._tool.mouse_release(event, scene_pos)
                event.accept()
                return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F:
            self.fov_requested.emit(QPointF(self._last_scene_pos))
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space:
            self.space_pressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_B:
            self.b_pressed.emit()
            event.accept()
            return
        if self._tool:
            self._tool.key_press(event)
        super().keyPressEvent(event)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._on_viewport_changed()

    # ------------------------------------------------------------------
    def _on_viewport_changed(self) -> None:
        scene = self.scene()
        if isinstance(scene, SlideScene):
            vr = self.mapToScene(self.viewport().rect()).boundingRect()
            zoom = self.transform().m11()
            scene.update_viewport(vr, zoom)

    def current_zoom(self) -> float:
        return self.transform().m11()

    def viewport_transform(self):
        return self.viewportTransform()
