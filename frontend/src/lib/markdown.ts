import MarkdownIt from "markdown-it";
import { gptVisMarkdownItPlugin } from "./markdown-it-gpt-vis";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
});

md.use(gptVisMarkdownItPlugin, {
  theme: "dark",
  height: 320,
  wrapper: true,
});

/** 流式缓冲：完整 fence 由插件转成 gpt-vis-host；不完整时仍按普通 md 渲染 */
export function renderMarkdown(source: string): string {
  if (!source.trim()) return "";
  try {
    return md.render(source);
  } catch {
    const escaped = source
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return `<pre class="md-fallback">${escaped}</pre>`;
  }
}

export type ContentSegment =
  | { kind: "md"; text: string }
  | { kind: "vis"; text: string; closed: boolean };

/**
 * 把流式 Markdown 拆成文本段 + GPT-Vis 段，便于未闭合 fence 也能边收边画。
 */
export function splitContentSegments(source: string): ContentSegment[] {
  const parts: ContentSegment[] = [];
  const fenceRe = /```(gpt-vis|gptvis|vis)\b[^\n]*\n([\s\S]*?)(?:```|$)/gi;
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = fenceRe.exec(source)) !== null) {
    if (match.index > last) {
      parts.push({ kind: "md", text: source.slice(last, match.index) });
    }
    const body = match[2] || "";
    const closed = match[0].trimEnd().endsWith("```");
    parts.push({ kind: "vis", text: body.replace(/\n```\s*$/, ""), closed });
    last = match.index + match[0].length;
  }
  if (last < source.length) {
    parts.push({ kind: "md", text: source.slice(last) });
  }
  if (!parts.length && source) {
    parts.push({ kind: "md", text: source });
  }
  return parts;
}
