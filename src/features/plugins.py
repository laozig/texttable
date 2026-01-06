# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import traceback

import pandas as pd
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.features.settings import SettingsManager


class LogDialog(QDialog):
    def __init__(self, title: str, content: str) -> None:
        super().__init__()
        self.setWindowTitle(title)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(content)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout()
        layout.addWidget(text)
        layout.addWidget(buttons)
        self.setLayout(layout)


class PluginDialog(QDialog):
    def __init__(self, settings: SettingsManager, run_callback) -> None:
        super().__init__()
        self.setWindowTitle("运行脚本")
        self._settings = settings
        self._run_callback = run_callback

        self._script_path = QLineEdit()
        self._browse_button = QPushButton("浏览")
        self._browse_button.clicked.connect(self._browse)

        self._scope_combo = QComboBox()
        self._scope_combo.addItem("全量数据", "Full dataset")
        self._scope_combo.addItem("当前筛选视图", "Current filtered view")

        self._dry_run = QCheckBox("仅预览（不应用结果）")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("运行")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self._script_path)
        path_layout.addWidget(self._browse_button)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("脚本："))
        layout.addLayout(path_layout)
        layout.addWidget(QLabel("范围："))
        layout.addWidget(self._scope_combo)
        layout.addWidget(self._dry_run)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self._restore_last_settings()

    def _restore_last_settings(self) -> None:
        data = self._settings.get_plugin_settings()
        script = data.get("last_script", "")
        scope = data.get("last_scope", "Full dataset")
        self._script_path.setText(script)
        for idx in range(self._scope_combo.count()):
            if self._scope_combo.itemData(idx) == scope:
                self._scope_combo.setCurrentIndex(idx)
                break

    def _browse(self) -> None:
        data = self._settings.get_plugin_settings()
        folder = data.get("script_folder", str(Path.cwd()))
        path, _ = QFileDialog.getOpenFileName(self, "选择脚本", folder, "Python 脚本 (*.py)")
        if not path:
            return
        self._script_path.setText(path)
        self._settings.set_plugin_settings(
            {
                "script_folder": str(Path(path).parent),
                "last_script": path,
                "last_scope": self._scope_combo.currentText(),
            }
        )

    def _run(self) -> None:
        path = self._script_path.text().strip()
        if not path:
            QMessageBox.warning(self, "脚本", "请先选择脚本。")
            return
        self._settings.set_plugin_settings(
            {
                "script_folder": str(Path(path).parent),
                "last_script": path,
                "last_scope": self._scope_combo.currentText(),
            }
        )
        scope = self._scope_combo.currentData() or self._scope_combo.currentText()
        dry_run = self._dry_run.isChecked()
        result = self._run_callback(Path(path), scope, dry_run)
        if result:
            self.accept()


def run_script(path: Path, df: pd.DataFrame) -> tuple[pd.DataFrame | None, str, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        code = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, "", "", f"读取脚本失败：{exc}"
    scope: dict = {}
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            exec(code, scope)
            if "transform" not in scope or not callable(scope["transform"]):
                return None, stdout.getvalue(), stderr.getvalue(), "脚本必须定义 transform(df)。"
            result = scope["transform"](df.copy())
            if not isinstance(result, pd.DataFrame):
                return None, stdout.getvalue(), stderr.getvalue(), "transform(df) 必须返回 DataFrame。"
            return result, stdout.getvalue(), stderr.getvalue(), ""
        except Exception:
            return None, stdout.getvalue(), stderr.getvalue(), traceback.format_exc()
