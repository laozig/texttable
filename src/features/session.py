from __future__ import annotations

from pathlib import Path

from src.features.settings import SettingsManager


class SessionManager:
    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings

    def add_recent_file(self, path: str) -> None:
        files = self._settings.get_recent_files()
        if path in files:
            files.remove(path)
        files.insert(0, path)
        self._settings.set_recent_files(files[:10])

    def get_recent_files(self) -> list[str]:
        files = self._settings.get_recent_files()
        return [path for path in files if Path(path).exists()]

    def set_last_session(self, files: list[str], text_backup: str) -> None:
        self._settings.set_last_files(files)
        self._settings.set_last_text(text_backup)

    def load_last_files(self) -> list[str]:
        files = self._settings.get_last_files()
        return [path for path in files if Path(path).exists()]

    def load_last_text(self) -> str:
        return self._settings.get_last_text()
