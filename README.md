# GIGABYTE AI Agent

技嘉 (GIGABYTE) 主機板產品資料 AI 助理。使用**本地 8B 等級 LLM（int4 量化，vLLM AsyncLLMEngine 內嵌於後端、支援多人並發非同步推論）**驅動 **ReAct** 推理迴圈，
可勾選啟用 **MCP 工具**（網路搜尋 / RAG 向量檢索 / 資料庫查詢），並可切換不同「Skill」（領域知識提示詞模組）。

## 架構總覽

```
┌─────────────────┐      SSE (逐步驟串流)      ┌───────────────────────────────┐
│  Vue 3 前端      │ ───────────────────────▶ │  FastAPI 後端                   │
│  - 勾選 MCP 工具  │ ◀─────────────────────── │  - ReAct Agent Loop             │
│  - 選擇 Skill    │      Thought/Action/...   │  - MCP Client                   │
└─────────────────┘                            │  - vLLM AsyncLLMEngine (內嵌)   │
                                                │    Qwen3-8B-AWQ，continuous     │
                                                │    batching，多人並發非同步推論 │
                                                └──────────┬───────────┬─────────┘
                                                    stdio (MCP)         │ HTTP
                                                            ▼           ▼
                                                ┌───────────────────┐ ┌────────────────┐
                                                │  MCP Tool Server    │ │ Ollama (Embedding)│
                                                │  - web_search       │ │ nomic-embed-text  │
                                                │  - rag_search       │ └────────────────┘
                                                │  - db_query         │
                                                └──────────┬─────────┘
                                                            │
                                                            ▼
                                                ┌──────────────────────┐
                                                │ PostgreSQL + pgvector  │
                                                │ motherboards           │
                                                │ kb_documents (向量)    │
                                                └──────────────────────┘
```

## 技術選型

- **後端**: Python 3.11 + FastAPI，ReAct 迴圈為手寫的 Thought/Action/Action Input/Observation 文字解析（不依賴原生 function-calling，因為小型本地模型對 function-calling 支援不穩定）
- **LLM**: [vLLM](https://github.com/vllm-project/vllm) 的 `AsyncLLMEngine` 直接內嵌在後端程式裡（不透過額外的 HTTP server），預設模型 `Qwen/Qwen3-8B-AWQ`（8B 參數、AWQ int4 量化，首次啟動會自動從 Hugging Face 下載並快取）。`AsyncLLMEngine` 內建 continuous batching，多個使用者同時對話時的請求會被引擎自動合併批次推論，不會互相卡住；可透過 `VLLM_MODEL`／`VLLM_QUANTIZATION` 換成其他 vLLM 支援的模型
- **Embedding**: 獨立的 Ollama 服務提供 `nomic-embed-text`（本地產生向量，供 RAG 使用；embedding 模型體積小、不需要 vLLM 的批次推論能力，維持用 Ollama 服務較單純）
- **MCP**: 使用官方 `mcp` Python SDK（`FastMCP`）實作一個 stdio MCP Server，暴露 3 個工具；後端以 MCP Client 連線呼叫
- **向量資料庫**: PostgreSQL + `pgvector` extension
- **網路搜尋**: [DuckDuckGo](https://duckduckgo.com)（透過 `ddgs` 套件，免 API Key 即可使用）
- **前端**: Vue 3 + TypeScript + Vite，原生 `fetch` 讀取 SSE 串流，逐步顯示 Thought / Action / Observation / Final Answer

## 目錄結構

```
backend/
  app/
    core/            # 設定、LLM 呼叫封裝
    agent/           # ReAct 迴圈與 prompt 樣板
    mcp_server/      # MCP tool server（web_search / rag_search / db_query）
    mcp_client/      # MCP client 封裝
    skills/          # 領域知識 skill 模組 (Markdown + frontmatter)
    api/             # FastAPI routes (chat / tools / skills)
    db/              # SQLAlchemy models + session
  scripts/
    init_db.sql      # 建表 + pgvector extension
    seed_data.py     # 灌入範例技嘉主機板資料 + 產生 RAG 向量
frontend/
  src/
    components/      # ToolSelector, SkillSelector, ChatWindow, MessageInput
    composables/      # useChat（SSE 串流）
    api/              # API client
docker-compose.yml
```

## 快速開始

### 1. 安裝並啟動 Ollama（僅用於 Embedding 模型）

```powershell
# 安裝 Ollama: https://ollama.com/download
ollama pull nomic-embed-text
```

生成用的 LLM（`Qwen/Qwen3-8B-AWQ`）不再透過 Ollama，而是由後端程式內嵌的 vLLM `AsyncLLMEngine`
在啟動時自動從 Hugging Face 下載並載入（需要 NVIDIA GPU + 足夠 VRAM，且需要能連上 Hugging Face
的網路環境；首次啟動下載約 8GB，之後會快取在本機不必重複下載）。

### 2. 啟動 PostgreSQL (pgvector)

```powershell
docker compose up -d db
```

### 3. 建立資料表並灌入範例資料

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
psql (連線字串見 .env) -f scripts/init_db.sql   # 或用任何 Postgres client 執行該檔
python scripts/seed_data.py
```

### 4. 設定環境變數

複製 `.env.example` 為 `.env`，依需要調整（`web_search` 工具透過 DuckDuckGo 運作，不需要額外的 API Key）。

語音輸入功能（faster-whisper）首次執行時會自動下載模型權重（預設 `base`，可用 `WHISPER_MODEL_SIZE` 調整），需要網路連線，行為類似 `ollama pull`。

### 5. 啟動後端

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

### 6. 啟動前端

```powershell
cd frontend
npm install
npm run dev
```

瀏覽器打開 `http://localhost:5173`，即可在畫面上勾選要啟用的 MCP 工具、選擇 Skill，並開始對話。

## Docker Compose 一鍵啟動（含 Ollama Embedding 服務）

```powershell
docker compose up -d --build
docker exec -it gigabyte-ollama ollama pull nomic-embed-text
docker exec -it gigabyte-backend python scripts/seed_data.py
```

`backend` 容器啟動時會自動下載並載入 `Qwen/Qwen3-8B-AWQ`（vLLM 內嵌引擎），可用
`docker logs -f gigabyte-backend` 觀察下載/載入進度，或用 `curl http://localhost:8000/api/health`
確認 `llm_ready` 是否為 `true`。下載的權重會存在 `gigabyte_hf_cache` volume，重建容器不會重新下載。

## ReAct 迴圈說明

`backend/app/agent/react_agent.py` 會將使用者問題、可用工具清單（依前端勾選過濾）、選用的 Skill 提示詞組成 system prompt，
要求 LLM 嚴格輸出：

```
Thought: ...
Action: <tool name 或 Final Answer>
Action Input: <JSON>
```

後端解析出 `Action`，透過 MCP Client 呼叫對應工具取得 `Observation`，把結果接回對話紀錄，再次呼叫 LLM，
如此重複最多 `MAX_REACT_STEPS` 次，直到模型輸出 `Final Answer` 或達到步數上限為止。每一步都會即時以 SSE
事件推送到前端，讓使用者看到完整的思考鏈與工具呼叫過程。
