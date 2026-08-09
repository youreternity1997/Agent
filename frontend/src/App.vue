<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import ChatWindow from "./components/ChatWindow.vue";
import ConversationList from "./components/ConversationList.vue";
import MessageInput from "./components/MessageInput.vue";
import SkillSelector from "./components/SkillSelector.vue";
import ToolSelector from "./components/ToolSelector.vue";
import { streamChat } from "./composables/useChat";
import type { ChatMessage, Conversation } from "./types";

const STORAGE_KEY = "gigabyte-agent-conversations";

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "新對話", messages: [] };
}

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Conversation[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {
    // ignore malformed storage, fall through to a fresh conversation
  }
  return [newConversation()];
}

const selectedTools = ref<string[]>([]);
const selectedSkill = ref<string | null>(null);
const isLoading = ref(false);

const conversations = reactive<Conversation[]>(loadConversations());
const activeId = ref(conversations[0].id);

const activeConversation = computed(
  () => conversations.find((c) => c.id === activeId.value) ?? conversations[0],
);

watch(
  conversations,
  () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  },
  { deep: true },
);

function handleNewConversation() {
  const conv = newConversation();
  conversations.unshift(conv);
  activeId.value = conv.id;
}

function handleSelectConversation(id: string) {
  activeId.value = id;
}

async function handleSend(text: string) {
  const conv = activeConversation.value;
  if (conv.title === "新對話") {
    conv.title = text.length > 24 ? `${text.slice(0, 24)}...` : text;
  }

  conv.messages.push({ role: "user", content: text, steps: [], pending: false });

  const assistantMsg = reactive<ChatMessage>({
    role: "assistant",
    content: "",
    steps: [],
    pending: true,
    streamingText: "",
  });
  conv.messages.push(assistantMsg);

  isLoading.value = true;
  try {
    for await (const event of streamChat({
      message: text,
      tools: selectedTools.value,
      skill: selectedSkill.value,
    })) {
      switch (event.type) {
        case "delta":
          assistantMsg.streamingText = (assistantMsg.streamingText ?? "") + event.content;
          break;
        case "thought":
          assistantMsg.streamingText = "";
          assistantMsg.steps.push({ kind: "thought", content: event.content, step: event.step });
          break;
        case "action":
          assistantMsg.streamingText = "";
          assistantMsg.steps.push({
            kind: "action",
            tool: event.tool,
            input: event.input,
            step: event.step,
          });
          break;
        case "observation":
          assistantMsg.steps.push({ kind: "observation", content: event.content, step: event.step });
          break;
        case "final_answer":
          assistantMsg.streamingText = "";
          assistantMsg.content = event.content;
          assistantMsg.pending = false;
          break;
        case "error":
          assistantMsg.streamingText = "";
          assistantMsg.steps.push({ kind: "error", content: event.content });
          assistantMsg.pending = false;
          break;
        case "done":
          break;
      }
    }
  } catch (err) {
    assistantMsg.streamingText = "";
    assistantMsg.steps.push({
      kind: "error",
      content: err instanceof Error ? err.message : String(err),
    });
  } finally {
    if (!assistantMsg.content && !assistantMsg.steps.some((s) => s.kind === "error")) {
      assistantMsg.steps.push({
        kind: "error",
        content: "連線在收到最終回答前結束（可能是模型回應太久被逾時中斷）。",
      });
    }
    assistantMsg.streamingText = "";
    assistantMsg.pending = false;
    isLoading.value = false;
  }
}
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="brand">🦾 GIGABYTE AI Agent</div>
      <div class="subtitle">主機板產品資料助理 · 本地 LLM + ReAct + MCP</div>
    </header>

    <div class="body">
      <aside class="sidebar">
        <ConversationList
          :conversations="conversations"
          :active-id="activeId"
          @select="handleSelectConversation"
          @new="handleNewConversation"
        />
        <ToolSelector v-model="selectedTools" />
        <SkillSelector v-model="selectedSkill" />
      </aside>

      <main class="chat-area">
        <ChatWindow :messages="activeConversation.messages" :key="activeConversation.id" />
        <MessageInput :disabled="isLoading" @send="handleSend" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.topbar {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--panel-bg);
}
.brand {
  font-size: 1.15rem;
  font-weight: 800;
}
.subtitle {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 2px;
}
.body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.sidebar {
  width: 300px;
  flex-shrink: 0;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  border-right: 1px solid var(--border);
}
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
</style>
