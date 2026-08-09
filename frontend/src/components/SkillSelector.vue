<script setup lang="ts">
import { onMounted, ref } from "vue";
import { fetchSkills, type SkillInfo } from "../api/client";

const modelValue = defineModel<string | null>({ required: true });

const skills = ref<SkillInfo[]>([]);
const loadError = ref<string | null>(null);

onMounted(async () => {
  try {
    skills.value = await fetchSkills();
    if (!modelValue.value && skills.value.length > 0) {
      modelValue.value = skills.value[0].id;
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err);
  }
});

const current = () => skills.value.find((s) => s.id === modelValue.value);
</script>

<template>
  <div class="panel">
    <h3>🧠 Skill（角色 / 領域知識）</h3>
    <p v-if="loadError" class="error-text">{{ loadError }}</p>
    <select v-model="modelValue">
      <option v-for="s in skills" :key="s.id" :value="s.id">{{ s.title }}</option>
    </select>
    <p v-if="current()" class="tool-desc">{{ current()!.description }}</p>
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
select {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 0.88rem;
}
.tool-desc {
  margin: 8px 0 0;
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.4;
}
.error-text {
  color: #e5484d;
  font-size: 0.8rem;
}
</style>
