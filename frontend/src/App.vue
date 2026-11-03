<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import MarkdownMessage from "./components/MarkdownMessage.vue";
import {
  fetchSemanticCatalog,
  postQuery,
  routeLabel,
  streamChat,
  type ChatResponse,
  type QueryResponse,
  type SemanticCatalog,
  type SemanticMetric,
} from "./api";

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
  "查询昨天各变电站的最高温度",
  "统计各区域告警数量",
  "各等级告警占比怎么样？",
  "统计各区域离线设备数",
];

/** 走真实 /api/v1/chat/stream，后端 NL2SQL 会在回答里带 gpt-vis */
const backendChartPrompts = [
  "查询昨天各变电站的最高温度",
  "统计各区域告警数量",
  "各等级告警占比怎么样？",
  "统计严重告警按区域分布",
];

/** 本地 GPT-Vis 样例：不打后端，直接看 chat 里出图 */
const chartDemos: Array<{ label: string; question: string; answer: string }> = [
  {
    label: "饼图 · 告警占比",
    question: "各等级告警占比怎么样？",
    answer: `根据近 24 小时告警汇总，**严重**与**一般**占比较高。

\`\`\`gpt-vis
vis pie
data
  - category 严重
    value 28
  - category 重要
    value 41
  - category 一般
    value 63
  - category 提示
    value 19
innerRadius: 0.62
\`\`\`

结论：一般告警最多，建议优先收敛误报规则。`,
  },
  {
    label: "折线 · 温度趋势",
    question: "主变 A 近 12 小时温度趋势？",
    answer: `主变 A 绕组温度呈午后抬升、夜间回落。

\`\`\`gpt-vis
vis line
data
  - time 08:00
    value 62
  - time 10:00
    value 68
  - time 12:00
    value 74
  - time 14:00
    value 81
  - time 16:00
    value 79
  - time 18:00
    value 73
  - time 20:00
    value 67
axisXTitle: 时间
axisYTitle: 温度 ℃
\`\`\`

14:00 附近触及 **81℃**，仍低于 90℃ 告警阈值。`,
  },
  {
    label: "柱状 · 站点对比",
    question: "对比各变电站昨日最高温度",
    answer: `昨日各站最高温度对比如下。

\`\`\`gpt-vis
vis column
data
  - category 城东站
    value 78
  - category 城西站
    value 84
  - category 滨江站
    value 71
  - category 高新站
    value 88
  - category 空港站
    value 76
axisYTitle: 最高温度 ℃
\`\`\`

**高新站**最高（88℃），建议优先巡检散热与负荷。`,
  },
  {
    label: "多图 · 组合样例",
    question: "给一份告警与在线率简报",
    answer: `## 运行简报

昨日新增告警 **151** 条，设备在线率维持高位。

### 告警结构

\`\`\`gpt-vis
vis bar
data
  - category 过温
    value 52
  - category 通信中断
    value 34
  - category 油位异常
    value 21
  - category 其他
    value 44
\`\`\`

### 在线率

\`\`\`gpt-vis
vis pie
data
  - category 在线
    value 96
  - category 离线
    value 4
innerRadius: 0.7
\`\`\`

若需要下钻到具体设备，直接点名站名或设备编号即可。`,
  },
];

const sessions = ref<Session[]>([]);
const activeId = ref("");
const draft = ref("");
const busy = ref(false);
const showDiag = ref(false);
const error = ref("");
const feedRef = ref<HTMLElement | null>(null);
const semantic = ref<SemanticCatalog | null>(null);
const selectedMetric = ref<string>("");
const requireMetric = ref(true);

const selectedMetricMeta = computed<SemanticMetric | null>(() => {
  const key = selectedMetric.value;
  if (!key || !semantic.value) return null;
  return semantic.value.metrics.find((m) => m.key === key) || null;
});

const active = computed(() => sessions.value.find((s) => s.id === activeId.value) || null);
const hasMessages = computed(() => (active.value?.messages.length || 0) > 0);

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
  if (requireMetric.value && !selectedMetric.value) {
    error.value = "请先选择业务口径（指标）再提问";
    return;
  }

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
    text: "",
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
    let streamFailed = false;

    const patchAssistant = (patch: Partial<Message>) => {
      const idx = session.messages.findIndex((m) => m.id === thinkingId);
      if (idx < 0) return;
      session.messages[idx] = { ...session.messages[idx], ...patch };
    };

    const fail = (msg: string, failRoute?: string | null) => {
      streamFailed = true;
      error.value = msg;
      patchAssistant({
        text: `**出错了**\n\n${msg}`,
        thinking: false,
        route: failRoute || route || "nl2sql",
      });
    };

    const metric = selectedMetric.value || null;
    const dimensions = selectedMetricMeta.value?.default_dimensions || null;

    await streamChat(
      content,
      session.id,
      (event, data) => {
      if (event === "error") {
        fail(String(data.message || data.detail || "问数失败"), data.route as string | null);
        return;
      }
      if (event === "status") {
        const stage = String(data.stage || "");
        if (stage === "routing") {
          patchAssistant({ text: assembled, thinking: true, route });
        } else if (stage === "answer") {
          route = (data.route as string) || route;
          patchAssistant({
            text: assembled,
            route,
            thinking: !assembled,
          });
        }
      } else if (event === "event") {
        patchAssistant({
          text: assembled,
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
        if (summary && typeof summary.error === "string" && summary.error) {
          fail(String(summary.error), route);
          return;
        }
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
      },
      { metric, dimensions },
    );

    if (
      !streamFailed &&
      (!rows || rows.length === 0) &&
      (route === "nl2sql" || metric || /温度|告警|在线|排名|对比|离线/.test(content))
    ) {
      try {
        const q: QueryResponse = await postQuery(content, { metric, dimensions });
        rows = q.rows;
        summary = q.summary;
        sql = q.sql;
        let text = assembled;
        if (q.gpt_vis && !text.includes("```gpt-vis")) {
          text = `${text || "已完成问数查询。"}\n\n${q.gpt_vis}`;
        }
        patchAssistant({
          rows,
          summary,
          sql,
          route: route || "nl2sql",
          text,
          thinking: false,
        });
      } catch (qe) {
        const msg = qe instanceof Error ? qe.message : String(qe);
        // 流式已有正文时保留，并追加错误；否则整段失败提示
        if (assembled.trim()) {
          error.value = msg;
          patchAssistant({
            text: `${assembled}\n\n**补充问数失败：** ${msg}`,
            thinking: false,
            route: route || "nl2sql",
          });
        } else {
          fail(msg, route || "nl2sql");
        }
      }
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    error.value = msg;
    const idx = session.messages.findIndex((m) => m.id === thinkingId);
    if (idx >= 0) {
      session.messages[idx] = {
        ...session.messages[idx],
        text: `**出错了**\n\n${msg}`,
        thinking: false,
        route: "nl2sql",
      };
    }
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

async function showChartDemo(demo: (typeof chartDemos)[number]) {
  if (busy.value) return;
  const session = ensureSession();
  error.value = "";
  if (session.messages.length === 0) {
    session.title = summarizeTitle(demo.question);
  }
  session.messages.push({
    id: uid("m"),
    role: "user",
    text: demo.question,
  });
  session.messages.push({
    id: uid("m"),
    role: "assistant",
    text: demo.answer,
    route: "nl2sql",
  });
  session.updatedAt = Date.now();
  await scrollBottom();
}

onMounted(async () => {
  try {
    semantic.value = await fetchSemanticCatalog();
    if (!selectedMetric.value && semantic.value.metrics.length) {
      selectedMetric.value = semantic.value.metrics[0].key;
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "语义目录加载失败";
  }
  createSession("图表样例");
  await showChartDemo(chartDemos[0]);
});
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <div class="brand">
        <div class="mark" aria-hidden="true"></div>
        <div class="brand-text">
          <div class="brand-name">GridMind</div>
          <div class="brand-sub">Studio</div>
        </div>
      </div>

      <button class="new-btn" type="button" @click="createSession()">新建分析</button>

      <div class="rail-label">最近</div>
      <div class="session-list">
        <button
          v-for="s in sessions"
          :key="s.id"
          type="button"
          class="session-item"
          :class="{ active: s.id === activeId }"
          @click="activeId = s.id"
        >
          {{ s.title }}
        </button>
      </div>

      <div class="rail-foot">
        <div class="rail-label">后端出图</div>
        <button
          v-for="q in backendChartPrompts"
          :key="q"
          type="button"
          class="demo-link"
          :disabled="busy"
          @click="send(q)"
        >
          {{ q }}
        </button>
        <div class="rail-label">本地样例</div>
        <button
          v-for="demo in chartDemos"
          :key="demo.label"
          type="button"
          class="demo-link"
          @click="showChartDemo(demo)"
        >
          {{ demo.label }}
        </button>
      </div>
    </aside>

    <main class="stage">
      <div class="stage-head">
        <header class="topbar">
          <div class="topbar-title">{{ active?.title || "新的分析" }}</div>
          <div class="topbar-actions">
            <label class="metric-pick">
              <span>口径</span>
              <select v-model="selectedMetric">
                <option value="">自动识别</option>
                <option v-for="m in semantic?.metrics || []" :key="m.key" :value="m.key">
                  {{ m.label }}
                </option>
              </select>
            </label>
            <label class="diag-toggle">
              <input v-model="requireMetric" type="checkbox" />
              强制口径
            </label>
            <label class="diag-toggle">
              <input v-model="showDiag" type="checkbox" />
              诊断
            </label>
          </div>
        </header>

        <div v-if="selectedMetricMeta" class="metric-banner">
          <strong>{{ selectedMetricMeta.label }}</strong>
          <span>{{ selectedMetricMeta.definition }}</span>
        </div>
      </div>

      <section ref="feedRef" class="feed" aria-live="polite">
        <div class="feed-inner">
          <div v-if="!hasMessages" class="empty">
            <h2 class="empty-title">想查什么？</h2>
            <p class="empty-lede">检索口径、问数分析或设备状态，直接说即可。</p>
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
              <span class="who">{{ m.role === "user" ? "你" : "GridMind" }}</span>
              <span
                v-if="m.route"
                class="route"
                :class="`route-${m.route}`"
              >{{ routeLabel(m.route) }}</span>
              <span v-if="m.thinking" class="thinking-dots" aria-hidden="true">
                <i /><i /><i />
              </span>
            </div>

            <MarkdownMessage
              v-if="m.role === 'assistant' && (m.text || m.thinking)"
              :content="m.text || (m.thinking ? '_正在组织分析…_' : '')"
              :streaming="busy && m.id === active?.messages[active.messages.length - 1]?.id && !m.thinking"
            />
            <div v-else class="bubble-text">{{ m.text }}</div>

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
        </div>
      </section>

      <footer class="composer">
        <div class="composer-inner">
          <div v-if="error" class="error" role="alert">
            <span class="error-label">错误</span>
            <span class="error-text">{{ error }}</span>
            <button type="button" class="error-dismiss" @click="error = ''">关闭</button>
          </div>
          <div class="composer-box">
            <textarea
              v-model="draft"
              rows="2"
              placeholder="输入问题，Enter 发送"
              :disabled="busy"
              @keydown="onKeydown"
            />
            <button class="send" type="button" :disabled="busy || !draft.trim()" @click="send()">
              {{ busy ? "…" : "发送" }}
            </button>
          </div>
        </div>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.shell {
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
}

.rail {
  padding: 20px 14px 16px;
  border-right: 1px solid var(--line);
  background: var(--rail);
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  overflow: hidden;
}

.brand {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 2px 6px 6px;
}

.mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--ink-bright);
}

.brand-name {
  font-family: var(--display);
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--ink-bright);
  line-height: 1.1;
}

.brand-sub {
  color: var(--muted);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-top: 2px;
}

.new-btn,
.send,
.prompt,
.session-item,
.demo-link {
  border: 0;
  background: transparent;
  color: var(--ink);
  transition: background 0.15s ease, color 0.15s ease;
}

.new-btn {
  border-radius: 10px;
  padding: 10px 12px;
  font-weight: 600;
  font-size: 0.9rem;
  background: var(--bg-elevated);
  color: var(--ink-bright);
  text-align: left;
}

.new-btn:hover,
.prompt:hover {
  background: #1b1b1b;
}

.rail-label {
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 4px 8px 0;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.session-item {
  text-align: left;
  border-radius: 8px;
  padding: 9px 10px;
  color: var(--ink-soft);
  font-size: 0.88rem;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item:hover {
  background: rgba(255, 255, 255, 0.03);
  color: var(--ink);
}

.session-item.active {
  background: var(--accent-soft);
  color: var(--ink-bright);
}

.rail-foot {
  margin-top: auto;
  display: grid;
  gap: 2px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
  max-height: 42%;
  overflow: auto;
  min-height: 0;
}

.demo-link {
  text-align: left;
  border-radius: 8px;
  padding: 7px 10px;
  color: var(--muted);
  font-size: 0.78rem;
}

.demo-link:hover {
  color: var(--ink-soft);
  background: rgba(255, 255, 255, 0.03);
}

.stage {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  height: 100dvh;
  overflow: hidden;
  background: var(--bg);
}

.stage-head {
  flex-shrink: 0;
  z-index: 5;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}

.topbar {
  min-height: 52px;
  padding: 10px 28px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.topbar-title {
  font-size: 0.92rem;
  font-weight: 560;
  color: var(--ink-bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: flex-end;
}

.metric-pick {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 0.78rem;
}

.metric-pick select {
  appearance: none;
  border: 1px solid var(--line);
  background: #141414;
  color: var(--ink-bright);
  border-radius: 8px;
  padding: 6px 10px;
  min-width: 140px;
}

.metric-banner {
  display: flex;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
  padding: 0 28px 10px;
  color: var(--ink-soft);
  font-size: 0.82rem;
}

.metric-banner strong {
  color: var(--ink-bright);
  font-weight: 650;
}

.diag-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 0.78rem;
  white-space: nowrap;
}

.feed {
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 24px 20px 12px;
}

.feed-inner {
  width: min(100%, var(--content));
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.empty {
  padding: 48px 0 24px;
  animation: rise 0.45s ease both;
}

.empty-title {
  margin: 0;
  font-family: var(--display);
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--ink-bright);
}

.empty-lede {
  margin: 10px 0 22px;
  color: var(--ink-soft);
  font-size: 0.95rem;
  line-height: 1.5;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.prompt {
  text-align: left;
  border-radius: 12px;
  padding: 14px 14px;
  line-height: 1.45;
  background: var(--bg-elevated);
  color: var(--ink-soft);
  font-size: 0.9rem;
}

.bubble {
  width: 100%;
  animation: rise 0.35s ease both;
}

.bubble.user {
  align-self: end;
  width: fit-content;
  max-width: 85%;
  margin-left: auto;
  padding: 12px 14px;
  border-radius: 14px 14px 4px 14px;
  background: #171717;
  color: var(--ink-bright);
}

.bubble.assistant {
  padding: 2px 0 4px;
}

.bubble-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 0.78rem;
  color: var(--muted);
}

.who {
  font-weight: 600;
  color: var(--ink-soft);
}

.route {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: 1.2;
  color: #111;
  background: #e8e6e0;
}

.route-nl2sql {
  color: #10231c;
  background: #9fe6c3;
}

.route-rag {
  color: #1a2030;
  background: #b7c7f5;
}

.route-mcp {
  color: #2a1d10;
  background: #efc89a;
}

.route-hybrid {
  color: #241828;
  background: #ddb8e8;
}

.thinking-dots {
  display: inline-flex;
  gap: 4px;
}

.thinking-dots i {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--ink-soft);
  animation: pulse-dot 1.1s ease-in-out infinite;
}

.thinking-dots i:nth-child(2) {
  animation-delay: 0.15s;
}
.thinking-dots i:nth-child(3) {
  animation-delay: 0.3s;
}

.bubble-text {
  white-space: pre-wrap;
  line-height: 1.65;
}

.summary,
.sources,
.table-wrap,
.diag {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.summary-title {
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
  color: var(--muted);
}

.summary dl {
  margin: 0;
  display: grid;
  gap: 6px;
}

.summary dl > div {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
}

.summary dt {
  color: var(--muted);
}

.summary dd {
  margin: 0;
  font-family: var(--mono);
  font-size: 0.84rem;
  color: var(--ink);
}

.table-wrap {
  overflow: auto;
  border-radius: 10px;
  background: #121212;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
}

th,
td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

th {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}

.source {
  display: grid;
  gap: 3px;
  padding: 7px 0;
  font-size: 0.88rem;
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
  border-radius: 10px;
  background: #101010;
  color: var(--ink);
  overflow: auto;
  font-family: var(--mono);
  font-size: 0.78rem;
}

.composer {
  flex-shrink: 0;
  padding: 10px 20px 18px;
  background: var(--bg);
}

.composer-inner {
  width: min(100%, var(--content));
  margin: 0 auto;
}

.composer-box {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: end;
  padding: 10px 10px 10px 14px;
  border-radius: 16px;
  background: #141414;
  border: 1px solid var(--line);
}

textarea {
  width: 100%;
  border: 0;
  resize: none;
  outline: none;
  background: transparent;
  color: var(--ink-bright);
  line-height: 1.5;
  min-height: 48px;
  max-height: 160px;
}

textarea::placeholder {
  color: var(--muted);
}

.send {
  border-radius: 999px;
  padding: 10px 16px;
  background: var(--ink-bright);
  color: #111;
  font-weight: 650;
  font-size: 0.88rem;
}

.send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.error {
  margin-bottom: 10px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(196, 91, 91, 0.35);
  background: rgba(196, 91, 91, 0.1);
  color: #f0b4b4;
  font-size: 0.84rem;
  line-height: 1.45;
}

.error-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #e88a8a;
  padding-top: 2px;
}

.error-text {
  word-break: break-word;
}

.error-dismiss {
  border: 0;
  background: transparent;
  color: #e8c0c0;
  font-size: 0.78rem;
  padding: 0 2px;
}

@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .rail {
    border-right: 0;
    border-bottom: 1px solid var(--line);
    max-height: 148px;
  }

  .rail-foot {
    display: none;
  }

  .session-list {
    max-height: 56px;
  }

  .stage {
    height: auto;
    min-height: 0;
  }

  .topbar,
  .feed,
  .composer {
    padding-left: 14px;
    padding-right: 14px;
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }
}
</style>
