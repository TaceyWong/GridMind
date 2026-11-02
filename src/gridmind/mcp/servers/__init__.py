from gridmind.mcp.servers.bi import register_bi_tools
from gridmind.mcp.servers.iot import register_iot_tools


def register_all_servers() -> None:
    register_iot_tools()
    register_bi_tools()
