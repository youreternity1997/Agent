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
