"""Extract column-level schema changes from a git diff.

Handles the shapes a data PR actually takes: dbt/SQL model edits and dbt YAML
schema files. The goal is not a full SQL parser — it is to spot the specific
edits that break downstream consumers: a column renamed, dropped, or retyped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ChangeKind(str, Enum):
    RENAMED = "renamed"
    DROPPED = "dropped"
    ADDED = "added"
    RETYPED = "retyped"


@dataclass
class ColumnChange:
    kind: ChangeKind
    table: str
    column: str
    new_column: str | None = None
    file: str | None = None

    @property
    def breaking(self) -> bool:
        # Adding a column cannot break an existing consumer.
        return self.kind is not ChangeKind.ADDED

    def describe(self) -> str:
        if self.kind is ChangeKind.RENAMED:
            return f"Rename {self.table}.{self.column} to {self.new_column}"
        if self.kind is ChangeKind.DROPPED:
            return f"Drop {self.table}.{self.column}"
        if self.kind is ChangeKind.RETYPED:
            return f"Change type of {self.table}.{self.column}"
        return f"Add {self.table}.{self.new_column or self.column}"


_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
# "col AS alias", "col as alias", or a bare selected column.
_ALIAS_RE = re.compile(r"^\s*([\w.]+)\s+as\s+(\w+)\s*,?\s*$", re.IGNORECASE)
_BARE_COL_RE = re.compile(r"^\s*([\w.]+)\s*,?\s*$")
_YAML_NAME_RE = re.compile(r"^\s*-?\s*name:\s*([\w]+)\s*$")


def _table_from_path(path: str) -> str:
    """dbt convention: models/marts/orders.sql defines the `orders` model."""
    leaf = path.rsplit("/", 1)[-1]
    for suffix in (".sql", ".yml", ".yaml"):
        if leaf.endswith(suffix):
            return leaf[: -len(suffix)]
    return leaf


def _strip_qualifier(col: str) -> str:
    return col.rsplit(".", 1)[-1]


def parse_diff(diff_text: str) -> list[ColumnChange]:
    """Parse a unified diff into column changes."""
    changes: list[ColumnChange] = []
    current_file = ""
    removed: list[str] = []
    added: list[str] = []

    def flush() -> None:
        """Pair removals with additions in one hunk to detect renames."""
        nonlocal removed, added
        if not current_file:
            removed, added = [], []
            return

        table = _table_from_path(current_file)
        rem = [_strip_qualifier(c) for c in removed]
        add = [_strip_qualifier(c) for c in added]

        rem_only = [c for c in rem if c not in add]
        add_only = [c for c in add if c not in rem]

        # A single swap inside one hunk is a rename; anything else is a
        # drop/add pair and we say so rather than guessing.
        if len(rem_only) == 1 and len(add_only) == 1:
            changes.append(ColumnChange(
                kind=ChangeKind.RENAMED,
                table=table,
                column=rem_only[0],
                new_column=add_only[0],
                file=current_file,
            ))
        else:
            for col in rem_only:
                changes.append(ColumnChange(
                    kind=ChangeKind.DROPPED, table=table, column=col, file=current_file,
                ))
            for col in add_only:
                changes.append(ColumnChange(
                    kind=ChangeKind.ADDED, table=table, column=col,
                    new_column=col, file=current_file,
                ))
        removed, added = [], []

    for line in diff_text.splitlines():
        header = _FILE_RE.match(line)
        if header:
            flush()
            current_file = header.group(1)
            continue

        if line.startswith("@@"):
            flush()
            continue

        if line.startswith(("+++", "---", "diff ", "index ")):
            continue

        if line.startswith("-"):
            body = line[1:]
            for pattern in (_ALIAS_RE, _YAML_NAME_RE, _BARE_COL_RE):
                m = pattern.match(body)
                if m:
                    removed.append(m.group(2) if pattern is _ALIAS_RE else m.group(1))
                    break
        elif line.startswith("+"):
            body = line[1:]
            for pattern in (_ALIAS_RE, _YAML_NAME_RE, _BARE_COL_RE):
                m = pattern.match(body)
                if m:
                    added.append(m.group(2) if pattern is _ALIAS_RE else m.group(1))
                    break

    flush()

    # Ignore SQL keywords that survive the naive line matchers.
    noise = {"select", "from", "where", "group", "order", "by", "with", "as",
             "join", "on", "and", "or", "case", "when", "then", "else", "end",
             "null", "not", "distinct", "limit", "having", "union", "all"}
    return [c for c in changes if c.column.lower() not in noise]
