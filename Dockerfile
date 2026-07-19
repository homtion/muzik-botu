# Dockerfile'ın içeriğini şu şekilde düzenle
FROM python:3.12-slim

# Gerekli sistem kütüphanelerini kur (ses için şart)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libffi-dev \
    libnacl-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce kütüphaneleri yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PyNaCl'ı açıkça ve derleyerek tekrar kur
RUN pip uninstall -y pynacl && pip install --no-cache-dir pynacl

COPY . .

CMD ["python", "bot.py"]