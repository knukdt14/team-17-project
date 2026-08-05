FROM python:3.12-slim

WORKDIR /app

# PyMuPDF(OCR 폴백)에 필요한 tesseract 엔진 (한국어 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 로컬 LLM(Qwen2.5-7B-Instruct)을 4bit 양자화로 GPU에서 돌리기 위해 CUDA 빌드 torch 사용.
# 호스트에 nvidia-container-toolkit이 설치되어 있고 docker-compose에서 GPU를 넘겨줘야 동작함.
# --extra-index-url로 나머지 패키지는 그대로 PyPI에서 받도록 함.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cu130 \
        --extra-index-url https://pypi.org/simple \
        -r requirements.txt

COPY src/ ./src/
RUN mkdir -p /app/data/raw /app/vectorstore /app/uploads

WORKDIR /app/src

EXPOSE 8100

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8100"]
