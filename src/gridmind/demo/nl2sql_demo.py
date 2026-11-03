"""学习示例：NL2SQL 原理落地

业务引擎：LLM 逻辑 SQL → Wren 展开 → Guard → 执行（无模板、无回退）。
本文件 step_by_step 仍用 compiler 做离线示意，便于理解 IR/Guard。

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

    # 3) 离线示意：compiler 模板（业务引擎不走这条）
    sql = compile_sql(ir)
    print("示意 SQL（非业务路径）:\n", sql)

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
    section("引擎一次跑通（LLM → Wren，无模板回退）")
    if not has_api_key():
        need_key_hint()
        print("未配置 LLM_API_KEY：业务引擎会直接报错，跳过本段。\n")
        return

    from gridmind.nl2sql.engine import Nl2SqlError

    engine = get_nl2sql_engine()
    questions = [
        "查询昨天各变电站的最高温度",
        "查询过去7天告警数量排名前10的设备",
        "查询当前在线设备数量",
        "对比本月和上月的设备告警数量",
    ]
    for q in questions:
        try:
            result = await engine.run(q)
        except Nl2SqlError as exc:
            print(f"Q: {q}")
            print(f"  ERROR: {exc}")
            print()
            continue
        print(f"Q: {q}")
        print(f"  planner={result['summary'].get('planner')} metric={result['summary'].get('metric')}")
        print(f"  logical={str(result.get('logical_sql', '')).replace(chr(10), ' ')[:100]}...")
        print(f"  sql={result['sql'].replace(chr(10), ' ')[:100]}...")
        print(f"  rows={result['rows'][:3]}")
        print()


def principle_notes() -> None:
    section("原理对照")
    print(
        """
自然语言
  → Query IR（意图/指标约束，可选）
  → LLM 生成逻辑 SQL（对语义模型；无 LLM 直接报错）
  → Wren Core 语义展开
  → SQLGlot Guard → Executor
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
