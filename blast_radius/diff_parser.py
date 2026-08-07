"""Extract column-level schema changes from a git diff.

Handles the shapes a data PR actually takes: dbt/SQL model edits and dbt YAML
schema files. The goal is not a full SQL parser — it is to spot the specific
edits that break downstream consumers: a column renamed, dropped, or retyped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
# A changed column in schema.yml is indented under `columns:` — at least six
# spaces in dbt's conventional layout. Shallower names are models, not columns.
_YAML_NAME_RE = re.compile(r"^\s{5,}-?\s*name:\s*([\w]+)\s*$")
# In a dbt schema.yml the hunk header carries the enclosing model, e.g.
#   @@ -5,7 +5,7 @@ models:   - name: orders
_HUNK_CONTEXT_RE = re.compile(r"^@@[^@]*@@\s*(.*)$")
# A model entry sits directly under `models:` (shallow indent); a column entry
# sits deeper under `columns:`. Indentation is what tells them apart.
_YAML_MODEL_RE = re.compile(r"^(\s{0,4})-\s*name:\s*([\w]+)\s*$")


def _table_from_path(path: str) -> str:
    """dbt convention: models/marts/orders.sql defines the `orders` model."""
    leaf = path.rsplit("/", 1)[-1]
    for suffix in (".sql", ".yml", ".yaml"):
        if leaf.endswith(suffix):
            return leaf[: -len(suffix)]
    return leaf


def _strip_qualifier(col: str) -> str:
    return col.rsplit(".", 1)[-1]


def _is_yaml(path: str) -> bool:
    return path.endswith((".yml", ".yaml"))


def _model_for_column(path: str, column: str, repo_root: str | None) -> str | None:
    """Find which dbt model a schema.yml column belongs to.

    git only shows a few lines of context, and `- name: <model>` usually sits
    outside that window, so the diff alone cannot say which model a changed
    column belongs to. When the working tree is available, read the file and
    resolve it properly instead of guessing from the filename.
    """
    if not repo_root:
        return None
    full = Path(repo_root) / path
    if not full.is_file():
        return None

    current_model: str | None = None
    in_columns = False
    for raw in full.read_text().splitlines():
        model = _YAML_MODEL_RE.match(raw)
        if model:
            current_model = model.group(2)
            in_columns = False
            continue
        if re.match(r"^\s*columns:\s*$", raw):
            in_columns = True
            continue
        if in_columns and re.match(rf"^\s*-\s*name:\s*{re.escape(column)}\s*$", raw):
            return current_model
    return None


def parse_diff(diff_text: str, repo_root: str | None = None) -> list[ColumnChange]:
    """Parse a unified diff into column changes.

    ``repo_root`` lets schema.yml columns be attributed to the right dbt model
    by reading the file; without it, the filename is used as a fallback.
    """
    changes: list[ColumnChange] = []
    current_file = ""
    removed: list[str] = []
    added: list[str] = []
    # For dbt schema.yml, the model being described is declared in the file,
    # not implied by the filename.
    yaml_model = ""

    def flush() -> None:
        """Pair removals with additions in one hunk to detect renames."""
        nonlocal removed, added
        if not current_file:
            removed, added = [], []
            return

        resolved: str | None = None
        if _is_yaml(current_file) and not yaml_model:
            # The working tree holds the post-change name, so try the added
            # column first and fall back to the removed one.
            for probe in [*added, *removed]:
                resolved = _model_for_column(
                    current_file, _strip_qualifier(probe), repo_root
                )
                if resolved:
                    break
        table = yaml_model or resolved or _table_from_path(current_file)
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
            yaml_model = ""
            continue

        hunk = _HUNK_CONTEXT_RE.match(line)
        if hunk:
            flush()
            if _is_yaml(current_file):
                model = _YAML_MODEL_RE.match(hunk.group(1))
                if model:
                    yaml_model = model.group(2)
            continue

        # Context lines inside a YAML hunk reveal the enclosing model.
        if _is_yaml(current_file) and line.startswith(" "):
            model = _YAML_MODEL_RE.match(line[1:])
            if model:
                yaml_model = model.group(2)

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
    kept = [c for c in changes if c.column.lower() not in noise]

    # A dbt rename usually touches both the model and its schema.yml. That is
    # one change to report, not two.
    deduped: dict[tuple[str, str, str, str | None], ColumnChange] = {}
    for change in kept:
        key = (change.kind.value, change.table, change.column, change.new_column)
        if key not in deduped:
            deduped[key] = change
    return list(deduped.values())
