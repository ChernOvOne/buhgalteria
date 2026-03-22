FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc libpq-dev fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
# Build context is project root (set in docker-compose)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --timeout 120 -r requirements.txt
# Копируем шрифты для PDF
RUN mkdir -p /app/fonts && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/fonts/ && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /app/fonts/
COPY backend/app ./app
COPY bot ./bot
CMD ["python", "bot/main.py"]
