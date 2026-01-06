# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class TextTableModel(QAbstractTableModel):
    def __init__(self, data: list[list[str]] | None = None, headers: list[str] | None = None) -> None:
        super().__init__()
        self._headers: list[str] = headers or []
        self._data: list[list[str]] = []
        self._row_ids: list[int] = []
        if data is not None:
            self.set_data(data, headers=headers)

    def set_data(self, data: list[list[str]], headers: list[str] | None = None) -> None:
        normalized, header_count = self._normalize_data(data)
        self.beginResetModel()
        self._data = normalized
        if headers:
            self._headers = headers[:]
        elif header_count > 0:
            self._headers = [f"列 {i + 1}" for i in range(header_count)]
        else:
            self._headers = []
        self._row_ids = list(range(1, len(self._data) + 1))
        self.endResetModel()

    def get_data(self) -> list[list[str]]:
        return [row[:] for row in self._data]

    def get_headers(self) -> list[str]:
        return self._headers[:]

    def data_column_count(self) -> int:
        return len(self._headers)

    def get_row_id(self, row: int) -> int:
        return self._row_ids[row]


    def set_headers(self, headers: list[str]) -> None:
        self._headers = headers[:]
        self.headerDataChanged.emit(Qt.Horizontal, 0, max(0, len(self._headers) - 1))

    def rename_column(self, column: int, name: str) -> None:
        if 0 <= column < len(self._headers):
            self._headers[column] = name
            self.headerDataChanged.emit(Qt.Horizontal, column, column)

    def reorder_columns(self, order: list[int]) -> None:
        if not order:
            return
        if sorted(order) != list(range(len(self._headers))):
            return
        self.layoutAboutToBeChanged.emit()
        self._headers = [self._headers[i] for i in order]
        for row_index, row in enumerate(self._data):
            self._data[row_index] = [row[i] for i in order]
        self.layoutChanged.emit()

    def remove_rows(self, rows: list[int]) -> None:
        for row in rows:
            if 0 <= row < len(self._data):
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._data[row]
                del self._row_ids[row]
                self.endRemoveRows()

    def insert_columns(self, index: int, headers: list[str], columns_data: list[list[str]]) -> None:
        if not headers:
            return
        if index < 0:
            index = 0
        if index > len(self._headers):
            index = len(self._headers)
        self.beginInsertColumns(QModelIndex(), index, index + len(headers) - 1)
        for row_index, row in enumerate(self._data):
            insert_values = [columns_data[col_index][row_index] for col_index in range(len(headers))]
            self._data[row_index] = row[:index] + insert_values + row[index:]
        self._headers[index:index] = headers
        self.endInsertColumns()

    def remove_columns(self, columns: list[int]) -> None:
        if not columns:
            return
        for column in sorted(columns, reverse=True):
            if 0 <= column < len(self._headers):
                self.beginRemoveColumns(QModelIndex(), column, column)
                for row_index, row in enumerate(self._data):
                    del row[column]
                    self._data[row_index] = row
                del self._headers[column]
                self.endRemoveColumns()

    def split_column(self, column: int, delimiter: str, keep_original: bool) -> None:
        if not (0 <= column < len(self._headers)):
            return
        parts_per_row: list[list[str]] = []
        max_parts = 0
        for row in self._data:
            parts = row[column].split(delimiter)
            parts_per_row.append(parts)
            max_parts = max(max_parts, len(parts))
        if max_parts <= 1:
            return
        new_headers = [f"{self._headers[column]} 部分 {i + 1}" for i in range(max_parts)]
        new_columns_data: list[list[str]] = [[] for _ in range(max_parts)]
        for parts in parts_per_row:
            padded = parts + [""] * (max_parts - len(parts))
            for idx, value in enumerate(padded):
                new_columns_data[idx].append(value)
        if keep_original:
            self.insert_columns(column + 1, new_headers, new_columns_data)
        else:
            self.layoutAboutToBeChanged.emit()
            for row_index, row in enumerate(self._data):
                row[column] = new_columns_data[0][row_index]
                insert_values = [col[row_index] for col in new_columns_data[1:]]
                self._data[row_index] = row[: column + 1] + insert_values + row[column + 1 :]
            self._headers[column : column + 1] = new_headers
            self.layoutChanged.emit()

    def merge_columns(self, columns: list[int], delimiter: str, keep_originals: bool) -> None:
        if len(columns) < 2:
            return
        columns = sorted(columns)
        if columns[0] < 0 or columns[-1] >= len(self._headers):
            return
        merged_values: list[str] = []
        for row in self._data:
            merged_values.append(delimiter.join(row[i] for i in columns))
        merged_header = "合并"
        insert_at = columns[-1] + 1
        if keep_originals:
            self.insert_columns(insert_at, [merged_header], [merged_values])
            return
        self.layoutAboutToBeChanged.emit()
        for row_index, row in enumerate(self._data):
            row[columns[0]] = merged_values[row_index]
            for col in reversed(columns[1:]):
                del row[col]
            self._data[row_index] = row
        self._headers[columns[0]] = merged_header
        for col in reversed(columns[1:]):
            del self._headers[col]
        self.layoutChanged.emit()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        if not self._headers:
            return 0
        return len(self._headers) + 1

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            if index.column() == 0:
                return str(self._row_ids[index.row()])
            return self._data[index.row()][index.column() - 1]
        if role == Qt.ToolTipRole:
            if index.column() == 0:
                return f"序号：{self._row_ids[index.row()]}"
            return self._data[index.row()][index.column() - 1]
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        if role != Qt.EditRole or not index.isValid():
            return False
        row = index.row()
        column = index.column()
        if not (0 <= row < len(self._data)) or column == 0:
            return False
        if not (0 <= column - 1 < len(self._headers)):
            return False
        self._data[row][column - 1] = "" if value is None else str(value)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        if index.column() == 0:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if not self._headers:
                return None
            if section == 0:
                return "序号"
            data_index = section - 1
            if 0 <= data_index < len(self._headers):
                return self._headers[data_index]
            return f"列 {section + 1}"
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if not self._data:
            return
        reverse = order == Qt.DescendingOrder
        self.layoutAboutToBeChanged.emit()
        if column == 0:
            combined = list(zip(self._row_ids, self._data))
            combined.sort(key=lambda item: item[0], reverse=reverse)
            self._row_ids = [item[0] for item in combined]
            self._data = [item[1] for item in combined]
        else:
            data_col = column - 1
            combined = list(zip(self._row_ids, self._data))
            combined.sort(
                key=lambda item: item[1][data_col] if data_col < len(item[1]) else "",
                reverse=reverse,
            )
            self._row_ids = [item[0] for item in combined]
            self._data = [item[1] for item in combined]
        self.layoutChanged.emit()

    def _normalize_data(self, data: Iterable[Iterable[str]]) -> tuple[list[list[str]], int]:
        rows: list[list[str]] = []
        max_cols = 0
        for row in data:
            row_list = ["" if cell is None else str(cell) for cell in row]
            rows.append(row_list)
            max_cols = max(max_cols, len(row_list))
        if max_cols == 0:
            return rows, 0
        for row in rows:
            if len(row) < max_cols:
                row.extend([""] * (max_cols - len(row)))
        return rows, max_cols
