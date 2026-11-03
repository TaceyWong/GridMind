/**
 * 本地实现（npm 上的 markdown-it-gpt-vis / @gpt-vis-plugin 未打包 dist）。
 * API 对齐官方：拦截 GPT-Vis fence → 输出占位节点，由 Vue 挂载 GPTVis。
 */
import type MarkdownIt from "markdown-it";

export type GptVisPluginOptions = {
  theme?: "default" | "light" | "dark" | "academy";
  height?: number;
  width?: number;
  wrapper?: boolean;
};

const VIS_LANG = /^(gpt-vis|gptvis|vis)$/i;

export function gptVisMarkdownItPlugin(
  md: MarkdownIt,
  options: GptVisPluginOptions = {},
): void {
  const theme = options.theme || "dark";
  const height = options.height ?? 320;
  const width = options.width;
  const wrapper = options.wrapper ? "1" : "0";

  const defaultFence =
    md.renderer.rules.fence ||
    ((tokens, idx, opts, _env, self) => self.renderToken(tokens, idx, opts));

  md.renderer.rules.fence = (tokens, idx, opts, env, self) => {
    const token = tokens[idx];
    const lang = (token.info || "").trim().split(/\s+/)[0] || "";
    if (!VIS_LANG.test(lang)) {
      return defaultFence(tokens, idx, opts, env, self);
    }
    const syntax = token.content || "";
    const encoded = encodeURIComponent(syntax);
    const w = width ? ` data-width="${width}"` : "";
    return (
      `<div class="gpt-vis-host" data-gpt-vis="${encoded}" data-theme="${theme}"` +
      ` data-height="${height}" data-wrapper="${wrapper}"${w}></div>\n`
    );
  };
}

export default gptVisMarkdownItPlugin;
