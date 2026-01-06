# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import re

from PySide6.QtCore import QSortFilterProxyModel, Qt


@dataclass
class FilterRule:
    column: int | None
    mode: str
    value: str


class FilterProxyModel(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self._global_filter: str = ""
        self._rules: list[FilterRule] = []
        self._whole_row_sort: Qt.SortOrder | None = None

    def set_global_filter(self, text: str) -> None:
        self._global_filter = text.strip()
        self.invalidateFilter()

    def set_filters(self, rules: list[FilterRule]) -> None:
        self._rules = rules[:]
        self.invalidateFilter()

    def add_filter(self, rule: FilterRule) -> None:
        self._rules.append(rule)
        self.invalidateFilter()

    def clear_filters(self) -> None:
        self._rules.clear()
        self.invalidateFilter()

    def filters(self) -> list[FilterRule]:
        return self._rules[:]

    def set_whole_row_sort(self, order: Qt.SortOrder) -> None:
        self._whole_row_sort = order
        self.invalidate()
        self.sort(0, order)

    def clear_whole_row_sort(self) -> None:
        self._whole_row_sort = None
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model = self.sourceModel()
        if model is None:
            return False
        column_count = model.columnCount() - 1
        if column_count <= 0:
            return False
        row_values = [
            str(model.data(model.index(source_row, col + 1), Qt.DisplayRole) or "")
            for col in range(column_count)
        ]
        if self._global_filter:
            needle = self._global_filter.lower()
            if not any(needle in value.lower() for value in row_values):
                return False
        for rule in self._rules:
            if not self._apply_rule(rule, row_values):
                return False
        return True

    def lessThan(self, left, right) -> bool:
        if left.column() == 0 and right.column() == 0:
            try:
                return int(left.data()) < int(right.data())
            except (TypeError, ValueError):
                return str(left.data()) < str(right.data())
        if self._whole_row_sort is not None:
            model = self.sourceModel()
            if model is None:
                return False
            column_count = model.columnCount() - 1
            if column_count <= 0:
                return False
            left_values = [
                str(model.data(model.index(left.row(), col + 1), Qt.DisplayRole) or "")
                for col in range(column_count)
            ]
            right_values = [
                str(model.data(model.index(right.row(), col + 1), Qt.DisplayRole) or "")
                for col in range(column_count)
            ]
            left_key = "----".join(left_values)
            right_key = "----".join(right_values)
            return left_key < right_key
        return super().lessThan(left, right)

    def _apply_rule(self, rule: FilterRule, row_values: list[str]) -> bool:
        if rule.column is None:
            return self._apply_rule_all_columns(rule, row_values)
        if rule.column < 0 or rule.column >= len(row_values):
            return False
        return self._match_value(row_values[rule.column], rule)

    def _apply_rule_all_columns(self, rule: FilterRule, row_values: list[str]) -> bool:
        if rule.mode == "Not contains":
            needle = rule.value.lower()
            return all(needle not in value.lower() for value in row_values)
        return any(self._match_value(value, rule) for value in row_values)

    def _match_value(self, value: str, rule: FilterRule, invert: bool = False) -> bool:
        haystack = value
        needle = rule.value
        if rule.mode == "Regex":
            try:
                return re.search(needle, haystack, re.IGNORECASE) is not None
            except re.error:
                return False
        haystack_lower = haystack.lower()
        needle_lower = needle.lower()
        if rule.mode == "Contains":
            return needle_lower in haystack_lower
        if rule.mode == "Not contains":
            return needle_lower not in haystack_lower
        if rule.mode == "Equals":
            return haystack_lower == needle_lower
        if rule.mode == "Starts with":
            return haystack_lower.startswith(needle_lower)
        if rule.mode == "Ends with":
            return haystack_lower.endswith(needle_lower)
        return False
