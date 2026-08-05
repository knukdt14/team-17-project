FROM python:3.12-slim

WORKDIR /app

# PyMuPDF(OCR 폴백)에 필요한 tesseract 엔진 (한국어 포함) +
# triton(torch가 리눅스에서만 끌어오는 의존성)이 일부 커널을 JIT 컴파일할 때 필요한 C 컴파일러.
# 이게 없으면 로컬 LLM 스트리밍 생성 스레드가 "Failed to find C compiler"로 조용히 죽고,
# 메인 스레드는 TextIteratorStreamer 60초 타임아웃까지 아무 응답 없이 멈춰있게 됨.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-kor \
        build-essential \
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
