# پائتھن کا ورژن
FROM python:3.11-slim

# ورکنگ ڈائریکٹری
WORKDIR /app

# کلاؤڈ فلیر کو بائی پاس کرنے کے لیے اصلی کرومیم اور ورچوئل ڈسپلے (Xvfb) انسٹال کریں
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    x11-utils \
    libnss3 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxkbcommon0 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# ریکوائرمنٹس انسٹال کریں
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# سارا کوڈ کاپی کریں
COPY . .

# سرور سٹارٹ کریں
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
