FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use shell form to allow command chaining and environment variables
CMD python migrate.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
