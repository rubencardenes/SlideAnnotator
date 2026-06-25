from __future__ import annotations

from dbagenticquery import AgentEvent
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..settings import get_settings
from ..workers.agent_worker import AgentWorker
from .widgets.chart_canvas import ChartWindow

_ROLE_STYLES = {
    "user": "color: #cde; background: #20304a; border-radius: 6px; padding: 6px 10px;",
    "agent": "color: #e8e8e8; background: #232323; border-radius: 6px; padding: 6px 10px;",
    "error": "color: #ffb3b3; background: #3a1f1f; border-radius: 6px; padding: 6px 10px;",
    "sql": (
        "color: #9fd0a0; background: #1d2620; border-radius: 6px; padding: 6px 10px; "
        "font-family: monospace; font-size: 11px;"
    ),
}


class AgentPanel(QWidget):
    """Bottom panel: ask the annotation database questions in natural language."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: AgentWorker | None = None
        self._history: list[dict] | None = None
        self._status_label: QLabel | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet("background: #161616;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(6)

        top = QFrame()
        top.setFrameShape(QFrame.Shape.HLine)
        top.setStyleSheet("background: #333; max-height: 1px;")
        layout.addWidget(top)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFixedHeight(180)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: #161616; }")

        self._results = QWidget()
        self._results.setStyleSheet("background: #161616;")
        self._results_layout = QVBoxLayout(self._results)
        self._results_layout.setContentsMargins(4, 4, 4, 4)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch(1)
        self._scroll.setWidget(self._results)
        self._scroll.hide()
        layout.addWidget(self._scroll)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText(
            'Ask about the annotation database… e.g. "How many annotations are there?" '
            'or "Plot annotations per biomarker"'
        )
        self._input.setStyleSheet(
            "QLineEdit { background: #222; color: #eee; border: 1px solid #444; "
            "border-radius: 4px; padding: 6px 8px; }"
        )
        self._input.returnPressed.connect(self._on_ask)

        self._ask_btn = QPushButton("Ask")
        self._ask_btn.setFixedWidth(70)
        self._ask_btn.setStyleSheet(
            "QPushButton { background: #2a4a7a; color: #eee; border: none; "
            "border-radius: 4px; padding: 6px 8px; }"
            "QPushButton:hover { background: #355d99; }"
            "QPushButton:disabled { background: #2a2a2a; color: #777; }"
        )
        self._ask_btn.clicked.connect(self._on_ask)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(60)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: #2e2e2e; color: #ccc; border: 1px solid #444; "
            "border-radius: 4px; padding: 6px 8px; }"
            "QPushButton:hover { background: #3a3a3a; }"
        )
        self._clear_btn.clicked.connect(self._on_clear)

        self._toggle_btn = QPushButton("Show")
        self._toggle_btn.setFixedWidth(60)
        self._toggle_btn.setStyleSheet(
            "QPushButton { background: #2e2e2e; color: #ccc; border: 1px solid #444; "
            "border-radius: 4px; padding: 6px 8px; }"
            "QPushButton:hover { background: #3a3a3a; }"
        )
        self._toggle_btn.clicked.connect(self._on_toggle_panel)

        row.addWidget(self._input)
        row.addWidget(self._ask_btn)
        row.addWidget(self._clear_btn)
        row.addWidget(self._toggle_btn)
        layout.addLayout(row)

    # ------------------------------------------------------------------
    def _add_bubble(self, text: str, role: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(_ROLE_STYLES.get(role, _ROLE_STYLES["agent"]))
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._results_layout.insertWidget(self._results_layout.count() - 1, lbl)
        self._scroll_to_bottom()
        return lbl

    def _add_chart(self, fig: Figure) -> None:
        window = ChartWindow(fig, title="Agent chart", parent=self.window())
        window.show()
        window.raise_()
        window.activateWindow()

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_status(self, text: str) -> None:
        if self._status_label is None:
            self._status_label = self._add_bubble(text, role="agent")
            self._status_label.setStyleSheet(
                _ROLE_STYLES["agent"] + "color: #888; font-style: italic;"
            )
        else:
            self._status_label.setText(text)
        self._scroll_to_bottom()

    def _clear_status(self) -> None:
        if self._status_label is not None:
            self._status_label.deleteLater()
            self._status_label = None

    def _show_panel(self) -> None:
        if not self._scroll.isVisible():
            self._scroll.setVisible(True)
            self._toggle_btn.setText("Hide")

    def _on_toggle_panel(self) -> None:
        visible = not self._scroll.isVisible()
        self._scroll.setVisible(visible)
        self._toggle_btn.setText("Hide" if visible else "Show")

    # ------------------------------------------------------------------
    def _on_clear(self) -> None:
        self._history = None
        self._status_label = None
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _on_ask(self) -> None:
        question = self._input.text().strip()
        if not question or self._worker is not None:
            return
        self._show_panel()
        self._add_bubble(question, role="user")
        self._input.clear()
        self._set_busy(True)

        db_path = get_settings().db_path.expanduser().resolve()
        db_url = f"sqlite:///{db_path}"

        self._worker = AgentWorker(question, db_url, history=self._history)
        self._worker.event_received.connect(self._on_event)
        self._worker.finished_signal.connect(self._on_finished)
        self._worker.start()

    def _set_busy(self, busy: bool) -> None:
        self._ask_btn.setEnabled(not busy)
        self._input.setEnabled(not busy)

    def _on_event(self, event: AgentEvent) -> None:
        if event.kind == "thinking":
            self._set_status(str(event.content))
        elif event.kind == "sql":
            self._clear_status()
            self._add_bubble(f"SQL: {event.content}", role="sql")
        elif event.kind == "text":
            self._clear_status()
            self._add_bubble(str(event.content), role="agent")
        elif event.kind == "chart":
            self._clear_status()
            self._add_chart(event.content)
        elif event.kind == "error":
            self._clear_status()
            self._add_bubble(str(event.content), role="error")
        elif event.kind == "history":
            self._history = event.content

    def _on_finished(self) -> None:
        self._clear_status()
        self._set_busy(False)
        self._worker = None

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Wait for any in-flight agent query before the app closes."""
        if self._worker is not None:
            self._worker.wait(2000)
