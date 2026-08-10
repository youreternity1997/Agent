<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { deleteDocument, fetchDocuments, uploadDocument } from "../api/client";
import type { UploadedFileInfo } from "../types";

const ACCEPTED = ".txt,.md,.pdf,.docx";
const POLL_MS = 3000;

const files = ref<UploadedFileInfo[]>([]);
const isDragging = ref(false);
const uploadError = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

let pollTimer: ReturnType<typeof setInterval> | null = null;

async function refresh() {
  try {
    files.value = await fetchDocuments();
  } catch {
    // transient network hiccup - keep showing the last known list
  }
}

function hasProcessing() {
  return files.value.some((f) => f.status === "processing");
}

async function uploadFiles(fileList: FileList | File[]) {
  uploadError.value = "";
  for (const file of Array.from(fileList)) {
    try {
      const record = await uploadDocument(file);
      files.value.unshift(record);
    } catch (err) {
      uploadError.value = err instanceof Error ? err.message : "上傳失敗";
    }
  }
}

function onDrop(e: DragEvent) {
  isDragging.value = false;
  if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files);
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) uploadFiles(input.files);
  input.value = "";
}

async function handleDelete(id: number) {
  await deleteDocument(id);
  files.value = files.value.filter((f) => f.id !== id);
}

function statusLabel(f: UploadedFileInfo) {
  if (f.status === "processing") return "處理中...";
  if (f.status === "error") return `失敗：${f.error_message ?? ""}`;
  return `完成（${f.chunk_count} 個片段）`;
}

onMounted(async () => {
  await refresh();
  pollTimer = setInterval(() => {
    if (hasProcessing()) refresh();
  }, POLL_MS);
});
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="panel">
    <h3>📁 知識庫檔案</h3>
    <div
      class="dropzone"
      :class="{ dragging: isDragging }"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      拖放或點擊上傳<br />
      <span class="hint">支援 .txt / .md / .pdf / .docx</span>
      <input ref="fileInput" type="file" multiple :accept="ACCEPTED" hidden @change="onPick" />
    </div>

    <div v-if="uploadError" class="upload-error">⚠️ {{ uploadError }}</div>

    <ul v-if="files.length > 0" class="file-list">
      <li v-for="f in files" :key="f.id" :class="f.status">
        <div class="file-main">
          <span class="filename" :title="f.filename">{{ f.filename }}</span>
          <button class="delete-btn" type="button" title="刪除檔案" @click="handleDelete(f.id)">🗑</button>
        </div>
        <div class="file-status">{{ statusLabel(f) }}</div>
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
h3 {
  margin: 0 0 10px;
  font-size: 0.95rem;
}
.dropzone {
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 14px 10px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
  cursor: pointer;
}
.dropzone.dragging {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--bg);
}
.dropzone .hint {
  font-size: 0.7rem;
  opacity: 0.8;
}
.upload-error {
  margin-top: 8px;
  font-size: 0.76rem;
  color: #e5484d;
}
.file-list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 180px;
  overflow-y: auto;
}
.file-list li {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 0.76rem;
}
.file-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.filename {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
}
.file-status {
  color: var(--text-muted);
  margin-top: 2px;
}
.file-list li.error .file-status {
  color: #e5484d;
}
.file-list li.done .file-status {
  color: #30a46c;
}
.delete-btn {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 0.75rem;
}
.delete-btn:hover {
  opacity: 1;
}
</style>
