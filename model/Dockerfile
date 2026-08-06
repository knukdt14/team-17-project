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

# python:3.12-slim(Debian)에는 locale 패키지가 없어서 한글 등 비ASCII 파일명을 읽을 때
# (예: data/raw의 규정집 PDF, 관리자가 업로드한 PDF) sys.getfilesystemencoding()이 UTF-8로
# 정상 동작하지 않고 mojibake(깨진 서로게이트 문자)가 섞여 나오는 문제가 실측으로 확인됨 -
# 이 문자열을 그대로 삭제 API의 URL로 인코딩하려 하면 UnicodeEncodeError가 나서 관리자
# 화면에서 "삭제가 안 되는" 것처럼 보였다. PYTHONUTF8=1(PEP 540)로 로케일과 무관하게 항상
# UTF-8을 쓰도록 강제해서 근본 원인을 없앤다. (pip install 뒤에 둬서 코드만 바뀔 때
# 무거운 torch/cuda 레이어까지 캐시가 깨지지 않게 함)
ENV PYTHONUTF8=1 PYTHONIOENCODING=utf-8

COPY src/ ./src/
RUN mkdir -p /app/data/raw /app/vectorstore /app/uploads

WORKDIR /app/src

EXPOSE 8100

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8100"]
