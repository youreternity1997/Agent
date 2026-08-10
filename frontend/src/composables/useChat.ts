export type ChatEvent =
  | { type: "meta"; user_message_id?: number; assistant_message_id?: number }
  | { type: "delta"; content: string; step: number }
  | { type: "thought"; content: string; step: number }
  | { type: "action"; tool: string; input: Record<string, unknown>; step: number }
  | { type: "observation"; content: string; step: number }
  | { type: "final_answer"; content: string; step: number }
  | { type: "error"; content: string }
  | { type: "done" };

interface StreamChatParams {
  message: string;
  conversationId: number;
  tools: string[];
  skill: string | null;
  signal?: AbortSignal;
}

/**
 * POSTs to /api/chat and yields each Server-Sent Event as it arrives.
 * Native EventSource can't send a POST body, so the SSE frames
 * ("data: {...}\n\n") are parsed by hand from the fetch response stream.
 */
export async function* streamChat({
  message,
  conversationId,
  tools,
  skill,
  signal,
}: StreamChatParams): AsyncGenerator<ChatEvent> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId, tools, skill }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`聊天請求失敗 (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      const line = rawEvent.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const jsonStr = line.slice("data:".length).trim();
      if (!jsonStr) continue;

      try {
        yield JSON.parse(jsonStr) as ChatEvent;
      } catch {
        // ignore malformed frame
      }
    }
  }
}
