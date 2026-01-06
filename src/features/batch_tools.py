# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)


class BatchToolsDialog(QDialog):
    def __init__(self, headers: list[str], apply_callback) -> None:
        super().__init__()
        self.setWindowTitle("批量工具")
        self._apply_callback = apply_callback

        self._scope_combo = QComboBox()
        self._scope_combo.addItem("整个表格", "Entire Table")
        self._scope_combo.addItem("选中行", "Selected Rows")
        self._scope_combo.addItem("选中单元格", "Selected Cells")

        self._columns_list = QListWidget()
        for idx, header in enumerate(headers):
            item = QListWidgetItem(header)
            item.setData(Qt.UserRole, idx)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Checked)
            self._columns_list.addItem(item)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_replace_tab(), "替换")
        self._tabs.addTab(self._build_prefix_suffix_tab(), "前后缀")
        self._tabs.addTab(self._build_split_tab(), "拆分列")
        self._tabs.addTab(self._build_merge_tab(), "合并列")
        self._tabs.addTab(self._build_clean_tab(), "清理/转换")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("应用")
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        scope_layout = QHBoxLayout()
        scope_layout.addWidget(QLabel("范围："))
        scope_layout.addWidget(self._scope_combo)

        layout = QVBoxLayout()
        layout.addLayout(scope_layout)
        layout.addWidget(QLabel("目标列："))
        layout.addWidget(self._columns_list)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def _build_replace_tab(self):
        tab = QDialog()
        self._replace_find = QLineEdit()
        self._replace_with = QLineEdit()
        self._replace_regex = QCheckBox("正则")
        layout = QFormLayout()
        layout.addRow("查找：", self._replace_find)
        layout.addRow("替换为：", self._replace_with)
        layout.addRow("", self._replace_regex)
        tab.setLayout(layout)
        return tab

    def _build_prefix_suffix_tab(self):
        tab = QDialog()
        self._prefix_input = QLineEdit()
        self._suffix_input = QLineEdit()
        layout = QFormLayout()
        layout.addRow("前缀：", self._prefix_input)
        layout.addRow("后缀：", self._suffix_input)
        tab.setLayout(layout)
        return tab

    def _build_split_tab(self):
        tab = QDialog()
        self._split_delim = QLineEdit("----")
        self._split_keep = QCheckBox("保留原列")
        layout = QFormLayout()
        layout.addRow("分隔符：", self._split_delim)
        layout.addRow("", self._split_keep)
        tab.setLayout(layout)
        return tab

    def _build_merge_tab(self):
        tab = QDialog()
        self._merge_delim = QLineEdit("----")
        self._merge_keep = QCheckBox("保留原列")
        layout = QFormLayout()
        layout.addRow("分隔符：", self._merge_delim)
        layout.addRow("", self._merge_keep)
        tab.setLayout(layout)
        return tab

    def _build_clean_tab(self):
        tab = QDialog()
        self._clean_action = QComboBox()
        self._clean_action.addItem("去空格（两端）", "strip")
        self._clean_action.addItem("去空格（全部）", "strip_all")
        self._clean_action.addItem("转大写", "upper")
        self._clean_action.addItem("转小写", "lower")
        self._clean_action.addItem("全角转半角", "to_half")
        self._clean_action.addItem("半角转全角", "to_full")
        self._clean_action.addItem("删除空行", "remove_empty_rows")
        self._clean_action.addItem("删除空列", "remove_empty_cols")
        layout = QFormLayout()
        layout.addRow("操作：", self._clean_action)
        tab.setLayout(layout)
        return tab

    def _apply(self) -> None:
        columns = [
            int(self._columns_list.item(i).data(Qt.UserRole))
            for i in range(self._columns_list.count())
            if self._columns_list.item(i).checkState() == Qt.Checked
        ]
        scope = self._scope_combo.currentData() or self._scope_combo.currentText()
        tab_index = self._tabs.currentIndex()
        if tab_index == 0:
            params = {
                "find": self._replace_find.text(),
                "replace": self._replace_with.text(),
                "regex": self._replace_regex.isChecked(),
            }
            op = "replace"
        elif tab_index == 1:
            params = {
                "prefix": self._prefix_input.text(),
                "suffix": self._suffix_input.text(),
            }
            op = "prefix_suffix"
        elif tab_index == 2:
            params = {
                "delimiter": self._split_delim.text(),
                "keep_original": self._split_keep.isChecked(),
            }
            op = "split"
        elif tab_index == 3:
            params = {
                "delimiter": self._merge_delim.text(),
                "keep_originals": self._merge_keep.isChecked(),
            }
            op = "merge"
        else:
            params = {"action": self._clean_action.currentData() or "strip"}
            op = "clean"
        if self._apply_callback(op, params, scope, columns):
            self.accept()
