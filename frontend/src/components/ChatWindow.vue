<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import type { ChatMessage } from "../types";

const props = defineProps<{
  messages: ChatMessage[];
  loading?: boolean;
  hasMore?: boolean;
  loadingOlder?: boolean;
}>();
const emit = defineEmits<{ loadOlder: []; deleteMessage: [id: number] }>();

const scrollRef = ref<HTMLElement | null>(null);

watch(
  () => props.messages.length + props.messages.reduce((n, m) => n + m.steps.length, 0),
  async () => {
    await nextTick();
    scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight, behavior: "smooth" });
  },
);

function handleDelete(msg: ChatMessage) {
  if (!msg.id) return;
  if (!confirm("刪除這則訊息？")) return;
  emit("deleteMessage", msg.id);
}

function stepLabel(kind: string) {
  switch (kind) {
    case "thought":
      return "💭 Thought";
    case "action":
      return "🔧 Action";
    case "observation":
      return "📄 Observation";
    case "error":
      return "⚠️ Error";
    default:
      return kind;
  }
}
</script>

<template>
  <div ref="scrollRef" class="chat-window">
    <div v-if="hasMore" class="load-older">
      <button type="button" :disabled="loadingOlder" @click="emit('loadOlder')">
        {{ loadingOlder ? "載入中..." : "載入更多歷史" }}
      </button>
    </div>

    <div v-if="loading" class="empty-hint">載入對話中...</div>
    <div v-else-if="messages.length === 0" class="empty-hint">
      👋 你好，我是技嘉主機板 AI 助理。左側可勾選要啟用的工具與 Skill，接著在下方輸入問題開始對話。
    </div>

    <div v-for="(msg, i) in messages" :key="msg.id ?? i" class="msg-row" :class="msg.role">
      <div class="bubble">
        <button
          v-if="msg.id"
          class="msg-delete"
          type="button"
          title="刪除這則訊息"
          @click="handleDelete(msg)"
        >
          🗑
        </button>
        <template v-if="msg.role === 'user'">
          {{ msg.content }}
        </template>

        <template v-else>
          <details v-if="msg.steps.length > 0" class="trace" open>
            <summary>推理過程（{{ msg.steps.length }} 步）</summary>
            <div v-for="(step, si) in msg.steps" :key="si" class="step" :class="step.kind">
              <div class="step-label">{{ stepLabel(step.kind) }}<span v-if="step.step"> · 第 {{ step.step }} 步</span></div>
              <div v-if="step.kind === 'action'" class="step-body">
                呼叫工具 <code>{{ step.tool }}</code>
                <pre>{{ JSON.stringify(step.input, null, 2) }}</pre>
              </div>
              <div v-else class="step-body">{{ step.content }}</div>
            </div>
          </details>

          <div class="final-answer" v-if="msg.content">{{ msg.content }}</div>
          <div v-else-if="msg.streamingText" class="streaming-text">{{ msg.streamingText }}<span class="cursor"></span></div>
          <div v-else-if="msg.pending" class="pending">思考中...</div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.empty-hint {
  margin: auto;
  max-width: 420px;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.92rem;
  line-height: 1.6;
}
.msg-row {
  display: flex;
}
.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}
.load-older {
  display: flex;
  justify-content: center;
}
.load-older button {
  border: 1px solid var(--border);
  background: var(--panel-bg);
  color: var(--text-muted);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 0.78rem;
  cursor: pointer;
}
.load-older button:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.load-older button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.bubble {
  position: relative;
  max-width: 720px;
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 0.92rem;
  line-height: 1.6;
  white-space: pre-wrap;
}
.msg-delete {
  position: absolute;
  top: 4px;
  right: 6px;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 4px;
  border-radius: 4px;
  transition: opacity 0.15s;
}
.bubble:hover .msg-delete {
  opacity: 0.6;
}
.msg-delete:hover {
  opacity: 1 !important;
  background: rgba(0, 0, 0, 0.15);
}
.msg-row.user .bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 2px;
}
.msg-row.assistant .bubble {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-bottom-left-radius: 2px;
  width: 100%;
}
.trace {
  margin-bottom: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--bg);
}
.trace summary {
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--text-muted);
  font-weight: 600;
}
.step {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 0.82rem;
}
.step:first-of-type {
  border-top: none;
}
.step-label {
  font-weight: 700;
  margin-bottom: 3px;
}
.step.error .step-label {
  color: #e5484d;
}
.step-body {
  color: var(--text-muted);
  white-space: pre-wrap;
}
.step-body pre {
  margin: 4px 0 0;
  background: var(--panel-bg);
  padding: 6px 8px;
  border-radius: 6px;
  overflow-x: auto;
}
.final-answer {
  white-space: pre-wrap;
}
.pending {
  color: var(--text-muted);
  font-style: italic;
}
.streaming-text {
  white-space: pre-wrap;
  color: var(--text-muted);
}
.cursor {
  display: inline-block;
  width: 0.5em;
  height: 1em;
  margin-left: 2px;
  background: var(--text-muted);
  vertical-align: text-bottom;
  animation: blink 1s step-start infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
