FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скачиваем DejaVu шрифты для кириллицы в PDF
RUN mkdir -p /app/fonts && \
    wget -q "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2" \
    -O /tmp/dejavu.tar.bz2 && \
    tar -xjf /tmp/dejavu.tar.bz2 -C /tmp && \
    cp /tmp/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf /app/fonts/ && \
    cp /tmp/dejavu-fonts-ttf-2.37/ttf/DejaVuSans-Bold.ttf /app/fonts/ && \
    rm -rf /tmp/dejavu*

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
