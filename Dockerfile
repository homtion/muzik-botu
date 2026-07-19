FROM python:3.12-slim

# Gerekli sistem paketlerini ve ffmpeg'i kur
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce bağımlılıkları yükle (önbellek avantajı için)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pynacl

# Kalan tüm dosyaları kopyala
COPY . .

CMD ["python", "bot.py"]