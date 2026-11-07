from __future__ import annotations

from collections.abc import Iterable, Sequence

from psycopg import Cursor, sql


def copy_rows(
    cur: Cursor,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> int:
    """COPY ``rows`` into ``table`` and return the number of rows written."""
    statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
    )
    count = 0
    with cur.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count
