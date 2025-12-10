# 產品化待辦清單 (低成本/免費方案)

這份清單旨在協助將目前的 POC 轉型為可上線的產品，並將營運成本降至最低（接近 $0）。

## 1. 資料庫遷移 (Database)
目標：解決雲端環境重啟後資料遺失的問題。
- [x] **註冊服務**：註冊 **Supabase** 或 **Neon** (提供免費 PostgreSQL)。
- [x] **取得連線資訊**：獲取資料庫連線字串 (Connection String)。
- [x] **修改程式碼** (`backend/database.py`)：
    - [x] 安裝 `psycopg2-binary` 套件。
    - [x] 將 `sqlite:///./sql_app.db` 替換為 PostgreSQL 連線字串。

## 2. 檔案儲存雲端化 (Storage)
目標：解決雲端環境無法持久保存音檔的問題，並節省流量費。
- [ ] **註冊服務**：註冊 **Cloudflare R2** (相容 S3 API，且免流量傳輸費)。
- [ ] **設定 Bucket**：建立一個新的 Bucket，並設定公開存取權限 (Public Access) 或透過 Worker 存取。
- [ ] **取得金鑰**：獲取 Access Key ID 和 Secret Access Key。
- [ ] **修改程式碼** (`backend/main.py`)：
    - [ ] 安裝 `boto3` 套件。
    - [ ] 移除 `shutil.copyfileobj` 存到本地 `media/` 的邏輯。
    - [ ] 實作 `upload_to_r2` 函式，將檔案上傳至 Cloudflare R2。
    - [ ] 修改資料庫寫入邏輯，`audio_path` 欄位改為儲存 R2 的公開 URL。

## 3. AI 模型 API 化 (Compute)
目標：移除對昂貴 GPU 伺服器的依賴，大幅提升轉錄速度。
- [ ] **Whisper 語音轉文字**：
    - [ ] 註冊 **Groq API** (提供極速 Whisper 服務)。
    - [ ] 修改 `backend/logic.py`：
        - [ ] 移除本地 `whisper` 套件與模型載入邏輯。
        - [ ] 改為呼叫 Groq API 進行轉錄。
- [ ] **LLM 文字修正與摘要**：
    - [ ] 繼續使用 **Google Gemini API** (Free Tier)。
    - [x] **優化**：實作錯誤重試機制 (Retry Logic)，以應對免費版的速率限制 (Rate Limit)。

## 4. 部署與託管 (Deployment)
目標：將服務發布到網路上供他人使用。
- [x] **準備工作**：
    - [x] 建立 `requirements.txt` (包含 `fastapi`, `streamlit`, `boto3`, `psycopg2-binary`, `google-generativeai` 等)。
    - [x] 確保程式碼中所有 API Key 都改為讀取 **環境變數 (Environment Variables)**，絕不寫死在程式碼裡。
- [ ] **選擇託管方案**：
    - [ ] **方案 A (推薦 - 一站式)**：使用 **Hugging Face Spaces**。
        - [ ] 建立 Docker Space (免費 CPU Tier)。
        - [ ] 撰寫 `Dockerfile` 同時啟動 FastAPI 和 Streamlit。
    - [ ] **方案 B (分離式)**：
        - [ ] 前端：部署至 **Streamlit Community Cloud** (連結 GitHub)。
        - [ ] 後端：部署至 **Render** 或 **Railway** (Free Tier)。

## 5. 安全性基礎 (Security)
- [x] **簡易驗證**：在 Streamlit 前端加入密碼保護，防止路人隨意使用消耗額度。
- [ ] **HTTPS**：雲端平台通常會自動提供 HTTPS，確保連線安全。

## 6. 後續處理
- [x] 更新requirements.txt
- [x] 更新README.md
- [x] 更新首頁
- [x] 更新API Doc