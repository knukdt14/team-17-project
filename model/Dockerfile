FROM python:3.12-slim

WORKDIR /app

# PyMuPDF(OCR 폴백)에 필요한 tesseract 엔진 (한국어 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN mkdir -p /app/data/raw /app/vectorstore /app/uploads

WORKDIR /app/src

EXPOSE 8100

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8100"]
