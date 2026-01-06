from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication


def copy_rows_to_clipboard(model, rows: list[int], delimiter: str = "----") -> None:
    if not rows:
        return
    column_count = model.columnCount()
    lines: list[str] = []
    for row in rows:
        parts: list[str] = []
        for column in range(column_count):
            value = model.data(model.index(row, column), Qt.DisplayRole)
            parts.append("" if value is None else str(value))
        lines.append(delimiter.join(parts))
    QGuiApplication.clipboard().setText("\n".join(lines))
