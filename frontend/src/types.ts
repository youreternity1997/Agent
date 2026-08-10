export interface ReactStep {
  kind: "thought" | "action" | "observation" | "error";
  step?: number;
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
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
