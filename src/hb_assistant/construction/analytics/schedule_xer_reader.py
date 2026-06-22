"""Tab-delimited Primavera P6 XER table reader (%T / %F / %R)."""

from __future__ import annotations


def decode_xer_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def read_xer_tables(text: str) -> dict[str, list[dict[str, str]]]:
    """Parse XER export into table name -> list of row dicts."""
    tables: dict[str, list[dict[str, str]]] = {}
    current_table: str | None = None
    fields: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if not line.startswith("%"):
            continue
        parts = line.split("\t")
        marker = parts[0]
        if marker == "%T" and len(parts) > 1:
            current_table = parts[1].strip()
            fields = []
            tables.setdefault(current_table, [])
            continue
        if marker == "%F" and current_table:
            fields = [p.strip() for p in parts[1:] if p.strip()]
            continue
        if marker == "%R" and current_table and fields:
            values = parts[1:]
            if len(values) < len(fields):
                values = values + [""] * (len(fields) - len(values))
            row = {fields[i]: values[i] if i < len(values) else "" for i in range(len(fields))}
            tables[current_table].append(row)
    return tables