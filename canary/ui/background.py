"""The background thread: runs the worker (and, from task 7, the Telegram listener) beside the window."""
import asyncio

from PySide6.QtCore import QThread, Signal

from .. import db, worker
from ..analyze import analyze_leak


class Background(QThread):
    changed = Signal()                 # a leak was processed: screens should refresh

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self._vault = vault            # task 7 passes this to the listener
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None

    def run(self) -> None:
        conn = db.connect()            # SQLite connections belong to one thread, so this one opens its own
        self._loop = asyncio.new_event_loop()
        self._stop = asyncio.Event()

        async def main() -> None:
            while not self._stop.is_set():
                if worker.process_next(conn, analyze_leak):
                    self.changed.emit()
                    continue
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

        try:
            self._loop.run_until_complete(main())
        finally:
            conn.close()
            self._loop.close()

    def stop(self) -> None:
        if self._loop and self._stop and self.isRunning():
            self._loop.call_soon_threadsafe(self._stop.set)
        self.wait(5000)
