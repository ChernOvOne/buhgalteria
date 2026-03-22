FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Копируем шрифты
RUN mkdir -p /app/fonts && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/fonts/ && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /app/fonts/

COPY requirements.txt .

# Устанавливаем по группам — каждый слой кешируется отдельно
RUN pip install --no-cache-dir --timeout 120 \
    fastapi==0.111.0 \
    uvicorn[standard]==0.29.0 \
    python-multipart==0.0.9

RUN pip install --no-cache-dir --timeout 120 \
    sqlalchemy==2.0.30 \
    asyncpg==0.29.0 \
    psycopg2-binary==2.9.9 \
    alembic==1.13.1

RUN pip install --no-cache-dir --timeout 120 \
    pydantic==2.7.1 \
    pydantic-settings==2.2.1

RUN pip install --no-cache-dir --timeout 120 \
    python-jose[cryptography]==3.3.0 \
    passlib==1.7.4 \
    bcrypt==4.0.1

RUN pip install --no-cache-dir --timeout 120 \
    redis==5.0.4 \
    aiofiles==23.2.1 \
    httpx==0.27.0

RUN pip install --no-cache-dir --timeout 120 \
    reportlab==4.1.0 \
    openpyxl==3.1.2 \
    pillow==10.3.0

RUN pip install --no-cache-dir --timeout 120 \
    python-dateutil==2.9.0 \
    babel==2.15.0 \
    celery==5.4.0

RUN pip install --no-cache-dir --timeout 120 \
    matplotlib==3.9.0

RUN pip install --no-cache-dir --timeout 120 \
    aiogram==3.6.0

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
