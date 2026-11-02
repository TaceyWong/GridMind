"""学习示例：Ruff（Lint + Format）

目标：
- 理解 Ruff = 超快的 Python 检查器/格式化工具
- 现场制造几处问题，跑 `ruff check` / `--fix` / `format`

运行::

    uv run python -m gridmind.demo ruff
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from gridmind.demo._common import banner

# 故意不规范的示例代码（仅用于演示 Ruff）
BAD_SOURCE = '''\
import os,sys
import json

unused = 1

def add( a,b ):
    x=a+b
    return x
'''


def run_ruff(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> None:
    banner("Ruff：Lint + Format")
    print("Ruff 能做什么：")
    print("  - ruff check   ≈ Flake8/isort（找问题，可自动修）")
    print("  - ruff format  ≈ Black（统一代码风格）")
    print("  - 配置通常写在 pyproject.toml 的 [tool.ruff]")

    with tempfile.TemporaryDirectory(prefix="gridmind-ruff-") as tmp:
        root = Path(tmp)
        sample = root / "sample_bad.py"
        sample.write_text(BAD_SOURCE, encoding="utf-8")
        print(f"\n临时样例: {sample}")
        print("----- 原始代码 -----")
        print(BAD_SOURCE)

        print("----- 1) ruff check（只报告） -----")
        checked = run_ruff(["check", str(sample)], cwd=root)
        print(checked.stdout or checked.stderr or "(no output)")
        print("exit_code =", checked.returncode)

        print("----- 2) ruff check --fix（自动修能修的） -----")
        fixed = run_ruff(["check", "--fix", str(sample)], cwd=root)
        print(fixed.stdout or fixed.stderr or "(no output)")
        print("修复后文件:")
        print(sample.read_text(encoding="utf-8"))

        print("----- 3) ruff format -----")
        formatted = run_ruff(["format", str(sample)], cwd=root)
        print(formatted.stdout or formatted.stderr or "(formatted)")
        print("格式化后文件:")
        print(sample.read_text(encoding="utf-8"))

    print("日常用法（在仓库根目录）:")
    print("  uv run ruff check src")
    print("  uv run ruff check src --fix")
    print("  uv run ruff format src")
    print("\n要点：Ruff 管代码质量与风格；Pydantic 管数据结构校验——两者不互相替代。")


if __name__ == "__main__":
    main()
