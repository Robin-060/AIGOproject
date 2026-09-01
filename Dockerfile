FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt /app/requirements.txt

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*



RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install fastapi uvicorn python-multipart

COPY . /app

EXPOSE 8000 8501

CMD ["python", "-m", "streamlit", "run", "src/web/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
