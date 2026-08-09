<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{ disabled: boolean }>();
const emit = defineEmits<{ send: [text: string] }>();

const text = ref("");

function submit() {
  const value = text.value.trim();
  if (!value || props.disabled) return;
  emit("send", value);
  text.value = "";
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submit();
  }
}
</script>

<template>
  <form class="input-row" @submit.prevent="submit">
    <textarea
      v-model="text"
      :disabled="disabled"
      rows="2"
      placeholder="輸入關於技嘉主機板的問題，例如：B650 AORUS ELITE AX 支援 DDR5 嗎？（Enter 送出，Shift+Enter 換行）"
      @keydown="onKeydown"
    />
    <button type="submit" :disabled="disabled || !text.trim()">
      {{ disabled ? "思考中..." : "送出" }}
    </button>
  </form>
</template>

<style scoped>
.input-row {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-top: 1px solid var(--border);
  background: var(--panel-bg);
}
textarea {
  flex: 1;
  resize: none;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-family: inherit;
  font-size: 0.92rem;
  line-height: 1.4;
}
button {
  padding: 0 20px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  min-width: 84px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
