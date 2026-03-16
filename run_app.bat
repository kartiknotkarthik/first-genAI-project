@echo off
echo ==========================================
echo Starting Zomato AI Project - Unified Run
echo ==========================================

echo [1/2] Starting FastAPI Backend on port 8000...
start /min cmd /c "cd phase4 && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000"

echo [2/2] Starting Streamlit Frontend...
streamlit run app.py

echo Both services are now being orchestrated.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:8501
pause
