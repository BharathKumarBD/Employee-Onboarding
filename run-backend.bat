@echo off
set PYTHONPATH=%~dp0;%~dp0backend
echo ===================================================
echo Starting Aarambh-AI Backend (FastAPI + LangGraph)
echo Using virtual environment at .venv...
echo API will be available at: http://127.0.0.1:8000
echo Docs at: http://127.0.0.1:8000/docs
echo ===================================================
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
pause

