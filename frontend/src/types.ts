export interface ReactStep {
  kind: "thought" | "action" | "observation" | "error";
  step?: number;
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  steps: ReactStep[];
  pending: boolean;
  streamingText?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
}
