<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useSystemStatus } from "../composables/useSystemStatus";

const { status, connected } = useSystemStatus();

const expanded = ref(false);
const rootRef = ref<HTMLElement | null>(null);

function toggle() {
  expanded.value = !expanded.value;
}

function onDocumentClick(e: MouseEvent) {
  if (expanded.value && rootRef.value && !rootRef.value.contains(e.target as Node)) {
    expanded.value = false;
  }
}

onMounted(() => document.addEventListener("click", onDocumentClick));
onBeforeUnmount(() => document.removeEventListener("click", onDocumentClick));

function formatExpiry(iso: string | null): string {
  if (!iso) return "--";
  const diffMs = new Date(iso).getTime() - Date.now();
  if (diffMs <= 0) return "即將卸載";
  const mins = Math.round(diffMs / 60000);
  return mins < 60 ? `${mins} 分鐘後卸載` : `${Math.round(mins / 60)} 小時後卸載`;
}
</script>

<template>
  <div class="hw-root" ref="rootRef">
    <button type="button" class="hw-strip" @click="toggle">
      <span class="dot" :class="{ on: connected }" :title="connected ? '已連線' : '未連線'"></span>

      <template v-if="status">
        <div class="chip" title="CPU 使用率">
          <span class="chip-label">CPU</span>
          <span class="chip-value">{{ status.cpu.percent.toFixed(0) }}%</span>
        </div>

        <div class="chip" title="記憶體使用量">
          <span class="chip-label">DRAM</span>
          <span class="chip-value">{{ status.memory.used_gb.toFixed(1) }}/{{ status.memory.total_gb.toFixed(0) }}GB</span>
        </div>

        <div class="chip" v-if="status.gpu.available" title="GPU 使用率">
          <span class="chip-label">GPU</span>
          <span class="chip-value">{{ status.gpu.util_percent }}%</span>
        </div>
        <div class="chip muted" v-else title="未偵測到 NVIDIA GPU">
          <span class="chip-label">GPU</span>
          <span class="chip-value">--</span>
        </div>

        <div class="chip model" :title="status.ollama.configured_model">
          <span class="chip-label">模型</span>
          <span class="chip-value">
            <span v-if="!status.ollama.reachable" class="warn">無法連線</span>
            <span v-else-if="status.ollama.loaded_models.length === 0">閒置中</span>
            <span v-else>推論中</span>
          </span>
        </div>

        <span class="caret" :class="{ open: expanded }">▾</span>
      </template>

      <span v-else class="connecting">硬體資訊連線中...</span>
    </button>

    <div v-if="expanded && status" class="hw-panel" @click.stop>
      <section class="hw-section">
        <h4>CPU</h4>
        <div class="kv-grid">
          <span>使用率</span><span>{{ status.cpu.percent.toFixed(1) }}%</span>
          <span>核心數</span>
          <span>{{ status.cpu.cores_physical ?? "?" }} 實體 / {{ status.cpu.cores_logical }} 邏輯</span>
          <span>頻率</span>
          <span>
            {{ status.cpu.freq_current_mhz ? `${(status.cpu.freq_current_mhz / 1000).toFixed(2)} GHz` : "--" }}
            <template v-if="status.cpu.freq_max_mhz"> (上限 {{ (status.cpu.freq_max_mhz / 1000).toFixed(2) }} GHz)</template>
          </span>
          <span>負載平均 (1m)</span><span>{{ status.cpu.load_avg_1m ?? "--" }}</span>
        </div>
        <div class="core-bars" v-if="status.cpu.per_core.length">
          <div
            v-for="(pct, i) in status.cpu.per_core"
            :key="i"
            class="core-bar"
            :title="`核心 ${i}: ${pct.toFixed(0)}%`"
          >
            <div class="core-bar-fill" :style="{ height: `${Math.max(2, pct)}%` }"></div>
          </div>
        </div>
      </section>

      <section class="hw-section">
        <h4>記憶體 (DRAM)</h4>
        <div class="kv-grid">
          <span>已使用</span><span>{{ status.memory.used_gb.toFixed(2) }} GB</span>
          <span>可用</span><span>{{ status.memory.available_gb.toFixed(2) }} GB</span>
          <span>總容量</span><span>{{ status.memory.total_gb.toFixed(2) }} GB</span>
          <span>使用率</span><span>{{ status.memory.percent.toFixed(1) }}%</span>
        </div>
        <div class="bar">
          <div class="bar-fill" :style="{ width: `${status.memory.percent}%` }"></div>
        </div>
      </section>

      <section class="hw-section">
        <h4>GPU</h4>
        <template v-if="status.gpu.available">
          <div class="kv-grid">
            <span>裝置</span><span>{{ status.gpu.name }}</span>
            <span>使用率</span><span>{{ status.gpu.util_percent }}%</span>
            <span>VRAM</span>
            <span>{{ status.gpu.vram_used_gb.toFixed(2) }} / {{ status.gpu.vram_total_gb.toFixed(2) }} GB</span>
            <span>溫度</span><span>{{ status.gpu.temperature_c != null ? `${status.gpu.temperature_c} °C` : "--" }}</span>
            <span>功耗</span><span>{{ status.gpu.power_w != null ? `${status.gpu.power_w} W` : "--" }}</span>
            <span>風扇</span><span>{{ status.gpu.fan_percent != null ? `${status.gpu.fan_percent}%` : "--" }}</span>
          </div>
          <div class="bar">
            <div class="bar-fill" :style="{ width: `${status.gpu.util_percent}%` }"></div>
          </div>
        </template>
        <p v-else class="hint">未偵測到 NVIDIA GPU（無驅動或無 GPU）。</p>
      </section>

      <section class="hw-section">
        <h4>Ollama 模型狀態</h4>
        <div class="kv-grid">
          <span>連線</span>
          <span :class="{ warn: !status.ollama.reachable }">
            {{ status.ollama.reachable ? "已連線" : "無法連線" }}
          </span>
          <span>設定的模型</span><span>{{ status.ollama.configured_model }}</span>
          <span>Embedding 模型</span><span>{{ status.ollama.embed_model }}</span>
        </div>
        <div v-if="status.ollama.loaded_models.length" class="loaded-models">
          <div v-for="m in status.ollama.loaded_models" :key="m.name" class="loaded-model-row">
            <span class="model-name">{{ m.name }}</span>
            <span>{{ m.size_gb.toFixed(1) }} GB · VRAM {{ m.vram_gb.toFixed(1) }} GB</span>
            <span class="expiry">{{ formatExpiry(m.expires_at) }}</span>
          </div>
        </div>
        <p v-else class="hint">目前沒有已載入記憶體的模型（閒置中）。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.hw-root {
  position: relative;
  flex-shrink: 0;
}
.hw-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: inherit;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #e5484d;
  flex-shrink: 0;
}
.dot.on {
  background: #30a46c;
}
.connecting {
  font-size: 0.76rem;
  color: var(--text-muted);
}
.chip {
  display: flex;
  align-items: baseline;
  gap: 5px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg);
  font-size: 0.76rem;
  white-space: nowrap;
  color: var(--text);
}
.chip.muted {
  opacity: 0.6;
}
.chip-label {
  color: var(--text-muted);
  font-weight: 600;
}
.chip-value {
  font-variant-numeric: tabular-nums;
}
.chip.model .chip-value {
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.warn {
  color: #e5484d;
}
.caret {
  color: var(--text-muted);
  font-size: 0.7rem;
  transition: transform 0.15s ease;
}
.caret.open {
  transform: rotate(180deg);
}

.hw-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 340px;
  max-height: 70vh;
  overflow-y: auto;
  background: var(--panel-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  z-index: 50;
  cursor: default;
}
.hw-section + .hw-section {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
}
.hw-section h4 {
  margin: 0 0 8px;
  font-size: 0.82rem;
}
.kv-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 10px;
  font-size: 0.78rem;
  color: var(--text-muted);
}
.kv-grid span:nth-child(odd) {
  color: var(--text-muted);
}
.kv-grid span:nth-child(even) {
  color: var(--text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.bar {
  margin-top: 8px;
  height: 6px;
  border-radius: 999px;
  background: var(--bg);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: var(--accent);
}
.core-bars {
  margin-top: 10px;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 40px;
}
.core-bar {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
  background: var(--bg);
  border-radius: 2px;
  overflow: hidden;
}
.core-bar-fill {
  width: 100%;
  background: var(--accent);
}
.hint {
  margin: 4px 0 0;
  font-size: 0.76rem;
  color: var(--text-muted);
}
.loaded-models {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.loaded-model-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.76rem;
  padding: 6px 8px;
  background: var(--bg);
  border-radius: 6px;
}
.model-name {
  font-weight: 700;
}
.expiry {
  color: var(--text-muted);
}
</style>
