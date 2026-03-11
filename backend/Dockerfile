FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    tesseract-ocr \
    libxml2 \
    libxslt1.1 \
    libjpeg62-turbo \
    zlib1g \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.docker.txt /app/requirements.docker.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements.docker.txt

COPY . /app

EXPOSE 5000

CMD ["sh", "-c", "python docker_bootstrap.py && gunicorn --bind 0.0.0.0:5000 --workers=${GUNICORN_WORKERS:-2} --threads=${GUNICORN_THREADS:-4} --timeout=${GUNICORN_TIMEOUT:-1200} main:app"]
