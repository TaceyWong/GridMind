from gridmind.graph.nodes.router import rule_route


def test_route_rag():
    assert rule_route("告警等级是如何定义的？") == "rag"


def test_route_nl2sql():
    assert rule_route("查询昨天各变电站的最高温度") == "nl2sql"


def test_route_mcp():
    assert rule_route("设备 DEV-001 当前状态是什么？") == "mcp"


def test_route_hybrid():
    assert rule_route("查询昨天告警最多的五台设备，并分析温度变化是否异常") == "hybrid"
