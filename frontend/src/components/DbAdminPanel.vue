<script setup lang="ts">
import { onMounted, ref } from "vue";
import { deleteTableRow, fetchDbTables, fetchTableRows } from "../api/client";
import type { DbTableInfo } from "../types";

const emit = defineEmits<{ close: [] }>();

const PAGE_SIZE = 25;

const tables = ref<DbTableInfo[]>([]);
const activeTable = ref<string | null>(null);
const columns = ref<string[]>([]);
const primaryKey = ref<string[]>([]);
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const error = ref("");

async function loadTables() {
  error.value = "";
  try {
    tables.value = await fetchDbTables();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "載入資料表清單失敗";
  }
}

async function selectTable(name: string) {
  activeTable.value = name;
  offset.value = 0;
  await loadRows();
}

async function loadRows() {
  if (!activeTable.value) return;
  loading.value = true;
  error.value = "";
  try {
    const data = await fetchTableRows(activeTable.value, { limit: PAGE_SIZE, offset: offset.value });
    columns.value = data.columns;
    primaryKey.value = data.primary_key;
    rows.value = data.rows;
    total.value = data.total;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "載入資料表內容失敗";
  } finally {
    loading.value = false;
  }
}

function rowPkValue(row: Record<string, unknown>): string | number | null {
  if (primaryKey.value.length !== 1) return null;
  return row[primaryKey.value[0]] as string | number;
}

async function handleDeleteRow(row: Record<string, unknown>) {
  const pkValue = rowPkValue(row);
  if (pkValue == null || !activeTable.value) return;
  if (!confirm(`確定要刪除資料表「${activeTable.value}」中主鍵為 ${pkValue} 的這筆資料嗎？這個動作無法復原。`)) return;
  try {
    await deleteTableRow(activeTable.value, pkValue);
    await loadRows();
    await loadTables();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "刪除失敗";
  }
}

function cellText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function prevPage() {
  if (offset.value === 0) return;
  offset.value = Math.max(0, offset.value - PAGE_SIZE);
  loadRows();
}

function nextPage() {
  if (offset.value + PAGE_SIZE >= total.value) return;
  offset.value += PAGE_SIZE;
  loadRows();
}

onMounted(loadTables);
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal">
      <header>
        <h3>🗄 資料庫管理</h3>
        <button type="button" class="close-btn" @click="emit('close')">✕</button>
      </header>

      <div v-if="error" class="error">⚠️ {{ error }}</div>

      <div class="body">
        <aside class="table-list">
          <button
            v-for="t in tables"
            :key="t.name"
            type="button"
            class="table-item"
            :class="{ active: activeTable === t.name }"
            @click="selectTable(t.name)"
          >
            <span class="table-name">{{ t.name }}</span>
            <span class="table-count">{{ t.row_count }}</span>
          </button>
        </aside>

        <section class="table-view">
          <div v-if="!activeTable" class="hint">請從左側選擇一個資料表</div>
          <div v-else-if="loading" class="hint">載入中...</div>
          <template v-else>
            <div class="scroll-wrap">
              <table>
                <thead>
                  <tr>
                    <th v-for="col in columns" :key="col">{{ col }}</th>
                    <th class="op-col"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in rows" :key="i">
                    <td v-for="col in columns" :key="col" :title="cellText(row[col])">
                      {{ cellText(row[col]) }}
                    </td>
                    <td class="op-col">
                      <button
                        v-if="rowPkValue(row) != null"
                        type="button"
                        class="delete-btn"
                        title="刪除此筆資料"
                        @click="handleDeleteRow(row)"
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                  <tr v-if="rows.length === 0">
                    <td :colspan="columns.length + 1" class="hint">此資料表沒有資料</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <footer v-if="total > PAGE_SIZE">
              <button type="button" :disabled="offset === 0" @click="prevPage">← 上一頁</button>
              <span>{{ offset + 1 }} - {{ Math.min(offset + PAGE_SIZE, total) }} / {{ total }}</span>
              <button type="button" :disabled="offset + PAGE_SIZE >= total" @click="nextPage">下一頁 →</button>
            </footer>
          </template>
        </section>
      </div>
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
  width: min(900px, 94vw);
  height: min(600px, 88vh);
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
  flex-shrink: 0;
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
.error {
  color: #e5484d;
  font-size: 0.8rem;
  margin: 8px 0 0;
  flex-shrink: 0;
}
.body {
  flex: 1;
  display: flex;
  gap: 14px;
  margin-top: 12px;
  min-height: 0;
}
.table-list {
  width: 170px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}
.table-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 0.78rem;
  cursor: pointer;
  color: var(--text);
  text-align: left;
}
.table-item.active {
  border-color: var(--accent);
  color: var(--accent);
}
.table-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.table-count {
  flex-shrink: 0;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.table-item.active .table-count {
  color: var(--accent);
}
.table-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.hint {
  color: var(--text-muted);
  font-size: 0.82rem;
  padding: 12px 0;
}
.scroll-wrap {
  flex: 1;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.76rem;
}
th,
td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  white-space: nowrap;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
}
th {
  position: sticky;
  top: 0;
  background: var(--panel-bg);
  color: var(--text-muted);
  font-weight: 600;
}
.op-col {
  width: 32px;
  max-width: 32px;
}
.delete-btn {
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 0.78rem;
}
.delete-btn:hover {
  opacity: 1;
}
footer {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 0.78rem;
  color: var(--text-muted);
  flex-shrink: 0;
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
