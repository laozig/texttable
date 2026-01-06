# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from pathlib import Path
import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableView,
    QFileDialog,
    QVBoxLayout,
)

from src.model.table_model import TextTableModel


class DedupDialog(QDialog):
    def __init__(self, headers: list[str], preview_callback) -> None:
        super().__init__()
        self.setWindowTitle("去重")
        self._preview_callback = preview_callback

        self._columns_list = QListWidget()
        for idx, header in enumerate(headers):
            item = QListWidgetItem(header)
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked)
            self._columns_list.addItem(item)

        self._keep_combo = QComboBox()
        self._keep_combo.addItem("保留第一条", "Keep first")
        self._keep_combo.addItem("保留最后一条", "Keep last")
        self._keep_combo.currentIndexChanged.connect(self._update_preview)

        self._preview_label = QLabel("要删除的行数：0")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("列："))
        layout.addWidget(self._columns_list)
        layout.addWidget(QLabel("保留："))
        layout.addWidget(self._keep_combo)
        layout.addWidget(self._preview_label)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self._columns_list.itemChanged.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self) -> None:
        columns = self.get_columns()
        keep_last = self._keep_combo.currentData() == "Keep last"
        count = self._preview_callback(columns, keep_last)
        self._preview_label.setText(f"要删除的行数：{count}")

    def get_columns(self) -> list[int]:
        return [
            int(self._columns_list.item(i).data(Qt.UserRole))
            for i in range(self._columns_list.count())
            if self._columns_list.item(i).checkState() == Qt.Checked
        ]

    def keep_last(self) -> bool:
        return self._keep_combo.currentData() == "Keep last"


class GroupDialog(QDialog):
    def __init__(self, headers: list[str], data: list[list[str]]) -> None:
        super().__init__()
        self.setWindowTitle("分组")
        self._headers = headers
        self._data = data

        self._columns_list = QListWidget()
        for idx, header in enumerate(headers):
            item = QListWidgetItem(header)
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked)
            self._columns_list.addItem(item)

        self._result_view = QTableView()
        self._result_model = TextTableModel()
        self._result_view.setModel(self._result_model)

        apply_button = QPushButton("分组")
        apply_button.clicked.connect(self._apply_grouping)
        export_button = QPushButton("导出汇总")
        export_button.clicked.connect(self._export_summary)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("按列分组："))
        layout.addWidget(self._columns_list)
        layout.addWidget(apply_button)
        layout.addWidget(export_button)
        layout.addWidget(self._result_view)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _apply_grouping(self) -> None:
        columns = [
            int(self._columns_list.item(i).data(Qt.UserRole))
            for i in range(self._columns_list.count())
            if self._columns_list.item(i).checkState() == Qt.Checked
        ]
        if not columns:
            return
        counter: Counter[tuple[str, ...]] = Counter()
        for row in self._data:
            key = tuple(row[i] for i in columns)
            counter[key] += 1
        result_rows: list[list[str]] = []
        for key, count in counter.items():
            result_rows.append(list(key) + [str(count)])
        headers = [self._headers[i] for i in columns] + ["计数"]
        self._result_model.set_data(result_rows, headers=headers)

    def _export_summary(self) -> None:
        if self._result_model.rowCount() == 0:
            return
        path_str, _ = QFileDialog.getSaveFileName(self, "导出汇总", "", "CSV (*.csv)")
        if not path_str:
            return
        path = Path(path_str)
        headers = self._result_model.get_headers()
        rows = self._result_model.get_data()
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(rows)
