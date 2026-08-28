<script setup lang="ts">
import { onMounted, ref } from "vue";
import { clearRagDatabase, deleteRagChunk, fetchRagChunks } from "../api/client";
import type { RagChunk } from "../types";

const emit = defineEmits<{ close: [] }>();

const PAGE_SIZE = 20;

const chunks = ref<RagChunk[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const error = ref("");
const expandedId = ref<number | null>(null);

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const page = await fetchRagChunks({ limit: PAGE_SIZE, offset: offset.value });
    chunks.value = page.chunks;
    total.value = page.total;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "載入失敗";
  } finally {
    loading.value = false;
  }
}

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id;
}

async function handleDeleteChunk(id: number) {
  if (!confirm("確定要刪除這筆 RAG 資料嗎？這個動作無法復原。")) return;
  await deleteRagChunk(id);
  chunks.value = chunks.value.filter((c) => c.id !== id);
  total.value -= 1;
  if (chunks.value.length === 0 && offset.value > 0) {
    offset.value = Math.max(0, offset.value - PAGE_SIZE);
  }
  await load();
}

async function handleClearAll() {
  if (!confirm("確定要清空整個 RAG 資料庫嗎？所有已上傳檔案與向量化片段都會被永久刪除，這個動作無法復原。")) return;
  await clearRagDatabase();
  offset.value = 0;
  await load();
}

function prevPage() {
  if (offset.value === 0) return;
  offset.value = Math.max(0, offset.value - PAGE_SIZE);
  load();
}

function nextPage() {
  if (offset.value + PAGE_SIZE >= total.value) return;
  offset.value += PAGE_SIZE;
  load();
}

onMounted(load);
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal">
      <header>
        <h3>📚 RAG 資料庫（共 {{ total }} 筆）</h3>
        <button type="button" class="close-btn" @click="emit('close')">✕</button>
      </header>

      <div class="toolbar">
        <button type="button" class="danger-btn" @click="handleClearAll">🗑 清空整個 RAG 資料庫</button>
      </div>

      <div v-if="error" class="error">⚠️ {{ error }}</div>
      <div v-if="loading" class="hint">載入中...</div>

      <ul v-if="!loading && chunks.length > 0" class="chunk-list">
        <li v-for="c in chunks" :key="c.id">
          <div class="chunk-main" @click="toggleExpand(c.id)">
            <div class="chunk-info">
              <span class="chunk-title">{{ c.title }}</span>
              <span class="chunk-meta">
                #{{ c.id }}
                <template v-if="c.motherboard_name"> · {{ c.motherboard_name }}</template>
                <template v-if="c.uploaded_file_id"> · 檔案 #{{ c.uploaded_file_id }}</template>
              </span>
            </div>
            <button class="delete-btn" type="button" title="刪除此筆資料" @click.stop="handleDeleteChunk(c.id)">🗑</button>
          </div>
          <p class="chunk-content" :class="{ expanded: expandedId === c.id }">
            {{ expandedId === c.id ? c.content : c.content_preview }}
          </p>
        </li>
      </ul>
      <div v-else-if="!loading" class="hint">目前沒有任何 RAG 資料。</div>

      <footer v-if="total > PAGE_SIZE">
        <button type="button" :disabled="offset === 0" @click="prevPage">← 上一頁</button>
        <span>{{ offset + 1 }} - {{ Math.min(offset + PAGE_SIZE, total) }} / {{ total }}</span>
        <button type="button" :disabled="offset + PAGE_SIZE >= total" @click="nextPage">下一頁 →</button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  width: min(620px, 92vw);
  max-height: 82vh;
  display: flex;
  flex-direction: column;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.25);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
header h3 {
  margin: 0;
  font-size: 1rem;
}
.close-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.9rem;
}
.close-btn:hover {
  color: var(--text);
}
.toolbar {
  margin: 10px 0;
}
.danger-btn {
  border: 1px solid #e5484d;
  color: #e5484d;
  background: transparent;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.8rem;
  cursor: pointer;
}
.danger-btn:hover {
  background: rgba(229, 72, 77, 0.1);
}
.error {
  color: #e5484d;
  font-size: 0.8rem;
  margin-bottom: 8px;
}
.hint {
  color: var(--text-muted);
  font-size: 0.82rem;
  padding: 12px 0;
}
.chunk-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chunk-list li {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
}
.chunk-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  cursor: pointer;
}
.chunk-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.chunk-title {
  font-weight: 600;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chunk-meta {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.delete-btn {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 0.8rem;
}
.delete-btn:hover {
  opacity: 1;
}
.chunk-content {
  margin: 6px 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
  white-space: pre-wrap;
}
.chunk-content:not(.expanded) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
footer {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 0.78rem;
  color: var(--text-muted);
}
footer button {
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  color: var(--text);
}
footer button:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
