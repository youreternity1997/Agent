export interface ReactStep {
  kind: "thought" | "action" | "observation" | "error" | "plan";
  step?: number;
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
  /** Only for kind "plan": the confirmed Multi-Planner step list the agent is executing. */
  steps?: string[];
}

/** One editable step in a Multi-Planner draft, before the user confirms it. */
export interface PlanStep {
  id: string;
  content: string;
}

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant";
  content: string;
  steps: ReactStep[];
  pending: boolean;
  streamingText?: string;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ConversationMessagesPage {
  messages: ChatMessage[];
  has_more: boolean;
}

export interface UploadedFileInfo {
  id: number;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  chunk_count: number;
  status: "processing" | "done" | "error";
  error_message: string | null;
  created_at: string;
}

export interface RagChunk {
  id: number;
  title: string;
  content: string;
  content_preview: string;
  motherboard_id: number | null;
  motherboard_name: string | null;
  uploaded_file_id: number | null;
  doc_metadata: Record<string, unknown>;
}

export interface RagChunksPage {
  total: number;
  chunks: RagChunk[];
}

export interface DbTableInfo {
  name: string;
  columns: string[];
  primary_key: string[];
  row_count: number;
}

export interface DbTableRows {
  columns: string[];
  primary_key: string[];
  total: number;
  rows: Record<string, unknown>[];
}
