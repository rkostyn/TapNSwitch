FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    apk add --no-cache libffi && \
    apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev && \
    pip install --no-cache-dir --upgrade -r requirements.txt && \
    apk del .build-deps

COPY app ./

CMD ["fastapi", "run", "/app/main.py", "--port", "80", "--workers", "1"]
