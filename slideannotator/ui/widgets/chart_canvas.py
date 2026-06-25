from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ChartCanvas(FigureCanvasQTAgg):
    """Qt widget that displays a matplotlib Figure."""

    def __init__(self, parent=None) -> None:
        self._fig = Figure(figsize=(6, 4), tight_layout=True)
        super().__init__(self._fig)
        self.setParent(parent)

    def show_figure(self, fig: Figure) -> None:
        """Replace the currently displayed figure."""
        self.figure = fig
        fig.set_tight_layout(True)
        self.draw()


class ChartWindow(QWidget):
    """Top-level pop-up window that displays a matplotlib Figure."""

    def __init__(self, fig: Figure, title: str = "Chart", parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        canvas = ChartCanvas()
        canvas.show_figure(fig)
        layout.addWidget(canvas)
