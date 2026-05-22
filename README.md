# AI POC - Whisper & Gemini

這是一個使用 Python 構建的 AI 音訊處理概念驗證 (POC) 專案。

## 功能特色

- **語音轉文字 (Transcription)**：使用 OpenAI 的 [Whisper](https://github.com/openai/whisper) 模型（本地運行）將語音精準轉換為文字。
- **說話者分離 (Speaker Diarization)**：整合 [pyannote.audio](https://github.com/pyannote/pyannote-audio) 辨識多位說話者，需提供 Hugging Face Token（選填）。
- **AI 錯字修正 (Typo Correction)**：使用 Google [Gemini](https://ai.google.dev/) 模型自動修正逐字稿中的錯別字與繁簡轉換。
- **重點摘要 (Summarization)**：使用 Google Gemini 生成帶有時間戳記的重點摘要。
- **使用者驗證**：整合 [Supabase](https://supabase.com/) Auth，支援註冊、登入與訪客模式。
- **前端介面**：使用 [Streamlit](https://streamlit.io/) 構建的直觀操作介面。
- **後端 API**：使用 [FastAPI](https://fastapi.tiangolo.com/) 構建的高效能後端，支援非同步背景任務處理。

## 前置需求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/)（必須安裝並加入系統 PATH，Whisper 依賴此工具）
- Google Gemini API Key（[在此獲取](https://makersuite.google.com/keys)）
- Supabase 專案 URL 與 Anon Key（[在此建立](https://supabase.com/)）
- Hugging Face Token（選填，用於說話者分離功能）

## 安裝教學

### 1. 建立虛擬環境

```powershell
python -m venv venv
```

### 2. 安裝依賴套件

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

> **注意**：安裝時請確認後端服務未在運行，否則部分 `.pyd` 檔案會被鎖定導致安裝失敗。

### 3. 設定環境變數

透過 `.env.example` 複製並建立 `.env` 檔

## 啟動應用程式

### 快速啟動（推薦）

在專案根目錄執行啟動腳本，會自動開啟 Backend 與 Frontend 兩個視窗：

```powershell
.\start.ps1
```

> 首次執行若出現「執行原則」錯誤，請先執行：
>
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 手動啟動

需分別開啟兩個終端機。

**Backend**（必須使用 venv 的 python 執行，避免 uvicorn reloader 繼承系統 Python）：

```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn main:app --reload
```

後端啟動於 `http://localhost:8000`。

**Frontend**：

```powershell
cd frontend
..\venv\Scripts\python.exe -m streamlit run app.py
```

前端介面自動在瀏覽器開啟（`http://localhost:8501`）。

## 使用說明

1. 開啟瀏覽器進入 `http://localhost:8501`。
2. 登入帳號（或使用訪客模式）。
3. 在側邊欄輸入 **Google Gemini API Key**（若後端已設定系統金鑰則可略過）。
4. 選填 **Hugging Face Token** 以啟用說話者分離功能。
5. 上傳音訊檔案（支援 MP3、WAV、M4A 等格式）。
6. 點擊 **Start Processing** 開始處理。
7. 系統將依序執行：轉錄 → 說話者分離（選填）→ 錯字修正 → 重點摘要。
8. 完成後可查看、編輯並下載結果。

## 常見問題排除

### FFmpeg 錯誤

確認已安裝 FFmpeg 且可在命令列中執行 `ffmpeg -version`。

### ModuleNotFoundError: No module named 'whisper'

不可直接執行 `uvicorn main:app --reload`，必須透過 venv 的 python 執行：

```powershell
..\venv\Scripts\python.exe -m uvicorn main:app --reload
```

### 說話者分離錯誤（use_auth_token）

`pyannote.audio==3.4.0` 與 `huggingface_hub>=1.0` 不相容，請降版：

```powershell
.\venv\Scripts\python.exe -m pip install "huggingface_hub<1.0"
```

### 安裝套件時出現 WinError 5（存取被拒）

停止 uvicorn（`Ctrl+C`）後再重新執行安裝。

### 處理速度慢

本地 Whisper 模型需要較多 CPU/GPU 資源。錯字修正與摘要依賴 Google API，速度取決於網路與模型回應時間。
