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
        -r requirements.txt \
    # torch가 리눅스에서는 triton을 같이 까는데(윈도우는 휠이 없어서 애초에 안 깔림), 이 환경에서
    # 4bit 추론 중 triton 커널 경로를 타면서 매 호출마다 gcc로 커널을 JIT 재컴파일해 응답이
    # 수십 분씩 걸리는 문제를 실측으로 확인함(단순히 컴파일러가 없어 죽는 것보다 훨씬 치명적).
    # build-essential을 넣어 컴파일러를 쥐어주는 대신, triton 자체를 제거해서 네이티브(Windows)에서
    # 이미 검증된 "triton 없는" fallback 경로를 강제로 타게 함.
    && pip uninstall -y triton

COPY src/ ./src/
RUN mkdir -p /app/data/raw /app/vectorstore /app/uploads

WORKDIR /app/src

EXPOSE 8100

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8100"]
