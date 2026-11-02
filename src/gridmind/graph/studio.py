"""LangGraph Agent Server / Studio entrypoint.

Studio input example:

```json
{
  "question": "查询昨天各变电站的最高温度"
}
```
"""

from gridmind.graph.workflow import build_chat_graph

# Agent Server injects persistence; do not attach MemorySaver here.
graph = build_chat_graph(with_memory=False)
