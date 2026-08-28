import DOMPurify from "dompurify";
import { marked } from "marked";

// GFM enables pipe-table syntax (the "| col | col |" tables the agent's
// Final Answer tends to produce when asked to compare things); breaks turns
// the model's single newlines into <br> so prose doesn't collapse into one
// run-on paragraph the way plain Markdown would render it.
marked.setOptions({ gfm: true, breaks: true });

/**
 * Render assistant Markdown (tables, lists, bold, code, etc.) to sanitized
 * HTML for v-html. Sanitizing matters here specifically because the agent's
 * answers often quote raw web_search/RAG snippets scraped from third-party
 * pages, which could themselves contain markup.
 */
export function renderMarkdown(text: string): string {
  const rawHtml = marked.parse(text, { async: false }) as string;
  return DOMPurify.sanitize(rawHtml);
}
