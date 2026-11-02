"""python -m gridmind.demo [name]"""

from __future__ import annotations

import argparse
import importlib
import sys

from gridmind.demo import DEMOS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GridMind 学习示例")
    parser.add_argument(
        "name",
        nargs="?",
        choices=DEMOS,
        help="示例名；省略则列出全部",
    )
    args = parser.parse_args(argv)

    if not args.name:
        print("可用示例：")
        for name in DEMOS:
            print(f"  uv run python -m gridmind.demo {name}")
        return 0

    module = importlib.import_module(f"gridmind.demo.{args.name}_demo")
    module.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
