<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { postQuery, routeLabel, streamChat, type ChatResponse, type QueryResponse } from "./api";

type Role = "user" | "assistant";

type Message = {
  id: string;
  role: Role;
  text: string;
  route?: string | null;
  summary?: Record<string, unknown> | null;
  rows?: Record<string, unknown>[];
  sources?: ChatResponse["sources"];
  sql?: string | null;
  thinking?: boolean;
};

type Session = {
  id: string;
  title: string;
  updatedAt: number;
  messages: Message[];
};

const prompts = [
  "告警等级是如何定义的？",
  "查询昨天各变电站的最高温度",
  "设备 DEV-001 当前状态是什么？",
  "查询告警最多的设备，并分析温度是否异常",
];

const sessions = ref<Session[]>([]);
const activeId = ref("");
const draft = ref("");
const busy = ref(false);
const showDiag = ref(false);
const error = ref("");
const feedRef = ref<HTMLElement | null>(null);

const active = computed(() => sessions.value.find((s) => s.id === activeId.value) || null);

function uid(prefix = "id") {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function createSession(title = "新的分析") {
  const session: Session = {
    id: uid("s"),
    title,
    updatedAt: Date.now(),
    messages: [],
  };
  sessions.value.unshift(session);
  activeId.value = session.id;
  return session;
}

function ensureSession() {
  if (!active.value) createSession();
  return active.value!;
}

async function scrollBottom() {
  await nextTick();
  if (feedRef.value) {
    feedRef.value.scrollTop = feedRef.value.scrollHeight;
  }
}

function summarizeTitle(text: string) {
  return text.length > 18 ? `${text.slice(0, 18)}…` : text;
}

async function send(text?: string) {
  const content = (text ?? draft.value).trim();
  if (!content || busy.value) return;

  const session = ensureSession();
  error.value = "";
  draft.value = "";
  busy.value = true;

  if (session.messages.length === 0) {
    session.title = summarizeTitle(content);
  }

  session.messages.push({
    id: uid("m"),
    role: "user",
    text: content,
  });

  const thinkingId = uid("m");
  session.messages.push({
    id: thinkingId,
    role: "assistant",
    text: "正在理解问题并组织分析…",
    thinking: true,
  });
  session.updatedAt = Date.now();
  await scrollBottom();

  try {
    let route: string | null | undefined;
    let summary: Record<string, unknown> | null | undefined;
    let sql: string | null | undefined;
    let sources: ChatResponse["sources"];
    let rows: Record<string, unknown>[] | undefined;
    let assembled = "";

    const patchAssistant = (patch: Partial<Message>) => {
      const idx = session.messages.findIndex((m) => m.id === thinkingId);
      if (idx < 0) return;
      session.messages[idx] = { ...session.messages[idx], ...patch };
    };

    await streamChat(content, session.id, (event, data) => {
      if (event === "status") {
        const stage = String(data.stage || "");
        if (stage === "routing") {
          patchAssistant({ text: "正在路由分析路径…", thinking: true });
        } else if (stage === "answer") {
          route = (data.route as string) || route;
          patchAssistant({
            text: assembled || "正在生成回答…",
            route,
            thinking: !assembled,
          });
        }
      } else if (event === "event") {
        const kind = String(data.type || "step");
        patchAssistant({
          text: assembled || `执行中：${kind}`,
          thinking: !assembled,
          route: (data.route as string) || route,
        });
      } else if (event === "token") {
        assembled += String(data.text || "");
        patchAssistant({ text: assembled, thinking: false, route });
        void scrollBottom();
      } else if (event === "done") {
        assembled = String(data.message || assembled);
        route = (data.route as string) || route;
        summary = (data.query_summary as Record<string, unknown>) || summary;
        sql = (data.sql as string) || sql;
        sources = (data.sources as ChatResponse["sources"]) || sources;
        const doneRows = data.query_rows as Record<string, unknown>[] | undefined;
        if (doneRows?.length) rows = doneRows;
        patchAssistant({
          text: assembled,
          thinking: false,
          route,
          summary,
          sql,
          sources,
          rows,
        });
      }
    });

    if (
      (!rows || rows.length === 0) &&
      (route === "nl2sql" || /温度|告警|在线|排名|对比/.test(content))
    ) {
      try {
        const q: QueryResponse = await postQuery(content);
        rows = q.rows;
        summary = q.summary;
        sql = q.sql;
        patchAssistant({ rows, summary, sql, route, text: assembled, thinking: false });
      } catch {
        // keep streamed payload
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e);
    session.messages = session.messages.filter((m) => m.id !== thinkingId);
  } finally {
    busy.value = false;
    session.updatedAt = Date.now();
    await scrollBottom();
  }
}

function onKeydown(ev: KeyboardEvent) {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    void send();
  }
}

function formatSummary(summary?: Record<string, unknown> | null) {
  if (!summary) return [];
  const map: Array<[string, string]> = [
    ["time_range", "时间范围"],
    ["metric", "指标"],
    ["dimensions", "维度"],
    ["definition", "口径"],
    ["filters", "过滤"],
  ];
  return map
    .map(([key, label]) => {
      const value = summary[key];
      if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) {
        return null;
      }
      return {
        label,
        value: typeof value === "string" ? value : JSON.stringify(value),
      };
    })
    .filter(Boolean) as Array<{ label: string; value: string }>;
}

function rowKeys(rows?: Record<string, unknown>[]) {
  if (!rows?.length) return [];
  return Object.keys(rows[0]);
}

onMounted(() => {
  createSession("欢迎使用 GridMind");
});
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <div class="brand">
        <div class="mark" aria-hidden="true"></div>
        <div>
          <div class="brand-name">GridMind</div>
          <div class="brand-sub">电网智能问数</div>
        </div>
      </div>

      <button class="new-btn" type="button" @click="createSession()">新建分析</button>

      <div class="rail-label">历史对话</div>
      <div class="session-list">
        <button
          v-for="s in sessions"
          :key="s.id"
          type="button"
          class="session-item"
          :class="{ active: s.id === activeId }"
          @click="activeId = s.id"
        >
          <span>{{ s.title }}</span>
          <small>{{ new Date(s.updatedAt).toLocaleTimeString() }}</small>
        </button>
      </div>

      <div class="rail-foot">
        <div class="pill">工作空间 · 演示数据集</div>
        <div class="hint">默认自然语言；口径可见，结果可验证</div>
      </div>
    </aside>

    <main class="stage">
      <header class="topbar">
        <div>
          <h1>把问题丢进来，系统自动完成检索、问数与设备查询</h1>
          <p>用户无感底层技术；可看到理解口径、表格结果与引用来源。</p>
        </div>
        <label class="diag-toggle">
          <input v-model="showDiag" type="checkbox" />
          高级诊断
        </label>
      </header>

      <section ref="feedRef" class="feed" aria-live="polite">
        <div v-if="!active?.messages.length" class="empty">
          <div class="empty-title">从一条业务问题开始</div>
          <div class="prompt-grid">
            <button
              v-for="p in prompts"
              :key="p"
              type="button"
              class="prompt"
              @click="send(p)"
            >
              {{ p }}
            </button>
          </div>
        </div>

        <article
          v-for="m in active?.messages || []"
          :key="m.id"
          class="bubble"
          :class="[m.role, { thinking: m.thinking }]"
        >
          <div class="bubble-meta">
            <span>{{ m.role === "user" ? "你" : "GridMind" }}</span>
            <span v-if="m.route" class="route">{{ routeLabel(m.route) }}</span>
          </div>
          <div class="bubble-text">{{ m.text }}</div>

          <div v-if="formatSummary(m.summary).length" class="summary">
            <div class="summary-title">分析口径</div>
            <dl>
              <div v-for="item in formatSummary(m.summary)" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </div>
            </dl>
          </div>

          <div v-if="m.rows?.length" class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="k in rowKeys(m.rows)" :key="k">{{ k }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in m.rows" :key="i">
                  <td v-for="k in rowKeys(m.rows)" :key="k">{{ row[k] }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="m.sources?.length" class="sources">
            <div class="summary-title">引用来源</div>
            <div v-for="(s, i) in m.sources" :key="i" class="source">
              <strong>{{ s.source || s.doc_id }}</strong>
              <span>{{ s.snippet }}</span>
            </div>
          </div>

          <details v-if="showDiag && m.sql" class="diag">
            <summary>查看生成 SQL</summary>
            <pre>{{ m.sql }}</pre>
          </details>
        </article>
      </section>

      <footer class="composer">
        <div v-if="error" class="error">{{ error }}</div>
        <div class="composer-box">
          <textarea
            v-model="draft"
            rows="2"
            placeholder="例如：上个月各区域的设备告警数量？"
            :disabled="busy"
            @keydown="onKeydown"
          />
          <button class="send" type="button" :disabled="busy || !draft.trim()" @click="send()">
            {{ busy ? "分析中" : "发送" }}
          </button>
        </div>
        <div class="composer-hint">Enter 发送 · Shift+Enter 换行</div>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px 1fr;
}

.rail {
  padding: 28px 20px;
  border-right: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.55), rgba(255, 255, 255, 0.28));
  backdrop-filter: blur(10px);
  display: flex;
  flex-direction: column;
  gap: 18px;
  animation: rise 0.7s ease both;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
}

.mark {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background:
    linear-gradient(135deg, transparent 46%, var(--accent) 46% 54%, transparent 54%),
    linear-gradient(45deg, transparent 46%, var(--accent-deep) 46% 54%, transparent 54%),
    radial-gradient(circle at 50% 50%, var(--accent-soft), transparent 70%),
    #fff;
  box-shadow: inset 0 0 0 1px var(--line);
  animation: pulse-mark 3.2s ease-in-out infinite;
}

.brand-name {
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.brand-sub {
  color: var(--muted);
  font-size: 0.82rem;
}

.new-btn,
.send,
.prompt,
.session-item {
  border: 1px solid var(--line);
  background: var(--panel-strong);
  color: var(--ink);
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.new-btn {
  border-radius: 999px;
  padding: 12px 16px;
  font-weight: 600;
  background: var(--accent);
  color: white;
  border-color: transparent;
}

.new-btn:hover,
.send:hover:not(:disabled),
.prompt:hover {
  transform: translateY(-1px);
}

.rail-label {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: auto;
  flex: 1;
}

.session-item {
  text-align: left;
  border-radius: 14px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-item.active {
  background: var(--accent-soft);
  border-color: rgba(15, 118, 110, 0.35);
}

.session-item small {
  color: var(--muted);
}

.rail-foot {
  margin-top: auto;
  display: grid;
  gap: 8px;
}

.pill {
  display: inline-flex;
  width: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent-deep);
  font-size: 0.78rem;
  font-weight: 600;
}

.hint {
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.5;
}

.stage {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
  animation: rise 0.85s ease 0.08s both;
}

.topbar {
  padding: 28px 36px 12px;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: start;
}

.topbar h1 {
  margin: 0;
  font-size: clamp(1.35rem, 2vw, 1.85rem);
  letter-spacing: -0.03em;
  max-width: 18ch;
  line-height: 1.2;
}

.topbar p {
  margin: 10px 0 0;
  color: var(--ink-soft);
  max-width: 46ch;
}

.diag-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 0.9rem;
  white-space: nowrap;
  padding-top: 6px;
}

.feed {
  padding: 8px 36px 24px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty {
  margin: auto 0;
  padding: 28px 0 48px;
  animation: rise 0.8s ease both;
}

.empty-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 16px;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  max-width: 820px;
}

.prompt {
  text-align: left;
  border-radius: var(--radius);
  padding: 16px 18px;
  line-height: 1.45;
  background: var(--panel);
  box-shadow: var(--shadow);
}

.bubble {
  max-width: 860px;
  padding: 16px 18px;
  border-radius: var(--radius);
  background: var(--panel);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  animation: rise 0.45s ease both;
}

.bubble.user {
  align-self: end;
  background: linear-gradient(180deg, #16352f, #0f766e);
  color: #f4fffc;
  border-color: transparent;
}

.bubble.thinking {
  color: var(--muted);
}

.bubble-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 0.78rem;
  opacity: 0.8;
}

.route {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
}

.bubble.assistant .route {
  background: var(--accent-soft);
  color: var(--accent-deep);
}

.bubble-text {
  white-space: pre-wrap;
  line-height: 1.6;
}

.summary,
.sources,
.table-wrap,
.diag {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.18);
}

.bubble.assistant .summary,
.bubble.assistant .sources,
.bubble.assistant .table-wrap,
.bubble.assistant .diag {
  border-top-color: var(--line);
}

.summary-title {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 8px;
  opacity: 0.8;
}

.summary dl {
  margin: 0;
  display: grid;
  gap: 8px;
}

.summary dl > div {
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 8px;
}

.summary dt {
  color: inherit;
  opacity: 0.7;
}

.summary dd {
  margin: 0;
  font-family: var(--mono);
  font-size: 0.86rem;
}

.table-wrap {
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

th {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}

.source {
  display: grid;
  gap: 4px;
  padding: 8px 0;
  font-size: 0.9rem;
}

.source span {
  color: var(--ink-soft);
}

.diag summary {
  cursor: pointer;
  color: var(--muted);
}

.diag pre {
  margin: 10px 0 0;
  padding: 12px;
  border-radius: 12px;
  background: #10231f;
  color: #d7fff4;
  overflow: auto;
  font-family: var(--mono);
  font-size: 0.8rem;
}

.composer {
  padding: 0 36px 28px;
}

.composer-box {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: end;
  padding: 14px;
  border-radius: 22px;
  background: var(--panel-strong);
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
}

textarea {
  width: 100%;
  border: 0;
  resize: none;
  outline: none;
  background: transparent;
  color: var(--ink);
  line-height: 1.5;
  min-height: 56px;
}

.send {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  background: var(--accent);
  color: white;
  font-weight: 600;
}

.send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.composer-hint,
.error {
  margin-top: 8px;
  font-size: 0.8rem;
}

.composer-hint {
  color: var(--muted);
}

.error {
  color: var(--danger);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse-mark {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.04);
  }
}

@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .rail {
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .session-list {
    max-height: 140px;
  }

  .topbar,
  .feed,
  .composer {
    padding-left: 18px;
    padding-right: 18px;
  }

  .topbar {
    flex-direction: column;
  }

  .topbar h1 {
    max-width: none;
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }
}
</style>
