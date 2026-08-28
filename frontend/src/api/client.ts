import type { Conversation, ConversationMessagesPage, UploadedFileInfo } from "../types";

export interface ToolInfo {
  id: string;
  name: string;
  description: string;
}

export interface SkillInfo {
  id: string;
  title: string;
  description: string;
}

export interface PlanResult {
  needs_plan: boolean;
  steps: string[];
}

export interface PlanRequestParams {
  message: string;
  conversationId: number;
  tools: string[];
  skill: string | null;
}

/** Multi-Planner preview: ask the backend whether this message needs to be
 * broken into steps, and if so, get a first draft to show for editing. */
export function fetchPlan(params: PlanRequestParams): Promise<PlanResult> {
  return fetch("/api/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: params.message,
      conversation_id: params.conversationId,
      tools: params.tools,
      skill: params.skill,
    }),
  }).then((res) => unwrap(res, "產生執行計畫失敗"));
}

export async function fetchTools(): Promise<ToolInfo[]> {
  const res = await fetch("/api/tools");
  if (!res.ok) throw new Error(`載入工具清單失敗 (${res.status})`);
  return res.json();
}

export async function fetchSkills(): Promise<SkillInfo[]> {
  const res = await fetch("/api/skills");
  if (!res.ok) throw new Error(`載入 Skill 清單失敗 (${res.status})`);
  return res.json();
}

async function unwrap<T>(res: Response, errorLabel: string): Promise<T> {
  if (!res.ok) throw new Error(`${errorLabel} (${res.status})`);
  return res.json();
}

export function fetchConversations(): Promise<Conversation[]> {
  return fetch("/api/conversations").then((res) => unwrap(res, "載入對話清單失敗"));
}

export function createConversation(title = "新對話"): Promise<Conversation> {
  return fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  }).then((res) => unwrap(res, "建立對話失敗"));
}

export function renameConversation(id: number, title: string): Promise<Conversation> {
  return fetch(`/api/conversations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  }).then((res) => unwrap(res, "重新命名對話失敗"));
}

export async function deleteConversation(id: number): Promise<void> {
  const res = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`刪除對話失敗 (${res.status})`);
}

export function fetchMessages(
  conversationId: number,
  opts: { beforeId?: number; limit?: number } = {},
): Promise<ConversationMessagesPage> {
  const params = new URLSearchParams();
  if (opts.beforeId) params.set("before_id", String(opts.beforeId));
  if (opts.limit) params.set("limit", String(opts.limit));
  const qs = params.toString();
  return fetch(`/api/conversations/${conversationId}/messages${qs ? `?${qs}` : ""}`).then((res) =>
    unwrap<ConversationMessagesPage>(res, "載入訊息失敗"),
  );
}

export async function deleteMessage(conversationId: number, messageId: number): Promise<void> {
  const res = await fetch(`/api/conversations/${conversationId}/messages/${messageId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`刪除訊息失敗 (${res.status})`);
}

export function fetchDocuments(): Promise<UploadedFileInfo[]> {
  return fetch("/api/documents").then((res) => unwrap(res, "載入檔案清單失敗"));
}

export function uploadDocument(file: File): Promise<UploadedFileInfo> {
  const form = new FormData();
  form.append("file", file);
  return fetch("/api/documents/upload", { method: "POST", body: form }).then((res) =>
    unwrap(res, `上傳「${file.name}」失敗`),
  );
}

export async function deleteDocument(id: number): Promise<void> {
  const res = await fetch(`/api/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`刪除檔案失敗 (${res.status})`);
}

export async function transcribeAudio(blob: Blob): Promise<string> {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  const res = await fetch("/api/transcribe", { method: "POST", body: form });
  const data = await unwrap<{ text: string }>(res, "語音轉文字失敗");
  return data.text;
}
