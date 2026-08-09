<script setup lang="ts">
import type { Conversation } from "../types";

defineProps<{ conversations: Conversation[]; activeId: string }>();
const emit = defineEmits<{ select: [id: string]; new: [] }>();
</script>

<template>
  <div class="panel">
    <div class="header">
      <h3>💬 對話紀錄</h3>
      <button class="new-btn" type="button" @click="emit('new')">+ 新對話</button>
    </div>
    <ul class="conv-list">
      <li
        v-for="conv in conversations"
        :key="conv.id"
        :class="{ active: conv.id === activeId }"
        @click="emit('select', conv.id)"
      >
        {{ conv.title }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.panel {
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
h3 {
  margin: 0;
  font-size: 0.95rem;
}
.new-btn {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
}
.new-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.conv-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
}
.conv-list li {
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-muted);
}
.conv-list li:hover {
  background: var(--bg);
}
.conv-list li.active {
  background: var(--accent);
  color: #fff;
  font-weight: 600;
}
</style>
