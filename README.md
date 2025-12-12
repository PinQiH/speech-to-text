# AI POC - Whisper & Gemini

這是一個使用 Python 構建的 AI 音訊處理概念驗證 (POC) 專案。

## 功能特色

- **語音轉文字 (Transcription)**：使用 OpenAI 的 [Whisper](https://github.com/openai/whisper) 模型（本地運行）將語音精準轉換為文字。
- **AI 錯字修正 (Typo Correction)**：使用 Google [Gemini](https://ai.google.dev/) 模型自動修正逐字稿中的錯別字與繁簡轉換。
- **重點摘要 (Summarization)**：使用 Google Gemini 生成帶有時間戳記的重點摘要。
- **前端介面**：使用 [Streamlit](https://streamlit.io/) 構建的直觀操作介面。
- **後端 API**：使用 [FastAPI](https://fastapi.tiangolo.com/) 構建的高效能後端，支援非同步任務處理。

## 前置需求

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/) (必須安裝並加入系統 PATH 環境變數，Whisper 依賴此工具)。
- Google Generative AI API Key ([在此獲取](https://makersuite.google.com/keys))。

## 安裝教學

1.  **建立虛擬環境** (建議)：
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

2.  **安裝依賴套件**：
    ```bash
    # 安裝後端依賴
    pip install -r backend/requirements.txt

    # 安裝前端依賴
    pip install -r frontend/requirements.txt
    ```

## 啟動應用程式

你需要分別開啟兩個終端機 (Terminal) 來運行後端與前端。

### 1. 啟動後端 (Backend)
開啟一個終端機，啟用虛擬環境後執行：
```bash
cd backend
uvicorn main:app --reload
```
後端將啟動於 `http://127.0.0.1:8000`。

### 2. 啟動前端 (Frontend)
開啟**另一個**新的終端機，啟用虛擬環境後執行：
```bash
cd frontend
streamlit run app.py
```
前端介面將自動在瀏覽器中開啟 (通常為 `http://localhost:8501`)。

## 使用說明

1.  在瀏覽器中開啟 Streamlit 應用程式。
2.  在側邊欄輸入您的 **Google Gemini API Key**。
3.  上傳音訊檔案 (支援 MP3, WAV 等格式)。
4.  點擊 **Start Processing** 開始處理。
5.  系統將依序進行：轉錄 -> 錯字修正 -> 重點摘要。
6.  完成後即可查看並下載結果。

## 常見問題排除

- **FFmpeg Error**：如果看到與 `ffmpeg` 相關的錯誤，請確認您已正確安裝 FFmpeg 並且可以在命令列中執行它。
- **處理速度慢**：本地 Whisper 模型需要較多 CPU/GPU 資源。錯字修正與摘要依賴 Google API，速度取決於網路與模型回應時間。
