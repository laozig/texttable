from __future__ import annotations


def parse_text(text: str, delimiter: str = "----") -> list[list[str]]:
    rows: list[list[str]] = []
    max_cols = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(delimiter)]
        rows.append(parts)
        max_cols = max(max_cols, len(parts))
    if max_cols == 0:
        return []
    for row in rows:
        if len(row) < max_cols:
            row.extend([""] * (max_cols - len(row)))
    return rows


def rows_to_text(rows: list[list[str]], delimiter: str = "----") -> str:
    return "\n".join(delimiter.join(row) for row in rows)
