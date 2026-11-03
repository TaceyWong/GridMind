<script setup lang="ts">
import { GPTVis, isVisSyntax, parse } from "@antv/gpt-vis";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    syntax: string;
    theme?: "default" | "light" | "dark" | "academy";
    height?: number;
  }>(),
  {
    theme: "dark",
    height: 280,
  },
);

const container = ref<HTMLElement | null>(null);
const failed = ref(false);
let chart: GPTVis | undefined;

function normalizeSyntax(raw: string): string {
  return raw.replace(/^\uFEFF/, "").trim();
}

function ensureChart() {
  if (!container.value || chart) return;
  const width = Math.max(container.value.clientWidth || 560, 280);
  chart = new GPTVis({
    container: container.value,
    width,
    height: props.height,
    theme: props.theme,
    wrapper: false,
    locale: "zh-CN",
  });
}

async function paint(raw: string) {
  failed.value = false;
  const syntax = normalizeSyntax(raw);
  if (!syntax) return;

  await nextTick();
  ensureChart();
  if (!chart) return;

  if (!isVisSyntax(syntax)) {
    failed.value = true;
    return;
  }

  try {
    chart.render(parse(syntax));
  } catch {
    try {
      chart.render(syntax);
    } catch {
      failed.value = true;
    }
  }
}

onMounted(() => {
  void paint(props.syntax);
});

watch(
  () => props.syntax,
  (syntax) => {
    void paint(syntax);
  },
);

onBeforeUnmount(() => {
  chart?.destroy();
  chart = undefined;
});
</script>

<template>
  <div class="vis-shell" :class="{ failed }">
    <div ref="container" class="vis-canvas" :style="{ height: `${height}px` }" />
    <div v-if="failed" class="vis-fallback">图表未能渲染</div>
  </div>
</template>

<style scoped>
.vis-shell {
  margin: 0.85rem 0 1rem;
  border-radius: 14px;
  background: #161616;
  border: 1px solid var(--line);
  overflow: hidden;
}

.vis-canvas {
  width: 100%;
  min-height: 220px;
}

.vis-shell.failed .vis-canvas {
  display: none;
}

.vis-fallback {
  padding: 20px 16px;
  color: var(--ink-soft);
  font-size: 0.86rem;
}
</style>
