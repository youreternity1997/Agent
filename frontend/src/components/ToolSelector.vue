<script setup lang="ts">
import { onMounted, ref } from "vue";
import { fetchTools, type ToolInfo } from "../api/client";

const modelValue = defineModel<string[]>({ required: true });

const tools = ref<ToolInfo[]>([]);
const loadError = ref<string | null>(null);

onMounted(async () => {
  try {
    tools.value = await fetchTools();
    // Default: enable every tool the MCP server exposes.
    if (modelValue.value.length === 0) {
      modelValue.value = tools.value.map((t) => t.id);
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err);
  }
});

function toggle(id: string, checked: boolean) {
  if (checked) {
    if (!modelValue.value.includes(id)) modelValue.value = [...modelValue.value, id];
  } else {
    modelValue.value = modelValue.value.filter((t) => t !== id);
  }
}
</script>

<template>
  <div class="panel">
    <h3>🔧 MCP 工具</h3>
    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <ul class="tool-list">
      <li v-for="tool in tools" :key="tool.id">
        <label>
          <input
            type="checkbox"
            :checked="modelValue.includes(tool.id)"
            @change="toggle(tool.id, ($event.target as HTMLInputElement).checked)"
          />
          <span class="tool-name">{{ tool.name }}</span>
        </label>
        <p class="tool-desc">{{ tool.description }}</p>
      </li>
      <li v-if="!loadError && tools.length === 0" class="muted">載入工具清單中...</li>
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
.tool-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.tool-list li {
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border);
}
.tool-list li:last-child {
  border-bottom: none;
}
label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
}
.tool-desc {
  margin: 4px 0 0 24px;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.4;
}
.error-text {
  color: #e5484d;
  font-size: 0.8rem;
}
.muted {
  color: var(--text-muted);
  font-size: 0.8rem;
}
</style>
