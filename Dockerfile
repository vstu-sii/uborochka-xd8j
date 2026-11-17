FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY backend/ ./backend/
COPY database/migrations/ ./database/migrations/
COPY frontend/prototype/ ./frontend/prototype/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "python -m backend.migrate && exec uvicorn src.main:app --host 0.0.0.0 --port 8000"]
