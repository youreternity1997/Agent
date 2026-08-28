<script setup lang="ts">
import type { PlanStep } from "../types";

const props = defineProps<{ steps: PlanStep[]; goal: string }>();
const emit = defineEmits<{
  "update:steps": [steps: PlanStep[]];
  confirm: [];
  cancel: [];
}>();

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `step-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function updateContent(id: string, value: string) {
  emit(
    "update:steps",
    props.steps.map((s) => (s.id === id ? { ...s, content: value } : s)),
  );
}

function removeStep(id: string) {
  emit(
    "update:steps",
    props.steps.filter((s) => s.id !== id),
  );
}

function addStep() {
  emit("update:steps", [...props.steps, { id: newId(), content: "" }]);
}

function move(id: string, dir: -1 | 1) {
  const idx = props.steps.findIndex((s) => s.id === id);
  const target = idx + dir;
  if (idx === -1 || target < 0 || target >= props.steps.length) return;
  const next = [...props.steps];
  [next[idx], next[target]] = [next[target], next[idx]];
  emit("update:steps", next);
}

function usableStepCount() {
  return props.steps.filter((s) => s.content.trim().length > 0).length;
}
</script>

<template>
  <div class="plan-panel">
    <div class="plan-header">
      <h3>🗂️ 執行計畫草稿</h3>
      <p class="goal">目標：{{ goal }}</p>
      <p class="hint">Agent 已將目標拆解成以下步驟，你可以刪除、修改或新增步驟，確認後才會開始執行。</p>
    </div>

    <ol class="plan-steps">
      <li v-for="(step, i) in steps" :key="step.id">
        <span class="step-index">{{ i + 1 }}</span>
        <textarea
          :value="step.content"
          rows="1"
          placeholder="輸入這個步驟要做的事..."
          @input="updateContent(step.id, ($event.target as HTMLTextAreaElement).value)"
        />
        <div class="step-actions">
          <button type="button" title="上移" :disabled="i === 0" @click="move(step.id, -1)">↑</button>
          <button type="button" title="下移" :disabled="i === steps.length - 1" @click="move(step.id, 1)">
            ↓
          </button>
          <button type="button" class="remove-btn" title="刪除步驟" @click="removeStep(step.id)">🗑</button>
        </div>
      </li>
      <li v-if="steps.length === 0" class="empty">目前沒有任何步驟，請新增，或取消計畫改用一般回答。</li>
    </ol>

    <button type="button" class="add-step-btn" @click="addStep">+ 新增步驟</button>

    <div class="plan-footer">
      <button type="button" class="cancel-btn" @click="emit('cancel')">取消計畫，直接回答</button>
      <button type="button" class="confirm-btn" :disabled="usableStepCount() === 0" @click="emit('confirm')">
        確認計畫並執行（{{ usableStepCount() }} 步）
      </button>
    </div>
  </div>
</template>

<style scoped>
.plan-panel {
  margin: 0 20px 12px;
  padding: 14px 16px;
  border: 1px solid var(--accent);
  border-radius: 10px;
  background: var(--panel-bg);
}
.plan-header {
  margin-bottom: 10px;
}
.plan-header h3 {
  margin: 0 0 4px;
  font-size: 0.95rem;
}
.goal {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
}
.hint {
  margin: 4px 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.4;
}
.plan-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-steps li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.step-index {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
}
.plan-steps textarea {
  flex: 1;
  resize: vertical;
  min-height: 34px;
  padding: 7px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-family: inherit;
  font-size: 0.86rem;
  line-height: 1.4;
}
.step-actions {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  margin-top: 2px;
}
.step-actions button {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  border-radius: 6px;
  width: 26px;
  height: 26px;
  font-size: 0.8rem;
  cursor: pointer;
  padding: 0;
}
.step-actions button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.step-actions .remove-btn:hover:not(:disabled) {
  border-color: #e5484d;
  color: #e5484d;
}
.empty {
  font-size: 0.82rem;
  color: var(--text-muted);
}
.add-step-btn {
  margin-top: 10px;
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--text-muted);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 0.8rem;
  cursor: pointer;
  width: 100%;
}
.add-step-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.plan-footer {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.plan-footer button {
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}
.cancel-btn {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
}
.cancel-btn:hover {
  border-color: var(--text-muted);
}
.confirm-btn {
  border: none;
  background: var(--accent);
  color: #fff;
}
.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
