@echo off
REM Start the new FastAPI app
cd QlikToPowerBIConverter
python -m uvicorn server:app --host 127.0.0.1 --port 8000 --reload
