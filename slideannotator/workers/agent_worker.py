from __future__ import annotations

from pathlib import Path

from dbagenticquery import AgentEvent, query
from PySide6.QtCore import QThread, Signal

try:
    import dbagenticquery
    from dotenv import load_dotenv

    # dbagenticquery's own CLI loads its .env on startup; importing it as a
    # library skips that, so replicate it here to pick up API keys.
    load_dotenv(Path(dbagenticquery.__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


class AgentWorker(QThread):
    """Runs a DBAgenticQuery question in a background thread.

    Emits ``event_received`` for every ``AgentEvent`` the agent yields
    (thinking/sql/text/chart/error/history), then ``finished_signal``.
    """

    event_received = Signal(object)
    finished_signal = Signal()

    def __init__(self, question: str, db_url: str, history: list[dict] | None = None) -> None:
        super().__init__()
        self.question = question
        self.db_url = db_url
        self.history = history

    def run(self) -> None:
        try:
            for event in query(self.question, self.db_url, history=self.history):
                self.event_received.emit(event)
        except Exception as e:
            self.event_received.emit(AgentEvent(kind="error", content=str(e)))
        self.finished_signal.emit()
