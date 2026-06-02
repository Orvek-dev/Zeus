from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Union

SQLiteValue = Union[str, int, None]


@dataclass(frozen=True)
class IdempotencyConflictError(RuntimeError):
    table_name: str
    key_name: str
    key_value: str

    def __str__(self) -> str:
        return "conflicting idempotent replay for {0}.{1}={2}".format(
            self.table_name,
            self.key_name,
            self.key_value,
        )


def confirm_existing_row(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    columns: tuple[str, ...],
    key_column: str,
    key_value: str,
    values: tuple[SQLiteValue, ...],
    cause: sqlite3.IntegrityError,
) -> None:
    row = connection.execute(
        "SELECT {0} FROM {1} WHERE {2} = ?".format(
            ", ".join(columns),
            table_name,
            key_column,
        ),
        (key_value,),
    ).fetchone()
    if row is not None and tuple(row) == values:
        return
    raise IdempotencyConflictError(table_name, key_column, key_value) from cause


def insert_or_confirm_same(
    connection: sqlite3.Connection,
    statement: str,
    values: tuple[SQLiteValue, ...],
    *,
    table_name: str,
    columns: tuple[str, ...],
    key_columns: tuple[tuple[str, str], ...],
) -> None:
    try:
        connection.execute(statement, values)
    except sqlite3.IntegrityError as exc:
        rows = connection.execute(
            "SELECT {0} FROM {1} WHERE {2}".format(
                ", ".join(columns),
                table_name,
                " OR ".join("{0} = ?".format(column) for column, _ in key_columns),
            ),
            tuple(value for _, value in key_columns),
        ).fetchall()
        if any(tuple(row) == values for row in rows):
            return
        key_name = "|".join(column for column, _ in key_columns)
        key_value = "|".join(value for _, value in key_columns)
        raise IdempotencyConflictError(table_name, key_name, key_value) from exc
