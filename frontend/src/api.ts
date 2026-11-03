export type ChatResponse = {
  message: string;
  session_id?: string | null;
  source?: string;
  route?: string | null;
  events?: Record<string, unknown>[];
  sources?: Array<{
    doc_id?: string;
    source?: string;
    score?: number;
    snippet?: string;
  }>;
  sql?: string | null;
  query_summary?: Record<string, unknown> | null;
};

export type QueryResponse = {
  question: string;
  summary: Record<string, unknown>;
  sql: string;
  rows: Record<string, unknown>[];
  chart?: Record<string, unknown> | null;
  gpt_vis?: string | null;
  ir?: Record<string, unknown> | null;
};

export type SemanticMetric = {
  key: string;
  label: string;
  definition: string;
  sql?: string;
  default_dimensions?: string[];
  synonyms?: string[];
};

export type SemanticDimension = {
  key: string;
  label: string;
  definition: string;
};

export type SemanticCatalog = {
  name?: string | null;
  description?: string | null;
  handbook?: string | null;
  metrics: SemanticMetric[];
  dimensions: SemanticDimension[];
  entities?: Array<Record<string, unknown>>;
};

const API_BASE = "";

/** 解析 FastAPI / 普通文本错误，避免把整段 JSON 甩到界面上。 */
export async function readApiError(resp: Response): Promise<string> {
  const raw = await resp.text();
  if (!raw) return `请求失败（HTTP ${resp.status}）`;
  try {
    const body = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    const detail = body.detail ?? body.message;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (typeof item === "object" && item && "msg" in item ? String((item as { msg: unknown }).msg) : String(item)))
        .join("；");
    }
    if (detail != null) return JSON.stringify(detail);
  } catch {
    /* plain text */
  }
  return raw.length > 280 ? `${raw.slice(0, 280)}…` : raw;
}

export async function fetchSemanticCatalog(): Promise<SemanticCatalog> {
  const resp = await fetch(`${API_BASE}/api/v1/semantic`);
  if (!resp.ok) {
    throw new Error(await readApiError(resp));
  }
  return resp.json();
}

export async function postChat(message: string, sessionId: string): Promise<ChatResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!resp.ok) {
    throw new Error(await readApiError(resp));
  }
  return resp.json();
}

export async function postQuery(
  question: string,
  opts?: { metric?: string | null; dimensions?: string[] | null },
): Promise<QueryResponse> {
  const resp = await fetch(`${API_BASE}/api/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      metric: opts?.metric || undefined,
      dimensions: opts?.dimensions || undefined,
    }),
  });
  if (!resp.ok) {
    throw new Error(await readApiError(resp));
  }
  return resp.json();
}

export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  opts?: { metric?: string | null; dimensions?: string[] | null },
): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      metric: opts?.metric || undefined,
      dimensions: opts?.dimensions || undefined,
    }),
  });
  if (!resp.ok || !resp.body) {
    throw new Error(await readApiError(resp));
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        onEvent(event, JSON.parse(data));
      } catch {
        onEvent(event, { raw: data });
      }
    }
  }
}

export function routeLabel(route?: string | null): string {
  switch (route) {
    case "rag":
      return "知识检索";
    case "nl2sql":
      return "问数分析";
    case "mcp":
      return "设备查询";
    case "hybrid":
      return "综合分析";
    default:
      return "智能路由";
  }
}
