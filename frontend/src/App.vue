<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import ChatWindow from "./components/ChatWindow.vue";
import ConversationList from "./components/ConversationList.vue";
import FileUpload from "./components/FileUpload.vue";
import HardwareStatus from "./components/HardwareStatus.vue";
import MessageInput from "./components/MessageInput.vue";
import SkillSelector from "./components/SkillSelector.vue";
import ToolSelector from "./components/ToolSelector.vue";
import {
  createConversation,
  deleteConversation as apiDeleteConversation,
  deleteMessage as apiDeleteMessage,
  fetchConversations,
  fetchMessages,
  renameConversation,
} from "./api/client";
import { streamChat } from "./composables/useChat";
import type { ChatMessage, Conversation } from "./types";

const MESSAGES_PAGE_SIZE = 50;

const selectedTools = ref<string[]>([]);
const selectedSkill = ref<string | null>(null);
const isLoading = ref(false);
const isLoadingMessages = ref(false);
const isLoadingOlder = ref(false);
const hasMoreMessages = ref(false);

const conversations = reactive<Conversation[]>([]);
const activeId = ref<number | null>(null);
const activeMessages = reactive<ChatMessage[]>([]);

const activeConversation = () => conversations.find((c) => c.id === activeId.value) ?? null;

async function loadMessagesForActive() {
  if (activeId.value == null) return;
  isLoadingMessages.value = true;
  activeMessages.splice(0, activeMessages.length);
  try {
    const page = await fetchMessages(activeId.value, { limit: MESSAGES_PAGE_SIZE });
    activeMessages.push(...page.messages);
    hasMoreMessages.value = page.has_more;
  } finally {
    isLoadingMessages.value = false;
  }
}

async function handleLoadOlder() {
  if (activeId.value == null || !activeMessages[0]?.id) return;
  isLoadingOlder.value = true;
  try {
    const page = await fetchMessages(activeId.value, {
      beforeId: activeMessages[0].id,
      limit: MESSAGES_PAGE_SIZE,
    });
    activeMessages.unshift(...page.messages);
    hasMoreMessages.value = page.has_more;
  } finally {
    isLoadingOlder.value = false;
  }
}

async function handleNewConversation() {
  const conv = await createConversation();
  conversations.unshift(conv);
  activeId.value = conv.id;
  await loadMessagesForActive();
}

async function handleSelectConversation(id: number) {
  if (id === activeId.value) return;
  activeId.value = id;
  await loadMessagesForActive();
}

async function handleDeleteConversation(id: number) {
  if (!confirm("確定要刪除這個對話嗎？這個動作無法復原。")) return;
  await apiDeleteConversation(id);
  const idx = conversations.findIndex((c) => c.id === id);
  if (idx !== -1) conversations.splice(idx, 1);

  if (activeId.value === id) {
    if (conversations.length > 0) {
      activeId.value = conversations[0].id;
      await loadMessagesForActive();
    } else {
      await handleNewConversation();
    }
  }
}

async function handleDeleteMessage(messageId: number) {
  if (activeId.value == null) return;
  await apiDeleteMessage(activeId.value, messageId);
  const idx = activeMessages.findIndex((m) => m.id === messageId);
  if (idx !== -1) activeMessages.splice(idx, 1);
}

async function handleSend(text: string) {
  const conv = activeConversation();
  if (!conv || activeId.value == null) return;

  if (conv.title === "新對話") {
    conv.title = text.length > 24 ? `${text.slice(0, 24)}...` : text;
    renameConversation(conv.id, conv.title).catch(() => {
      // best-effort - local title already reflects the change either way
    });
  }

  const userMsg = reactive<ChatMessage>({ role: "user", content: text, steps: [], pending: false });
  activeMessages.push(userMsg);

  const assistantMsg = reactive<ChatMessage>({
    role: "assistant",
    content: "",
    steps: [],
    pending: true,
    streamingText: "",
  });
  activeMessages.push(assistantMsg);

  isLoading.value = true;
  try {
    for await (const event of streamChat({
      message: text,
      conversationId: activeId.value,
      tools: selectedTools.value,
      skill: selectedSkill.value,
    })) {
      switch (event.type) {
        case "meta":
          if (event.user_message_id) userMsg.id = event.user_message_id;
          if (event.assistant_message_id) assistantMsg.id = event.assistant_message_id;
          break;
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

onMounted(async () => {
  conversations.push(...(await fetchConversations()));
  if (conversations.length === 0) {
    await handleNewConversation();
  } else {
    activeId.value = conversations[0].id;
    await loadMessagesForActive();
  }
});
</script>

<template>
  <div class="layout">
    <header class="topbar">
      <div class="topbar-text">
        <div class="brand">🦾 GIGABYTE AI Agent</div>
        <div class="subtitle">主機板產品資料助理 · 本地 LLM + ReAct + MCP</div>
      </div>
      <HardwareStatus />
    </header>

    <div class="body">
      <aside class="sidebar">
        <FileUpload />
        <ConversationList
          :conversations="conversations"
          :active-id="activeId"
          @select="handleSelectConversation"
          @new="handleNewConversation"
          @delete="handleDeleteConversation"
        />
        <ToolSelector v-model="selectedTools" />
        <SkillSelector v-model="selectedSkill" />
      </aside>

      <main class="chat-area">
        <ChatWindow
          :messages="activeMessages"
          :loading="isLoadingMessages"
          :has-more="hasMoreMessages"
          :loading-older="isLoadingOlder"
          :key="activeId ?? 'none'"
          @load-older="handleLoadOlder"
          @delete-message="handleDeleteMessage"
        />
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.topbar-text {
  min-width: 0;
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
