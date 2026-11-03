<script setup lang="ts">
import { computed } from "vue";
import { renderMarkdown, splitContentSegments } from "../lib/markdown";
import GptVisBlock from "./GptVisBlock.vue";

const props = defineProps<{
  content: string;
  streaming?: boolean;
}>();

const segments = computed(() => splitContentSegments(props.content));
</script>

<template>
  <div class="md-body" :class="{ streaming: streaming }">
    <template v-for="(seg, i) in segments" :key="i">
      <div v-if="seg.kind === 'md'" class="md-chunk" v-html="renderMarkdown(seg.text)" />
      <GptVisBlock v-else theme="light" :height="280" :syntax="seg.text" />
    </template>
  </div>
</template>

<style scoped>
.md-body {
  line-height: 1.7;
  font-size: 0.98rem;
  color: var(--ink);
  word-break: break-word;
}

.md-chunk :deep(p) {
  margin: 0 0 0.85em;
}

.md-chunk :deep(p:last-child) {
  margin-bottom: 0;
}

.md-chunk :deep(h1),
.md-chunk :deep(h2),
.md-chunk :deep(h3) {
  margin: 1.1em 0 0.45em;
  letter-spacing: -0.03em;
  font-weight: 600;
  line-height: 1.25;
  color: var(--ink-bright);
}

.md-chunk :deep(h1) {
  font-size: 1.35rem;
}
.md-chunk :deep(h2) {
  font-size: 1.18rem;
}
.md-chunk :deep(h3) {
  font-size: 1.05rem;
}

.md-chunk :deep(ul),
.md-chunk :deep(ol) {
  margin: 0.4em 0 0.9em;
  padding-left: 1.25em;
}

.md-chunk :deep(li) {
  margin: 0.25em 0;
}

.md-chunk :deep(a) {
  color: var(--ink-bright);
  text-decoration: none;
  border-bottom: 1px solid var(--line-strong);
}

.md-chunk :deep(code) {
  font-family: var(--mono);
  font-size: 0.86em;
  padding: 0.12em 0.4em;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--ink-bright);
}

.md-chunk :deep(pre) {
  margin: 0.85em 0;
  padding: 14px 16px;
  border-radius: 14px;
  overflow: auto;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--line);
  font-family: var(--mono);
  font-size: 0.82rem;
  line-height: 1.55;
}

.md-chunk :deep(pre code) {
  padding: 0;
  background: transparent;
  color: var(--ink);
}

.md-chunk :deep(blockquote) {
  margin: 0.8em 0;
  padding: 0.2em 0 0.2em 14px;
  border-left: 2px solid var(--line-strong);
  color: var(--ink-soft);
}

.md-chunk :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.9em 0;
  font-size: 0.9rem;
}

.md-chunk :deep(th),
.md-chunk :deep(td) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}

.md-chunk :deep(.gpt-vis-host) {
  display: none;
}

.md-body.streaming .md-chunk:last-child :deep(p:last-child)::after {
  content: "";
  display: inline-block;
  width: 7px;
  height: 1.05em;
  margin-left: 3px;
  vertical-align: text-bottom;
  background: var(--ink-soft);
  animation: caret 1s steps(1) infinite;
}

@keyframes caret {
  50% {
    opacity: 0;
  }
}
</style>
