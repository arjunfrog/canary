"""The background thread: runs the analysis worker and the Telegram listener beside the window.

Both run on one asyncio loop in this thread. Each thread opens its own SQLite connection. The window
is told what changed through two signals and reads the database itself.
"""
import asyncio
import threading

from PySide6.QtCore import QThread, Signal

from .. import db, lurker, worker
from ..analyze import make_handler


class Background(QThread):
    leak_changed = Signal(int)         # a leak arrived or changed status: lists should refresh
    case_created = Signal(int)         # a leak was analysed into this case

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self._vault = vault
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._stop_requested = threading.Event()       # set even if stop() is called before the loop exists
        self.telegram = lurker.ListenerState()         # read by the status line

    def run(self) -> None:
        conn = db.connect()            # SQLite connections belong to one thread, so this one opens its own
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop = asyncio.Event()
        if self._stop_requested.is_set():
            self._stop.set()

        def on_case(leak_id: int, case_id: int | None) -> None:
            if case_id is not None:
                self.case_created.emit(case_id)

        handler = make_handler(self._vault, on_case=on_case)

        async def main() -> None:
            from .. import reader
            asyncio.get_running_loop().run_in_executor(None, reader.warm_up)   # loads the photo models in the background
            await asyncio.gather(
                worker.run_worker(handler, self._stop, on_done=self.leak_changed.emit),
                lurker.run_listener(conn, self._vault, self._stop, on_leak=self.leak_changed.emit, state=self.telegram))

        try:
            self._loop.run_until_complete(main())
        finally:
            conn.close()
            self._loop.close()

    def stop(self) -> None:
        self._stop_requested.set()
        loop, stop = self._loop, self._stop
        if loop is not None and stop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop.set)
            except RuntimeError:                       # the loop closed between the check and the call
                pass
        self.wait(10000)
