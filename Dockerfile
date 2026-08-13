FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir fastapi uvicorn python-multipart

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.demo_backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
