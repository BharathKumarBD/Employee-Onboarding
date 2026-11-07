# Set PYTHONPATH to project root and backend folder
$env:PYTHONPATH = "$PSScriptRoot;$PSScriptRoot\backend"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting Aarambh-AI Backend (FastAPI + LangGraph)" -ForegroundColor Green
Write-Host "Using virtual environment: $PSScriptRoot\.venv" -ForegroundColor Yellow
Write-Host "API: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

