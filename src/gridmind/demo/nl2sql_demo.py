"""学习示例：NL2SQL 原理落地

演示完整链路（学习版，默认可离线）：

1. 语义层（YAML：实体/指标/表白名单）
2. 意图 → Query IR（结构化中间表示）
3. IR → SQL（规则编译；有 Key 时可用 LLM 改写）
4. SQLGlot Guard（只读、白名单、LIMIT）
5. 执行 → 结果 / 口径摘要

运行::

    uv run python -m gridmind.demo nl2sql
"""

from __future__ import annotations

import asyncio
import json

from gridmind.core.errors import GridMindError
from gridmind.demo._common import banner, has_api_key, need_key_hint
from gridmind.nl2sql.compiler import compile_sql
from gridmind.nl2sql.engine import get_nl2sql_engine
from gridmind.nl2sql.executor import init_demo_db
from gridmind.nl2sql.planner import plan_from_question
from gridmind.nl2sql.semantic import load_semantic_model, schema_prompt, tables_whitelist
from gridmind.nl2sql.sql_guard import validate_sql


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def step_by_step(question: str) -> None:
    """把一条问题拆开打印，便于理解原理。"""
    print(f"\n问题: {question}")

    # 1) 语义层
    model = load_semantic_model()
    metrics = model.get("metrics", {})
    print("语义层指标:", list(metrics.keys()))
    print("表白名单:", sorted(tables_whitelist(model)))

    # 2) IR
    ir = plan_from_question(question)
    print("Query IR:", json.dumps(ir.model_dump(), ensure_ascii=False))

    # 3) 编译 SQL
    sql = compile_sql(ir)
    print("编译 SQL:\n", sql)

    # 4) Guard
    safe = validate_sql(sql, dialect="sqlite")
    print("校验后 SQL:\n", safe)

    # 5) 执行
    init_demo_db()
    from gridmind.nl2sql.executor import execute_sql

    rows = execute_sql(safe)
    definition = metrics.get(ir.metric or "", {}).get("definition", "")
    print("口径:", definition or "(无)")
    print("结果行数:", len(rows))
    print("结果预览:", rows[:5])


def guard_demos() -> None:
    section("SQL Guard：拦截危险 / 非法 SQL")
    cases = [
        "DELETE FROM devices",
        "SELECT * FROM secrets",
        "SELECT device_id FROM devices; DROP TABLE devices",
        "UPDATE devices SET status='offline'",
    ]
    for sql in cases:
        try:
            validate_sql(sql, dialect="sqlite")
            print(f"  UNEXPECTED PASS: {sql}")
        except GridMindError as exc:
            print(f"  BLOCKED [{exc.code}] {sql}")
            print(f"           → {exc.message}")


async def full_engine_demo() -> None:
    section("引擎一次跑通（与业务 Nl2SqlEngine 相同）")
    if not has_api_key():
        need_key_hint()
        print("本段 use_llm=False，只走规则编译。\n")

    engine = get_nl2sql_engine()
    questions = [
        "查询昨天各变电站的最高温度",
        "查询过去7天告警数量排名前10的设备",
        "查询当前在线设备数量",
        "对比本月和上月的设备告警数量",
    ]
    for q in questions:
        result = await engine.run(q, use_llm=False)
        print(f"Q: {q}")
        print(f"  metric={result['summary'].get('metric')} dims={result['summary'].get('dimensions')}")
        print(f"  sql={result['sql'].replace(chr(10), ' ')[:100]}...")
        print(f"  rows={result['rows'][:3]}")
        print()

    if has_api_key():
        print("检测到 API Key：再跑一条 LLM 辅助生成")
        q = "查询昨天各变电站的最高温度"
        result = await engine.run(q, use_llm=True)
        print(f"Q: {q}")
        print("SQL:", result["sql"])
        print("rows:", result["rows"][:3])


def principle_notes() -> None:
    section("原理对照")
    print(
        """
自然语言
  → 意图 / Schema Linking（planner + 语义层）
  → Query IR（结构化计划，不是直接 SQL）
  → SQL Compiler / LLM
  → SQLGlot Guard（只读、白名单、LIMIT）
  → Executor（SQLite 演示库；生产换 PG/TDengine）
  → 口径摘要 + 表格/图表
""".strip()
    )
    print("\n语义层片段（给 LLM 的 schema 提示）:")
    print(schema_prompt()[:500])
    print("...")


def main() -> None:
    banner("NL2SQL 原理 Demo")
    principle_notes()

    section("逐步拆解一条问题")
    step_by_step("查询昨天各变电站的最高温度")

    guard_demos()
    asyncio.run(full_engine_demo())

    print("\n要点：NL2SQL 的难点是口径与安全，不是会不会写 SELECT。")
    print("相关代码: gridmind.nl2sql.{semantic,planner,compiler,sql_guard,executor,engine}")


if __name__ == "__main__":
    main()
