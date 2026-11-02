from __future__ import annotations

import sqlglot
from sqlglot import exp

from gridmind.core.errors import GridMindError
from gridmind.nl2sql.semantic import tables_whitelist


FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
)


def validate_sql(sql: str, dialect: str = "sqlite") -> str:
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except Exception as exc:  # noqa: BLE001
        raise GridMindError(f"SQL 解析失败: {exc}", code="sql_parse_error") from exc

    if len(statements) != 1:
        raise GridMindError("只允许执行一条 SQL", code="sql_multi_statement")

    tree = statements[0]
    if tree is None:
        raise GridMindError("空 SQL", code="sql_empty")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise GridMindError("禁止非只读 SQL", code="sql_forbidden")

    if not isinstance(tree, (exp.Select, exp.With)):
        raise GridMindError("只允许 SELECT 查询", code="sql_not_select")

    allowed = tables_whitelist()
    used_tables = {t.name for t in tree.find_all(exp.Table) if t.name}
    unknown = used_tables - allowed
    if unknown:
        raise GridMindError(f"表不在白名单: {sorted(unknown)}", code="sql_table_denied")

    # Ensure LIMIT exists for unbounded selects
    select = tree.args.get("this") if isinstance(tree, exp.With) else tree
    if isinstance(select, exp.Select) and select.args.get("limit") is None:
        select = select.limit(100)
        if isinstance(tree, exp.With):
            tree.set("this", select)
            return tree.sql(dialect=dialect)
        return select.sql(dialect=dialect)

    return tree.sql(dialect=dialect)
