FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY app ./app

EXPOSE 8088

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8088}"]