# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class ColumnManagerDialog(QDialog):
    def __init__(self, headers: list[str], visibility: list[bool]) -> None:
        super().__init__()
        self.setWindowTitle("列管理")
        self._default_headers = headers[:]
        self._default_visibility = visibility[:]

        self._list = QListWidget()
        for idx, header in enumerate(headers):
            item = QListWidgetItem(header)
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if visibility[idx] else Qt.Unchecked)
            self._list.addItem(item)

        self._rename_input = QLineEdit()
        self._rename_input.setPlaceholderText("重命名列")
        self._rename_button = QPushButton("重命名")
        self._rename_button.clicked.connect(self._rename_current)

        self._move_up = QPushButton("上移")
        self._move_down = QPushButton("下移")
        self._delete_button = QPushButton("删除列")
        self._move_up.clicked.connect(lambda: self._move_selected(-1))
        self._move_down.clicked.connect(lambda: self._move_selected(1))
        self._delete_button.clicked.connect(self._delete_selected)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        reset_button = QPushButton("重置为默认")
        buttons.addButton(reset_button, QDialogButtonBox.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        reset_button.clicked.connect(self._reset)

        rename_layout = QHBoxLayout()
        rename_layout.addWidget(QLabel("名称："))
        rename_layout.addWidget(self._rename_input)
        rename_layout.addWidget(self._rename_button)

        move_layout = QHBoxLayout()
        move_layout.addWidget(self._move_up)
        move_layout.addWidget(self._move_down)
        move_layout.addWidget(self._delete_button)

        layout = QVBoxLayout()
        layout.addWidget(self._list)
        layout.addLayout(move_layout)
        layout.addLayout(rename_layout)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self._list.currentItemChanged.connect(self._sync_rename_input)
        self._sync_rename_input()

    def _sync_rename_input(self) -> None:
        item = self._list.currentItem()
        if item:
            self._rename_input.setText(item.text())

    def _rename_current(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        name = self._rename_input.text().strip()
        if name:
            item.setText(name)

    def _move_selected(self, direction: int) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self._list.count():
            return
        item = self._list.takeItem(row)
        self._list.insertItem(new_row, item)
        self._list.setCurrentRow(new_row)

    def _reset(self) -> None:
        self._list.clear()
        for idx, header in enumerate(self._default_headers):
            item = QListWidgetItem(header)
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked if self._default_visibility[idx] else Qt.Unchecked)
            self._list.addItem(item)

    def _delete_selected(self) -> None:
        rows = sorted({self._list.row(item) for item in self._list.selectedItems()}, reverse=True)
        for row in rows:
            self._list.takeItem(row)

    def get_state(self) -> tuple[list[int], list[str], list[bool]]:
        order: list[int] = []
        names: list[str] = []
        visibility: list[bool] = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            order.append(int(item.data(Qt.UserRole)))
            names.append(item.text())
            visibility.append(item.checkState() == Qt.Checked)
        return order, names, visibility
