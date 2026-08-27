import { onMounted, onUnmounted, ref } from "vue";

export interface SystemStatus {
  cpu: {
    percent: number;
    per_core: number[];
    cores_logical: number;
    cores_physical: number | null;
    freq_current_mhz: number | null;
    freq_max_mhz: number | null;
    load_avg_1m: number | null;
  };
  memory: { total_gb: number; used_gb: number; available_gb: number; percent: number };
  gpu:
    | { available: false }
    | {
        available: true;
        name: string;
        util_percent: number;
        mem_util_percent: number;
        vram_total_gb: number;
        vram_used_gb: number;
        temperature_c: number | null;
        power_w: number | null;
        fan_percent: number | null;
        devices: Array<{
          name: string;
          util_percent: number;
          mem_util_percent: number;
          vram_total_gb: number;
          vram_used_gb: number;
          temperature_c: number | null;
          power_w: number | null;
          fan_percent: number | null;
        }>;
      };
  llm: {
    engine: string;
    model: string;
    quantization: string;
    max_model_len: number;
    ready: boolean;
  };
  embedding: {
    model: string;
    base_url: string;
    reachable: boolean;
  };
}

const RECONNECT_DELAY_MS = 3000;

/** Connects to the /ws/system WebSocket (separate channel from chat's SSE
 * stream) and keeps `status` updated with the latest hardware snapshot.
 */
export function useSystemStatus() {
  const status = ref<SystemStatus | null>(null);
  const connected = ref(false);

  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;

  function connect() {
    if (stopped) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    socket = new WebSocket(`${proto}//${window.location.host}/ws/system`);

    socket.onopen = () => {
      connected.value = true;
    };
    socket.onmessage = (event) => {
      try {
        status.value = JSON.parse(event.data);
      } catch {
        // ignore malformed frame
      }
    };
    socket.onclose = () => {
      connected.value = false;
      if (!stopped) reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
    };
    socket.onerror = () => {
      socket?.close();
    };
  }

  onMounted(connect);
  onUnmounted(() => {
    stopped = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    socket?.close();
  });

  return { status, connected };
}
