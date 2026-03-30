# پائتھن کا ہلکا پھلکا ورژن
FROM python:3.11-slim

# ورکنگ ڈائریکٹری سیٹ کریں
WORKDIR /app

# کرومیم اور اس کی ضروری فائلیں انسٹال کریں
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# ریکوائرمنٹس کاپی کریں اور انسٹال کریں
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# باقی سارا کوڈ کاپی کریں
COPY . .

# سرور چلانے کی کمانڈ
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
