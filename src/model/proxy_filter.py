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
        left_value = left.data()
        right_value = right.data()
        if left.column() == 0 and right.column() == 0:
            try:
                return int(left_value) < int(right_value)
            except (TypeError, ValueError):
                return str(left_value) < str(right_value)
        return self._compare_with_numeric_prefix(left_value, right_value)

    def _compare_with_numeric_prefix(self, left_value, right_value) -> bool:
        left_text = "" if left_value is None else str(left_value)
        right_text = "" if right_value is None else str(right_value)
        left_num = self._leading_number(left_text)
        right_num = self._leading_number(right_text)
        if left_num is not None and right_num is not None:
            if left_num != right_num:
                return left_num < right_num
            return left_text < right_text
        if left_num is not None and right_num is None:
            return True
        if left_num is None and right_num is not None:
            return False
        return left_text < right_text

    @staticmethod
    def _leading_number(text: str) -> int | None:
        match = re.match(r"\s*(\d+)", text)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

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
