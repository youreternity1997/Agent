<script setup lang="ts">
import { ref } from "vue";
import { transcribeAudio } from "../api/client";

const props = defineProps<{ disabled: boolean }>();
const emit = defineEmits<{ send: [text: string] }>();

const text = ref("");
const isRecording = ref(false);
const isTranscribing = ref(false);
const micError = ref("");

let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];
let mediaStream: MediaStream | null = null;

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

async function toggleRecording() {
  if (isRecording.value) {
    mediaRecorder?.stop();
    return;
  }

  micError.value = "";
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    micError.value = "無法取得麥克風權限";
    return;
  }

  audioChunks = [];
  mediaRecorder = new MediaRecorder(mediaStream);
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };
  mediaRecorder.onstop = async () => {
    isRecording.value = false;
    mediaStream?.getTracks().forEach((t) => t.stop());
    mediaStream = null;

    if (audioChunks.length === 0) return;
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    isTranscribing.value = true;
    try {
      const transcribed = await transcribeAudio(blob);
      text.value = text.value ? `${text.value} ${transcribed}` : transcribed;
    } catch (err) {
      micError.value = err instanceof Error ? err.message : "語音轉文字失敗";
    } finally {
      isTranscribing.value = false;
    }
  };

  mediaRecorder.start();
  isRecording.value = true;
}
</script>

<template>
  <form class="input-row" @submit.prevent="submit">
    <button
      type="button"
      class="mic-btn"
      :class="{ recording: isRecording }"
      :disabled="disabled || isTranscribing"
      :title="isRecording ? '停止錄音' : '語音輸入'"
      @click="toggleRecording"
    >
      {{ isTranscribing ? "⏳" : isRecording ? "⏹" : "🎤" }}
    </button>
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
  <div v-if="micError" class="mic-error">⚠️ {{ micError }}</div>
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
.mic-btn {
  min-width: 44px;
  padding: 0;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 1.1rem;
}
.mic-btn.recording {
  background: #e5484d;
  border-color: #e5484d;
  color: #fff;
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    opacity: 0.6;
  }
}
.mic-error {
  padding: 0 12px 10px;
  font-size: 0.78rem;
  color: #e5484d;
  background: var(--panel-bg);
}
</style>
