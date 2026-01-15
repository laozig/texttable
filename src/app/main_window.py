# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QObject, Qt, QThread, Signal
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QGuiApplication,
    QShortcut,
    QFont,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableView,
    QToolBar,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QProgressDialog,
)

from src.features.batch_tools import BatchToolsDialog
from src.features.column_manager import ColumnManagerDialog
from src.features.dedup_group import DedupDialog, GroupDialog
from src.features.export import ExportDialog, export_csv, export_txt, export_xlsx
from src.features.plugins import LogDialog, PluginDialog, run_script
from src.features.session import SessionManager
from src.features.settings import SettingsManager
from src.model.proxy_filter import FilterProxyModel, FilterRule
from src.model.table_model import TextTableModel
from src.utils.parser import parse_text


class ParseWorker(QObject):
    finished = Signal(list, str)

    def __init__(self, text: str, delimiter: str) -> None:
        super().__init__()
        self._text = text
        self._delimiter = delimiter

    def run(self) -> None:
        data = parse_text(self._text, delimiter=self._delimiter)
        self.finished.emit(data, self._text)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("文本表格")
        self.setAcceptDrops(True)

        self._settings = SettingsManager()
        self._session = SessionManager(self._settings)
        self._last_text = ""
        self._last_files: list[str] = []
        self._column_order_names: list[str] = []
        self._undo_stack: list[tuple[list[list[str]], list[str]]] = []
        self._redo_stack: list[tuple[list[list[str]], list[str]]] = []
        self._max_undo = 30
        self._copy_only_selected_columns = False
        self._parse_thread: QThread | None = None
        self._parse_worker: ParseWorker | None = None

        self._model = TextTableModel()
        self._proxy = FilterProxyModel()
        self._proxy.setSourceModel(self._model)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._view.setSortingEnabled(True)
        self._view.setAlternatingRowColors(True)
        self._view.verticalHeader().setVisible(False)
        self._view.horizontalHeader().setStretchLastSection(False)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._view.horizontalHeader().setDefaultSectionSize(140)
        self._view.setWordWrap(False)
        self._view.setTextElideMode(Qt.ElideRight)
        self._view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._show_context_menu)

        self._global_filter = QLineEdit()
        self._global_filter.setPlaceholderText("全局筛选（所有列）")
        self._global_filter.textChanged.connect(self._apply_global_filter)

        self._filter_column = QComboBox()
        self._filter_mode = QComboBox()
        self._filter_mode.addItem("包含", "Contains")
        self._filter_mode.addItem("不包含", "Not contains")
        self._filter_mode.addItem("等于", "Equals")
        self._filter_mode.addItem("开头为", "Starts with")
        self._filter_mode.addItem("结尾为", "Ends with")
        self._filter_mode.addItem("正则", "Regex")
        self._filter_value = QLineEdit()
        self._filter_value.setPlaceholderText("筛选值")
        self._filter_apply = QPushButton("应用筛选")
        self._filter_clear = QPushButton("清除筛选")
        self._filter_apply.clicked.connect(self._apply_filter_rule)
        self._filter_clear.clicked.connect(self._clear_filters)
        self._filters_summary = QLabel("筛选：无")

        self._filter_template_combo = QComboBox()
        self._filter_template_combo.addItem("筛选方案...")
        self._filter_template_combo.currentIndexChanged.connect(self._apply_filter_template)
        self._filter_template_name = QLineEdit()
        self._filter_template_name.setPlaceholderText("方案名称")
        self._filter_template_save = QPushButton("保存方案")
        self._filter_template_delete = QPushButton("删除方案")
        self._filter_template_save.clicked.connect(self._save_filter_template)
        self._filter_template_delete.clicked.connect(self._delete_filter_template)


        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self._global_filter)
        filter_layout.addWidget(self._filter_column)
        filter_layout.addWidget(self._filter_mode)
        filter_layout.addWidget(self._filter_value)
        filter_layout.addWidget(self._filter_apply)
        filter_layout.addWidget(self._filter_clear)
        filter_layout.addWidget(self._filter_template_combo)
        filter_layout.addWidget(self._filter_template_name)
        filter_layout.addWidget(self._filter_template_save)
        filter_layout.addWidget(self._filter_template_delete)

        filter_panel = QWidget()
        filter_panel.setLayout(filter_layout)

        central = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(filter_panel)
        layout.addWidget(self._filters_summary)
        layout.addWidget(self._view)
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._setup_shortcuts()
        self._refresh_filter_columns()
        self._refresh_filter_templates()
        self._init_theme()
        self._update_undo_actions()

        self._model.modelReset.connect(self._sync_after_model_change)
        self._model.layoutChanged.connect(self._sync_after_model_change)
        self._proxy.rowsInserted.connect(self._update_status)
        self._proxy.rowsRemoved.connect(self._update_status)
        self._proxy.modelReset.connect(self._update_status)
        self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self._restore_geometry()
        self._restore_last_session()
        self._update_status("就绪")

    def _build_actions(self) -> None:
        self._import_action = QAction("导入", self)
        self._import_action.triggered.connect(self._open_files_dialog)
        self._paste_action = QAction("粘贴", self)
        self._paste_action.triggered.connect(self._paste_from_clipboard)
        self._undo_action = QAction("撤销", self)
        self._redo_action = QAction("重做", self)
        self._undo_action.setShortcut(QKeySequence.Undo)
        self._redo_action.setShortcut(QKeySequence.Redo)
        self._undo_action.triggered.connect(self._undo)
        self._redo_action.triggered.connect(self._redo)

        self._export_action = QAction("导出", self)
        self._export_action.triggered.connect(lambda: self._export(None))

        self._column_manager_action = QAction("列管理", self)
        self._column_manager_action.triggered.connect(self._open_column_manager)

        self._batch_tools_action = QAction("批量工具", self)
        self._batch_tools_action.triggered.connect(self._open_batch_tools)

        self._dedup_action = QAction("去重", self)
        self._dedup_action.triggered.connect(self._open_dedup)

        self._group_action = QAction("分组", self)
        self._group_action.triggered.connect(self._open_group)

        self._plugin_action = None

        self._restore_option_action = QAction("启动时恢复上次会话", self)
        self._restore_option_action.setCheckable(True)
        self._restore_option_action.setChecked(False)
        self._restore_option_action.setEnabled(False)




    def _build_menus(self) -> None:
        menu = self.menuBar().addMenu("文件")
        menu.addAction(self._import_action)
        menu.addAction(self._paste_action)
        menu.addSeparator()
        menu.addAction(self._export_action)
        menu.addSeparator()
        self._recent_menu = menu.addMenu("最近文件")

        tools = self.menuBar().addMenu("工具")
        tools.addAction(self._column_manager_action)
        tools.addAction(self._batch_tools_action)
        tools.addAction(self._dedup_action)
        tools.addAction(self._group_action)
        edit = self.menuBar().addMenu("编辑")
        edit.addAction(self._undo_action)
        edit.addAction(self._redo_action)

        self._refresh_recent_menu()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.addAction(self._undo_action)
        toolbar.addAction(self._redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self._import_action)
        toolbar.addAction(self._paste_action)
        toolbar.addAction(self._export_action)
        toolbar.addAction(self._column_manager_action)
        toolbar.addAction(self._batch_tools_action)
        toolbar.addAction(self._dedup_action)
        toolbar.addAction(self._group_action)
        # scripts removed
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("主题："))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(
            [
                "极简商务",
                "深色高对比",
                "清爽科技",
                "温和文档",
                "晨雾蓝",
                "石墨灰",
                "松石绿",
                "日落橙",
            ]
        )
        self._theme_combo.currentTextChanged.connect(self._apply_theme)
        toolbar.addWidget(self._theme_combo)
        toolbar.addSeparator()
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("查找："))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Ctrl+F")
        self._search_next = QPushButton("下一个")
        self._search_prev = QPushButton("上一个")
        self._search_next.clicked.connect(lambda: self._find_next(True))
        self._search_prev.clicked.connect(lambda: self._find_next(False))
        toolbar.addWidget(self._search_input)
        toolbar.addWidget(self._search_prev)
        toolbar.addWidget(self._search_next)
        self.addToolBar(toolbar)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence.Copy, self._view, activated=self._copy_selected)
        QShortcut(QKeySequence.Delete, self._view, activated=self._delete_selected)
        QShortcut(QKeySequence.SelectAll, self._view, activated=self._view.selectAll)
        QShortcut(QKeySequence.Find, self, activated=self._focus_search)

    def _init_theme(self) -> None:
        app = QGuiApplication.instance()
        if app is None:
            return
        app.setFont(QFont("Microsoft YaHei UI", 10))
        theme = self._settings.get_theme()
        if hasattr(self, "_theme_combo"):
            self._theme_combo.setCurrentText(theme)
        self._apply_theme(theme)

    def _apply_theme(self, name: str) -> None:
        themes = {
            "极简商务": """
                QMainWindow { background: #f4f6f9; }
                QToolBar { background: #ffffff; border-bottom: 1px solid #e3e7ee; }
                QStatusBar { background: #ffffff; border-top: 1px solid #e3e7ee; }
                QLabel { color: #2b2f38; }
                QLineEdit, QComboBox {
                    background: #ffffff; border: 1px solid #cfd6e4; border-radius: 6px;
                    padding: 4px 8px; color: #2b2f38;
                }
                QPushButton {
                    background: #1f5eff; color: #ffffff; border: none; border-radius: 6px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #1748c7; }
                QTableView {
                    background: #ffffff; alternate-background-color: #f0f3f8;
                    gridline-color: #e3e7ee; border: 1px solid #d7dde8;
                }
                QTableView::item:selected { background: #ffd24d; color: #1f1f1f; }
                QHeaderView::section {
                    background: #f7f9fc; color: #2b2f38; border: 1px solid #e3e7ee;
                    padding: 4px 6px;
                }
            """,
            "深色高对比": """
                QMainWindow { background: #121417; }
                QToolBar { background: #1a1d22; border-bottom: 1px solid #2a2f38; }
                QStatusBar { background: #1a1d22; border-top: 1px solid #2a2f38; color: #e7f6ff; }
                QLabel { color: #e7f6ff; }
                QLineEdit, QComboBox {
                    background: #1f242c; border: 1px solid #3a414d; border-radius: 6px;
                    padding: 4px 8px; color: #e7f6ff;
                }
                QPushButton {
                    background: #00e5ff; color: #0b0d10; border: none; border-radius: 6px;
                    padding: 6px 10px; font-weight: 600;
                }
                QPushButton:hover { background: #00bcd4; }
                QTableView {
                    background: #171b21; alternate-background-color: #1f242c;
                    gridline-color: #2a2f38; border: 1px solid #2a2f38; color: #e7f6ff;
                }
                QTableView::item:selected { background: #00e5ff; color: #0b0d10; }
                QHeaderView::section {
                    background: #20252c; color: #e7f6ff; border: 1px solid #2a2f38;
                    padding: 4px 6px;
                }
            """,
            "清爽科技": """
                QMainWindow { background: #eefaf7; }
                QToolBar { background: #ffffff; border-bottom: 1px solid #d4efe6; }
                QStatusBar { background: #ffffff; border-top: 1px solid #d4efe6; }
                QLabel { color: #1f2e2b; }
                QLineEdit, QComboBox {
                    background: #ffffff; border: 1px solid #bfe7db; border-radius: 8px;
                    padding: 4px 8px; color: #1f2e2b;
                }
                QPushButton {
                    background: #1abc9c; color: #ffffff; border: none; border-radius: 8px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #14967b; }
                QTableView {
                    background: #ffffff; alternate-background-color: #e6f7f2;
                    gridline-color: #d4efe6; border: 1px solid #cfe9df;
                }
                QTableView::item:selected { background: #7ce1cd; color: #0b2c24; }
                QHeaderView::section {
                    background: #f2fbf9; color: #1f2e2b; border: 1px solid #d4efe6;
                    padding: 4px 6px;
                }
            """,
            "温和文档": """
                QMainWindow { background: #f8f4ef; }
                QToolBar { background: #fffdf9; border-bottom: 1px solid #e9e1d6; }
                QStatusBar { background: #fffdf9; border-top: 1px solid #e9e1d6; }
                QLabel { color: #3b342c; }
                QLineEdit, QComboBox {
                    background: #fffdf9; border: 1px solid #e0d6c9; border-radius: 6px;
                    padding: 4px 8px; color: #3b342c;
                }
                QPushButton {
                    background: #8b6b4f; color: #ffffff; border: none; border-radius: 6px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #735741; }
                QTableView {
                    background: #fffdf9; alternate-background-color: #f2ece4;
                    gridline-color: #e9e1d6; border: 1px solid #e0d6c9;
                }
                QTableView::item:selected { background: #f1c27d; color: #3b342c; }
                QHeaderView::section {
                    background: #f6f1ea; color: #3b342c; border: 1px solid #e0d6c9;
                    padding: 4px 6px;
                }
            """,
            "晨雾蓝": """
                QMainWindow { background: #eef4fb; }
                QToolBar { background: #ffffff; border-bottom: 1px solid #d7e3f4; }
                QStatusBar { background: #ffffff; border-top: 1px solid #d7e3f4; }
                QLabel { color: #2a3a4a; }
                QLineEdit, QComboBox {
                    background: #ffffff; border: 1px solid #c9d8ed; border-radius: 8px;
                    padding: 4px 8px; color: #2a3a4a;
                }
                QPushButton {
                    background: #4a7bd1; color: #ffffff; border: none; border-radius: 8px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #3c65ad; }
                QTableView {
                    background: #ffffff; alternate-background-color: #e8f0fb;
                    gridline-color: #d7e3f4; border: 1px solid #c9d8ed;
                }
                QTableView::item:selected { background: #b9d4ff; color: #1f2d3a; }
                QHeaderView::section {
                    background: #f0f6ff; color: #2a3a4a; border: 1px solid #d7e3f4;
                    padding: 4px 6px;
                }
            """,
            "石墨灰": """
                QMainWindow { background: #f2f2f2; }
                QToolBar { background: #ffffff; border-bottom: 1px solid #d6d6d6; }
                QStatusBar { background: #ffffff; border-top: 1px solid #d6d6d6; }
                QLabel { color: #2c2c2c; }
                QLineEdit, QComboBox {
                    background: #ffffff; border: 1px solid #c8c8c8; border-radius: 6px;
                    padding: 4px 8px; color: #2c2c2c;
                }
                QPushButton {
                    background: #5a5a5a; color: #ffffff; border: none; border-radius: 6px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #444444; }
                QTableView {
                    background: #ffffff; alternate-background-color: #ededed;
                    gridline-color: #d6d6d6; border: 1px solid #c8c8c8;
                }
                QTableView::item:selected { background: #cfcfcf; color: #1a1a1a; }
                QHeaderView::section {
                    background: #f5f5f5; color: #2c2c2c; border: 1px solid #d6d6d6;
                    padding: 4px 6px;
                }
            """,
            "松石绿": """
                QMainWindow { background: #edf9f6; }
                QToolBar { background: #ffffff; border-bottom: 1px solid #cfe8e1; }
                QStatusBar { background: #ffffff; border-top: 1px solid #cfe8e1; }
                QLabel { color: #21423b; }
                QLineEdit, QComboBox {
                    background: #ffffff; border: 1px solid #b7ded3; border-radius: 8px;
                    padding: 4px 8px; color: #21423b;
                }
                QPushButton {
                    background: #2dbfa5; color: #ffffff; border: none; border-radius: 8px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #239b86; }
                QTableView {
                    background: #ffffff; alternate-background-color: #e3f5f0;
                    gridline-color: #cfe8e1; border: 1px solid #b7ded3;
                }
                QTableView::item:selected { background: #9de5d5; color: #12332d; }
                QHeaderView::section {
                    background: #f1fbf9; color: #21423b; border: 1px solid #cfe8e1;
                    padding: 4px 6px;
                }
            """,
            "日落橙": """
                QMainWindow { background: #fff4ec; }
                QToolBar { background: #ffffff; border-bottom: 1px solid #f0d7c6; }
                QStatusBar { background: #ffffff; border-top: 1px solid #f0d7c6; }
                QLabel { color: #4a2f1e; }
                QLineEdit, QComboBox {
                    background: #ffffff; border: 1px solid #e6c2a7; border-radius: 8px;
                    padding: 4px 8px; color: #4a2f1e;
                }
                QPushButton {
                    background: #e07a3f; color: #ffffff; border: none; border-radius: 8px;
                    padding: 6px 10px;
                }
                QPushButton:hover { background: #c86733; }
                QTableView {
                    background: #ffffff; alternate-background-color: #ffe9da;
                    gridline-color: #f0d7c6; border: 1px solid #e6c2a7;
                }
                QTableView::item:selected { background: #ffc08a; color: #4a2f1e; }
                QHeaderView::section {
                    background: #fff1e6; color: #4a2f1e; border: 1px solid #f0d7c6;
                    padding: 4px 6px;
                }
            """,
        }
        self.setStyleSheet(themes.get(name, ""))
        self._settings.set_theme(name)

    def _restore_geometry(self) -> None:
        geometry = self._settings.load_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _sync_after_model_change(self) -> None:
        self._refresh_filter_columns()
        self._update_status()
        self._update_undo_actions()

    def _on_selection_changed(self, *_args) -> None:
        self._update_status()

    def _refresh_filter_columns(self) -> None:
        self._filter_column.clear()
        self._filter_column.addItem("全部列", None)
        for idx, header in enumerate(self._model.get_headers()):
            self._filter_column.addItem(header, idx)

    def _refresh_filter_templates(self) -> None:
        self._filter_templates = self._settings.get_filter_templates()
        self._filter_template_combo.blockSignals(True)
        self._filter_template_combo.clear()
        self._filter_template_combo.addItem("筛选方案...")
        for item in self._filter_templates:
            self._filter_template_combo.addItem(item.get("name", "未命名"))
        self._filter_template_combo.blockSignals(False)

    def _save_filter_template(self) -> None:
        name = self._filter_template_name.text().strip()
        if not name:
            return
        rules = [
            {"column": rule.column, "mode": rule.mode, "value": rule.value}
            for rule in self._proxy.filters()
        ]
        template = {"name": name, "global": self._global_filter.text().strip(), "rules": rules}
        self._filter_templates = [t for t in self._filter_templates if t.get("name") != name]
        self._filter_templates.append(template)
        self._settings.set_filter_templates(self._filter_templates)
        self._refresh_filter_templates()

    def _apply_filter_template(self) -> None:
        idx = self._filter_template_combo.currentIndex() - 1
        if idx < 0 or idx >= len(self._filter_templates):
            return
        template = self._filter_templates[idx]
        self._global_filter.setText(template.get("global", ""))
        rules = []
        for item in template.get("rules", []):
            rules.append(
                FilterRule(
                    column=item.get("column"),
                    mode=item.get("mode", "Contains"),
                    value=item.get("value", ""),
                )
            )
        self._proxy.set_filters(rules)
        self._update_filter_summary()
        self._update_status()

    def _delete_filter_template(self) -> None:
        name = self._filter_template_name.text().strip()
        if not name:
            return
        self._filter_templates = [t for t in self._filter_templates if t.get("name") != name]
        self._settings.set_filter_templates(self._filter_templates)
        self._refresh_filter_templates()

    def _apply_global_filter(self, text: str) -> None:
        self._proxy.set_global_filter(text)
        self._update_filter_summary()
        self._update_status()

    def _apply_filter_rule(self) -> None:
        value = self._filter_value.text().strip()
        if not value:
            return
        column = self._filter_column.currentData()
        mode = self._filter_mode.currentData() or self._filter_mode.currentText()
        self._proxy.add_filter(FilterRule(column=column, mode=mode, value=value))
        self._filter_value.clear()
        self._update_filter_summary()
        self._update_status()

    def _clear_filters(self) -> None:
        self._proxy.clear_filters()
        self._global_filter.clear()
        self._update_filter_summary()
        self._update_status()

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)
        menu.addAction("复制选中", self._copy_selected)
        menu.addAction("删除选中", self._delete_selected)
        menu.addSeparator()
        only_cols_action = menu.addAction("仅复制选中列")
        only_cols_action.setCheckable(True)
        only_cols_action.setChecked(self._copy_only_selected_columns)
        only_cols_action.triggered.connect(
            lambda checked: setattr(self, "_copy_only_selected_columns", checked)
        )
        menu.addSeparator()
        menu.addAction("反选", self._invert_selection)
        menu.addAction("全选", self._view.selectAll)
        menu.exec(self._view.viewport().mapToGlobal(position))

    def _focus_search(self) -> None:
        if hasattr(self, "_search_input"):
            self._search_input.setFocus()
            self._search_input.selectAll()

    def _copy_selected(self) -> None:
        selection = self._view.selectionModel()
        if not selection:
            return
        rows = sorted({index.row() for index in selection.selectedRows()})
        if not rows:
            return
        headers = self._model.get_headers()
        if self._copy_only_selected_columns:
            columns = self._get_selected_proxy_columns()
            if not columns:
                self._update_status("未选中列，已改为复制全部列")
                columns = list(range(len(headers)))
        else:
            columns = list(range(len(headers)))
        lines: list[str] = []
        for row in rows:
            values = []
            for col in columns:
                value = self._proxy.data(self._proxy.index(row, col + 1), Qt.DisplayRole)
                values.append("" if value is None else str(value))
            lines.append(self._settings.get_delimiter().join(values))
        QGuiApplication.clipboard().setText("\n".join(lines))
        self._update_status("已复制所选行")

    def _delete_selected(self) -> None:
        selection = self._view.selectionModel()
        if not selection:
            return
        source_rows = sorted(
            {self._proxy.mapToSource(index).row() for index in selection.selectedRows()},
            reverse=True,
        )
        if not source_rows:
            return
        self._push_undo("删除行")
        self._model.remove_rows(source_rows)
        self._update_status("已删除所选行")

    def _invert_selection(self) -> None:
        selection = self._view.selectionModel()
        if not selection:
            return
        row_count = self._proxy.rowCount()
        column_count = self._proxy.columnCount()
        if row_count == 0 or column_count == 0:
            return
        selected_rows = {index.row() for index in selection.selectedRows()}
        selection.clearSelection()
        to_select = QItemSelection()
        for row in range(row_count):
            if row in selected_rows:
                continue
            left = self._proxy.index(row, 0)
            right = self._proxy.index(row, column_count - 1)
            to_select.select(left, right)
        selection.select(to_select, QItemSelectionModel.Select | QItemSelectionModel.Rows)

    def _open_files_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "打开文件", "", "文本文件 (*.txt *.log *.csv);;所有文件 (*)"
        )
        if paths:
            self._load_files(paths)

    def _paste_from_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text()
        if text:
            self._apply_text(text)

    def _load_files(self, paths: list[str]) -> None:
        text_parts = []
        for path in paths:
            try:
                raw = Path(path).read_bytes()
            except OSError:
                continue
            text = self._decode_text(raw)
            if text:
                text_parts.append(text)
            self._session.add_recent_file(path)
        combined = "\n".join(text_parts)
        if combined:
            self._last_files = paths
            self._apply_text(combined)
            self._refresh_recent_menu()

    def _restore_last_session(self) -> None:
        files = self._session.load_last_files()
        if files:
            self._load_files(files)
            return
        text = self._session.load_last_text()
        if text:
            self._apply_text(text)

    def _apply_text(self, text: str) -> None:
        if self._parse_thread and self._parse_thread.isRunning():
            self._update_status("正在解析，请稍后")
            return
        delimiter = self._settings.get_delimiter()
        self._view.setSortingEnabled(False)
        self._parse_thread = QThread(self)
        self._parse_worker = ParseWorker(text, delimiter)
        self._parse_worker.moveToThread(self._parse_thread)
        self._parse_thread.started.connect(self._parse_worker.run)
        self._parse_worker.finished.connect(self._on_parse_finished)
        self._parse_worker.finished.connect(self._parse_thread.quit)
        self._parse_worker.finished.connect(self._parse_worker.deleteLater)
        self._parse_thread.finished.connect(self._parse_thread.deleteLater)
        self._update_status("正在解析...")
        self._parse_thread.start()

    def _on_parse_finished(self, data: list[list[str]], text: str) -> None:
        if self._model.rowCount() > 0:
            self._push_undo("加载数据")
        self._last_text = text
        self._view.setUpdatesEnabled(False)
        self._view.setSortingEnabled(False)
        self._proxy.setDynamicSortFilter(False)
        self._view.setModel(None)
        self._proxy.setSourceModel(None)
        self._model.set_data(data)
        self._proxy.setSourceModel(self._model)
        self._view.setModel(self._proxy)
        if self._view.selectionModel():
            self._view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._column_order_names = self._model.get_headers()
        self._view.setColumnHidden(0, False)
        if data:
            self._view.horizontalHeader().setStretchLastSection(False)
            self._view.setColumnWidth(0, 60)
        self._refresh_filter_columns()
        self._proxy.setDynamicSortFilter(True)
        self._view.setSortingEnabled(True)
        self._view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self._view.setUpdatesEnabled(True)
        self._update_status("数据已加载")
        self._update_undo_actions()
        if "\ufffd" in text:
            self._update_status("检测到可能的乱码，请确认编码")
        self._parse_worker = None
        self._parse_thread = None

    def _capture_snapshot(self) -> tuple[list[list[str]], list[str]]:
        data = [row[:] for row in self._model.get_data()]
        headers = self._model.get_headers()[:]
        return data, headers

    def _push_undo(self, reason: str | None = None) -> None:
        if self._model.rowCount() == 0 and not self._model.get_headers():
            return
        self._undo_stack.append(self._capture_snapshot())
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        if reason:
            self._update_status(f"已记录可撤销：{reason}")
        self._update_undo_actions()

    def _restore_snapshot(self, snapshot: tuple[list[list[str]], list[str]]) -> None:
        data, headers = snapshot
        self._model.set_data([row[:] for row in data], headers=headers[:])
        self._column_order_names = self._model.get_headers()
        if self._model.rowCount() > 0:
            self._view.setColumnHidden(0, False)
            self._view.setColumnWidth(0, 60)
        else:
            self._view.setColumnHidden(0, True)
        self._refresh_filter_columns()
        self._update_status("数据已恢复")

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._capture_snapshot())
        snapshot = self._undo_stack.pop()
        self._restore_snapshot(snapshot)
        self._update_undo_actions()

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._capture_snapshot())
        snapshot = self._redo_stack.pop()
        self._restore_snapshot(snapshot)
        self._update_undo_actions()

    def _update_undo_actions(self) -> None:
        if hasattr(self, "_undo_action"):
            self._undo_action.setEnabled(bool(self._undo_stack))
        if hasattr(self, "_redo_action"):
            self._redo_action.setEnabled(bool(self._redo_stack))

    def _parse_text_with_progress(self, text: str, delimiter: str) -> list[list[str]]:
        lines = text.splitlines()
        total = len(lines)
        if total < 200000:
            return parse_text(text, delimiter=delimiter)
        progress = QProgressDialog("正在加载大文件...", "取消", 0, total, self)
        progress.setWindowTitle("加载")
        progress.setValue(0)
        progress.setMinimumDuration(0)
        rows: list[list[str]] = []
        max_cols = 0
        for idx, raw_line in enumerate(lines, 1):
            if progress.wasCanceled():
                self._update_status("已取消加载")
                return []
            line = raw_line.strip()
            if not line:
                progress.setValue(idx)
                continue
            parts = [part.strip() for part in line.split(delimiter)]
            rows.append(parts)
            max_cols = max(max_cols, len(parts))
            if idx % 5000 == 0:
                progress.setValue(idx)
        progress.setValue(total)
        if max_cols == 0:
            return []
        for row in rows:
            if len(row) < max_cols:
                row.extend([""] * (max_cols - len(row)))
        return rows

    def _decode_text(self, raw: bytes) -> str:
        for encoding in ("utf-8", "gb18030", "gbk"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        files = self._session.get_recent_files()
        if not files:
            self._recent_menu.addAction("(无)").setEnabled(False)
            return
        for path in files:
            action = QAction(path, self)
            action.triggered.connect(lambda checked=False, p=path: self._load_files([p]))
            self._recent_menu.addAction(action)

    def _open_column_manager(self) -> None:
        headers = self._model.get_headers()
        visibility = [not self._view.isColumnHidden(i + 1) for i in range(len(headers))]
        dialog = ColumnManagerDialog(headers, visibility)
        if dialog.exec() != QDialog.Accepted:
            return
        self._push_undo("列管理")
        order, names, visibility = dialog.get_state()
        original_indices = list(range(len(headers)))
        remaining_set = set(order)
        deleted = [idx for idx in original_indices if idx not in remaining_set]
        if deleted:
            self._model.remove_columns(sorted(deleted, reverse=True))
            remaining_sorted = sorted(remaining_set)
            index_map = {orig: new_idx for new_idx, orig in enumerate(remaining_sorted)}
            new_order = [index_map[orig] for orig in order]
        else:
            new_order = order
        self._model.reorder_columns(new_order)
        self._model.set_headers(names)
        self._column_order_names = self._model.get_headers()
        for idx, visible in enumerate(visibility):
            self._view.setColumnHidden(idx + 1, not visible)
        self._update_status("列已更新")

    def _open_batch_tools(self) -> None:
        headers = self._model.get_headers()

        def apply_callback(op: str, params: dict, scope: str, columns: list[int]) -> bool:
            if not columns:
                QMessageBox.warning(self, "批量工具", "请至少选择一列。")
                return False
            destructive = op in {"replace", "split", "merge", "clean"}
            if destructive:
                reply = QMessageBox.question(
                    self,
                    "确认",
                    "确定执行该操作？这会修改数据。",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return False
            if op in {"replace", "prefix_suffix"}:
                self._apply_text_operation(op, params, scope, columns)
                return True
            if op == "split":
                self._apply_split_operation(params, scope, columns)
                return True
            if op == "merge":
                self._apply_merge_operation(params, scope, columns)
                return True
            if op == "clean":
                self._apply_clean_operation(params, scope, columns)
                return True
            return False

        dialog = BatchToolsDialog(headers, apply_callback)
        dialog.exec()

    def _apply_text_operation(self, op: str, params: dict, scope: str, columns: list[int]) -> None:
        self._push_undo("批量文本")
        if scope == "Selected Cells":
            cells = self._get_selected_source_cells()
            targets = [(row, col) for row, col in cells if col in columns]
        elif scope == "Selected Rows":
            rows = self._get_selected_source_rows()
            targets = [(row, col) for row in rows for col in columns]
        else:
            targets = [(row, col) for row in range(self._model.rowCount()) for col in columns]

        for row, col in targets:
            index = self._model.index(row, col + 1)
            value = str(self._model.data(index, Qt.DisplayRole) or "")
            if op == "replace":
                find = params.get("find", "")
                replace = params.get("replace", "")
                if params.get("regex"):
                    try:
                        value = re.sub(find, replace, value)
                    except re.error:
                        QMessageBox.warning(self, "批量工具", "无效的正则表达式。")
                        return
                else:
                    value = value.replace(find, replace)
            elif op == "prefix_suffix":
                value = f"{params.get('prefix', '')}{value}{params.get('suffix', '')}"
            self._model.setData(index, value)
        self._update_status("批量操作完成")

    def _apply_split_operation(self, params: dict, scope: str, columns: list[int]) -> None:
        self._push_undo("拆分列")
        delimiter = params.get("delimiter", "----")
        keep_original = params.get("keep_original", False)
        rows_in_scope = self._get_scope_rows(scope)
        data = self._model.get_data()
        headers = self._model.get_headers()
        offset = 0
        for col in sorted(columns):
            adjusted_col = col + offset
            max_parts = 0
            per_row_parts: list[list[str]] = []
            for row_index, row in enumerate(data):
                if row_index in rows_in_scope:
                    parts = row[adjusted_col].split(delimiter)
                else:
                    parts = []
                per_row_parts.append(parts)
                max_parts = max(max_parts, len(parts))
            if max_parts <= 1:
                continue
            new_headers = [f"{headers[adjusted_col]} 部分 {i + 1}" for i in range(max_parts)]
            new_columns = [[""] * len(data) for _ in range(max_parts)]
            for row_index, parts in enumerate(per_row_parts):
                padded = parts + [""] * (max_parts - len(parts))
                for i in range(max_parts):
                    new_columns[i][row_index] = padded[i]
            if keep_original:
                for row_index, row in enumerate(data):
                    insert_values = [new_columns[i][row_index] for i in range(max_parts)]
                    data[row_index] = (
                        row[: adjusted_col + 1] + insert_values + row[adjusted_col + 1 :]
                    )
                headers = headers[: adjusted_col + 1] + new_headers + headers[adjusted_col + 1 :]
                offset += max_parts
            else:
                for row_index, row in enumerate(data):
                    if row_index in rows_in_scope:
                        row[adjusted_col] = new_columns[0][row_index]
                    insert_values = [new_columns[i][row_index] for i in range(1, max_parts)]
                    data[row_index] = (
                        row[: adjusted_col + 1] + insert_values + row[adjusted_col + 1 :]
                    )
                headers = headers[:adjusted_col] + new_headers + headers[adjusted_col + 1 :]
                offset += max_parts - 1
        self._model.set_data(data, headers=headers)
        self._column_order_names = self._model.get_headers()
        self._update_status("列已拆分")

    def _apply_merge_operation(self, params: dict, scope: str, columns: list[int]) -> None:
        self._push_undo("合并列")
        columns = sorted(columns)
        if len(columns) < 2:
            QMessageBox.warning(self, "批量工具", "合并需要至少选择两列。")
            return
        delimiter = params.get("delimiter", "----")
        keep_originals = params.get("keep_originals", False)
        rows_in_scope = self._get_scope_rows(scope)
        data = self._model.get_data()
        headers = self._model.get_headers()
        merged_values: list[str] = []
        for row_index, row in enumerate(data):
            if row_index in rows_in_scope:
                merged_values.append(delimiter.join(row[i] for i in columns))
            else:
                merged_values.append("" if keep_originals else delimiter.join(row[i] for i in columns))
        insert_at = columns[-1] + 1
        if keep_originals:
            for row_index, row in enumerate(data):
                data[row_index] = row[:insert_at] + [merged_values[row_index]] + row[insert_at:]
            headers = headers[:insert_at] + ["合并"] + headers[insert_at:]
        else:
            for row_index, row in enumerate(data):
                row[columns[0]] = merged_values[row_index]
                for col in reversed(columns[1:]):
                    del row[col]
                data[row_index] = row
            headers[columns[0]] = "合并"
            for col in reversed(columns[1:]):
                del headers[col]
        self._model.set_data(data, headers=headers)
        self._column_order_names = self._model.get_headers()
        self._update_status("列已合并")

    def _apply_clean_operation(self, params: dict, scope: str, columns: list[int]) -> None:
        self._push_undo("清理转换")
        action = params.get("action", "strip")
        rows_in_scope = self._get_scope_rows(scope)
        if action == "remove_empty_rows":
            data = self._model.get_data()
            rows_to_remove = []
            for row in rows_in_scope:
                if all(not data[row][col].strip() for col in columns):
                    rows_to_remove.append(row)
            self._model.remove_rows(sorted(rows_to_remove, reverse=True))
            self._update_status("空行已删除")
            return
        if action == "remove_empty_cols":
            data = self._model.get_data()
            empty_cols = []
            for col in columns:
                if all(not data[row][col].strip() for row in range(len(data))):
                    empty_cols.append(col)
            if empty_cols:
                self._model.remove_columns(sorted(empty_cols, reverse=True))
            self._update_status("空列已删除")
            return
        if scope == "Selected Cells":
            targets = [(row, col) for row, col in self._get_selected_source_cells() if col in columns]
        elif scope == "Selected Rows":
            rows = self._get_selected_source_rows()
            targets = [(row, col) for row in rows for col in columns]
        else:
            targets = [(row, col) for row in range(self._model.rowCount()) for col in columns]

        for row, col in targets:
            index = self._model.index(row, col + 1)
            value = str(self._model.data(index, Qt.DisplayRole) or "")
            if action == "strip":
                value = value.strip()
            elif action == "strip_all":
                value = "".join(value.split())
            elif action == "upper":
                value = value.upper()
            elif action == "lower":
                value = value.lower()
            elif action == "to_half":
                value = self._to_half_width(value)
            elif action == "to_full":
                value = self._to_full_width(value)
            self._model.setData(index, value)
        self._update_status("转换完成")

    def _get_scope_rows(self, scope: str) -> set[int]:
        if scope == "Selected Cells":
            return {row for row, _ in self._get_selected_source_cells()}
        if scope == "Selected Rows":
            return set(self._get_selected_source_rows())
        return set(range(self._model.rowCount()))

    def _get_selected_source_rows(self) -> list[int]:
        selection = self._view.selectionModel()
        if not selection:
            return []
        rows = {self._proxy.mapToSource(index).row() for index in selection.selectedRows()}
        return sorted(rows)

    def _get_selected_proxy_rows(self) -> list[int]:
        selection = self._view.selectionModel()
        if not selection:
            return []
        rows = sorted({index.row() for index in selection.selectedRows()})
        return rows

    def _get_selected_proxy_columns(self) -> list[int]:
        selection = self._view.selectionModel()
        if not selection:
            return []
        cols = set()
        for index in selection.selectedIndexes():
            if index.column() == 0:
                continue
            cols.add(index.column() - 1)
        return sorted(cols)

    def _get_selected_source_cells(self) -> list[tuple[int, int]]:
        selection = self._view.selectionModel()
        if not selection:
            return []
        cells = []
        for index in selection.selectedIndexes():
            source_index = self._proxy.mapToSource(index)
            if source_index.column() == 0:
                continue
            cells.append((source_index.row(), source_index.column() - 1))
        return cells

    def _open_dedup(self) -> None:
        headers = self._model.get_headers()
        data = self._model.get_data()

        def preview(columns: list[int], keep_last: bool) -> int:
            keys = []
            for row in data:
                keys.append(tuple(row[i] for i in columns))
            seen = set()
            removed = 0
            if keep_last:
                for key in reversed(keys):
                    if key in seen:
                        removed += 1
                    else:
                        seen.add(key)
            else:
                for key in keys:
                    if key in seen:
                        removed += 1
                    else:
                        seen.add(key)
            return removed

        dialog = DedupDialog(headers, preview)
        if dialog.exec() != QDialog.Accepted:
            return
        columns = dialog.get_columns()
        keep_last = dialog.keep_last()
        if not columns:
            return
        keys = {}
        result_rows: list[list[str]] = []
        if keep_last:
            for idx in reversed(range(len(data))):
                key = tuple(data[idx][i] for i in columns)
                if key in keys:
                    continue
                keys[key] = idx
                result_rows.append(data[idx])
            result_rows.reverse()
        else:
            for row in data:
                key = tuple(row[i] for i in columns)
                if key in keys:
                    continue
                keys[key] = True
                result_rows.append(row)
        self._push_undo("去重")
        self._model.set_data(result_rows, headers=headers)
        self._column_order_names = self._model.get_headers()
        self._update_status("去重完成")

    def _open_group(self) -> None:
        headers = self._model.get_headers()
        data = self._get_proxy_data(list(range(len(headers))))
        dialog = GroupDialog(headers, data)
        dialog.exec()

    def _to_half_width(self, text: str) -> str:
        result = []
        for ch in text:
            code = ord(ch)
            if code == 0x3000:
                result.append(" ")
            elif 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(ch)
        return "".join(result)

    def _to_full_width(self, text: str) -> str:
        result = []
        for ch in text:
            code = ord(ch)
            if code == 0x20:
                result.append(chr(0x3000))
            elif 0x21 <= code <= 0x7E:
                result.append(chr(code + 0xFEE0))
            else:
                result.append(ch)
        return "".join(result)


    def _export(self, export_type: str | None) -> None:
        headers = self._model.get_headers()
        templates = self._settings.get_export_templates()
        selected_rows = self._get_selected_proxy_rows()
        selected_columns_in_view = self._get_selected_proxy_columns()
        default_columns = selected_columns_in_view if selected_columns_in_view else list(range(len(headers)))
        dialog = ExportDialog(
            headers=headers,
            templates=templates,
            selected_rows=len(selected_rows),
            selected_columns=default_columns,
        )
        if export_type:
            dialog._type_combo.setCurrentText(export_type)
        dialog._delimiter_input.setText(self._settings.get_delimiter())
        if dialog.exec() != QDialog.Accepted:
            return
        config = dialog.get_export_config()
        self._settings.set_export_templates(dialog.templates())
        selected_columns = config.get("columns", [])
        if config.get("only_selected_columns"):
            if not selected_columns_in_view:
                QMessageBox.warning(self, "导出", "请先选中列。")
                return
            selected_columns = selected_columns_in_view
        if not selected_columns:
            QMessageBox.warning(self, "导出", "请至少选择一列。")
            return
        if config.get("only_selected_rows"):
            if not selected_rows:
                QMessageBox.warning(self, "导出", "请先选中行。")
                return
            data = self._get_proxy_data_for_rows(selected_rows, selected_columns)
        else:
            data = self._get_proxy_data(selected_columns)
        export_headers = [headers[i] for i in selected_columns]
        export_type = config.get("type", "TXT")
        file_filter = f"{export_type} (*.{export_type.lower()})"
        default_dir = self._settings.get_last_export_dir()
        path_str, _ = QFileDialog.getSaveFileName(self, "导出", default_dir, file_filter)
        if not path_str:
            return
        path = Path(path_str)
        if export_type == "TXT":
            export_txt(path, export_headers, data, config.get("delimiter", "----"))
        elif export_type == "CSV":
            export_csv(path, export_headers, data)
        else:
            export_xlsx(path, export_headers, data)
        self._settings.set_last_export_dir(str(path.parent))
        self._update_status(f"已导出 {export_type}：{path}")

    def _get_proxy_data(self, columns: list[int]) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in range(self._proxy.rowCount()):
            values = []
            for col in columns:
                value = self._proxy.data(self._proxy.index(row, col + 1), Qt.DisplayRole)
                values.append("" if value is None else str(value))
            rows.append(values)
        return rows

    def _get_proxy_data_for_rows(self, rows: list[int], columns: list[int]) -> list[list[str]]:
        result: list[list[str]] = []
        for row in rows:
            values = []
            for col in columns:
                value = self._proxy.data(self._proxy.index(row, col + 1), Qt.DisplayRole)
                values.append("" if value is None else str(value))
            result.append(values)
        return result

    def _update_status(self, message: str | None = None) -> None:
        visible_rows = self._proxy.rowCount()
        total_rows = self._model.rowCount()
        columns = len(self._model.get_headers())
        selection = self._view.selectionModel()
        selected_rows = len(selection.selectedRows()) if selection else 0
        current = self._view.currentIndex()
        if current.isValid():
            row_num = current.row() + 1
            col_num = current.column() + 1
            if current.column() == 0:
                col_name = "序号"
            else:
                headers = self._model.get_headers()
                data_index = current.column() - 1
                col_name = headers[data_index] if data_index < len(headers) else "未知"
            cursor_info = f"当前：第{row_num}行 第{col_num}列（{col_name}）"
        else:
            cursor_info = "当前：无"
        mode_hint = "  大数据模式" if total_rows >= 100000 else ""
        status = (
            f"行：{visible_rows}/{total_rows}  列：{columns}  已选行：{selected_rows}  "
            f"{cursor_info}{mode_hint}"
        )
        if message:
            status = f"{message} | {status}"
        self._status.showMessage(status)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if mime.hasUrls():
            paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            if paths:
                self._load_files(paths)
            event.acceptProposedAction()
            return
        if mime.hasText():
            text = mime.text()
            self._apply_text(text)
            event.acceptProposedAction()
            return
        event.ignore()

    def closeEvent(self, event) -> None:
        self._session.set_last_session(self._last_files, self._last_text)
        self._settings.save_geometry(self.saveGeometry())
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
