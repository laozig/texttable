from __future__ import annotations

import json

from PySide6.QtCore import QSettings, QByteArray


class SettingsManager:
    def __init__(self) -> None:
        self._settings = QSettings("TextTable", "TextTable")

    def save_geometry(self, geometry: QByteArray) -> None:
        self._settings.setValue("window/geometry", geometry)

    def load_geometry(self) -> QByteArray | None:
        value = self._settings.value("window/geometry")
        return value if isinstance(value, QByteArray) else None

    def set_delimiter(self, delimiter: str) -> None:
        self._settings.setValue("parser/delimiter", delimiter)

    def get_delimiter(self) -> str:
        value = self._settings.value("parser/delimiter", "----")
        return str(value)

    def set_column_state(self, state: dict) -> None:
        self._settings.setValue("columns/state", json.dumps(state))

    def get_column_state(self) -> dict | None:
        value = self._settings.value("columns/state")
        if not value:
            return None
        try:
            return json.loads(str(value))
        except json.JSONDecodeError:
            return None

    def set_filters(self, filters: list[dict]) -> None:
        self._settings.setValue("filters/active", json.dumps(filters))

    def get_filters(self) -> list[dict]:
        value = self._settings.value("filters/active")
        if not value:
            return []
        try:
            data = json.loads(str(value))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def set_global_filter(self, text: str) -> None:
        self._settings.setValue("filters/global", text)

    def get_global_filter(self) -> str:
        value = self._settings.value("filters/global", "")
        return str(value)

    def set_export_templates(self, templates: list[dict]) -> None:
        self._settings.setValue("export/templates", json.dumps(templates))

    def get_export_templates(self) -> list[dict]:
        value = self._settings.value("export/templates")
        if not value:
            return []

    def set_filter_templates(self, templates: list[dict]) -> None:
        self._settings.setValue("filters/templates", json.dumps(templates))

    def get_filter_templates(self) -> list[dict]:
        value = self._settings.value("filters/templates")
        if not value:
            return []
        try:
            data = json.loads(str(value))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
        try:
            data = json.loads(str(value))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def set_recent_files(self, files: list[str]) -> None:
        self._settings.setValue("session/recent_files", json.dumps(files))

    def get_recent_files(self) -> list[str]:
        value = self._settings.value("session/recent_files")
        if not value:
            return []
        try:
            data = json.loads(str(value))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def set_last_files(self, files: list[str]) -> None:
        self._settings.setValue("session/last_files", json.dumps(files))

    def get_last_files(self) -> list[str]:
        value = self._settings.value("session/last_files")
        if not value:
            return []
        try:
            data = json.loads(str(value))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def set_last_text(self, text: str) -> None:
        self._settings.setValue("session/last_text", text)

    def get_last_text(self) -> str:
        value = self._settings.value("session/last_text", "")
        return str(value)

    def set_restore_enabled(self, enabled: bool) -> None:
        self._settings.setValue("session/restore_enabled", enabled)

    def get_restore_enabled(self) -> bool:
        value = self._settings.value("session/restore_enabled", True)
        return bool(value)

    def set_plugin_settings(self, data: dict) -> None:
        self._settings.setValue("plugins/settings", json.dumps(data))

    def get_plugin_settings(self) -> dict:
        value = self._settings.value("plugins/settings")
        if not value:
            return {}
        try:
            data = json.loads(str(value))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def set_theme(self, name: str) -> None:
        self._settings.setValue("ui/theme", name)

    def get_theme(self) -> str:
        value = self._settings.value("ui/theme", "极简商务")
        return str(value)
