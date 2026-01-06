# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableView,
    QVBoxLayout,
)


class ExportDialog(QDialog):
    def __init__(
        self,
        headers: list[str],
        templates: list[dict],
        preview_rows: list[list[str]],
        preview_headers: list[str],
        total_rows: int,
        selected_rows: int,
        selected_columns: list[int],
    ) -> None:
        super().__init__()
        self.setWindowTitle("导出")
        self._templates = templates
        self._selected_columns = selected_columns[:]

        self._type_combo = QComboBox()
        self._type_combo.addItems(["TXT", "CSV", "XLSX"])

        self._delimiter_input = QLineEdit("----")

        self._columns_list = QListWidget()
        for idx, header in enumerate(headers):
            item = QListWidgetItem(header)
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if idx in selected_columns else Qt.Unchecked)
            self._columns_list.addItem(item)

        self._move_up = QPushButton("上移")
        self._move_down = QPushButton("下移")
        self._move_up.clicked.connect(lambda: self._move_selected(-1))
        self._move_down.clicked.connect(lambda: self._move_selected(1))

        self._template_combo = QComboBox()
        self._template_combo.addItem("选择模板...")
        for template in templates:
            self._template_combo.addItem(template.get("name", "Unnamed"))
        self._template_combo.currentIndexChanged.connect(self._apply_template)

        self._template_name = QLineEdit()
        self._template_name.setPlaceholderText("模板名称")
        self._save_template = QPushButton("保存模板")
        self._delete_template = QPushButton("删除模板")
        self._save_template.clicked.connect(self._save_template_clicked)
        self._delete_template.clicked.connect(self._delete_template_clicked)

        self._export_selected_rows = QCheckBox(f"仅导出选中行（{selected_rows}）")
        self._export_selected_rows.setChecked(False)
        self._export_selected_columns = QCheckBox("仅导出选中列")
        self._export_selected_columns.setChecked(False)

        self._preview_label = QLabel(f"行数：{total_rows}")
        self._preview_view = QTableView()
        self._preview_model = QStandardItemModel()
        self._preview_model.setColumnCount(len(preview_headers))
        self._preview_model.setHorizontalHeaderLabels(preview_headers)
        for row in preview_rows:
            items = [QStandardItem(value) for value in row]
            self._preview_model.appendRow(items)
        self._preview_view.setModel(self._preview_model)
        self._preview_view.setMaximumHeight(140)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("导出")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        move_layout = QHBoxLayout()
        move_layout.addWidget(self._move_up)
        move_layout.addWidget(self._move_down)

        template_layout = QHBoxLayout()
        template_layout.addWidget(self._template_name)
        template_layout.addWidget(self._save_template)
        template_layout.addWidget(self._delete_template)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("导出类型："))
        layout.addWidget(self._type_combo)
        layout.addWidget(QLabel("TXT 分隔符："))
        layout.addWidget(self._delimiter_input)
        layout.addWidget(QLabel("列与顺序："))
        layout.addWidget(self._columns_list)
        layout.addLayout(move_layout)
        layout.addWidget(self._export_selected_rows)
        layout.addWidget(self._export_selected_columns)
        layout.addWidget(QLabel("模板："))
        layout.addWidget(self._template_combo)
        layout.addLayout(template_layout)
        layout.addWidget(QLabel("导出预览（前几行）："))
        layout.addWidget(self._preview_label)
        layout.addWidget(self._preview_view)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _move_selected(self, direction: int) -> None:
        row = self._columns_list.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self._columns_list.count():
            return
        item = self._columns_list.takeItem(row)
        self._columns_list.insertItem(new_row, item)
        self._columns_list.setCurrentRow(new_row)

    def _apply_template(self) -> None:
        idx = self._template_combo.currentIndex() - 1
        if idx < 0 or idx >= len(self._templates):
            return
        template = self._templates[idx]
        self._type_combo.setCurrentText(template.get("type", "TXT"))
        self._delimiter_input.setText(template.get("delimiter", "----"))
        order = template.get("columns", [])
        self._apply_column_order(order)
        self._apply_column_selection(order)

    def _apply_column_order(self, order: list[int]) -> None:
        items = [self._columns_list.item(i) for i in range(self._columns_list.count())]
        seen = set(order)
        items_sorted = [items[i] for i in order if 0 <= i < len(items)]
        items_sorted.extend(item for idx, item in enumerate(items) if idx not in seen)
        for i in reversed(range(self._columns_list.count())):
            self._columns_list.takeItem(i)
        for item in items_sorted:
            self._columns_list.addItem(item)

    def _apply_column_selection(self, order: list[int]) -> None:
        selected = set(order)
        for i in range(self._columns_list.count()):
            item = self._columns_list.item(i)
            idx = int(item.data(Qt.UserRole))
            item.setCheckState(Qt.Checked if idx in selected else Qt.Unchecked)

    def _save_template_clicked(self) -> None:
        name = self._template_name.text().strip()
        if not name:
            return
        template = self.get_template_config()
        template["name"] = name
        self._templates = [t for t in self._templates if t.get("name") != name]
        self._templates.append(template)
        self._refresh_template_combo()

    def _delete_template_clicked(self) -> None:
        name = self._template_name.text().strip()
        if not name:
            return
        self._templates = [t for t in self._templates if t.get("name") != name]
        self._refresh_template_combo()

    def _refresh_template_combo(self) -> None:
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        self._template_combo.addItem("选择模板...")
        for template in self._templates:
            self._template_combo.addItem(template.get("name", "Unnamed"))
        self._template_combo.blockSignals(False)

    def get_selected_columns(self) -> list[int]:
        return [
            int(self._columns_list.item(i).data(Qt.UserRole))
            for i in range(self._columns_list.count())
            if self._columns_list.item(i).checkState() == Qt.Checked
        ]

    def get_export_config(self) -> dict:
        return {
            "type": self._type_combo.currentText(),
            "delimiter": self._delimiter_input.text(),
            "columns": self.get_selected_columns(),
            "only_selected_rows": self._export_selected_rows.isChecked(),
            "only_selected_columns": self._export_selected_columns.isChecked(),
        }

    def get_template_config(self) -> dict:
        return self.get_export_config()

    def templates(self) -> list[dict]:
        return self._templates


def export_txt(path: Path, headers: list[str], rows: list[list[str]], delimiter: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        for row in rows:
            file.write(delimiter.join(row) + "\n")


def export_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def export_xlsx(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    data = {headers[i]: [row[i] for row in rows] for i in range(len(headers))}
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)
