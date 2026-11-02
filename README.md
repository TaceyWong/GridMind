# GridMind

电网智能问答与数据分析平台学习项目：**Agent + MCP + NL2SQL / ChatBI**。

基于 FastAPI + LangGraph 编排，整合 RAG、NL2SQL（SQLGlot）、MCP 风格工具调用。可在无 LLM Key / 无 PG / 无 TDengine / 无 Redis 时降级演示。

## 架构

```text
FastAPI  →  LangGraph(router → rag|nl2sql|mcp|hybrid → answer)
                │
     ┌──────────┼──────────┬──────────┐
     RAG        NL2SQL     MCP Client  LLM Gateway
  (BM25+向量)  (SQLGlot)   (IoT/BI)   (OpenAI兼容/Mock)
```

## 快速开始

```powershell
cd D:\pyspace\GridMind
uv sync --all-groups
copy .env.example .env   # 可选填写 LLM_API_KEY
uv run fastapi dev
```

打开 http://127.0.0.1:8000/docs

不配 `LLM_API_KEY` 时使用 Mock + 规则路由，问数/RAG/MCP 仍可跑通。

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat` | LangGraph 对话 |
| POST | `/api/v1/chat/stream` | SSE 流式 |
| POST | `/api/v1/chat/tools` | MCP 工具列表 |
| POST | `/api/v1/query` | NL2SQL 问数 |
| POST | `/api/v1/knowledge/upload` | 上传知识文档 |
| POST | `/api/v1/knowledge/search` | 混合检索 |
| POST | `/api/v1/knowledge/chat` | RAG 问答 |
| GET  | `/api/v1/knowledge/documents` | 文档列表 |
| GET  | `/api/v1/meta` | 运行时元信息 |

## 演示问题

```powershell
# RAG
curl -X POST http://127.0.0.1:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"message\":\"告警等级是如何定义的？\"}"

# NL2SQL
curl -X POST http://127.0.0.1:8000/api/v1/query -H "Content-Type: application/json" -d "{\"question\":\"查询昨天各变电站的最高温度\",\"use_llm\":false}"

# MCP / IoT
curl -X POST http://127.0.0.1:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"message\":\"设备 DEV-001 当前状态是什么？\"}"

# Hybrid
curl -X POST http://127.0.0.1:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"message\":\"查询昨天告警最多的五台设备，并分析这些设备最近一周的温度变化是否异常\"}"
```

## 降级策略

| 缺失项 | 行为 |
|--------|------|
| `LLM_API_KEY` | MockProvider + 规则路由 / 模板回答 |
| PostgreSQL | SQLite 样例库 `src/gridmind/data/gridmind.db` |
| TDengine | 内存遥测序列 |
| Redis / pgvector | 进程内状态与内存向量+BM25 |

## 可选依赖

```powershell
docker compose -f docker/docker-compose.yml up -d
```

默认代码路径不强制连接 Compose 服务；后续可把 `DATABASE_URL` / `REDIS_URL` 接到真实实现。

## 测试

```powershell
uv run pytest -q
```

## 目录要点

- `graph/` LangGraph 状态与节点
- `llm/` 模型网关与 Prompt
- `rag/` 文档加载、切分、检索、重排
- `nl2sql/` 语义层、Query IR、编译、SQLGlot 守卫、执行
- `mcp/` 进程内 MCP 风格 Client / IoT&BI Server
- `data/` 语义模型与知识库种子

## 说明

本期不做前端、真实 OAuth、生产 RBAC、模型微调。RAG 采用 LlamaIndex 风格的学习实现（本地 hash embedding + BM25 + rerank），便于无 GPU / 无云 Key 演示。
