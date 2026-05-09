from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xml", ".txt", ".md", ".markdown",
    ".csv", ".xlsx", ".xls", ".html", ".htm",
}


class FileWatcher:
    """Watch a folder and dispatch file_process_task for new/modified files."""

    def __init__(self, folder: str, team_id: str) -> None:
        self._folder = folder
        self._team_id = team_id
        self._observer = None

    def start(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            logger.error("watchdog not installed — file watcher disabled. Install with: pip install watchdog")
            return

        from src.file_agent.tasks import file_process_task

        class _Handler(FileSystemEventHandler):
            def __init__(self, team_id: str):
                self._team_id = team_id

            def _dispatch(self, path: str) -> None:
                if Path(path).suffix.lower() in _SUPPORTED_EXTENSIONS:
                    logger.info("file_watcher: queuing %s", path)
                    file_process_task.delay(path, self._team_id)

            def on_created(self, event):
                if not event.is_directory:
                    self._dispatch(event.src_path)

            def on_modified(self, event):
                if not event.is_directory:
                    self._dispatch(event.src_path)

        handler = _Handler(self._team_id)
        self._observer = Observer()
        self._observer.schedule(handler, self._folder, recursive=True)
        self._observer.start()
        logger.info("file_watcher: watching %s", self._folder)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("file_watcher: stopped")


def start_watching(folder: str, team_id: str) -> FileWatcher:
    """Start the watcher and block (call in a dedicated thread/process)."""
    watcher = FileWatcher(folder, team_id)
    watcher.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
    return watcher
