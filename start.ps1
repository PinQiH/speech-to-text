# > 快速啟動腳本：同時開啟 Backend 與 Frontend
$root = $PSScriptRoot

# - 啟動 Backend（uvicorn）
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd '$root\backend'; Write-Host '[Backend] 啟動中...' -ForegroundColor Cyan; ..\venv\Scripts\python.exe -m uvicorn main:app --reload"
)

# - 稍等 2 秒，讓 backend 先初始化
Start-Sleep -Seconds 2

# - 啟動 Frontend（streamlit）
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "cd '$root\frontend'; Write-Host '[Frontend] 啟動中...' -ForegroundColor Green; ..\venv\Scripts\python.exe -m streamlit run app.py"
)

Write-Host ""
Write-Host "✓ Backend  → http://localhost:8000" -ForegroundColor Cyan
Write-Host "✓ Frontend → http://localhost:8501" -ForegroundColor Green
Write-Host ""
Write-Host "關閉時請分別在兩個視窗按 Ctrl+C" -ForegroundColor Yellow
